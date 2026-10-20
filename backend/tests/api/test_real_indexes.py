"""One lifespan loads the real corpus once for all required real-index smoke checks."""
import math
from fastapi.testclient import TestClient
import pytest
from backend.api.config import Settings
from backend.api.main import create_app


@pytest.mark.real_indexes
def test_actual_corpus_end_to_end():
    with TestClient(create_app(Settings())) as client:
        assert client.get('/api/v1/health/ready').status_code == 200
        engine = client.app.state.service
        resources = engine.resources
        assert len(resources.indexes.ids) == 50000
        for query in ['quantum field theory', 'galaxy formation', 'graph neural networks', 'machine learning for climate prediction']:
            for mode in ['tfidf', 'bm25', 'semantic', 'hybrid']:
                response = client.get('/api/v1/search', params={'q': query, 'mode': mode})
                assert response.status_code == 200, response.text
                results = response.json()['results']
                assert len(results) == 10
                assert len({hit['paper']['id'] for hit in results}) == 10
                assert all(math.isfinite(hit['score']) for hit in results)
                assert all(results[i]['score'] >= results[i + 1]['score'] for i in range(9))
                expected = resources.repository.fetch_many([hit['paper']['id'] for hit in results])
                for hit in results:
                    assert hit['paper'] == expected[hit['paper']['id']].model_dump(mode='json')
                    assert hit['paper']['id'] in resources.repository.positions
                if mode in ['tfidf', 'bm25', 'semantic']:
                    cli = resources.indexes.search(query, mode, 10)
                    assert [h['score'] for h in results] == pytest.approx([h['score'] for h in cli], abs=3e-6)
                    if mode != 'semantic':
                        assert [h['paper']['id'] for h in results] == [h['paper_id'] for h in cli]
        params = {'q': 'graph neural networks', 'mode': 'hybrid', 'category': 'cs.LG', 'year_from': 2020, 'year_to': 2025}
        filtered = client.get('/api/v1/search', params=params)
        assert filtered.status_code == 200
        assert filtered.json()['results']
        for hit in filtered.json()['results']:
            assert 'cs.LG' in hit['paper']['categories']
            assert 2020 <= int(hit['paper']['published_at'][:4]) <= 2025
        compared = client.post('/api/v1/compare', json={'query': 'graph neural networks', 'filters': {'category': 'cs.LG', 'year_from': 2020}})
        assert compared.status_code == 200, compared.text
        assert set(compared.json()['methods']) == {'tfidf', 'bm25', 'semantic', 'hybrid'}
        paper_id = filtered.json()['results'][0]['paper']['id']
        assert client.get('/api/v1/papers', params={'arxiv_id': paper_id}).status_code == 200
        recommendations = client.get('/api/v1/papers/similar', params={'arxiv_id': paper_id})
        assert recommendations.status_code == 200
        assert all(h['paper']['id'] != paper_id for h in recommendations.json()['results'])
        stats = client.get('/api/v1/system/stats').json()
        assert stats['indexed_paper_count'] == 50000 and stats['embedding_dimension'] == 384
        assert stats['vocabulary_size'] == 129591
