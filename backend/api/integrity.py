"""Hash runtime and evaluation files against the preserved cleanup baseline."""
from .config import ROOT
from backend.pipeline.common import read_json, sha256, write_json


def main():
    baseline = read_json(ROOT / 'docs/ASSET_BASELINE.json')
    files = []
    for folder in ['data/raw', 'data/processed', 'data/indexes', 'data/models', 'data/evaluation']:
        files.extend(path for path in (ROOT / folder).rglob('*') if path.is_file())
    files.extend((ROOT / 'var').glob('*.sqlite'))
    current = {path.relative_to(ROOT).as_posix(): sha256(path) for path in sorted(files)}
    changed = sorted(name for name in set(baseline) | set(current) if baseline.get(name) != current.get(name))
    manifest_mismatches = []
    for folder in ['data/processed', 'data/indexes']:
        manifest = read_json(ROOT / folder / 'manifest.json')
        for name, digest in manifest['artifacts'].items():
            if current.get(f'{folder}/{name}') != digest:
                manifest_mismatches.append(f'{folder}/{name}')
    dataset = read_json(ROOT / 'data/processed/manifest.json')
    if current.get('data/raw/arxiv-metadata-oai-snapshot.json') != dataset['source']['sha256']:
        manifest_mismatches.append('data/raw/arxiv-metadata-oai-snapshot.json')
    report = {'status': 'passed' if not changed and not manifest_mismatches else 'failed',
              'protected_file_count': len(current), 'changed_added_or_removed_files': changed,
              'manifest_fingerprint_mismatches': manifest_mismatches,
              'baseline': 'docs/ASSET_BASELINE.json'}
    write_json(ROOT / 'var/artifact-integrity.json', report)
    print(report, flush=True)
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
