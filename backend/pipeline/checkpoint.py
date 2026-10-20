"""Validate and seal the completed prefix of an interrupted embedding build."""
import argparse
from pathlib import Path
import numpy as np
from .common import read_json, sha256, write_json, progress
from .indexes import load_corpus
from .text import semantic_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--indexes', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    args = parser.parse_args()
    papers, ids, _ = load_corpus(args.corpus)
    if (args.indexes / 'manifest.json').exists():
        raise ValueError('Build already complete; use its manifest directly')
    if read_json(args.indexes / 'doc_ids.json') != ids:
        raise ValueError('Mapping mismatch')
    vectors = np.load(args.indexes / 'embeddings.npy', mmap_mode='r')
    if vectors.shape != (len(ids), 384) or vectors.dtype != np.float32:
        raise ValueError('Embedding shape/dtype mismatch')
    norms = np.linalg.norm(vectors, axis=1)
    zero = np.flatnonzero(norms == 0)
    completed = int(zero[0]) if len(zero) else len(ids)
    if completed == 0 or not np.allclose(norms[:completed], 1, atol=1e-5) or not np.all(norms[completed:] == 0):
        raise ValueError('Embedding prefix incomplete or invalid; do not checkpoint a running process')
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(4)
    model = SentenceTransformer(str(args.model), local_files_only=True, device='cpu')
    positions = sorted(set([0, completed // 2, completed - 1]))
    expected = model.encode([semantic_text(papers[i]) for i in positions], normalize_embeddings=True)
    if not np.allclose(expected, vectors[positions], atol=2e-5):
        raise ValueError('Completed prefix failed source-document re-encoding')
    manifest = {'corpus_path': str(args.corpus.resolve()), 'completed': completed,
                'artifacts': {name: sha256(args.indexes / name) for name in ('doc_ids.json', 'embeddings.npy')},
                'semantic': {'encoder_backend': 'interrupted build; validated against PyTorch float32',
                             'model_files_sha256': {str(p.relative_to(args.model)).replace('\\', '/'): sha256(p)
                             for p in sorted(args.model.rglob('*')) if p.is_file() and '.cache' not in p.parts}}}
    write_json(args.indexes / 'checkpoint.json', manifest)
    progress('prefix_checkpointed', completed=completed)


if __name__ == '__main__':
    main()
