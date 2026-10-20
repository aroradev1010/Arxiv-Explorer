"""Frozen pools, human judgments, snapshot evaluation, and sequential latency jobs."""
import hashlib
import json
import platform
import os
import random
import threading
import uuid
from datetime import datetime, timezone
from time import perf_counter
from backend.api.errors import APIError
from backend.api.schemas import Filters, SearchRequest
from .store import Store, dump
from .queries import defaults
from .schemas import QueryCollection
from .metrics import evaluate, aggregate, latency_summary

MODES = ('tfidf', 'bm25', 'semantic', 'hybrid')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(dump(value).encode()).hexdigest()


class EvaluationService:
    def __init__(self, settings, search):
        self.settings, self.search = settings, search
        self.store = Store(settings.evaluation_db_path)
        self.job_lock = threading.Lock()
        if not self.store.rows('SELECT version FROM query_sets'):
            self.save_queries(defaults())

    def identity(self):
        if self.search is None:
            raise APIError(503, 'not_ready', 'Retrieval engine unavailable')
        r = self.search.resources
        return dict(corpus_version=r.dataset['artifacts']['papers.jsonl'], index_fingerprint=r.index_version,
                    algorithm_configuration=dict(rrf_k=self.search.settings.rrf_k,
                        rrf_candidate_depth=self.search.settings.rrf_candidate_depth,
                        max_ranking_window=self.search.settings.max_ranking_window,
                        index_manifest=r.indexes.manifest))

    def save_queries(self, definitions):
        collection = QueryCollection(queries=definitions)
        definitions = sorted([q.model_dump() for q in collection.queries], key=lambda q: q['id'])
        version = 'qs-' + digest(definitions)[:24]
        with self.store.connection() as db:
            db.execute('INSERT OR IGNORE INTO query_sets VALUES (?,?)', (version, now()))
            db.executemany('INSERT OR IGNORE INTO evaluation_queries VALUES (?,?,?)',
                           [(version, q['id'], dump(q)) for q in definitions])
        return self.queries(version)

    def queries(self, version=None):
        if version is None:
            version = self.store.rows('SELECT version FROM query_sets ORDER BY created_at DESC,version DESC LIMIT 1')[0]['version']
        rows = self.store.rows('SELECT definition FROM evaluation_queries WHERE query_set_version=? ORDER BY id', (version,))
        if not rows:
            raise APIError(404, 'unknown_query_set', 'Query set not found')
        return dict(version=version, queries=[json.loads(r['definition']) for r in rows],
                    versions=self.store.rows('SELECT * FROM query_sets ORDER BY created_at DESC'))

    def selected(self, request):
        collection = self.queries(request.query_set_version)
        selected = request.query_ids or [q['id'] for q in collection['queries']]
        queries = [q for q in collection['queries'] if q['id'] in selected]
        if len(queries) != len(selected):
            raise APIError(422, 'unknown_query', 'Selected query IDs do not belong to this query set')
        return collection['version'], queries

    def reserve_pool(self, request):
        identity = self.identity()
        if request.depth > min(self.search.settings.rrf_candidate_depth, self.search.settings.max_result_limit):
            raise APIError(422, 'invalid_depth', 'Depth exceeds retrieval limits')
        version, queries = self.selected(request)
        meta = dict(**identity, query_set_version=version, queries=queries, depth=request.depth,
                    filters=request.filters.model_dump(), random_seed=request.random_seed)
        key = digest(meta)
        with self.store.connection() as db:
            existing = db.execute('SELECT id,status FROM candidate_pools WHERE request_key=?', (key,)).fetchone()
            if existing:
                if existing['status'] == 'FAILED':
                    db.execute("UPDATE candidate_pools SET status='QUEUED',error=NULL WHERE id=?", (existing['id'],))
                    return existing['id'], True
                return existing['id'], False
            pool_id = 'pool-' + uuid.uuid4().hex
            db.execute('INSERT INTO candidate_pools VALUES (?,?,?,?,?,?,?,NULL)',
                       (pool_id, key, 'QUEUED', version, dump(meta), None, now()))
        return pool_id, True

    def generate_pool(self, pool_id):
        try:
            with self.store.connection() as db:
                db.execute("UPDATE candidate_pools SET status='RUNNING' WHERE id=?", (pool_id,))
            meta = self.pool(pool_id)['metadata']
            for q in meta['queries']:
                rankings, _, _ = self.search.rankings(q['query'], list(MODES), Filters(**meta['filters']))
                candidates = {}
                for mode in MODES:
                    for hit in rankings[mode][:meta['depth']]:
                        candidates.setdefault(hit.paper_id, {})[mode] = dict(rank=hit.rank, native_score=hit.score)
                # Sorting before shuffling eliminates set/dictionary insertion bias.
                order = sorted(candidates)
                random.Random(str(meta['random_seed']) + ':' + q['id']).shuffle(order)
                with self.store.connection() as db:
                    db.executemany('INSERT INTO pool_documents VALUES (?,?,?,?,?)',
                                   [(pool_id, q['id'], p, dump(candidates[p]), i) for i, p in enumerate(order)])
            with self.store.connection() as db:
                db.execute("UPDATE candidate_pools SET status='COMPLETED',completed_at=? WHERE id=?", (now(), pool_id))
        except Exception as exc:
            with self.store.connection() as db:
                db.execute('DELETE FROM pool_documents WHERE pool_id=?', (pool_id,))
                db.execute("UPDATE candidate_pools SET status='FAILED',error=?,completed_at=? WHERE id=?", (str(exc), now(), pool_id))

    def pools(self):
        return [self.pool(r['id']) for r in self.store.rows('SELECT id FROM candidate_pools ORDER BY created_at DESC')]

    def pool(self, pool_id):
        rows = self.store.rows('SELECT * FROM candidate_pools WHERE id=?', (pool_id,))
        if not rows:
            raise APIError(404, 'unknown_pool', 'Candidate pool not found')
        row = rows[0]
        row['metadata'] = json.loads(row['metadata'])
        row['candidate_count'] = self.store.rows('SELECT COUNT(*) AS n FROM pool_documents WHERE pool_id=?', (pool_id,))[0]['n']
        row['stale'] = self.search is None or any(row['metadata'][k] != self.identity()[k] for k in ('corpus_version', 'index_fingerprint', 'algorithm_configuration'))
        return row

    def documents(self, pool_id, query_id=None):
        self.pool(pool_id)
        sql = '''SELECT p.*,j.relevance_grade,j.updated_at FROM pool_documents p LEFT JOIN relevance_judgments j
                 USING(pool_id,query_id,paper_id) WHERE p.pool_id=?'''
        args = [pool_id]
        if query_id:
            sql += ' AND p.query_id=?'
            args.append(query_id)
        return self.store.rows(sql + ' ORDER BY p.query_id,p.annotation_order', args)

    def judgments(self, pool_id, query_id, offset, limit, status, text):
        if query_id not in {q['id'] for q in self.pool(pool_id)['metadata']['queries']}:
            raise APIError(404, 'unknown_query', 'Query does not belong to pool')
        rows = self.documents(pool_id, query_id)
        rows = [r for r in rows if status == 'all' or (status == 'unjudged') == (r['relevance_grade'] is None)]
        if text:
            metadata = self.search.repository.fetch_many([r['paper_id'] for r in rows])
            rows = [r for r in rows if text.lower() in (metadata[r['paper_id']].title + ' ' + metadata[r['paper_id']].abstract).lower()]
        total = len(rows)
        rows = rows[offset:offset + limit]
        metadata = self.search.repository.fetch_many([r['paper_id'] for r in rows])
        # Explicit allowlist: no ranking, native score, or retrieval provenance.
        return dict(total=total, offset=offset, items=[dict(query_id=r['query_id'], paper_id=r['paper_id'],
                  relevance_grade=r['relevance_grade'], annotation_order=r['annotation_order'],
                  paper=metadata[r['paper_id']].model_dump(mode='json')) for r in rows])

    def judge(self, pool_id, judgment):
        pool = self.pool(pool_id)
        if pool['status'] != 'COMPLETED' or pool['stale']:
            raise APIError(409, 'incompatible_pool', 'Pool must be completed and compatible before annotation')
        key = (pool_id, judgment.query_id, judgment.paper_id)
        with self.store.connection() as db:
            if not db.execute('SELECT 1 FROM pool_documents WHERE pool_id=? AND query_id=? AND paper_id=?', key).fetchone():
                raise APIError(404, 'not_in_pool', 'Query-paper pair is not in this pool')
            if judgment.relevance_grade is None:
                db.execute('DELETE FROM relevance_judgments WHERE pool_id=? AND query_id=? AND paper_id=?', key)
            else:
                db.execute('''INSERT INTO relevance_judgments VALUES (?,?,?,?,'human',?,?)
                    ON CONFLICT(pool_id,query_id,paper_id) DO UPDATE SET relevance_grade=excluded.relevance_grade,
                    updated_at=excluded.updated_at''', (*key, judgment.relevance_grade, now(), now()))
        return dict(saved=True, **judgment.model_dump())

    def readiness(self, pool_id, cutoff=10, threshold=1):
        pool = self.pool(pool_id)
        rows = self.documents(pool_id)
        progress = []
        for q in pool['metadata']['queries']:
            documents = [r for r in rows if r['query_id'] == q['id']]
            required = [r for r in documents if any(p['rank'] <= cutoff for p in json.loads(r['provenance']).values())]
            missing = [r['paper_id'] for r in required if r['relevance_grade'] is None]
            judged = sum(r['relevance_grade'] is not None for r in documents)
            status = ('STALE' if pool['stale'] else 'NOT_STARTED' if pool['status'] != 'COMPLETED' else
                      'INSUFFICIENT_DEPTH' if pool['metadata']['depth'] < cutoff else 'INCOMPLETE' if missing else 'READY')
            progress.append(dict(query_id=q['id'], total=len(documents), judged=judged,
                unjudged=len(documents)-judged, required=len(required), missing_required=len(missing),
                missing_paper_ids=missing, status=status, percent=100*judged/len(documents) if documents else 0,
                known_relevant=sum(r['relevance_grade'] is not None and r['relevance_grade'] >= threshold for r in documents),
                grades={str(g): sum(r['relevance_grade'] == g for r in documents) for g in range(3)}))
        return dict(pool_id=pool_id, total=sum(p['total'] for p in progress), judged=sum(p['judged'] for p in progress),
                    unjudged=sum(p['unjudged'] for p in progress), required=sum(p['required'] for p in progress),
                    missing_required=sum(p['missing_required'] for p in progress),
                    eligible_queries=sum(p['status']=='READY' for p in progress), queries=progress)

    def run(self, request):
        pool = self.pool(request.pool_id)
        run_id = 'run-' + uuid.uuid4().hex
        with self.store.connection() as db:
            # Freeze judgments and determine fairness in the same SQLite read transaction.
            rows = [dict(r) for r in db.execute('''SELECT p.*,j.relevance_grade FROM pool_documents p
                         LEFT JOIN relevance_judgments j USING(pool_id,query_id,paper_id)
                         WHERE p.pool_id=? ORDER BY p.query_id,p.annotation_order''', (request.pool_id,))]
            if pool['stale'] or pool['status'] != 'COMPLETED' or pool['metadata']['depth'] < request.cutoff:
                raise APIError(409, 'incompatible_pool', 'Pool is stale, unfinished, or too shallow')
            snapshot = {q['id']: {r['paper_id']:r['relevance_grade'] for r in rows if r['query_id']==q['id']} for q in pool['metadata']['queries']}
            eligible, excluded, metrics, rankings = [], [], [], []
            for q in pool['metadata']['queries']:
                documents = [r for r in rows if r['query_id']==q['id']]
                missing = [r['paper_id'] for r in documents if r['relevance_grade'] is None and
                           any(p['rank']<=request.cutoff for p in json.loads(r['provenance']).values())]
                if missing:
                    excluded.append(dict(query_id=q['id'], status='INCOMPLETE', missing_paper_ids=missing))
                    continue
                eligible.append(q['id'])
                for mode in MODES:
                    hits = [(r['paper_id'], json.loads(r['provenance'])[mode]) for r in documents if mode in json.loads(r['provenance'])]
                    hits.sort(key=lambda h: h[1]['rank'])
                    metrics.append(dict(query_id=q['id'], algorithm=mode,
                                        **evaluate([h[0] for h in hits], snapshot[q['id']], request.cutoff, request.relevance_threshold)))
                    rankings.extend((run_id,q['id'],mode,h[1]['rank'],h[0],h[1]['native_score']) for h in hits)
            if not eligible:
                raise APIError(409, 'incomplete_judgments', 'No query has complete judgments for the four-method top-K union')
            metadata = dict(**pool['metadata'], cutoff=request.cutoff, relevance_threshold=request.relevance_threshold,
                judgment_snapshot_version=digest(snapshot), judgment_policy='complete_top_k_union',
                eligible_queries=eligible, excluded_queries=excluded,
                aggregate={mode:aggregate([m for m in metrics if m['algorithm']==mode]) for mode in MODES},
                metric_definitions=dict(precision='relevant top K / K; missing retrieval positions contribute zero',
                    pooled_recall='relevant top K / known relevant in judged pool; not exhaustive corpus recall',
                    ap='sum precision at relevant ranks / min(known relevant,K)', ndcg='exponential gain / ideal judged pool gain',
                    curves='uninterpolated prefix points; aggregate macro mean by rank over same defined-recall queries'))
            db.execute('INSERT INTO evaluation_runs VALUES (?,?,?,?,?,?,?)',
                       (run_id,request.pool_id,'COMPLETED',dump(metadata),dump(snapshot),now(),now()))
            db.executemany('INSERT INTO evaluation_rankings VALUES (?,?,?,?,?,?)', rankings)
            db.executemany('INSERT INTO evaluation_metrics VALUES (?,?,?,?)',
                           [(run_id,m['query_id'],m['algorithm'],dump(m)) for m in metrics])
        return self.get_run(run_id)

    def runs(self):
        return [self.get_run(r['id'], detail=False) for r in self.store.rows('SELECT id FROM evaluation_runs ORDER BY created_at DESC')]

    def get_run(self, run_id, detail=True):
        rows = self.store.rows('SELECT * FROM evaluation_runs WHERE id=?', (run_id,))
        if not rows:
            raise APIError(404, 'unknown_run', 'Evaluation run not found')
        row = rows[0]
        row['metadata'] = json.loads(row['metadata'])
        row['judgment_snapshot'] = json.loads(row['judgment_snapshot']) if detail else None
        row['stale'] = self.pool(row['pool_id'])['stale']
        if detail:
            row['metrics'] = [json.loads(r['metrics']) for r in self.store.rows('SELECT metrics FROM evaluation_metrics WHERE run_id=? ORDER BY query_id,algorithm', (run_id,))]
            row['rankings'] = self.store.rows('SELECT query_id,algorithm,rank,paper_id,native_score FROM evaluation_rankings WHERE run_id=? ORDER BY query_id,algorithm,rank', (run_id,))
        return row

    def reserve_benchmark(self, request):
        version, queries = self.selected(request)
        if request.depth > min(self.search.settings.max_result_limit, self.search.settings.rrf_candidate_depth):
            raise APIError(422, 'invalid_depth', 'Depth exceeds retrieval limits')
        benchmark_id = 'bench-' + uuid.uuid4().hex
        metadata = dict(**self.identity(), configuration=request.model_dump(), queries=queries, query_set_version=version,
            environment=dict(os=platform.platform(), python=platform.python_version(), cpu=platform.processor() or None,
                logical_cpu_count=os.cpu_count(), worker_threads=self.settings.worker_threads,
                compute_threads=self.settings.compute_threads, corpus_size=len(self.search.indexes.ids),
                embedding_model=self.search.indexes.manifest['semantic']['model_name']),
            timing_scope='service-level full search; steady-state, single sequential worker',
            percentile_method='linear interpolation at (N-1)*p',
            total_samples=len(queries)*4*(request.warmup_iterations+request.measured_iterations))
        with self.store.connection() as db:
            db.execute('INSERT INTO benchmark_runs VALUES (?,?,?,?,?,NULL)', (benchmark_id,'QUEUED',dump(metadata),None,now()))
        return benchmark_id

    def benchmark(self, benchmark_id):
        try:
            with self.store.connection() as db:
                db.execute("UPDATE benchmark_runs SET status='RUNNING' WHERE id=?", (benchmark_id,))
            meta = self.get_benchmark(benchmark_id)['metadata']
            cfg = meta['configuration']
            rng = random.Random(cfg['random_seed'])
            failures = 0
            # Finish every warmup before any measured execution; randomize query/mode pairs per round.
            for warmup, count in ((True,cfg['warmup_iterations']),(False,cfg['measured_iterations'])):
                for iteration in range(count):
                    order = [(q,m) for q in meta['queries'] for m in MODES]
                    rng.shuffle(order)
                    for q, mode in order:
                        started = perf_counter()
                        latency, timing, error = None, None, None
                        try:
                            result = self.search.search(SearchRequest(q=q['query'],mode=mode,limit=cfg['depth'],**cfg['filters']))
                            latency = (perf_counter()-started)*1000
                            timing = dump(result.timing_ms.model_dump())
                        except Exception as exc:
                            error = str(exc)
                            failures += 1
                        with self.store.connection() as db:
                            db.execute('INSERT INTO benchmark_samples VALUES (?,?,?,?,?,?,?,?,?)',
                                (benchmark_id,q['id'],mode,iteration,int(warmup),latency,timing,error,now()))
            with self.store.connection() as db:
                db.execute('UPDATE benchmark_runs SET status=?,completed_at=? WHERE id=?',
                           ('COMPLETED_WITH_ERRORS' if failures else 'COMPLETED',now(),benchmark_id))
        except Exception as exc:
            with self.store.connection() as db:
                db.execute("UPDATE benchmark_runs SET status='FAILED',error=?,completed_at=? WHERE id=?", (str(exc),now(),benchmark_id))

    def get_benchmark(self, benchmark_id, detail=True):
        rows = self.store.rows('SELECT * FROM benchmark_runs WHERE id=?', (benchmark_id,))
        if not rows:
            raise APIError(404, 'unknown_benchmark', 'Benchmark not found')
        row = rows[0]
        row['metadata'] = json.loads(row['metadata'])
        samples = self.store.rows('SELECT * FROM benchmark_samples WHERE benchmark_run_id=? ORDER BY warmup DESC,iteration,query_id,algorithm', (benchmark_id,))
        if detail:
            for sample in samples:
                sample['timing_breakdown'] = json.loads(sample['timing_breakdown']) if sample['timing_breakdown'] else None
        row['samples'] = samples if detail else []
        row['completed_samples'] = len(samples)
        row['failed_samples'] = sum(s['error'] is not None for s in samples)
        row['summary'] = {m:latency_summary([s['latency_ms'] for s in samples if s['algorithm']==m and not s['warmup'] and s['error'] is None]) for m in MODES}
        return row
