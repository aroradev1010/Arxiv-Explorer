"""Hash protected artifacts read-only; never invokes indexing or model downloads."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
baseline = json.loads((ROOT / 'docs/PHASE2_ARTIFACT_BASELINE.json').read_text())
current = {}
for folder in ['data/raw', 'data/processed', 'data/indexes', 'data/models']:
    for path in sorted((ROOT / folder).rglob('*')):
        if not path.is_file(): continue
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''): digest.update(chunk)
        current[path.relative_to(ROOT).as_posix()] = {'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}
changed = sorted(k for k in set(baseline) | set(current) if baseline.get(k) != current.get(k))
metadata_baseline = json.loads((ROOT / 'docs/PHASE4_METADATA_HASH.json').read_text(encoding='utf-8-sig'))['Hash'].lower()
metadata_hash = hashlib.sha256((ROOT / 'var/metadata.sqlite').read_bytes()).hexdigest()
report = {'status': 'passed' if not changed and metadata_hash == metadata_baseline else 'failed',
          'protected_file_count': len(current), 'changed_added_or_removed_files': changed,
          'metadata_unchanged': metadata_hash == metadata_baseline,
          'baseline': 'docs/PHASE2_ARTIFACT_BASELINE.json'}
(ROOT / 'docs/PHASE4_ARTIFACT_INTEGRITY.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
assert report['status'] == 'passed'
