import math
import faiss
import numpy as np
import pytest
from backend.api.retrieval.base import PreparedQuery, SearchHit
from backend.api.retrieval.hybrid import reciprocal_rank_fusion
from backend.api.services import SearchService
from backend.api.schemas import Filters


@pytest.mark.parametrize('mode', ['tfidf', 'bm25', 'semantic'])
def test_filter_before_top_k(resources, mode):
    service = SearchService(resources)
    rankings, query, _ = service.rankings('quantum', [mode], Filters())
    target = resources.indexes.ids[-1]
    assert target not in [hit.paper_id for hit in rankings[mode][:10]]
    eligible = resources.repository.eligible(Filters(category='cs.LG'))
    hits = service.retrievers[mode].search(query, 10, eligible)
    assert len(hits) == 1 and hits[0].paper_id == target and hits[0].rank == 1
    assert service.retrievers[mode].search(query, 10, np.array([], dtype=np.int64)) == []


def test_semantic_all_eligible_and_ties(resources):
    service = SearchService(resources)
    query = PreparedQuery(None, None, np.array([[1, 0, 0]], dtype=np.float32))
    native = service.retrievers['semantic'].search(query, 10)
    filtered = service.retrievers['semantic'].search(query, 10, np.arange(16))
    assert native == filtered
    resources.vectors[:] = [1, 0, 0]
    resources.indexes.semantic = faiss.IndexFlatIP(3)
    resources.indexes.semantic.add(resources.vectors)
    from backend.api.retrieval.semantic import SemanticRetriever
    tied = SemanticRetriever(resources.indexes, resources.vectors).search(query, 3)
    assert [hit.paper_id for hit in tied] == resources.indexes.ids[:3]


def test_invalid_semantic_vector(resources):
    from backend.api.retrieval.semantic import SemanticRetriever
    with pytest.raises(RuntimeError, match='normalized query'):
        SemanticRetriever(resources.indexes, resources.vectors).search(PreparedQuery(None, None, np.zeros((1, 3), dtype=np.float32)), 10)


def test_zero_lexical_overlap(resources):
    service = SearchService(resources)
    rankings, _, _ = service.rankings('unfindablewordxyz', ['tfidf', 'bm25'], Filters())
    assert rankings == {'tfidf': [], 'bm25': []}


def hit(paper, position, rank, algorithm):
    return SearchHit(paper, position, rank, float(10 - rank), algorithm)


def test_rrf_hand_calculated_symmetric_tie():
    rankings = {mode: [hit(paper, 'ABC'.index(paper), rank, mode) for rank, paper in enumerate(order, 1)]
                for mode, order in [('tfidf', 'ABC'), ('bm25', 'BCA'), ('semantic', 'CAB')]}
    merged = reciprocal_rank_fusion(rankings)
    assert [h.paper_id for h in merged] == ['A', 'B', 'C']
    expected = math.fsum(1 / (60 + rank) for rank in [1, 2, 3])
    for h in merged:
        assert h.score == pytest.approx(expected)
        assert h.score == math.fsum(c['contribution'] for c in h.details['contributions'].values())
        assert all(c['contribution'] == 1 / (60 + c['rank']) for c in h.details['contributions'].values())


def test_rrf_missing_duplicate_and_depth():
    a = hit('A', 0, 1, 'tfidf')
    b = hit('B', 1, 3, 'tfidf')
    fused = reciprocal_rank_fusion({'tfidf': [a, a, b], 'bm25': [], 'semantic': []}, candidate_depth=2)
    assert len(fused) == 1 and fused[0].score == pytest.approx(1 / 61)
    assert reciprocal_rank_fusion({'tfidf': [], 'semantic': []}) == []
    with pytest.raises(ValueError, match='positions'):
        reciprocal_rank_fusion({'tfidf': [a], 'bm25': [hit('A', 5, 1, 'bm25')]})
