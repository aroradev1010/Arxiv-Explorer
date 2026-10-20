import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

from backend.pipeline.dataset import allocate, normalize, prepare, subject
from backend.pipeline.search import bm25_scores, ranked
from backend.pipeline.text import LexicalTokenizer, clean
from backend.pipeline.indexes import build
from backend.pipeline.verify import verify


def record(i=1, category='cs.AI', year=2020):
    return {'id': f'2001.{i:05d}', 'title': f'Neural network learning {i}',
            'abstract': 'Machine learning optimization and quantum field theory with galaxy formation.',
            'authors': 'A. Researcher', 'categories': category,
            'versions': [{'created': f'Wed, 1 Jan {year} 12:00:00 GMT'}], 'update_date': '2021-01-02'}


def test_normalization_and_legacy():
    raw = record()
    raw['id'] = 'hep-th/9901001'
    raw['versions'].insert(0, {'created': 'broken'})
    paper = normalize(raw)
    assert paper['published_at'] == '2020-01-01'
    assert paper['updated_at'] == '2021-01-02'
    assert paper['pdf_url'].endswith('hep-th/9901001')
    assert paper['title'] == raw['title']
    raw['abstract'] = None
    with pytest.raises(ValueError, match='missing_abstract'):
        normalize(raw)
    with pytest.raises(ValueError, match='not_object'):
        normalize([])


def test_invalid_dates_and_ids():
    raw = record()
    raw['versions'] = [{'created': 'not a date'}]
    with pytest.raises(ValueError, match='invalid_submission_date'):
        normalize(raw)
    raw = record()
    raw['id'] = '../../unsafe'
    with pytest.raises(ValueError, match='invalid_id'):
        normalize(raw)


def test_proportional_quotas():
    counts = {'a': 9990, 'b': 10, 'c': 1}
    quotas = allocate(counts, 1000)
    assert sum(quotas.values()) == 1000
    assert quotas['c'] == 0
    assert quotas['b'] == 1
    assert allocate({'a': 2, 'b': 2}, 4) == {'a': 2, 'b': 2}
    with pytest.raises(ValueError):
        allocate(counts, 10002)


def test_historical_subjects():
    assert subject('cmp-lg') == 'cs'
    for category in ['alg-geom', 'dg-ga', 'funct-an', 'q-alg', 'math.AG']:
        assert subject(category) == 'math'
    assert subject('quant-ph') == 'physics'


def test_streaming_sample_reproducible(tmp_path):
    records = [record(i, 'cs.AI' if i % 3 else 'quant-ph', 2000 if i % 2 else 2020) for i in range(60)]
    source = tmp_path / 'raw.jsonl'
    source.write_text('\n'.join(json.dumps(p) for p in records + [records[0], {'id': 'bad'}]) + '\n{bad json}\n[]\n', encoding='utf-8')
    first = prepare(source, tmp_path / 'a', 30, 42)
    second = prepare(source, tmp_path / 'b', 30, 42)
    assert first['artifacts']['papers.jsonl'] == second['artifacts']['papers.jsonl']
    assert first['unique_valid'] == 60
    assert first['rejected']['duplicate_id'] == 1
    ids = json.loads((tmp_path / 'a/doc_ids.json').read_text())
    assert len(ids) == len(set(ids)) == 30
    assert ids == sorted(ids)
    assert sum(s['selected_count'] for s in first['strata'].values()) == 30
    # ID-hash priorities make unique-record sampling independent of input order.
    source.write_text('\n'.join(json.dumps(p) for p in reversed(records)), encoding='utf-8')
    third = prepare(source, tmp_path / 'c', 30, 42)
    assert third['artifacts']['papers.jsonl'] == first['artifacts']['papers.jsonl']
    with pytest.raises(FileExistsError):
        prepare(source, tmp_path / 'a', 30, 42)


