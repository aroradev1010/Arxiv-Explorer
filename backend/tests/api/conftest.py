import json
import sqlite3
import threading
from types import SimpleNamespace
import faiss
import numpy as np
import pytest
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from fastapi.testclient import TestClient

from backend.api.config import Settings
from backend.api.main import create_app
from backend.api.prepare_metadata import folded, initialize_cache
from backend.api.repository import PaperRepository
from backend.pipeline.text import LexicalTokenizer


class FixtureEncoder:
    def __init__(self):
        self.calls = 0

    def encode(self, text, **kwargs):
        self.calls += 1
        return np.array([[1, 0, 0]], dtype=np.float32)


def make_resources(tmp_path):
    settings = Settings(app_env='test', dataset_dir=tmp_path, metadata_db=tmp_path / 'metadata.sqlite',
                        evaluation_enabled=False,
                        rrf_candidate_depth=12, max_ranking_window=100, compute_threads=1)
    ids = [f'2001.{i:05d}' for i in range(15)] + ['hep-th/9901001']
    papers = []
    for i, paper_id in enumerate(ids):
        title = 'quantum ' * (30 - i) if i < 14 else ('noise ' * 100 if i == 14 else 'quantum')
        abstract = 'field' if i < 14 else 'noise ' * 100
        categories = ['cs.AI'] if i != 15 else ['math.AG', 'cs.LG']
        published = None if i == 14 else ('2021-01-01' if i == 15 else '2000-01-01')
        papers.append(dict(id=paper_id, title=title, abstract=abstract,
                           authors='Johann SMITH' if i == 15 else f'Author {i}', categories=categories,
                           primary_category=categories[0], published_at=published, updated_at='2025-01-01',
                           doi=None, journal_ref=None, comments=None, license=None,
                           arxiv_url=f'https://arxiv.org/abs/{paper_id}', pdf_url=f'https://arxiv.org/pdf/{paper_id}',
                           stratum='math|2020-2024' if i == 15 else 'cs|2000-2004'))
    corpus_path = tmp_path / 'papers.sqlite'
    db = sqlite3.connect(corpus_path)
    db.execute('CREATE TABLE papers(doc_index INTEGER PRIMARY KEY,id TEXT UNIQUE,title TEXT,abstract TEXT,primary_category TEXT,published_at TEXT,metadata_json TEXT)')
    db.executemany('INSERT INTO papers VALUES (?,?,?,?,?,?,?)', [(i, p['id'], p['title'], p['abstract'], p['primary_category'], p['published_at'], json.dumps(p)) for i, p in enumerate(papers)])
    db.commit()
    db.close()
    db = sqlite3.connect(settings.metadata_db)
    initialize_cache(db)
    for p in papers:
        db.execute('INSERT INTO lookup VALUES (?,?,?,?,?,?)', (p['id'], int(p['published_at'][:4]) if p['published_at'] else None, p['stratum'].split('|')[0], json.dumps([p['authors']]), 'authors_parsed', folded(p['authors'])))
        db.executemany('INSERT INTO paper_categories VALUES (?,?)', [(p['id'], c) for c in p['categories']])
    db.execute('INSERT INTO provenance VALUES (?,?)', ('document_count', '16'))
    db.commit()
    db.close()
    vectorizer = CountVectorizer(tokenizer=LexicalTokenizer(), token_pattern=None, lowercase=False, dtype=np.int32)
    counts = vectorizer.fit_transform(p['title'] + ' ' + p['abstract'] for p in papers)
    transformer = TfidfTransformer(sublinear_tf=True)
    tfidf = transformer.fit_transform(counts).astype(np.float32).tocsr()
    postings = counts.tocsc()
    lengths = np.asarray(counts.sum(axis=1)).ravel().astype(np.float32)
    df = np.diff(postings.indptr)
    vectors = np.array([[np.cos(i * .03), np.sin(i * .03), 0] for i in range(15)] + [[.3, np.sqrt(.91), 0]], dtype=np.float32)
    index = faiss.IndexFlatIP(3)
    index.add(vectors)
    manifest = {'schema_version': 1, 'tfidf': {}, 'bm25': {}, 'packages': {}, 'resources': {},
                'semantic': {'model_name': 'deterministic test fixture', 'max_seq_length': 256,
                             'truncation': 'fixture', 'encoder_backend': 'fixture', 'batch_size': 1, 'threads': 1}}
    indexes = SimpleNamespace(ids=ids, vectorizer=vectorizer, transformer=transformer, tfidf=tfidf,
                              counts=postings, model=FixtureEncoder(), semantic=index, manifest=manifest,
                              stats={'doc_lengths': lengths, 'avgdl': lengths.mean(), 'k1': 1.5, 'b': .75,
                                     'idf': np.log1p((16 - df + .5) / (df + .5))})
    return SimpleNamespace(settings=settings, indexes=indexes, vectors=vectors,
                           repository=PaperRepository(corpus_path, settings.metadata_db, ids),
                           dataset={'artifacts': {'papers.jsonl': 'fixture'}}, model_revision='fixture',
                           index_version='fixture', model_lock=threading.Lock(), startup_ms=0,
                           close=lambda: None)


@pytest.fixture
def resources(tmp_path):
    return make_resources(tmp_path)


@pytest.fixture
def client(resources):
    application = create_app(resources.settings, resource_loader=lambda _: resources)
    with TestClient(application) as client:
        yield client
