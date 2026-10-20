import numpy as np
from backend.pipeline.search import bm25_scores
from .base import PreparedQuery, SearchHit, select


class TfidfRetriever:
    def __init__(self, indexes):
        self.indexes = indexes

    def search(self, query: PreparedQuery, top_k: int, eligible_positions: np.ndarray | None = None) -> list[SearchHit]:
        if eligible_positions is not None and len(eligible_positions) == 0:
            return []
        if query.tfidf.nnz == 0:
            return []
        if eligible_positions is None:
            scores = (self.indexes.tfidf @ query.tfidf.T).toarray().ravel()
        else:
            scores = np.zeros(len(self.indexes.ids))
            scores[eligible_positions] = (self.indexes.tfidf[eligible_positions] @ query.tfidf.T).toarray().ravel()
        return select(scores, self.indexes.ids, 'tfidf', top_k, eligible_positions)


class BM25Retriever:
    def __init__(self, indexes):
        self.indexes = indexes

    def search(self, query: PreparedQuery, top_k: int, eligible_positions: np.ndarray | None = None) -> list[SearchHit]:
        if eligible_positions is not None and len(eligible_positions) == 0:
            return []
        stats = self.indexes.stats
        # Reuse the independently tested sparse posting scorer, with corpus-wide IDF.
        scores = bm25_scores(self.indexes.counts, stats['doc_lengths'], stats['idf'],
                             float(stats['avgdl']), float(stats['k1']), float(stats['b']), query.counts.indices)
        return select(scores, self.indexes.ids, 'bm25', top_k, eligible_positions)
