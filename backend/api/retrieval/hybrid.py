import math
from .base import SearchHit


def reciprocal_rank_fusion(rankings: dict[str, list[SearchHit]], k: int = 60,
                           candidate_depth: int = 200) -> list[SearchHit]:
    if k < 1 or candidate_depth < 1:
        raise ValueError('RRF parameters must be positive')
    merged = {}
    for algorithm, hits in rankings.items():
        seen = set()
        for hit in hits[:candidate_depth]:
            if hit.rank < 1:
                raise ValueError('RRF requires 1-based ranks')
            if hit.paper_id in seen:
                continue
            seen.add(hit.paper_id)
            entry = merged.setdefault(hit.paper_id, {'position': hit.document_position, 'contributions': {}})
            if entry['position'] != hit.document_position:
                raise ValueError('Rankers disagree on document positions')
            entry['contributions'][algorithm] = {'rank': hit.rank, 'native_score': hit.score,
                                                  'contribution': 1 / (k + hit.rank)}
    scored = []
    for paper_id, entry in merged.items():
        # Accurate summation preserves symmetric ties across rankers.
        contributions = entry['contributions'].values()
        score = math.fsum(item['contribution'] for item in contributions)
        scored.append((paper_id, score, entry))
    scored.sort(key=lambda entry: (-entry[1], entry[0]))
    results = []
    for rank, (paper_id, score, entry) in enumerate(scored, 1):
        details = {'rrf_score': score, 'contributions': entry['contributions']}
        results.append(SearchHit(paper_id, entry['position'], rank, score, 'hybrid', details))
    return results
