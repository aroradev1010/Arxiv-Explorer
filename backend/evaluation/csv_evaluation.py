"""Validate CSV judgments and evaluate the preserved top-10 rankings."""
import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from statistics import mean

from .metrics import aggregate, evaluate

DIRECTORY = Path(__file__).resolve().parents[2] / 'data/evaluation'
MODES = ('tfidf', 'bm25', 'semantic', 'hybrid')
FIELDS = ('query_id', 'query_text', 'paper_id', 'title', 'abstract', 'relevance')
QUERIES = (
    ('Q001', 'graph neural networks'),
    ('Q002', 'methods for detecting cancer using medical images'),
    ('Q011', 'quantum entanglement entropy in black holes'),
    ('Q013', 'how galaxies form and evolve'),
    ('Q030', 'machine learning approaches for climate prediction'),
)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def write_json(path, value):
    """Replace the single current output without exposing a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def load_judgments(directory=DIRECTORY):
    """Validate the entire pool against all four preserved rankings, including blanks."""
    from backend.pipeline.dataset import ID

    rankings_bytes = (directory / 'rankings.json').read_bytes()
    saved = json.loads(rankings_bytes)
    if not isinstance(saved, dict) or saved.get('schema_version') != 1 or saved.get('cutoff') != 10:
        raise ValueError('Unsupported rankings file; restore the preserved rankings.json.')
    queries = saved.get('queries')
    expected_queries = dict(QUERIES)
    if not isinstance(queries, list) or len(queries) != len(expected_queries):
        raise ValueError(f'Rankings must contain all {len(expected_queries)} selected queries exactly once.')
    expected, seen_queries = set(), set()
    for query in queries:
        if not isinstance(query, dict):
            raise ValueError('Each saved query must include its ID, text, and four rankings.')
        query_id = query.get('query_id')
        if query_id not in expected_queries or query_id in seen_queries or query.get('query_text') != expected_queries[query_id]:
            raise ValueError('Unknown, duplicate, or inconsistent query in rankings.')
        seen_queries.add(query_id)
        rankings = query.get('rankings')
        if not isinstance(rankings, dict) or set(rankings) != set(MODES):
            raise ValueError(f'{query_id}: all four algorithm rankings are required.')
        for mode, ids in rankings.items():
            if not isinstance(ids, list) or len(ids) != 10:
                raise ValueError(f'{query_id}/{mode}: ten paper IDs are required.')
            invalid_ids = any(not isinstance(paper_id, str) or not ID.fullmatch(paper_id) for paper_id in ids)
            if invalid_ids or len(set(ids)) != 10:
                raise ValueError(f'{query_id}/{mode}: invalid or duplicate paper IDs; ten are required.')
            expected.update((query_id, paper_id) for paper_id in ids)
    csv_bytes = (directory / 'relevance_judgments.csv').read_bytes()
    reader = csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig'), newline=''))
    if reader.fieldnames != list(FIELDS):
        raise ValueError('CSV columns must be: ' + ','.join(FIELDS))
    judgments = {query_id: {} for query_id in expected_queries}
    actual = set()
    for line, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f'CSV record {line}: missing or extra fields.')
        query_id, paper_id = row['query_id'], row['paper_id']
        pair = query_id, paper_id
        if pair in actual:
            raise ValueError(f'CSV record {line}: duplicate query-paper pair.')
        if pair not in expected or row['query_text'] != expected_queries[query_id]:
            raise ValueError(f'CSV record {line}: unknown query/paper ID or changed query text. Import IDs as text in Excel.')
        if not row['title'].strip() or not row['abstract'].strip():
            raise ValueError(f'CSV record {line}: title and abstract are required.')
        grade = row['relevance'].strip()
        if grade not in ('', '0', '1', '2'):
            raise ValueError(f'CSV record {line}: relevance must be empty, 0, 1, or 2.')
        actual.add(pair)
        judgments[query_id][paper_id] = int(grade) if grade else None
    if actual != expected:
        raise ValueError(f'CSV is missing {len(expected - actual)} required query-paper pairs. Restore the missing rows.')
    return saved, judgments, dict(judgments_sha256=digest(csv_bytes), rankings_sha256=digest(rankings_bytes))


def calculate(directory=DIRECTORY):
    saved, judgments, fingerprints = load_judgments(directory)
    incomplete = {query_id: sum(grade is None for grade in grades.values())
                  for query_id, grades in judgments.items()}
    remaining = sum(incomplete.values())
    if remaining:
        result = dict(schema_version=1, status='pending', query_count=len(judgments),
                      remaining_judgments=remaining,
                      incomplete_queries={query_id: count for query_id, count in incomplete.items() if count})
    else:
        per_query, metrics, curves = [], {}, []
        for mode in MODES:
            rows = []
            for query in saved['queries']:
                query_id = query['query_id']
                row = evaluate(query['rankings'][mode], judgments[query_id], cutoff=10, threshold=1)
                rows.append(row)
                per_query.append(dict(query_id=query_id, algorithm=mode, **row))
            means = aggregate(rows)
            metrics[mode] = {name: means[name] for name in ('precision', 'pooled_recall', 'ap', 'ndcg')}
            eligible = [row for row in rows if row['pooled_recall'] is not None]
            for rank in range(1, 11):
                if eligible:
                    points = [row['curves'][rank - 1] for row in eligible]
                    curves.append(dict(algorithm=mode, rank=rank,
                                       precision=mean(point['precision'] for point in points),
                                       pooled_recall=mean(point['pooled_recall'] for point in points)))
        result = dict(schema_version=1, status='complete', cutoff=10, query_count=len(judgments),
                      judgment_count=sum(len(grades) for grades in judgments.values()), **fingerprints,
                      metrics=metrics, per_query=per_query, curves=curves)
    write_json(directory / 'results.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('evaluate',))
    args = parser.parse_args(argv)
    try:
        result = calculate(DIRECTORY)
        if result['status'] == 'pending':
            print(f"Awaiting {result['remaining_judgments']} manual judgments; no effectiveness metrics calculated.")
            for query_id, count in result['incomplete_queries'].items():
                print(f'  {query_id}: {count} remaining')
        else:
            print(f"Evaluated {result['query_count']} complete queries: {DIRECTORY / 'results.json'}")
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f'Evaluation error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
