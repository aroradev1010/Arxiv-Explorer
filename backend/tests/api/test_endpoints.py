from concurrent.futures import ThreadPoolExecutor
import math
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.api.main import create_app
from backend.api.errors import AssetError
from backend.api.schemas import Filters


@pytest.mark.parametrize('mode', ['tfidf', 'bm25', 'semantic', 'hybrid'])
def test_search(client, resources, mode):
    response = client.get('/api/v1/search', params={'q': 'quantum', 'mode': mode, 'limit': 5})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data['results']) == 5
    assert [h['rank'] for h in data['results']] == [1, 2, 3, 4, 5]
    assert len({h['paper']['id'] for h in data['results']}) == 5
    assert all(math.isfinite(h['score']) for h in data['results'])
    assert all(data['results'][i]['score'] >= data['results'][i + 1]['score'] for i in range(4))
    assert data['timing_ms']['total'] > 0
    for result in data['results']:
        details = result['ranking_details']
        assert details['final_rank'] == result['rank']
        if mode in ['tfidf', 'bm25']:
            assert details['matched_indexed_tokens'] == ['quantum']
        if mode == 'hybrid':
            assert result['score'] == pytest.approx(math.fsum(v['contribution'] for v in details['contributions'].values()))


@pytest.mark.parametrize('params', [{'q': ''}, {'q': '   '}, {'q': '!!!'}, {'q': 'x' * 1001},
                                  {'q': 'quantum', 'mode': 'invalid'}, {'q': 'x', 'limit': 0},
                                  {'q': 'x', 'limit': 101}, {'q': 'x', 'offset': -1},
                                  {'q': 'x', 'year_from': 2025, 'year_to': 2020},
                                  {'q': 'x', 'year_from': 1800}, {'q': 'x', 'subject': 'invalid'}])
def test_validation(client, params):
    response = client.get('/api/v1/search', params=params)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'


@pytest.mark.parametrize('mode', ['tfidf', 'bm25', 'semantic', 'hybrid'])
def test_combined_secondary_category_filters(client, resources, mode):
    response = client.get('/api/v1/search', params={'q': 'quantum', 'mode': mode, 'category': 'cs.LG',
                                                   'subject': 'math', 'year_from': 2020, 'year_to': 2022, 'author': 'sMiTh'})
    assert response.status_code == 200, response.text
    data = response.json()
    assert [hit['paper']['id'] for hit in data['results']] == [resources.indexes.ids[-1]]
    assert data['results'][0]['rank'] == 1


def test_filter_semantics(resources):
    repo = resources.repository
    assert 14 not in repo.eligible(Filters(year_from=1991))
    assert repo.eligible(Filters(author='SMITH')).tolist() == [15]
    assert repo.eligible(Filters(author="' OR 1=1 --")).tolist() == []
    assert repo.eligible(Filters(author='%')).tolist() == []
    assert repo.eligible(Filters(category='cs.LG')).tolist() == [15]
    assert repo.eligible(Filters(subject='math')).tolist() == [15]


def test_empty_filtered_results(client, resources):
    for mode in ['tfidf', 'bm25', 'semantic', 'hybrid']:
        response = client.get('/api/v1/search', params={'q': 'quantum', 'mode': mode, 'category': 'no-such-category'})
        assert response.status_code == 200
        assert response.json()['results'] == []
    assert resources.indexes.model.calls == 0


def test_pagination(client):
    first = client.get('/api/v1/search', params={'q': 'quantum', 'limit': 5}).json()
    second = client.get('/api/v1/search', params={'q': 'quantum', 'limit': 5, 'offset': 5}).json()
    assert not ({h['paper']['id'] for h in first['results']} & {h['paper']['id'] for h in second['results']})
    assert [h['rank'] for h in second['results']] == [6, 7, 8, 9, 10]
    last = client.get('/api/v1/search', params={'q': 'quantum', 'limit': 1, 'offset': 11}).json()
    assert last['pagination']['has_more'] is False
    assert last['pagination']['ranking_window_size'] == 12
    assert client.get('/api/v1/search', params={'q': 'quantum', 'limit': 10, 'offset': 5}).status_code == 422


