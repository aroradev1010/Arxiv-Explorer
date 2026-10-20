"""Read-only Phase 4 real-corpus smoke and explicitly marked test snapshots."""
import json
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlencode
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests' / 'fixtures'
OUT.mkdir(parents=True, exist_ok=True)
def fetch(path, args=None, body=None):
    url = 'http://127.0.0.1:8000/api/v1/' + path
    if args: url += '?' + urlencode(args)
    req = Request(url, data=json.dumps(body).encode() if body else None,
                  headers={'Content-Type': 'application/json'} if body else {})
    with urlopen(req, timeout=90) as response: return json.load(response)
def save(name, value):
    (OUT / (name + '.json')).write_text(json.dumps(value, indent=2), encoding='utf-8')
    return value
report = {}
for mode in ['hybrid', 'tfidf', 'bm25', 'semantic']:
    data = save(mode, fetch('search', {'q': 'graph neural networks', 'mode': mode, 'limit': 10}))
    assert data['mode'] == mode and data['results']
    assert [r['rank'] for r in data['results']] == list(range(1, len(data['results']) + 1))
    report[mode] = {'first_id': data['results'][0]['paper']['id'], 'score': data['results'][0]['score'], 'returned': len(data['results']), 'ms': data['timing_ms']['total']}
filtered = save('filtered', fetch('search', {'q': 'graph neural networks', 'mode': 'hybrid', 'category': 'cs.LG', 'subject': 'cs', 'year_from': 2015, 'year_to': 2025}))
assert all('cs.LG' in r['paper']['categories'] and 2015 <= int(r['paper']['published_at'][:4]) <= 2025 for r in filtered['results'])
source = json.loads((OUT / 'hybrid.json').read_text())['results'][0]['paper']
author_filtered = fetch('search', {'q': 'graph neural networks', 'mode': 'hybrid', 'category': 'cs.LG', 'subject': 'cs', 'year_from': 2015, 'year_to': 2025, 'author': source['authors'][0]})
assert author_filtered['results'] and any(r['paper']['id'] == source['id'] for r in author_filtered['results'])
report['author_combined_filter_returned'] = len(author_filtered['results'])
import sqlite3
with sqlite3.connect((ROOT.parent / 'data/processed/papers.sqlite').as_uri() + '?mode=ro', uri=True) as database:
    legacy_id = database.execute("SELECT id FROM papers WHERE id LIKE '%/%' LIMIT 1").fetchone()[0]
legacy = fetch('papers', {'arxiv_id': legacy_id})
assert legacy['id'] == legacy_id
report['legacy_id'] = legacy_id
paper = save('paper', fetch('papers', {'arxiv_id': source['id']}))
assert paper == source
similar = save('similar', fetch('papers/similar', {'arxiv_id': paper['id'], 'limit': 5}))
assert len(similar['results']) == 5 and all(r['paper']['id'] != paper['id'] for r in similar['results'])
comparison = save('compare', fetch('compare', body={'query': 'graph neural networks', 'top_k': 5, 'modes': ['tfidf', 'bm25', 'semantic', 'hybrid'], 'filters': {}}))
assert len(comparison['methods']) == 4
for r in comparison['methods']['hybrid']['results']:
    assert abs(sum(c['contribution'] for c in r['ranking_details']['contributions'].values()) - r['score']) < 1e-8
save('categories', fetch('categories'))
save('stats', fetch('system/stats'))
save('live', fetch('health/live'))
save('ready', fetch('health/ready'))
report.update(filtered_returned=len(filtered['results']), paper_id=paper['id'], similar_count=len(similar['results']), compared_methods=list(comparison['methods']), status='passed')
(OUT / 'README.md').write_text('Test data only: read-only snapshots of the actual local API, captured by scripts/live-smoke.py. Never imported by production components. Legacy and error fixtures in tests are explicitly synthetic test cases.\n', encoding='utf-8')
(ROOT.parent / 'docs' / 'PHASE4_LIVE_SMOKE.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
