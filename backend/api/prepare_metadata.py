"""Derive application-only filter/author lookups without touching verified assets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import unicodedata

from backend.pipeline.common import read_json, sha256, progress
from backend.pipeline.dataset import normalize
from .config import ROOT, Settings


def folded(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def signature(paper: dict) -> str:
    return hashlib.sha256(json.dumps(paper, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def initialize_cache(connection: sqlite3.Connection) -> None:
    connection.executescript('''
        CREATE TABLE provenance (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE lookup (id TEXT PRIMARY KEY, year INTEGER, subject TEXT NOT NULL,
                             authors_json TEXT NOT NULL, authors_source TEXT NOT NULL,
                             author_search TEXT NOT NULL);
        CREATE TABLE paper_categories (paper_id TEXT NOT NULL, category TEXT NOT NULL,
                                       PRIMARY KEY(paper_id,category));
        CREATE INDEX lookup_year ON lookup(year);
        CREATE INDEX lookup_subject ON lookup(subject);
        CREATE INDEX lookup_category ON paper_categories(category,paper_id);
    ''')


def prepare(settings: Settings, source: Path) -> dict:
    output = settings.metadata_db
    if any(output.is_relative_to(folder) for folder in [settings.dataset_dir, settings.index_dir, settings.model_dir, ROOT / 'data/raw', ROOT / 'data/models']):
        raise ValueError('Application metadata must be stored outside protected dataset/index/model directories')
    if output.exists():
        raise FileExistsError('Application metadata database exists; choose another METADATA_DB')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.building.sqlite')
    if temporary.exists():
        raise FileExistsError('An unfinished metadata build exists; choose a new output')
    corpus_manifest = read_json(settings.dataset_dir / 'manifest.json')
    expected = {}
    raw_authors = {}
    corpus = sqlite3.connect((settings.dataset_dir / 'papers.sqlite').as_uri() + '?mode=ro', uri=True)
    db = sqlite3.connect(temporary)
    try:
        initialize_cache(db)
        for paper_id, payload in corpus.execute('SELECT id,metadata_json FROM papers'):
            paper = json.loads(payload)
            expected[paper_id] = signature(paper)
            raw_authors[paper_id] = paper['authors']
            year = int(paper['published_at'][:4]) if paper.get('published_at') else None
            db.execute('INSERT INTO lookup VALUES (?,?,?,?,?,?)', (paper_id, year, paper['stratum'].split('|')[0], '[]', 'raw_only', folded(paper['authors'])))
            db.executemany('INSERT INTO paper_categories VALUES (?,?)', ((paper_id, c) for c in paper['categories']))
        db.commit()
        if len(expected) != corpus_manifest['sample_size']:
            raise ValueError('Corpus count differs from verified manifest')
        digest = hashlib.sha256()
        matched, parsed, lines = set(), 0, 0
        with source.open('rb') as stream:
            for line in stream:
                digest.update(line)
                lines += 1
                header = re.match(rb'\{\s*"id"\s*:\s*"([^"\\]+)"', line)
                raw = None
                if header:
                    paper_id = header[1].decode('utf-8')
                else:
                    try:
                        raw = json.loads(line)
                        paper_id = raw.get('id') if isinstance(raw, dict) else None
                    except (ValueError, UnicodeDecodeError):
                        continue
                if paper_id not in expected or paper_id in matched:
                    continue
                raw = json.loads(line) if raw is None else raw
                try:
                    paper = normalize(raw)
                except ValueError:
                    continue
                if signature(paper) != expected[paper_id]:
                    continue
                names = []
                for author in raw.get('authors_parsed', []) or []:
                    if isinstance(author, list) and 1 <= len(author) <= 3 and all(isinstance(part, str) for part in author):
                        parts = (author + ['', ''])[:3]
                        name = ' '.join(x.strip() for x in (parts[1], parts[0], parts[2]) if x.strip())
                        if name:
                            names.append(name)
                if names:
                    db.execute('UPDATE lookup SET authors_json=?, authors_source=?, author_search=? WHERE id=?',
                               (json.dumps(names, ensure_ascii=False), 'authors_parsed', folded(raw_authors[paper_id] + ' ' + ' '.join(names)), paper_id))
                    parsed += 1
                matched.add(paper_id)
                if len(matched) % 10000 == 0:
                    db.commit()
                    progress('application_metadata', matched=len(matched), source_lines=lines)
        if digest.hexdigest() != corpus_manifest['source']['sha256'] or len(matched) != len(expected):
            raise ValueError('Source fingerprint or selected-paper metadata does not match the verified corpus')
        provenance = {'dataset_manifest_sha256': sha256(settings.dataset_dir / 'manifest.json'),
                      'dataset_sha256': corpus_manifest['artifacts']['papers.jsonl'],
                      'source_sha256': digest.hexdigest(), 'document_count': len(expected),
                      'ordered_authors_available': parsed, 'schema_version': 1}
        db.executemany('INSERT INTO provenance VALUES (?,?)', ((key, json.dumps(value)) for key, value in provenance.items()))
        db.commit()
    except BaseException:
        db.close()
        corpus.close()
        # Only this command's application-owned partial file is removed.
        temporary.unlink(missing_ok=True)
        raise
    db.close()
    corpus.close()
    temporary.replace(output)
    progress('application_metadata_ready', **provenance)
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    settings = Settings()
    if args.output:
        settings = Settings(metadata_db=args.output)
    source = args.source.resolve() if args.source else settings.dataset_dir.parent / 'raw/arxiv-metadata-oai-snapshot.json'
    prepare(settings, source)


if __name__ == '__main__':
    main()
