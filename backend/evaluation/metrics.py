"""Pure pooled IR metrics. Unknown judgments never become grade zero."""
from math import log2, floor
from statistics import mean, median, pstdev


def evaluate(ranking, judgments, cutoff=10, threshold=1):
    if cutoff < 1 or threshold not in (1, 2):
        raise ValueError('Invalid cutoff or relevance threshold')
    if len(set(ranking)) != len(ranking):
        raise ValueError('Ranking contains duplicate IDs')
    if any(g not in (0, 1, 2, None) for g in judgments.values()):
        raise ValueError('Invalid grade')
    top = ranking[:cutoff]
    known = [g for g in judgments.values() if g is not None]
    coverage = sum(judgments.get(p) is not None for p in top) / len(top) if top else 1.0
    relevant = sum(g >= threshold for g in known)
    result = dict(precision=None, pooled_recall=None, ap=None, dcg=None, ndcg=None,
                  coverage=coverage, known_relevant=relevant, curves=[], status='INCOMPLETE')
    if coverage < 1:
        return result
    grades = [judgments[p] for p in top]
    hits, ap_sum, curves = 0, 0.0, []
    for rank, grade in enumerate(grades, 1):
        if grade >= threshold:
            hits += 1
            ap_sum += hits / rank
        curves.append(dict(rank=rank, precision=hits / rank,
                           pooled_recall=hits / relevant if relevant else None))
    dcg = sum((2 ** g - 1) / log2(i + 1) for i, g in enumerate(grades, 1))
    ideal = sum((2 ** g - 1) / log2(i + 1) for i, g in enumerate(sorted(known, reverse=True)[:cutoff], 1))
    result.update(precision=hits / cutoff, pooled_recall=hits / relevant if relevant else None,
                  ap=ap_sum / min(relevant, cutoff) if relevant else None,
                  dcg=dcg, ndcg=dcg / ideal if ideal else None, curves=curves,
                  status='READY' if relevant else 'NO_KNOWN_RELEVANT')
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


def latency_summary(values):
    """P95 uses linear interpolation at (N-1)*0.95; population standard deviation."""
    if not values:
        return dict(count=0, mean=None, p50=None, p95=None, minimum=None, maximum=None, stddev=None)
    values = sorted(values)
    position = (len(values) - 1) * .95
    lower = floor(position)
    p95 = values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)
    return dict(count=len(values), mean=mean(values), p50=median(values), p95=p95,
                minimum=values[0], maximum=values[-1], stddev=pstdev(values))
