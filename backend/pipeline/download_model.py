"""Download a pinned model snapshot once; builds operate entirely offline."""
import argparse
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download
from .common import write_json, progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/models/all-MiniLM-L6-v2'))
    parser.add_argument('--revision', default='main')
    args = parser.parse_args()
    name = 'sentence-transformers/all-MiniLM-L6-v2'
    revision = HfApi().model_info(name, revision=args.revision).sha
    snapshot_download(name, revision=revision, local_dir=args.output,
                      allow_patterns=['*.json', 'vocab.txt', 'model.safetensors', '1_Pooling/config.json'])
    write_json(args.output / 'snapshot.json', {'model_name': name, 'revision': revision})
    progress('model_downloaded', revision=revision, path=str(args.output))


if __name__ == '__main__':
    main()
