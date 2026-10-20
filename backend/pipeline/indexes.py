"""Build sparse lexical indexes and batched normalized Sentence Transformer vectors."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

import faiss
import joblib
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer

from .common import Resources, progress, read_json, sha256, write_json
from .text import LexicalTokenizer, lexical_text, semantic_text


def load_corpus(corpus: Path) -> tuple[list[dict], list[str], dict]:
    manifest = read_json(corpus / 'manifest.json')
    for name, digest in manifest['artifacts'].items():
        if sha256(corpus / name) != digest:
            raise ValueError(f'Corpus checksum mismatch: {name}')
    ids = read_json(corpus / 'doc_ids.json')
    with (corpus / 'papers.jsonl').open(encoding='utf-8') as stream:
        papers = [json.loads(line) for line in stream]
    if [p['id'] for p in papers] != ids or ids != sorted(set(ids)) or len(ids) != manifest['sample_size']:
        raise ValueError('Invalid corpus ID mapping')
    return papers, ids, manifest


def build(corpus: Path, output: Path, model_path: str, batch_size: int = 32,
          threads: int = 4, k1: float = 1.5, b: float = .75,
          stemming: bool = True, stopwords: bool = True, reuse_from: Path | None = None,
          cpu_optimized: bool = False) -> dict:
    if batch_size < 1 or threads < 1 or k1 <= 0 or not 0 <= b <= 1:
        raise ValueError('Invalid build parameters')
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Choose an empty --output directory')
    output.mkdir(parents=True, exist_ok=True)
    resources = Resources()
    papers, ids, dataset = load_corpus(corpus)
    n = len(ids)
    shutil.copyfile(corpus / 'doc_ids.json', output / 'doc_ids.json')
    tokenizer = LexicalTokenizer(stemming=stemming, stopwords=stopwords)
    counts_vectorizer = CountVectorizer(tokenizer=tokenizer, token_pattern=None,
                                        lowercase=False, dtype=np.int32)
    counts = counts_vectorizer.fit_transform(lexical_text(p) for p in papers).tocsr()
    lengths = np.asarray(counts.sum(axis=1)).ravel().astype(np.float32)
    if np.any(lengths == 0):
        raise ValueError('Empty document after lexical preprocessing')
    transformer = TfidfTransformer(norm='l2', smooth_idf=True, sublinear_tf=True)
    tfidf = transformer.fit_transform(counts).astype(np.float32).tocsr()
    joblib.dump(counts_vectorizer, output / 'count_vectorizer.joblib')
    joblib.dump(transformer, output / 'tfidf_transformer.joblib')
    sparse.save_npz(output / 'tfidf.npz', tfidf)
    postings = counts.tocsc()
    df = np.diff(postings.indptr)
    idf = np.log1p((n - df + .5) / (df + .5)).astype(np.float32)
    sparse.save_npz(output / 'bm25_counts.npz', postings)
    np.savez(output / 'bm25_stats.npz', doc_lengths=lengths, idf=idf,
             avgdl=lengths.mean(dtype=np.float64), k1=k1, b=b)
    progress('lexical_built', documents=n, vocabulary=len(counts_vectorizer.vocabulary_), nnz=counts.nnz, **resources.report())
    del counts, postings, tfidf
    import torch
    from .cpu_model import load_model
    torch.set_num_threads(threads)
    faiss.omp_set_num_threads(threads)
    model = load_model(model_path, threads, cpu_optimized)
    dimension = model.get_embedding_dimension()
    if dimension != 384:
        raise ValueError(f'Expected all-MiniLM-L6-v2 dimension 384, got {dimension}')
    vectors = np.lib.format.open_memmap(output / 'embeddings.npy', mode='w+', dtype=np.float32, shape=(n, dimension))
    semantic = faiss.IndexFlatIP(dimension)
    model_files = {str(path.relative_to(model_path)).replace('\\', '/'): sha256(path)
                   for path in sorted(Path(model_path).rglob('*')) if path.is_file() and '.cache' not in path.parts}
    reuse_positions, reuse_vectors = {}, None
    reuse_backend = None
    if reuse_from is not None:
        previous = read_json(reuse_from / ('manifest.json' if (reuse_from / 'manifest.json').exists() else 'checkpoint.json'))
        reuse_backend = previous['semantic'].get('encoder_backend', 'validated against PyTorch float32')
        if previous['semantic']['model_files_sha256'] != model_files:
            raise ValueError('Reuse model fingerprint mismatch')
        old_papers, old_ids, _ = load_corpus(Path(previous['corpus_path']))
        for name in ('doc_ids.json', 'embeddings.npy'):
            if sha256(reuse_from / name) != previous['artifacts'][name]:
                raise ValueError('Reuse artifact checksum mismatch')
        if read_json(reuse_from / 'doc_ids.json') != old_ids:
            raise ValueError('Reuse ID mapping mismatch')
        completed = previous.get('completed', len(old_ids))
        reuse_vectors = np.load(reuse_from / 'embeddings.npy', mmap_mode='r')
        if reuse_vectors.shape != (len(old_ids), dimension):
            raise ValueError('Reuse embedding shape mismatch')
        old_by_id = {p['id']: (i, semantic_text(p)) for i, p in enumerate(old_papers[:completed])}
        for i, paper in enumerate(papers):
            candidate = old_by_id.get(paper['id'])
            if candidate is not None and candidate[1] == semantic_text(paper):
                reuse_positions[i] = candidate[0]
        del old_by_id, old_papers
        progress('reuse_ready', reusable_documents=len(reuse_positions))
    for start in range(0, n, batch_size):
        end = min(n, start + batch_size)
        missing = [i for i in range(start, end) if i not in reuse_positions]
        encoded = np.empty((end - start, dimension), dtype=np.float32)
        if missing:
            fresh = model.encode([semantic_text(papers[i]) for i in missing], batch_size=batch_size,
                                 normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
            encoded[np.array(missing) - start] = fresh
        for i in range(start, end):
            if i in reuse_positions:
                encoded[i - start] = reuse_vectors[reuse_positions[i]]
        if not np.isfinite(encoded).all() or not np.allclose(np.linalg.norm(encoded, axis=1), 1, atol=1e-5):
            raise ValueError('Invalid semantic vectors')
        vectors[start:start + len(encoded)] = encoded
        semantic.add(encoded)
        if start // batch_size % 10 == 0 or start + batch_size >= n:
            progress('embedding', completed=min(start + batch_size, n), total=n, **resources.report())
    vectors.flush()
    del vectors
    faiss.write_index(semantic, str(output / 'semantic.faiss'))
    artifact_names = ['doc_ids.json', 'count_vectorizer.joblib', 'tfidf_transformer.joblib',
                      'tfidf.npz', 'bm25_counts.npz', 'bm25_stats.npz', 'embeddings.npy', 'semantic.faiss']
    manifest = {'schema_version': 1, 'document_count': n, 'dataset_sha256': dataset['artifacts']['papers.jsonl'],
                'corpus_path': str(corpus.resolve()), 'reused_embedding_count': len(reuse_positions),
                'dataset_manifest_sha256': sha256(corpus / 'manifest.json'),
                'id_mapping_sha256': sha256(output / 'doc_ids.json'),
                'lexical_configuration': tokenizer.configuration(),
                'tfidf': {'norm': 'l2', 'smooth_idf': True, 'sublinear_tf': True, 'dtype': 'float32'},
                'bm25': {'k1': k1, 'b': b, 'idf': 'log1p((N-df+0.5)/(df+0.5))', 'query_policy': 'unique query terms'},
                'semantic': {'model_name': 'sentence-transformers/all-MiniLM-L6-v2', 'model_path': str(Path(model_path).resolve()),
                             'model_files_sha256': model_files, 'dimension': dimension, 'max_seq_length': model.max_seq_length,
                             'truncation': 'title plus abstract truncated by model tokenizer to max_seq_length',
                             'normalized': True, 'dtype': 'float32', 'faiss_type': 'IndexFlatIP',
                             'encoder_backend': 'OpenVINO float32' if cpu_optimized else 'PyTorch float32',
                             'reused_encoder_backend': reuse_backend,
                             'batch_size': batch_size, 'threads': threads},
                'packages': {name: importlib.metadata.version(name) for name in ['numpy', 'scipy', 'scikit-learn', 'nltk', 'sentence-transformers', 'transformers', 'torch', 'faiss-cpu']},
                'python_version': sys.version, 'artifacts': {name: sha256(output / name) for name in artifact_names},
                'resources': resources.report()}
    if cpu_optimized:
        cache = Path(model_path).parent / (Path(model_path).name + '-openvino-f32')
        manifest['semantic']['optimized_encoder_files_sha256'] = {str(p.resolve()): sha256(p) for p in sorted(cache.iterdir()) if p.is_file()}
        manifest['packages']['openvino'] = importlib.metadata.version('openvino')
    write_json(output / 'manifest.json', manifest)
    progress('indexes_built', **resources.report())
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=Path('data/processed'))
    parser.add_argument('--output', type=Path, default=Path('data/indexes'))
    parser.add_argument('--model', default='data/models/all-MiniLM-L6-v2')
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--k1', type=float, default=1.5)
    parser.add_argument('--b', type=float, default=.75)
    parser.add_argument('--no-stemming', action='store_true')
    parser.add_argument('--no-stopwords', action='store_true')
    parser.add_argument('--reuse-from', type=Path, help='Reuse matching verified document embeddings from a previous build/checkpoint')
    parser.add_argument('--cpu-optimized', action='store_true', help='Use full-precision OpenVINO CPU encoder with ST tokenization and pooling')
    args = parser.parse_args()
    build(args.corpus, args.output, args.model, args.batch_size, args.threads,
          args.k1, args.b, not args.no_stemming, not args.no_stopwords, args.reuse_from, args.cpu_optimized)


if __name__ == '__main__':
    main()
