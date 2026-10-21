"""Pure pooled IR metrics. Unknown judgments never become grade zero."""
from math import log2
from statistics import mean, pstdev


def evaluate(ranking, judgments, cutoff=10, threshold=1):
    if cutoff < 1 or threshold not in (1, 2):
        raise ValueError('Invalid cutoff or relevance threshold')
    if len(set(ranking)) != len(ranking):
        raise ValueError('Ranking contains duplicate IDs')
    if any(g not in (0, 1, 2, None) for g in judgments.values()):
        raise ValueError('Invalid grade')
    top = ranking[:cutoff]
    known_grades = [grade for grade in judgments.values() if grade is not None]
    coverage = sum(judgments.get(paper_id) is not None for paper_id in top) / len(top) if top else 1.0
    relevant_count = sum(grade >= threshold for grade in known_grades)
    result = dict(precision=None, pooled_recall=None, ap=None, dcg=None, ndcg=None,
                  coverage=coverage, known_relevant=relevant_count, curves=[], status='INCOMPLETE')
    if coverage < 1:
        return result
    grades = [judgments[p] for p in top]
    relevant_hits, precision_sum, curves = 0, 0.0, []
    for rank, grade in enumerate(grades, 1):
        if grade >= threshold:
            relevant_hits += 1
            precision_sum += relevant_hits / rank
        curves.append(dict(rank=rank, precision=relevant_hits / rank,
                           pooled_recall=relevant_hits / relevant_count if relevant_count else None))
    dcg = sum((2 ** grade - 1) / log2(rank + 1) for rank, grade in enumerate(grades, 1))
    ideal_grades = sorted(known_grades, reverse=True)[:cutoff]
    ideal_dcg = sum((2 ** grade - 1) / log2(rank + 1) for rank, grade in enumerate(ideal_grades, 1))
    result.update(precision=relevant_hits / cutoff,
                  pooled_recall=relevant_hits / relevant_count if relevant_count else None,
                  ap=precision_sum / min(relevant_count, cutoff) if relevant_count else None,
                  dcg=dcg, ndcg=dcg / ideal_dcg if ideal_dcg else None, curves=curves,
                  status='READY' if relevant_count else 'NO_KNOWN_RELEVANT')
    return result


def aggregate(rows):
    """Macro means over identical eligible queries; undefined values excluded explicitly."""
    output = {}
    for metric in ('precision', 'pooled_recall', 'ap', 'dcg', 'ndcg'):
        values = [r[metric] for r in rows if r[metric] is not None]
        output[metric] = mean(values) if values else None
        output[metric + '_query_count'] = len(values)
        output[metric + '_stddev'] = pstdev(values) if values else None
    output['query_count'] = len(rows)
    return output