def test_preprocessing():
    tokenizer = LexicalTokenizer(stemming=False, stopwords=False)
    tokens = tokenizer(r'BERT CNN GPT-4 C++ L2 $x^2$ \alpha \beta')
    assert tokens == ['bert', 'cnn', 'gpt-4', 'c++', 'l2', 'x^2', 'alpha', 'beta']
    assert clean(r'\textbf{Neural}  networks') == 'Neural networks'
    assert LexicalTokenizer()('The networks are learning') == ['network', 'learn']
    assert tokenizer('') == []
    assert tokenizer('ＦＡＩＲ') == ['fair']


def test_bm25_manual_scores():
    counts = sparse.csc_matrix(np.array([[2, 0], [1, 1], [0, 2]], dtype=np.int32))
    lengths = np.array([2, 2, 2], dtype=np.float32)
    idf = np.array([math.log(1 + 1.5 / 2.5)] * 2)
    scores = bm25_scores(counts, lengths, idf, 2, 1.5, .75, np.array([0, 0]))
    assert scores[0] == pytest.approx(idf[0] * 2 * 2.5 / 3.5)
    assert scores[1] == pytest.approx(idf[0])
    assert scores[2] == 0
    assert ranked(scores, ['a', 'b', 'c'], 10)[0]['paper_id'] == 'a'
    assert ranked(np.array([1., 1., 0.]), ['a', 'b', 'c'], 10)[0]['paper_id'] == 'a'
    assert ranked(np.zeros(3), ['a', 'b', 'c'], 10) == []
    with pytest.raises(ValueError):
        ranked(scores, ['a', 'b', 'c'], 0)


def test_full_pipeline_and_corruption(tmp_path):
    model = Path('data/models/all-MiniLM-L6-v2').resolve()
    if not (model / 'model.safetensors').exists():
        pytest.skip('Official model not downloaded; use download_model first')
    source = tmp_path / 'raw.jsonl'
    records = [record(i) for i in range(12)]
    records[0]['title'] = 'Galaxy formation in astronomy'
    source.write_text('\n'.join(json.dumps(p) for p in records), encoding='utf-8')
    corpus, indexes = tmp_path / 'corpus', tmp_path / 'indexes'
    prepare(source, corpus, 12, 42)
    build(corpus, indexes, str(model), batch_size=4, threads=2)
    assert verify(corpus, indexes, 12)['status'] == 'passed'
    reused = tmp_path / 'reused-indexes'
    assert build(corpus, reused, str(model), batch_size=4, threads=2, reuse_from=indexes, cpu_optimized=True)['reused_embedding_count'] == 12
    assert verify(corpus, reused, 12)['status'] == 'passed'
    from backend.pipeline.search import SearchIndexes
    search = SearchIndexes(indexes)
    assert search.search('unfindablewordxyz', 'tfidf') == []
    assert search.search('', 'bm25') == []
    assert search.search('Galaxy astronomy', 'tfidf')[0]['paper_id'] == records[0]['id']
    assert search.search('Galaxy astronomy', 'bm25')[0]['paper_id'] == records[0]['id']
    ids = json.loads((indexes / 'doc_ids.json').read_text())
    (indexes / 'doc_ids.json').write_text(json.dumps(ids[::-1]))
    with pytest.raises(ValueError, match='Mapping checksum mismatch'):
        verify(corpus, indexes, 12)


def test_cpu_encoder_parity():
    model = Path('data/models/all-MiniLM-L6-v2').resolve()
    if not (model / 'model.safetensors').exists():
        pytest.skip('Official model not downloaded')
    from backend.pipeline.cpu_model import load_model
    texts = ['quantum physics', 'A galaxy forms from gas and dust. ' * 150]
    baseline = load_model(str(model), 2)
    expected = baseline.encode(texts, normalize_embeddings=True)
    del baseline
    optimized = load_model(str(model), 2, optimized=True)
    actual = optimized.encode(texts, normalize_embeddings=True)
    assert np.allclose(expected, actual, atol=2e-5)
