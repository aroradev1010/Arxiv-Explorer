"""Read-only startup integration with the independently verified pipeline artifacts."""
import importlib.metadata
from pathlib import Path
import threading
from time import perf_counter

import faiss
import numpy as np

from backend.pipeline.common import read_json, sha256
from backend.pipeline.search import SearchIndexes
from .config import Settings
from .errors import AssetError
from .repository import PaperRepository


class Resources:
    def __init__(self, settings: Settings, indexes: SearchIndexes, vectors: np.ndarray,
                 repository: PaperRepository, dataset: dict, model_revision: str | None):
        self.settings, self.indexes, self.vectors = settings, indexes, vectors
        self.repository, self.dataset, self.model_revision = repository, dataset, model_revision
        self.model_lock = threading.Lock()
        self.index_version = sha256(settings.index_dir / 'manifest.json')
        self.startup_ms = 0.0

    def close(self) -> None:
        self.indexes.model = None
        if hasattr(self.vectors, '_mmap') and self.vectors._mmap is not None:
            self.vectors._mmap.close()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssetError(message)


def load_resources(settings: Settings) -> Resources:
    started = perf_counter()
    required = [(settings.dataset_dir, ['manifest.json', 'doc_ids.json', 'papers.sqlite']),
                (settings.index_dir, ['manifest.json', 'doc_ids.json', 'count_vectorizer.joblib',
                                     'tfidf_transformer.joblib', 'tfidf.npz', 'bm25_counts.npz',
                                     'bm25_stats.npz', 'embeddings.npy', 'semantic.faiss', 'validation.json']),
                (settings.model_dir, ['model.safetensors', 'config.json', 'modules.json', 'snapshot.json'])]
    for directory, names in required:
        for name in names:
            check((directory / name).is_file(), f'Missing required search asset: {name}')
    check(settings.metadata_db.is_file(), 'Application metadata cache unavailable; run python -m backend.api.prepare_metadata')
    vectors = None
    try:
        try:
            dataset = read_json(settings.dataset_dir / 'manifest.json')
        except (ValueError, UnicodeError):
            raise AssetError('Invalid dataset manifest')
        try:
            manifest = read_json(settings.index_dir / 'manifest.json')
        except (ValueError, UnicodeError):
            raise AssetError('Invalid index manifest')
        check(manifest['schema_version'] == dataset['schema_version'] == 1, 'Unsupported manifest schema version')
        mapping_hash = sha256(settings.index_dir / 'doc_ids.json')
        check(mapping_hash == manifest['id_mapping_sha256'] == dataset['artifacts']['doc_ids.json'] == sha256(settings.dataset_dir / 'doc_ids.json'), 'Ordered document mapping fingerprints differ')
        check(manifest['dataset_manifest_sha256'] == sha256(settings.dataset_dir / 'manifest.json'), 'Index belongs to another dataset manifest')
        check(manifest['dataset_sha256'] == dataset['artifacts']['papers.jsonl'], 'Index corpus version differs')
        report = read_json(settings.index_dir / 'validation.json')
        check(report['status'] == 'passed' and report['id_mapping_sha256'] == mapping_hash, 'Verified index readiness report is incompatible')
        indexes = SearchIndexes(settings.index_dir)
        count, vocabulary = len(indexes.ids), len(indexes.vectorizer.vocabulary_)
        check(indexes.ids == sorted(set(indexes.ids)), 'Paper IDs must be unique and sorted')
        check(count == manifest['document_count'] == dataset['sample_size'] == report['document_count'], 'Document counts differ')
        check(indexes.tfidf.shape == indexes.counts.shape == (count, vocabulary), 'TF-IDF/BM25 matrix shapes differ from the mapping')
        check(indexes.tfidf.format == 'csr' and indexes.counts.format == 'csc', 'Sparse index formats are incompatible')
        check(len(indexes.transformer.idf_) == vocabulary, 'TF-IDF vocabulary/IDF mismatch')
        check(indexes.vectorizer.tokenizer.configuration() == manifest['lexical_configuration'], 'Persisted lexical preprocessing differs from its manifest')
        check(indexes.transformer.norm == manifest['tfidf']['norm'] == 'l2' and indexes.transformer.sublinear_tf == manifest['tfidf']['sublinear_tf'], 'TF-IDF configuration mismatch')
        stats_file = indexes.stats
        indexes.stats = {key: stats_file[key] for key in stats_file.files}
        stats_file.close()
        check(indexes.stats['doc_lengths'].shape == (count,) and indexes.stats['idf'].shape == (vocabulary,), 'BM25 statistics dimensions differ')
        check(float(indexes.stats['k1']) == manifest['bm25']['k1'] and float(indexes.stats['b']) == manifest['bm25']['b'], 'BM25 parameters differ from the index manifest')
        vectors = np.load(settings.index_dir / 'embeddings.npy', mmap_mode='r')
        dimension = manifest['semantic']['dimension']
        check(vectors.shape == (count, dimension) and vectors.dtype == np.float32, 'Embedding dimensions/dtype differ')
        check(indexes.semantic.ntotal == count and indexes.semantic.d == dimension and indexes.semantic.metric_type == faiss.METRIC_INNER_PRODUCT, 'FAISS count/dimension/metric mismatch')
        probe = np.array(sorted(set([0, count // 2, count - 1])))
        check(np.allclose(np.linalg.norm(vectors[probe], axis=1), 1, atol=1e-5), 'Stored embedding probes are not unit normalized')
        check(all(np.array_equal(indexes.semantic.reconstruct(int(i)), vectors[i]) for i in probe), 'FAISS/embedding probes are misaligned')
        for name, fingerprint in manifest['semantic']['model_files_sha256'].items():
            model_file = (settings.model_dir / name).resolve()
            check(model_file.is_relative_to(settings.model_dir), 'Unsafe model artifact path in manifest')
            check(model_file.is_file(), f'Missing local model artifact: {model_file.name}')
            check(sha256(model_file) == fingerprint, f'Local model revision mismatch: {model_file.name}')
        # Library changes affecting serialized/tokenized representations are not silently accepted.
        for name in ['numpy', 'scipy', 'scikit-learn', 'nltk', 'sentence-transformers', 'transformers', 'torch', 'faiss-cpu']:
            check(importlib.metadata.version(name) == manifest['packages'][name], f'Index package version mismatch: {name}')
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(settings.compute_threads)
        faiss.omp_set_num_threads(settings.compute_threads)
        indexes.model = SentenceTransformer(str(settings.model_dir), device='cpu', local_files_only=True)
        check(indexes.model.get_embedding_dimension() == dimension, 'Query model embedding dimension differs')
        check(indexes.model.max_seq_length == manifest['semantic']['max_seq_length'], 'Query model truncation differs')
        repository = PaperRepository(settings.dataset_dir / 'papers.sqlite', settings.metadata_db, indexes.ids)
        check(repository.provenance['dataset_manifest_sha256'] == manifest['dataset_manifest_sha256'] and repository.provenance['document_count'] == count, 'Application metadata cache belongs to another corpus')
        with repository.connection() as db:
            corpus_ids = list(db.execute('SELECT id,doc_index FROM papers ORDER BY id'))
            check([row[0] for row in corpus_ids] == indexes.ids and all(row[1] == i for i, row in enumerate(corpus_ids)), 'SQLite IDs/positions differ from the authoritative index mapping')
            check([row[0] for row in db.execute('SELECT id FROM application.lookup ORDER BY id')] == indexes.ids, 'Application metadata IDs differ from index mapping')
        revision = read_json(settings.model_dir / 'snapshot.json')['revision']
        resources = Resources(settings, indexes, vectors, repository, dataset, revision)
        resources.startup_ms = (perf_counter() - started) * 1000
        # Loaded sparse storage is protected against accidental request-side writes.
        for matrix in (indexes.tfidf, indexes.counts):
            for array in (matrix.data, matrix.indices, matrix.indptr):
                array.flags.writeable = False
        for array in indexes.stats.values():
            array.flags.writeable = False
        return resources
    except AssetError:
        if vectors is not None:
            vectors._mmap.close()
        raise
    except Exception as exc:
        if vectors is not None:
            vectors._mmap.close()
        raise AssetError('Search assets are unreadable or have incompatible manifest/schema data') from exc
