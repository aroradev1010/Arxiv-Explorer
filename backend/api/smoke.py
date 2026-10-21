"""Real HTTP smoke run with a temporary local listener and clean ASGI shutdown."""
import json
import socket
import threading
from time import perf_counter, sleep
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uvicorn

from .config import ROOT, Settings
from .main import create_app
from .prepare_metadata import folded


def main():
    app = create_app(Settings())
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port,
                                         access_log=False, log_level='info'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, name='real-api-smoke')
    thread.start()
    report = {'status': 'running', 'base_url': f'http://127.0.0.1:{port}', 'searches': []}

    def request(path, params=None, payload=None):
        url = report['base_url'] + path + ('?' + urlencode(params) if params else '')
        req = Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={'Content-Type': 'application/json'} if payload is not None else {})
        started = perf_counter()
        with urlopen(req, timeout=30) as response:
            body = json.load(response)
            assert response.status == 200
        return body, (perf_counter() - started) * 1000

    try:
        started = perf_counter()
        while not server.started:
            if not thread.is_alive() or perf_counter() - started > 120:
                raise RuntimeError('API server did not start')
            sleep(.05)
        assert request('/api/v1/health/ready')[0]['status'] == 'ready'
        for query in ['quantum field theory', 'galaxy formation', 'graph neural networks', 'machine learning for climate prediction']:
            for mode in ['tfidf', 'bm25', 'semantic', 'hybrid']:
                body, elapsed = request('/api/v1/search', {'q': query, 'mode': mode, 'limit': 5})
                assert len(body['results']) == 5
                assert len({h['paper']['id'] for h in body['results']}) == 5
                report['searches'].append({'query': query, 'mode': mode, 'http_elapsed_ms': elapsed,
                                           'timing_ms': body['timing_ms'], 'results': body['results']})
        filtered, _ = request('/api/v1/search', {'q': 'graph neural networks', 'mode': 'hybrid', 'category': 'cs.LG', 'year_from': 2020, 'year_to': 2025, 'limit': 5})
        assert filtered['results']
        assert all('cs.LG' in h['paper']['categories'] and 2020 <= int(h['paper']['published_at'][:4]) <= 2025 for h in filtered['results'])
        paper = filtered['results'][0]['paper']
        author = paper['authors'][0] if paper['authors'] else paper['authors_text'].split()[0]
        author_filtered, _ = request('/api/v1/search', {'q': 'graph neural networks', 'mode': 'semantic', 'category': 'cs.LG', 'author': author, 'limit': 5})
        assert author_filtered['results']
        assert all(folded(author) in folded(h['paper']['authors_text'] + ' ' + ' '.join(h['paper']['authors'])) for h in author_filtered['results'])
        report['filtered_search'] = filtered
        report['author_search'] = {'author': author, 'response': author_filtered}
        detail, _ = request('/api/v1/papers', {'arxiv_id': paper['id']})
        assert detail == paper
        similar, _ = request('/api/v1/papers/similar', {'arxiv_id': paper['id'], 'limit': 5})
        assert all(h['paper']['id'] != paper['id'] for h in similar['results'])
        report['similar'] = similar
        compared, _ = request('/api/v1/compare', payload={'query': 'graph neural networks', 'filters': {'category': 'cs.LG', 'year_from': 2020, 'year_to': 2025}})
        assert len(compared['methods']) == 4
        report['comparison'] = compared
        report['stats'] = request('/api/v1/system/stats')[0]
        report['categories'] = request('/api/v1/categories')[0]
        assert report['stats']['indexed_paper_count'] == 50000
        with urlopen(report['base_url'] + '/docs', timeout=10) as response:
            assert response.status == 200 and b'Swagger' in response.read()
        assert request('/api/v1/health/live')[0]['status'] == 'live'
        report['status'] = 'passed'
    finally:
        server.should_exit = True
        thread.join(timeout=30)
        listener.close()
        if thread.is_alive():
            raise RuntimeError('API server did not shut down cleanly')
        report['clean_shutdown'] = True
    output = ROOT / 'var/api-smoke.json'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'real_search_requests': len(report['searches']),
                      'clean_shutdown': report['clean_shutdown'], 'report': 'var/api-smoke.json'}), flush=True)


if __name__ == '__main__':
    main()
