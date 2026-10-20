from dataclasses import dataclass, field
from typing import Protocol
import numpy as np


@dataclass(frozen=True)
class SearchHit:
    paper_id: str
    document_position: int
    rank: int
    score: float
    algorithm: str
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PreparedQuery:
    counts: object
    tfidf: object
    vector: np.ndarray | None


class Retriever(Protocol):
    def search(self, query: PreparedQuery, top_k: int, eligible_positions: np.ndarray | None = None) -> list[SearchHit]: ...


def select(scores: np.ndarray, ids: list[str], algorithm: str, top_k: int,
           eligible: np.ndarray | None, positive: bool = True) -> list[SearchHit]:
    if top_k < 1:
        raise ValueError('top_k must be positive')
    candidates = np.arange(len(ids)) if eligible is None else eligible
    if positive:
        candidates = candidates[scores[candidates] > 0]
    if not np.isfinite(scores[candidates]).all():
        raise RuntimeError('Non-finite retrieval scores')
    ordered = candidates[np.lexsort((candidates, -scores[candidates]))[:top_k]]
    return [SearchHit(ids[i], int(i), rank, float(scores[i]), algorithm) for rank, i in enumerate(ordered, 1)]
