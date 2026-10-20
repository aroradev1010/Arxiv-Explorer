import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.api.config import Settings
from backend.api.errors import AssetError
from backend.api.main import create_app
from backend.api.prepare_metadata import folded, prepare
from backend.api.resources import load_resources
from backend.api.schemas import Filters


def test_missing_assets_have_clear_readiness_error(tmp_path):
    settings = Settings(dataset_dir=tmp_path / 'missing')
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/v1/health/live').status_code == 200
        response = client.get('/api/v1/health/ready')
        assert response.status_code == 503
        assert response.json()['reason'] == 'Missing required search asset: manifest.json'
        assert str(tmp_path) not in response.text


def test_corrupt_manifest_fails_explicitly(tmp_path):
    settings = Settings(dataset_dir=tmp_path / 'dataset', index_dir=tmp_path / 'indexes',
                        model_dir=tmp_path / 'model', metadata_db=tmp_path / 'app.sqlite')
    files = {settings.dataset_dir: ['manifest.json', 'doc_ids.json', 'papers.sqlite'],
             settings.index_dir: ['manifest.json', 'doc_ids.json', 'count_vectorizer.joblib', 'tfidf_transformer.joblib',
                                  'tfidf.npz', 'bm25_counts.npz', 'bm25_stats.npz', 'embeddings.npy', 'semantic.faiss', 'validation.json'],
             settings.model_dir: ['model.safetensors', 'config.json', 'modules.json', 'snapshot.json']}
    for directory, names in files.items():
        directory.mkdir()
        for name in names:
            (directory / name).write_text('')
    settings.metadata_db.touch()
    (settings.dataset_dir / 'manifest.json').write_text(json.dumps({'schema_version': 1}))
    (settings.index_dir / 'manifest.json').write_text('{bad json}')
    with pytest.raises(AssetError, match='Invalid index manifest'):
        load_resources(settings)


def test_unicode_author_matching_and_original_dates(resources):
    connection = sqlite3.connect(resources.settings.metadata_db)
    connection.execute('UPDATE lookup SET author_search=? WHERE id=?', (folded('JöRG STRAẞE'), resources.indexes.ids[0]))
    connection.commit()
    connection.close()
    assert resources.repository.eligible(Filters(author='JÖRG STRASSE')).tolist() == [0]
    assert resources.repository.eligible(Filters(category='cs.AI', year_from=2020)).tolist() == []


def test_request_capacity_is_bounded(resources):
    settings = resources.settings.model_copy(update={'worker_threads': 1, 'queue_timeout_seconds': .02})
    app = create_app(settings, lambda _: resources)
    with TestClient(app) as client:
        service = app.state.service
        original = service.search
        def slow_search(query):
            time.sleep(.2)
            return original(query)
        service.search = slow_search
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(client.get, '/api/v1/search', params={'q': 'quantum'})
            time.sleep(.05)
            busy = client.get('/api/v1/search', params={'q': 'quantum'})
            assert busy.status_code == 503 and busy.json()['error']['code'] == 'search_busy'
            assert client.get('/api/v1/health/live').status_code == 200
            assert first.result().status_code == 200


def test_storage_failure_is_explicit_503(client, resources):
    resources.repository.database = resources.settings.dataset_dir / 'unavailable.sqlite'
    assert client.get('/api/v1/health/ready').status_code == 503
    result = client.get('/api/v1/search', params={'q': 'quantum'})
    assert result.status_code == 503 and result.json()['error']['code'] == 'metadata_unavailable'


def test_metadata_builder_cannot_write_protected_assets(tmp_path):
    settings = Settings(metadata_db=Settings().dataset_dir / 'new-app-cache.sqlite')
    with pytest.raises(ValueError, match='outside protected'):
        prepare(settings, tmp_path / 'irrelevant.jsonl')


def test_configuration_validation_and_path_anchor():
    from backend.api.config import ROOT
    assert Settings(dataset_dir='data/processed').dataset_dir == ROOT / 'data/processed'
    assert Settings(cors_origins='http://localhost:3000').cors_origins == ['http://localhost:3000']
    with pytest.raises(ValueError):
        Settings(cors_origins='*')
    with pytest.raises(ValueError):
        Settings(rrf_candidate_depth=2000, max_ranking_window=1000)
