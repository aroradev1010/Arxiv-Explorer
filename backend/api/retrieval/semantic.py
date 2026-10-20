import numpy as np
from .base import PreparedQuery, SearchHit


class SemanticRetriever:
    def __init__(self, indexes, vectors):
        self.indexes, self.vectors = indexes, vectors

    def search(self, query: PreparedQuery, top_k: int, eligible_positions: np.ndarray | None = None) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError('top_k must be positive')
        if eligible_positions is not None and len(eligible_positions) == 0:
            return []
        vector = query.vector
        if vector is None or vector.shape != (1, self.indexes.semantic.d) or not np.isfinite(vector).all() or not np.allclose(np.linalg.norm(vector, axis=1), 1, atol=1e-5):
            raise RuntimeError('Invalid normalized query embedding')
        count = len(self.indexes.ids)
        if eligible_positions is None or np.array_equal(eligible_positions, np.arange(count)):
            # Expand the boundary when needed so FAISS tie order cannot hide lower-ID ties.
            depth = min(count, top_k + 32)
            while True:
                scores, positions = self.indexes.semantic.search(np.ascontiguousarray(vector), depth)
                valid = positions[0] >= 0
                values, candidates = scores[0][valid], positions[0][valid]
                if len(values) <= top_k or depth == count or values[-1] < values[top_k - 1]:
                    break
                depth = min(count, depth * 2)
        else:
            candidates = eligible_positions
            values = np.empty(len(candidates), dtype=np.float32)
            for start in range(0, len(candidates), 4096):
                stop = min(len(candidates), start + 4096)
                values[start:stop] = self.vectors[candidates[start:stop]] @ vector[0]
        if not np.isfinite(values).all() or np.any(candidates >= count):
            raise RuntimeError('Invalid FAISS results')
        order = np.lexsort((candidates, -values))[:top_k]
        return [SearchHit(self.indexes.ids[int(candidates[i])], int(candidates[i]), rank,
                          float(values[i]), 'semantic') for rank, i in enumerate(order, 1)]
