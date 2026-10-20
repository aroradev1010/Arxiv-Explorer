"""Fail closed on mapping, metadata, mathematical or artifact integrity errors."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

import faiss
import numpy as np

from .common import Resources, progress, read_json, sha256, write_json
from .indexes import load_corpus
from .search import SearchIndexes
from .text import lexical_text, semantic_text


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify(corpus: Path, path: Path, expected_size: int | None = None) -> dict:
    resources = Resources()
    papers, ids, dataset = load_corpus(corpus)
    manifest = read_json(path / 'manifest.json')
    n = len(ids)
    require(expected_size is None or n == expected_size, 'Unexpected corpus size')
    require(manifest['document_count'] == n, 'Manifest count mismatch')
    require(manifest['dataset_manifest_sha256'] == sha256(corpus / 'manifest.json'), 'Dataset manifest mismatch')
    require(manifest['dataset_sha256'] == sha256(corpus / 'papers.jsonl'), 'Index linked to wrong corpus')
    require(manifest['id_mapping_sha256'] == sha256(path / 'doc_ids.json'), 'Mapping checksum mismatch')
    for name, digest in manifest['artifacts'].items():
        require(sha256(path / name) == digest, f'Artifact checksum mismatch: {name}')
    require(read_json(path / 'doc_ids.json') == ids, 'Index/corpus ID ordering differs')
    counts = Counter(p['stratum'] for p in papers)
    for key, entry in dataset['strata'].items():
        require(counts[key] == entry['selected_count'], f'Stratum count mismatch: {key}')
    db = sqlite3.connect(f'{(corpus / "papers.sqlite").resolve().as_uri()}?mode=ro', uri=True)
    require(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLite integrity failure')
    rows = db.execute('SELECT doc_index,id,title,abstract,primary_category,published_at,metadata_json FROM papers ORDER BY doc_index')
    seen = 0
    for position, row in enumerate(rows):
        require(position < n, 'Extra SQLite row')
        p = papers[position]
        require(tuple(row[:6]) == (position, p['id'], p['title'], p['abstract'], p['primary_category'], p['published_at']), 'SQLite mapping/metadata mismatch')
        require(json.loads(row[6]) == p, 'SQLite stored metadata mismatch')
        seen += 1
    require(seen == n, 'SQLite row count mismatch')
    db.close()
    indexes = SearchIndexes(path)
    tfidf, postings, stats = indexes.tfidf, indexes.counts, indexes.stats
    vocabulary = len(indexes.vectorizer.vocabulary_)
    require(tfidf.shape == postings.shape == (n, vocabulary), 'Lexical shape mismatch')
    require(np.isfinite(tfidf.data).all() and np.all(tfidf.data >= 0), 'Invalid TF-IDF values')
    norms = np.asarray(tfidf.multiply(tfidf).sum(axis=1)).ravel()
    require(np.allclose(norms, 1, atol=1e-5), 'TF-IDF rows not unit normalized')
    require(postings.dtype == np.int32 and np.all(postings.data > 0), 'Invalid term counts')
    lengths = np.asarray(postings.sum(axis=1)).ravel()
    require(np.array_equal(lengths, stats['doc_lengths']), 'BM25 lengths mismatch')
    require(np.isclose(lengths.mean(), stats['avgdl']), 'BM25 average length mismatch')
    df = np.diff(postings.indptr)
    require(np.allclose(indexes.transformer.idf_, np.log((n + 1) / (df + 1)) + 1, atol=1e-6), 'TF-IDF smoothed IDF mismatch')
    require(np.allclose(stats['idf'], np.log1p((n - df + .5) / (df + .5)), atol=1e-6), 'BM25 IDF mismatch')
    require(float(stats['k1']) == manifest['bm25']['k1'] and float(stats['b']) == manifest['bm25']['b'], 'BM25 configuration mismatch')
    # Re-tokenize every document in bounded batches, proving lexical rows map to source IDs.
    csr = postings.tocsr()
    for start in range(0, n, 512):
        end = min(n, start + 512)
        rebuilt = indexes.vectorizer.transform(lexical_text(p) for p in papers[start:end])
        require((rebuilt != csr[start:end]).nnz == 0, 'Term counts differ from corpus text')
        diff = indexes.transformer.transform(rebuilt).astype(np.float32) - tfidf[start:end]
        require(diff.nnz == 0 or np.max(np.abs(diff.data)) < 1e-6, 'TF-IDF weights differ from rebuilt weights')
    progress('lexical_verified', documents=n, **resources.report())
    vectors = np.load(path / 'embeddings.npy', mmap_mode='r')
    semantic = indexes.semantic
    require(vectors.shape == (n, 384) and vectors.dtype == np.float32, 'Embedding shape/dtype mismatch')
    require(type(semantic).__name__ == 'IndexFlatIP' and semantic.metric_type == faiss.METRIC_INNER_PRODUCT, 'Wrong FAISS index type')
    require(semantic.ntotal == n and semantic.d == 384, 'FAISS count/dimension mismatch')
    for start in range(0, n, 1024):
        block = vectors[start:start + 1024]
        require(np.isfinite(block).all(), 'Non-finite embeddings')
        require(np.allclose(np.linalg.norm(block, axis=1), 1, atol=1e-5), 'Vectors not normalized')
        require(np.array_equal(semantic.reconstruct_n(start, len(block)), block), 'FAISS/embedding row mismatch')
    model_path = Path(manifest['semantic']['model_path'])
    for name, digest in manifest['semantic']['model_files_sha256'].items():
        require(sha256(model_path / name) == digest, f'Model checksum mismatch: {name}')
    for name, digest in manifest['semantic'].get('optimized_encoder_files_sha256', {}).items():
        require(sha256(Path(name)) == digest, f'Optimized encoder checksum mismatch: {name}')
    # Re-encode boundary and interior documents to detect incorrect vector/document alignment.
    positions = sorted(set([0, n // 4, n // 2, 3 * n // 4, n - 1]))
    from sentence_transformers import SentenceTransformer
    import torch
    torch.set_num_threads(manifest['semantic']['threads'])
    faiss.omp_set_num_threads(manifest['semantic']['threads'])
    model = SentenceTransformer(str(model_path), local_files_only=True, device='cpu')
    require(model.max_seq_length == manifest['semantic']['max_seq_length'], 'Tokenizer truncation configuration mismatch')
    encoded = model.encode([semantic_text(papers[i]) for i in positions], normalize_embeddings=True, show_progress_bar=False)
    require(np.allclose(encoded, vectors[positions], atol=2e-5), 'Re-encoded embeddings do not match mapped documents')
    for position in positions:
        distances, neighbors = semantic.search(np.ascontiguousarray(vectors[position:position + 1]), min(10, n))
        require(np.isclose(distances[0, 0], 1, atol=1e-5), 'FAISS self-match score invalid')
        require(position in neighbors[0] or np.allclose(vectors[neighbors[0, 0]], vectors[position], atol=1e-6), 'FAISS self-match mapping invalid')
    indexes.model = model
    smoke = {}
    for query in ['neural network learning', 'quantum field theory', 'galaxy formation']:
        smoke[query] = {}
        for algorithm in ['tfidf', 'bm25', 'semantic']:
            hits = indexes.search(query, algorithm, 10)
            require(len(hits) > 0, f'Empty smoke results: {algorithm}')
            require(len({hit['paper_id'] for hit in hits}) == len(hits), 'Duplicate results')
            require(all(ids[h['doc_index']] == h['paper_id'] and np.isfinite(h['score']) for h in hits), 'Result mapping invalid')
            require(all(hits[i]['score'] >= hits[i + 1]['score'] for i in range(len(hits) - 1)), 'Scores out of order')
            smoke[query][algorithm] = hits[:3]
    report = {'status': 'passed', 'document_count': n, 'vocabulary_size': vocabulary,
              'tfidf_shape': list(tfidf.shape), 'tfidf_nnz': tfidf.nnz, 'bm25_nnz': postings.nnz,
              'semantic_shape': list(vectors.shape), 'id_mapping_sha256': manifest['id_mapping_sha256'],
              'checks': ['all corpus/index/model artifact checksums', 'unique sorted IDs and exact index/corpus/SQLite mapping',
                         'SQLite integrity and all metadata rows', 'all sample stratum counts',
                         'all lexical rows re-tokenized and TF-IDF weights recomputed', 'BM25 lengths/average/IDF',
                         'all embedding norms and exact FAISS reconstruction', 'five mapped documents re-encoded',
                         'FAISS self matches', 'three real queries on each retriever'],
              'smoke_results': smoke, 'resources': resources.report()}
    write_json(path / 'validation.json', report)
    progress('validation_passed', documents=n, **resources.report())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=Path('data/processed'))
    parser.add_argument('--indexes', type=Path, default=Path('data/indexes'))
    parser.add_argument('--expected-size', type=int)
    args = parser.parse_args()
    verify(args.corpus, args.indexes, args.expected_size)


if __name__ == '__main__':
    main()