def test_papers_similar_and_legacy_id(client, resources):
    paper_id = resources.indexes.ids[-1]
    paper = client.get('/api/v1/papers', params={'arxiv_id': paper_id})
    assert paper.status_code == 200
    assert paper.json()['authors'] == ['Johann SMITH']
    assert paper.json()['pdf_url'].endswith(paper_id)
    similar = client.get('/api/v1/papers/similar', params={'arxiv_id': paper_id, 'limit': 5})
    assert similar.status_code == 200, similar.text
    assert all(h['paper']['id'] != paper_id for h in similar.json()['results'])
    assert resources.indexes.model.calls == 0
    assert client.get('/api/v1/papers', params={'arxiv_id': '9999.99999'}).status_code == 404
    assert client.get('/api/v1/papers', params={'arxiv_id': '../../bad'}).status_code == 422


def test_compare_reuses_preparation(client, resources):
    result = client.post('/api/v1/compare', json={'query': 'quantum', 'top_k': 5})
    assert result.status_code == 200, result.text
    data = result.json()
    assert set(data['methods']) == {'tfidf', 'bm25', 'semantic', 'hybrid'}
    assert resources.indexes.model.calls == 1
    assert len(data['overlaps']) == 6
    for item in data['rank_differences']:
        for pair, delta in item['delta_by_pair'].items():
            a, b = pair.split(':')
            expected = item['ranks'][b] - item['ranks'][a] if item['ranks'][a] is not None and item['ranks'][b] is not None else None
            assert delta == expected
    assert client.post('/api/v1/compare', json={'query': 'x', 'modes': ['bm25', 'bm25']}).status_code == 422


def test_categories_stats_health_openapi(client):
    assert client.get('/api/v1/health/live').json() == {'status': 'live', 'reason': None}
    assert client.get('/api/v1/health/ready').status_code == 200
    categories = client.get('/api/v1/categories').json()
    assert next(c for c in categories['categories'] if c['code'] == 'cs.LG')['count'] == 1
    stats = client.get('/api/v1/system/stats')
    assert stats.status_code == 200, stats.text
    assert stats.json()['indexed_paper_count'] == 16
    assert stats.json()['process_rss_bytes'] > 0
    assert client.get('/docs').status_code == 200
    schema = client.get('/openapi.json').json()
    assert {'/api/v1/search', '/api/v1/papers', '/api/v1/papers/similar', '/api/v1/categories',
            '/api/v1/compare', '/api/v1/system/stats', '/api/v1/health/live', '/api/v1/health/ready'} <= set(schema['paths'])
    assert {'q', 'mode', 'category', 'subject', 'year_from', 'year_to', 'author', 'offset', 'limit'} == {p['name'] for p in schema['paths']['/api/v1/search']['get']['parameters']}


def test_not_ready_and_sanitized_errors(resources):
    def unavailable(settings):
        raise AssetError('Missing required search asset: tfidf.npz')
    with TestClient(create_app(resources.settings, unavailable)) as client:
        assert client.get('/api/v1/health/live').status_code == 200
        assert client.get('/api/v1/health/ready').status_code == 503
        assert client.get('/api/v1/search', params={'q': 'quantum'}).status_code == 503


def test_invalid_encoder_produces_sanitized_500(resources):
    resources.indexes.model.encode = lambda *args, **kwargs: np.full((1, 3), np.nan, dtype=np.float32)
    with TestClient(create_app(resources.settings, lambda _: resources), raise_server_exceptions=False) as client:
        response = client.get('/api/v1/search', params={'q': 'quantum', 'mode': 'semantic'})
    assert response.status_code == 500
    assert response.json()['error']['message'] == 'Unexpected search service error'


def test_concurrent_read_only_requests(client, resources):
    tfidf_before = resources.indexes.tfidf.copy()
    counts_before = resources.indexes.counts.copy()
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.get('/api/v1/search', params={'q': 'quantum', 'mode': 'hybrid'}), range(4)))
    assert all(r.status_code == 200 for r in responses)
    assert all(r.json()['results'] == responses[0].json()['results'] for r in responses)
    assert (resources.indexes.tfidf != tfidf_before).nnz == 0
    assert (resources.indexes.counts != counts_before).nnz == 0
