"""Artifact integrity and resource accounting shared by offline commands."""
import hashlib
import json
import os
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def progress(event: str, **values) -> None:
    print(json.dumps({'event': event, **values}), flush=True)


class Resources:
    def __init__(self):
        self.started = time.perf_counter()

    def report(self) -> dict:
        import psutil
        info = psutil.Process().memory_info()
        return {'elapsed_seconds': round(time.perf_counter() - self.started, 3),
                'peak_rss_bytes': getattr(info, 'peak_wset', info.rss)}
