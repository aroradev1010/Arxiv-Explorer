"""Request-local orchestration with shared eligibility, preparation and explanations."""
from itertools import combinations
from dataclasses import replace
from time import perf_counter
import numpy as np
import psutil

from backend.pipeline.text import clean
from .errors import APIError
from .schemas import (CompareRequest, CompareResponse, Filters, Pagination, RankedPaper,
                      RankingDetails, RankDifference, SearchRequest, SearchResponse,
                      SimilarResponse, Stats, Timing)
from .retrieval.base import PreparedQuery
from .retrieval.lexical import BM25Retriever, TfidfRetriever
from .retrieval.semantic import SemanticRetriever
from .retrieval.hybrid import reciprocal_rank_fusion


STAGES = ['preprocessing', 'eligibility', 'embedding', 'tfidf', 'bm25', 'semantic', 'retrieval', 'fusion', 'metadata', 'total']


def timings(values: dict) -> Timing:
    return Timing(**{key: round(float(values.get(key, 0)), 6) for key in STAGES})


class SearchService:
    def __init__(self, resources):
        self.resources, self.settings = resources, resources.settings
        self.repository, self.indexes = resources.repository, resources.indexes
        self.retrievers = {'tfidf': TfidfRetriever(self.indexes), 'bm25': BM25Retriever(self.indexes),
                           'semantic': SemanticRetriever(self.indexes, resources.vectors)}
        self.tokens = self.indexes.vectorizer.get_feature_names_out()

    def validate_window(self, mode: str, offset: int, limit: int) -> int:
        window = self.settings.rrf_candidate_depth if mode == 'hybrid' else self.settings.max_ranking_window
        if limit > self.settings.max_result_limit:
            raise APIError(422, 'invalid_limit', f'limit must not exceed {self.settings.max_result_limit}')
        if offset + limit > window:
            raise APIError(422, 'invalid_pagination_window', f'{mode} supports offset + limit up to {window}')
        return window

    def prepare(self, query: str, needed: set[str], eligible: np.ndarray | None, measured: dict) -> PreparedQuery:
        started = perf_counter()
        counts = self.indexes.vectorizer.transform([query]) if needed & {'tfidf', 'bm25'} else None
        vector_tfidf = self.indexes.transformer.transform(counts) if 'tfidf' in needed else None
        text = clean(query) if 'semantic' in needed else None
        measured['preprocessing'] = (perf_counter() - started) * 1000
        vector = None
        if text and 'semantic' in needed and (eligible is None or len(eligible)):
            started = perf_counter()
            with self.resources.model_lock:
                vector = self.indexes.model.encode([text], normalize_embeddings=True, convert_to_numpy=True,
                                                  show_progress_bar=False).astype(np.float32)
            measured['embedding'] = (perf_counter() - started) * 1000
        return PreparedQuery(counts, vector_tfidf, vector)

    def rankings(self, query: str, modes: list[str], filters: Filters):
        measured = {key: 0.0 for key in STAGES}
        started = perf_counter()
        eligible = self.repository.eligible(filters)
        measured['eligibility'] = (perf_counter() - started) * 1000
        needed = set(modes) - {'hybrid'}
        if 'hybrid' in modes:
            needed.update(self.retrievers)
        prepared = self.prepare(query, needed, eligible, measured)
        rankings = {}
        for mode in ('tfidf', 'bm25', 'semantic'):
            if mode in needed:
                depth = self.settings.max_ranking_window if mode in modes else self.settings.rrf_candidate_depth
                started = perf_counter()
                rankings[mode] = self.retrievers[mode].search(prepared, depth, eligible)
                measured[mode] = (perf_counter() - started) * 1000
        measured['retrieval'] = sum(measured[mode] for mode in self.retrievers)
        if 'hybrid' in modes:
            started = perf_counter()
            rankings['hybrid'] = reciprocal_rank_fusion({mode: rankings[mode] for mode in self.retrievers},
                                                        self.settings.rrf_k, self.settings.rrf_candidate_depth)[:self.settings.rrf_candidate_depth]
            measured['fusion'] = (perf_counter() - started) * 1000
        return rankings, prepared, measured

    def assemble(self, hits, metadata, query: PreparedQuery) -> list[RankedPaper]:
        results = []
        for hit in hits:
            if hit.paper_id not in metadata:
                raise APIError(503, 'metadata_unavailable', 'Ranked paper metadata is unavailable')
            details = {'final_rank': hit.rank, **hit.details}
            if hit.algorithm in ('tfidf', 'bm25'):
                matched = np.intersect1d(self.indexes.tfidf[hit.document_position].indices, query.counts.indices)
                details['matched_indexed_tokens'] = [str(self.tokens[i]) for i in matched]
            elif hit.algorithm == 'semantic':
                details['cosine_similarity'] = hit.score
            results.append(RankedPaper(paper=metadata[hit.paper_id], rank=hit.rank, score=hit.score,
                                       algorithm=hit.algorithm, ranking_details=RankingDetails(**details)))
        return results

    def response(self, query, mode, filters, hits, offset, limit, metadata, prepared, measured):
        window = self.validate_window(mode, offset, limit)
        page = hits[offset:offset + limit]
        return SearchResponse(query=query, mode=mode, filters=filters,
                              pagination=Pagination(limit=limit, offset=offset, returned=len(page),
                                                    has_more=offset + len(page) < len(hits),
                                                    ranking_window_size=window, ranked_candidate_count=len(hits)),
                              results=self.assemble(page, metadata, prepared), timing_ms=timings(measured),
                              index_version=self.resources.index_version)

    def search(self, request: SearchRequest) -> SearchResponse:
        started = perf_counter()
        self.validate_window(request.mode, request.offset, request.limit)
        filters = request.filters()
        rankings, prepared, measured = self.rankings(request.q, [request.mode], filters)
        hits = rankings[request.mode]
        metadata_start = perf_counter()
        metadata = self.repository.fetch_many([h.paper_id for h in hits[request.offset:request.offset + request.limit]])
        measured['metadata'] = (perf_counter() - metadata_start) * 1000
        response = self.response(request.q, request.mode, filters, hits, request.offset, request.limit, metadata, prepared, measured)
        response.timing_ms.total = (perf_counter() - started) * 1000
        return response

    def paper(self, paper_id: str):
        paper = self.repository.get(paper_id)
        if paper is None:
            raise APIError(404, 'paper_not_found', 'Paper not present in the indexed corpus')
        return paper

    def similar(self, paper_id: str, limit: int) -> SimilarResponse:
        started = perf_counter()
        if limit > self.settings.max_result_limit:
            raise APIError(422, 'invalid_limit', f'limit must not exceed {self.settings.max_result_limit}')
        self.paper(paper_id)
        position = self.repository.positions[paper_id]
        vector = np.ascontiguousarray(self.resources.vectors[position:position + 1])
        retrieval_start = perf_counter()
        hits = self.retrievers['semantic'].search(PreparedQuery(None, None, vector), limit + 1)
        hits = [hit for hit in hits if hit.paper_id != paper_id][:limit]
        hits = [replace(hit, rank=rank) for rank, hit in enumerate(hits, 1)]
        measured = {'semantic': (perf_counter() - retrieval_start) * 1000}
        measured['retrieval'] = measured['semantic']
        metadata_start = perf_counter()
        metadata = self.repository.fetch_many([hit.paper_id for hit in hits])
        measured['metadata'] = (perf_counter() - metadata_start) * 1000
        results = self.assemble(hits, metadata, PreparedQuery(None, None, vector))
        measured['total'] = (perf_counter() - started) * 1000
        return SimilarResponse(arxiv_id=paper_id, results=results, timing_ms=timings(measured), index_version=self.resources.index_version)

    def compare(self, request: CompareRequest) -> CompareResponse:
        started = perf_counter()
        for mode in request.modes:
            self.validate_window(mode, 0, request.top_k)
        rankings, prepared, measured = self.rankings(request.query, request.modes, request.filters)
        ids = sorted({hit.paper_id for mode in request.modes for hit in rankings[mode][:request.top_k]})
        metadata_start = perf_counter()
        metadata = self.repository.fetch_many(ids)
        measured['metadata'] = (perf_counter() - metadata_start) * 1000
        methods = {}
        for mode in request.modes:
            included = set(self.retrievers) if mode == 'hybrid' else {mode}
            path = dict(measured)
            for name in self.retrievers:
                if name not in included:
                    path[name] = 0.0
            if 'semantic' not in included:
                path['embedding'] = 0.0
            if mode != 'hybrid':
                path['fusion'] = 0.0
            path['retrieval'] = sum(path[name] for name in included)
            path['total'] = sum(path[name] for name in ['preprocessing', 'eligibility', 'embedding', 'retrieval', 'fusion', 'metadata'])
            methods[mode] = self.response(request.query, mode, request.filters, rankings[mode], 0,
                                           request.top_k, metadata, prepared, path)
        ranks = {mode: {hit.paper_id: hit.rank for hit in rankings[mode][:request.top_k]} for mode in request.modes}
        pairs = list(combinations(request.modes, 2))
        overlaps = {f'{first}:{second}': sorted(set(ranks[first]) & set(ranks[second]))
                    for first, second in pairs}
        differences = []
        for paper_id in ids:
            positions = {mode: ranks[mode].get(paper_id) for mode in request.modes}
            deltas = {}
            for first, second in pairs:
                first_rank, second_rank = positions[first], positions[second]
                deltas[f'{first}:{second}'] = (
                    second_rank - first_rank if first_rank is not None and second_rank is not None else None
                )
            differences.append(RankDifference(paper_id=paper_id, ranks=positions, delta_by_pair=deltas))
        measured['total'] = (perf_counter() - started) * 1000
        return CompareResponse(query=request.query, filters=request.filters, methods=methods,
                               overlaps=overlaps, rank_differences=differences, timing_ms=timings(measured),
                               index_version=self.resources.index_version)

    def stats(self) -> Stats:
        manifest = self.indexes.manifest
        semantic = manifest['semantic']
        return Stats(indexed_paper_count=len(self.indexes.ids), algorithms=list(self.retrievers) + ['hybrid'],
                     vocabulary_size=len(self.indexes.vectorizer.vocabulary_), embedding_dimension=self.indexes.semantic.d,
                     embedding_model=semantic['model_name'], model_revision=self.resources.model_revision,
                     dataset_version=self.resources.dataset['artifacts']['papers.jsonl'], index_version=self.resources.index_version,
                     index_schema_version=manifest['schema_version'],
                     index_build_information={'tfidf': manifest['tfidf'], 'bm25': manifest['bm25'],
                                              'semantic': {key: semantic[key] for key in ['max_seq_length', 'truncation', 'encoder_backend', 'batch_size', 'threads']},
                                              'packages': manifest['packages'], 'resources': manifest['resources']},
                     category_counts=self.repository.categories, process_rss_bytes=psutil.Process().memory_info().rss,
                     startup_ms=self.resources.startup_ms, worker_threads=self.settings.worker_threads,
                     compute_threads=self.settings.compute_threads)
