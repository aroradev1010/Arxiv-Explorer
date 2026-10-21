"""Small offline search client over the persisted artifacts."""
import argparse
from pathlib import Path
import faiss
import joblib
import numpy as np
from scipy import sparse
from .common import read_json
from .text import clean


def ranked(scores: np.ndarray, ids: list[str], k: int, positive: bool = True) -> list[dict]:
    if k < 1:
        raise ValueError('top_k must be positive')
    candidates = np.flatnonzero(scores > 0) if positive else np.arange(len(ids))
    order = np.lexsort((candidates, -scores[candidates]))[:k]
    return [{'doc_index': int(i), 'paper_id': ids[i], 'score': float(scores[i])}
            for i in candidates[order]]


def bm25_scores(counts: sparse.csc_matrix, lengths: np.ndarray, idf: np.ndarray,
                avgdl: float, k1: float, b: float, terms: np.ndarray) -> np.ndarray:
    scores = np.zeros(counts.shape[0], dtype=np.float64)
    for term in np.unique(terms):
        start, end = counts.indptr[term:term + 2]
        documents = counts.indices[start:end]
        term_frequency = counts.data[start:end].astype(np.float64)
        length_normalization = k1 * (1 - b + b * lengths[documents] / avgdl)
        scores[documents] += (
            idf[term] * term_frequency * (k1 + 1) / (term_frequency + length_normalization)
        )
    return scores


class SearchIndexes:
    def __init__(self, path: Path):
        self.ids = read_json(path / 'doc_ids.json')
        self.manifest = read_json(path / 'manifest.json')
        self.vectorizer = joblib.load(path / 'count_vectorizer.joblib')
        self.transformer = joblib.load(path / 'tfidf_transformer.joblib')
        self.tfidf = sparse.load_npz(path / 'tfidf.npz')
        self.counts = sparse.load_npz(path / 'bm25_counts.npz').tocsc()
        self.stats = np.load(path / 'bm25_stats.npz')
        self.semantic = faiss.read_index(str(path / 'semantic.faiss'))
        self.model = None

    def search(self, query: str, algorithm: str, k: int = 10) -> list[dict]:
        if k < 1:
            raise ValueError('top_k must be positive')
        if not query.strip():
            return []
        if algorithm == 'semantic':
            if self.model is None:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.manifest['semantic']['model_path'], device='cpu', local_files_only=True)
            vector = self.model.encode([clean(query)], normalize_embeddings=True).astype(np.float32)
            scores, positions = self.semantic.search(vector, min(k, len(self.ids)))
            return [{'doc_index': int(i), 'paper_id': self.ids[i], 'score': float(s)}
                    for i, s in zip(positions[0], scores[0])]
        query_counts = self.vectorizer.transform([query])
        if algorithm == 'tfidf':
            vector = self.transformer.transform(query_counts)
            scores = (self.tfidf @ vector.T).toarray().ravel()  # Only N x 1 scores.
        elif algorithm == 'bm25':
            scores = bm25_scores(self.counts, self.stats['doc_lengths'], self.stats['idf'],
                                 float(self.stats['avgdl']), float(self.stats['k1']), float(self.stats['b']), query_counts.indices)
        else:
            raise ValueError(f'Unknown algorithm: {algorithm}')
        return ranked(scores, self.ids, k)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query')
    parser.add_argument('--indexes', type=Path, default=Path('data/indexes'))
    parser.add_argument('--algorithm', choices=['tfidf', 'bm25', 'semantic'], default='bm25')
    parser.add_argument('--top-k', type=int, default=10)
    args = parser.parse_args()
    import json
    print(json.dumps(SearchIndexes(args.indexes).search(args.query, args.algorithm, args.top_k), indent=2))


if __name__ == '__main__':
    main()
