"""Local-only mutations, explicit background jobs, blind responses and deterministic exports."""
import asyncio
import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Literal
from fastapi import APIRouter, Request, Query
from fastapi.responses import Response
from backend.api.errors import APIError
from .schemas import EvaluationQuery, QueryCollection, PoolRequest, Judgment, RunRequest, BenchmarkRequest
from .service import EvaluationService, MODES
from .store import dump
from .contracts import (CollectionResponse, ConfigResponse, PoolResponse, DocumentsResponse, SavedJudgment,
                        ProgressResponse, RunResponse, MetricsResponse, RunQueriesResponse, CurvesResponse, BenchmarkResponse)


def install(application, settings):
    router = APIRouter(prefix='/api/v1/evaluation', tags=['evaluation'])

    def service():
        value = getattr(application.state, 'evaluation', None)
        if not settings.evaluation_enabled or value is None:
            raise APIError(503, 'evaluation_disabled', 'Evaluation is disabled or unavailable')
        return value

    def mutation(request):
        service()
        host = request.client.host if request.client else ''
        if not settings.evaluation_mutations_enabled or settings.app_env == 'production' or host not in ('127.0.0.1', '::1', 'testclient'):
            raise APIError(403, 'evaluation_read_only', 'Enable EVALUATION_MUTATIONS_ENABLED in a trusted local environment')
        origin = request.headers.get('origin')
        if origin and origin not in settings.cors_origins:
            raise APIError(403, 'untrusted_origin', 'Evaluation mutations require a trusted local origin')

    async def call(function, *args):
        return await asyncio.to_thread(function, *args)

    def submit(function, job_id):
        executor = application.state.evaluation_executor
        def work():
            try:
                function(job_id)
            finally:
                service().job_lock.release()
        executor.submit(work)

    @router.get('/config', response_model=ConfigResponse)
    async def config():
        return dict(enabled=settings.evaluation_enabled,
                    mutations_enabled=settings.evaluation_mutations_enabled and settings.app_env != 'production')

    @router.get('/queries', response_model=CollectionResponse)
    async def queries(version: str | None = None):
        return await call(service().queries, version)

    @router.post('/queries', response_model=CollectionResponse)
    async def save_queries(body: QueryCollection, request: Request):
        mutation(request)
        return await call(service().save_queries, [q.model_dump() for q in body.queries])

    @router.patch('/queries/{query_id}', response_model=CollectionResponse)
    async def edit_query(query_id: str, body: EvaluationQuery, request: Request):
        mutation(request)
        if query_id != body.id:
            raise APIError(422, 'query_id_mismatch', 'Query ID cannot change when editing')
        collection = service().queries()
        if query_id not in {q['id'] for q in collection['queries']}:
            raise APIError(404, 'unknown_query', 'Query not found')
        return await call(service().save_queries, [body.model_dump() if q['id']==query_id else q for q in collection['queries']])

    @router.get('/pools', response_model=list[PoolResponse])
    async def pools():
        return await call(service().pools)

    @router.post('/pools', status_code=202, response_model=PoolResponse)
    async def create_pool(body: PoolRequest, request: Request):
        mutation(request)
        s = service()
        if not s.job_lock.acquire(blocking=False):
            # An idempotent retry of the running request may return its existing job.
            version, qs = s.selected(body)
            from .service import digest
            key = digest(dict(**s.identity(), query_set_version=version, queries=qs, depth=body.depth,
                              filters=body.filters.model_dump(), random_seed=body.random_seed))
            existing = s.store.rows('SELECT id FROM candidate_pools WHERE request_key=?', (key,))
            if existing:
                return s.pool(existing[0]['id'])
            raise APIError(409, 'job_busy', 'An evaluation retrieval job is already running')
        try:
            pool_id, fresh = s.reserve_pool(body)
            if fresh:
                submit(s.generate_pool, pool_id)
            else:
                s.job_lock.release()
            return s.pool(pool_id)
        except Exception:
            if s.job_lock.locked():
                s.job_lock.release()
            raise

    @router.get('/pools/{pool_id}', response_model=PoolResponse)
    async def pool(pool_id: str):
        return await call(service().pool, pool_id)

    @router.get('/pools/{pool_id}/judgments', response_model=DocumentsResponse)
    async def judgments(pool_id: str, query_id: str, offset: int = Query(0, ge=0),
                        limit: int = Query(50, ge=1, le=100),
                        status: Literal['all','judged','unjudged'] = 'all', text: str = Query('', max_length=200)):
        s = service()
        if s.search is None:
            raise APIError(503, 'not_ready', 'Paper metadata unavailable')
        return await call(s.judgments, pool_id, query_id, offset, limit, status, text)

    @router.put('/pools/{pool_id}/judgments', response_model=SavedJudgment)
    async def judge(pool_id: str, body: Judgment, request: Request):
        mutation(request)
        return await call(service().judge, pool_id, body)

    @router.get('/progress', response_model=ProgressResponse)
    async def progress(pool_id: str, cutoff: int = Query(10, ge=1, le=100), threshold: int = Query(1, ge=1, le=2)):
        return await call(service().readiness, pool_id, cutoff, threshold)

    @router.post('/runs', status_code=201, response_model=RunResponse)
    async def run(body: RunRequest, request: Request):
        mutation(request)
        return await call(service().run, body)

    @router.get('/runs', response_model=list[RunResponse])
    async def runs():
        return await call(service().runs)

    @router.get('/runs/{run_id}', response_model=RunResponse)
    async def get_run(run_id: str):
        return await call(service().get_run, run_id)

    @router.get('/runs/{run_id}/metrics', response_model=MetricsResponse)
    async def metrics(run_id: str):
        run = await call(service().get_run, run_id)
        return dict(aggregate=run['metadata']['aggregate'], per_query=run['metrics'],
                    excluded_queries=run['metadata']['excluded_queries'], stale=run['stale'])

    @router.get('/runs/{run_id}/queries', response_model=RunQueriesResponse)
    async def run_queries(run_id: str):
        run = await call(service().get_run, run_id)
        return dict(queries=run['metadata']['queries'], metrics=run['metrics'], rankings=run['rankings'])

    @router.get('/runs/{run_id}/curves', response_model=CurvesResponse)
    async def curves(run_id: str):
        run = await call(service().get_run, run_id)
        points = [dict(query_id=m['query_id'],algorithm=m['algorithm'],**p) for m in run['metrics'] for p in m['curves']]
        aggregate = []
        for mode in MODES:
            for rank in range(1,run['metadata']['cutoff']+1):
                eligible = [m for m in run['metrics'] if m['algorithm']==mode and m['pooled_recall'] is not None]
                values = [next((p for p in m['curves'] if p['rank']==rank),
                               dict(precision=m['precision']*run['metadata']['cutoff']/rank, pooled_recall=m['pooled_recall'])) for m in eligible]
                if values:
                    aggregate.append(dict(algorithm=mode,rank=rank,query_count=len(values),
                        precision=sum(p['precision'] for p in values)/len(values),
                        pooled_recall=sum(p['pooled_recall'] for p in values)/len(values)))
        return dict(points=points, aggregate=aggregate, convention='Macro means by rank, no interpolation; undefined recall queries excluded')

    @router.get('/benchmarks', response_model=list[BenchmarkResponse])
    async def benchmarks():
        s = service()
        return await call(lambda: [s.get_benchmark(r['id'], detail=False) for r in s.store.rows('SELECT id FROM benchmark_runs ORDER BY created_at DESC')])

    @router.post('/benchmarks', status_code=202, response_model=BenchmarkResponse)
    async def benchmark(body: BenchmarkRequest, request: Request):
        mutation(request)
        s = service()
        if s.search is None:
            raise APIError(503, 'not_ready', 'Retrieval engine unavailable')
        if not s.job_lock.acquire(blocking=False):
            raise APIError(409, 'job_busy', 'An evaluation retrieval job is already running')
        try:
            job_id = s.reserve_benchmark(body)
            submit(s.benchmark, job_id)
            return s.get_benchmark(job_id)
        except Exception:
            if s.job_lock.locked():
                s.job_lock.release()
            raise

    @router.get('/benchmarks/{benchmark_id}', response_model=BenchmarkResponse)
    async def get_benchmark(benchmark_id: str):
        return await call(service().get_benchmark, benchmark_id)

    @router.get('/export')
    async def export(kind: Literal['queries','pool','judgments','run','metrics','aggregate','curves','benchmark','report'],
                     format: Literal['json','csv','md'] = 'json', id: str | None = None):
        s = service()
        if kind == 'report' and (not id or id.startswith('pool-')):
            collection=s.queries()
            pools=[s.pool(id)] if id else s.pools()
            progress=[s.readiness(p['id']) for p in pools if p['status']=='COMPLETED']
            content='# ArXiv Explorer methodology and status report\n\n'
            content+='No effectiveness conclusions are supplied by this status report. Human judgments and complete top-K coverage are required.\n\n'
            content+='## Dataset and algorithms\n\n'+json.dumps(s.identity(),indent=2)+'\n\n'
            content+='## Query design\n\n'+json.dumps(collection,indent=2)+'\n\n'
            content+='## Pooling and human judgment progress\n\n'+json.dumps(progress,indent=2)+'\n\n'
            content+='## Methodology and limitations\n\nGrades 0/1/2 are assigned by humans from title and abstract. Unjudged is distinct from zero. Require the four-method top-K union to be judged. Precision divides by K; AP divides by min(known relevant,K). Recall is pool-relative. nDCG uses exponential graded gain against judged pool grades. No interpolation or significance claims. Benchmark latency separately after warmup.\n'
            return Response(content,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="evaluation-status.md"'})
        if kind not in ('queries','report') and not id:
            raise APIError(422, 'missing_id', 'Select a pool, run, or benchmark ID')
        if kind == 'queries':
            data = s.queries(id)
            rows = data['queries']
        elif kind in ('pool','judgments'):
            data = dict(pool=s.pool(id), documents=s.documents(id))
            rows = data['documents']
        elif kind == 'benchmark':
            data = s.get_benchmark(id)
            rows = data['samples']
        else:
            data = s.get_run(id)
            rows = data['metrics']
            if kind == 'aggregate':
                rows = [dict(algorithm=m,**v) for m,v in data['metadata']['aggregate'].items()]
            elif kind == 'curves':
                rows = [dict(query_id=m['query_id'],algorithm=m['algorithm'],**p) for m in data['metrics'] for p in m['curves']]
        if kind == 'report' or format == 'md':
            if kind != 'report':
                raise APIError(422, 'invalid_format', 'Markdown is supported for research reports')
            meta = data['metadata']
            content = f"# ArXiv Explorer research report\n\nRun: {id}\n\n"
            for title, value in [('Dataset', {k:meta[k] for k in ('corpus_version','index_fingerprint')}),
                    ('Retrieval algorithms',meta['algorithm_configuration']), ('Query design',meta['queries']),
                    ('Pooling methodology',dict(depth=meta['depth'],filters=meta['filters'])),
                    ('Human judgment process',dict(snapshot=meta['judgment_snapshot_version'],policy=meta['judgment_policy'])),
                    ('Effectiveness metrics',meta['aggregate']), ('Precision-recall results',[dict(query_id=m['query_id'],algorithm=m['algorithm'],curves=m['curves']) for m in rows]),
                    ('Latency benchmarks','Independent benchmark exports required; no latency measured by this evaluation run.'),
                    ('Algorithm tradeoffs','Compare per-query values; no significance test or universal winner is claimed.'),
                    ('Limitations','Pooled recall is not exhaustive. Unjudged documents outside top K may bias recall and ideal DCG.'),
                    ('Evidence-supported conclusions',dict(eligible=meta['eligible_queries'],excluded=meta['excluded_queries']))]:
                content += f'## {title}\n\n```json\n{json.dumps(value,indent=2)}\n```\n\n'
            media, extension = 'text/markdown', 'md'
        elif format == 'csv':
            output = io.StringIO(newline='')
            keys = sorted({k for r in rows for k in r})
            writer = csv.DictWriter(output, fieldnames=keys)
            writer.writeheader()
            for row in rows:
                values = {k:dump(v) if isinstance(v,(dict,list)) else v for k,v in row.items()}
                # Defuse spreadsheet formulas in user-supplied text exports.
                writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in values.items()})
            content, media, extension = output.getvalue(), 'text/csv', 'csv'
        else:
            content, media, extension = dump(data), 'application/json', 'json'
        filename = f'evaluation-{kind}-{id or "queries"}.{extension}'
        return Response(content, media_type=media, headers={'Content-Disposition':f'attachment; filename="{filename}"'})

    application.include_router(router)


def initialize(application, settings):
    if settings.evaluation_enabled:
        application.state.evaluation = EvaluationService(settings, application.state.service)
        import faiss
        application.state.evaluation_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='arxiv-evaluation',
            initializer=lambda:faiss.omp_set_num_threads(settings.compute_threads))


async def shutdown(application):
    executor = getattr(application.state,'evaluation_executor',None)
    if executor:
        await asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True)
