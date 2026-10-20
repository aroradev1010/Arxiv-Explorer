"""Disk-backed unique-ID catalogue and deterministic stratified hash sampling."""
import argparse
from collections import Counter
from datetime import date
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.parse import quote

from .common import Resources, progress, sha256, write_json

ID = re.compile(r'(?:\d{4}\.\d{4,5}|[a-z][a-z.-]*(?:\.[A-Z]{2})?/\d{7})\Z')
PHYSICS = {'astro-ph', 'cond-mat', 'gr-qc', 'hep-ex', 'hep-lat', 'hep-ph',
           'hep-th', 'math-ph', 'nlin', 'nucl-ex', 'nucl-th', 'physics', 'quant-ph',
           'acc-phys', 'adap-org', 'ao-sci', 'atom-ph', 'chao-dyn',
           'chem-ph', 'comp-gas', 'mtrl-th', 'patt-sol',
           'plasm-ph', 'solv-int', 'supr-con'}


def subject(category: str) -> str:
    if category in {'alg-geom', 'dg-ga', 'funct-an', 'q-alg'}:
        return 'math'
    if category == 'cmp-lg':
        return 'cs'
    prefix = category.split('.')[0]
    if prefix in {'cs', 'math', 'stat', 'q-bio', 'q-fin', 'econ', 'eess'}:
        return prefix
    return 'physics' if prefix in PHYSICS else 'other'


def normalize(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError('not_object')
    paper_id = raw.get('id')
    if not isinstance(paper_id, str) or not ID.fullmatch(paper_id):
        raise ValueError('invalid_id')
    for field in ('title', 'abstract', 'authors', 'categories'):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise ValueError('missing_' + field)
    categories = list(dict.fromkeys(raw['categories'].split()))
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9.-]*', c) for c in categories):
        raise ValueError('invalid_categories')
    published = None
    versions = raw.get('versions', [])
    if isinstance(versions, list):
        for version in versions:
            try:
                parsed = parsedate_to_datetime(version['created']).date()
                if 1991 <= parsed.year <= 2100:
                    published = parsed.isoformat()
                    break
            except (ValueError, TypeError, KeyError, IndexError, OverflowError, AttributeError):
                continue
    if not published:
        raise ValueError('invalid_submission_date')
    try:
        updated = date.fromisoformat(raw.get('update_date')).isoformat()
    except (TypeError, ValueError):
        updated = None
    year = int(published[:4])
    start = year // 5 * 5
    encoded = quote(paper_id, safe='/')
    result = {key: raw.get(key) for key in ('doi', 'comments', 'license')}
    result.update(id=paper_id, title=raw['title'], abstract=raw['abstract'], authors=raw['authors'],
                  categories=categories, primary_category=categories[0], published_at=published,
                  updated_at=updated, journal_ref=raw.get('journal-ref'),
                  arxiv_url='https://arxiv.org/abs/' + encoded,
                  pdf_url='https://arxiv.org/pdf/' + encoded,
                  stratum=f'{subject(categories[0])}|{start}-{start + 4}')
    return result


def allocate(counts: dict[str, int], size: int) -> dict[str, int]:
    """Hamilton largest-remainder proportional allocation; integer arithmetic."""
    total = sum(counts.values())
    if size < 1 or size > total:
        raise ValueError(f'Requested {size} documents; only {total} unique valid records available')
    quotas = {key: size * count // total for key, count in counts.items()}
    remainder = size - sum(quotas.values())
    ordered = sorted(counts, key=lambda key: (-(size * counts[key] % total), key))
    for key in ordered[:remainder]:
        quotas[key] += 1
    return quotas


def prepare(source: Path, output: Path, size: int, seed: int) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        raise FileExistsError('Output already contains a corpus; choose a fresh --output directory')
    resources = Resources()
    original_stat = source.stat()
    counts, rejected = Counter(), Counter()
    digest = hashlib.sha256()
    with tempfile.TemporaryDirectory(prefix='sampling-', dir=output) as temporary:
        catalog = sqlite3.connect(Path(temporary) / 'catalog.sqlite')
        catalog.execute('PRAGMA journal_mode=OFF')
        catalog.execute('PRAGMA synchronous=OFF')
        catalog.execute('PRAGMA cache_size=-32768')
        catalog.execute('CREATE TABLE records (id TEXT PRIMARY KEY, offset INTEGER, length INTEGER, stratum TEXT, priority TEXT)')
        lines = 0
        with source.open('rb') as stream:
            while True:
                offset = stream.tell()
                line = stream.readline()
                if not line:
                    break
                lines += 1
                digest.update(line)
                try:
                    paper = normalize(json.loads(line))
                except (ValueError, UnicodeDecodeError, RecursionError) as exc:
                    reason = str(exc) if type(exc) is ValueError else 'invalid_json'
                    rejected[reason if len(reason) < 80 else 'invalid_json'] += 1
                    continue
                priority = hashlib.sha256(f'{seed}\0{paper["id"]}'.encode()).hexdigest()
                inserted = catalog.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?,?)',
                                           (paper['id'], offset, len(line), paper['stratum'], priority)).rowcount
                if inserted:
                    counts[paper['stratum']] += 1
                else:
                    rejected['duplicate_id'] += 1
                if lines % 100000 == 0:
                    catalog.commit()
                    progress('scan', lines=lines, unique_valid=sum(counts.values()), **resources.report())
        catalog.commit()
        final_stat = source.stat()
        if (original_stat.st_size, original_stat.st_mtime_ns) != (final_stat.st_size, final_stat.st_mtime_ns):
            raise RuntimeError('Source changed while scanning')
        quotas = allocate(counts, size)
        progress('allocate', lines=lines, unique_valid=sum(counts.values()), rejected=dict(rejected))
        catalog.execute('CREATE INDEX sampling_order ON records(stratum,priority,id)')
        selected = []
        for key in sorted(quotas):
            selected.extend(catalog.execute('SELECT offset,length FROM records WHERE stratum=? ORDER BY priority,id LIMIT ?',
                                            (key, quotas[key])).fetchall())
        catalog.close()
        papers = []  # Bounded by requested sample size, never by raw dataset size.
        with source.open('rb') as stream:
            for offset, length in sorted(selected):
                stream.seek(offset)
                papers.append(normalize(json.loads(stream.read(length))))
        if (source.stat().st_size, source.stat().st_mtime_ns) != (original_stat.st_size, original_stat.st_mtime_ns):
            raise RuntimeError('Source changed while selecting')
        papers.sort(key=lambda paper: paper['id'])
        ids = [p['id'] for p in papers]
        assert len(ids) == size and len(set(ids)) == size
        corpus = output / 'papers.jsonl'
        with corpus.open('w', encoding='utf-8', newline='\n') as stream:
            for paper in papers:
                stream.write(json.dumps(paper, ensure_ascii=False, sort_keys=True) + '\n')
        write_json(output / 'doc_ids.json', ids)
        db_path = output / 'papers.sqlite'
        if db_path.exists():
            raise FileExistsError(db_path)
        db = sqlite3.connect(db_path)
        db.execute('CREATE TABLE papers (doc_index INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, title TEXT NOT NULL, abstract TEXT NOT NULL, primary_category TEXT NOT NULL, published_at TEXT NOT NULL, metadata_json TEXT NOT NULL)')
        db.executemany('INSERT INTO papers VALUES (?,?,?,?,?,?,?)',
                       ((i, p['id'], p['title'], p['abstract'], p['primary_category'], p['published_at'], json.dumps(p, ensure_ascii=False)) for i, p in enumerate(papers)))
        db.execute('CREATE INDEX by_category ON papers(primary_category)')
        db.execute('CREATE INDEX by_date ON papers(published_at)')
        db.commit()
        db.close()
    artifacts = {name: sha256(output / name) for name in ('papers.jsonl', 'doc_ids.json', 'papers.sqlite')}
    manifest = {'schema_version': 1, 'source': {'filename': source.name, 'bytes': original_stat.st_size, 'sha256': digest.hexdigest(), 'lines': lines},
                'sample_size': size, 'seed': seed, 'unique_valid': sum(counts.values()), 'rejected': dict(rejected),
                'strategy': 'primary broad subject x five-year band; Hamilton proportional quotas; smallest SHA256(seed NUL id) priorities; first valid duplicate wins',
                'document_order': 'ascending arxiv id', 'artifacts': artifacts,
                'processing_configuration': {'year_band_width': 5, 'valid_submission_years': [1991, 2100],
                                             'physics_prefixes': sorted(PHYSICS),
                                             'legacy_subject_mapping': {'cmp-lg': 'cs', 'alg-geom': 'math', 'dg-ga': 'math', 'funct-an': 'math', 'q-alg': 'math'}},
                'strata': {key: {'source_count': counts[key], 'selected_count': quotas[key], 'source_fraction': counts[key] / sum(counts.values()), 'selected_fraction': quotas[key] / size} for key in sorted(counts)},
                'resources': resources.report()}
    write_json(output / 'manifest.json', manifest)
    progress('prepared', sample_size=size, corpus_sha256=artifacts['papers.jsonl'], **resources.report())
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/raw/arxiv-metadata-oai-snapshot.json'))
    parser.add_argument('--output', type=Path, default=Path('data/processed'))
    parser.add_argument('--size', type=int, default=50000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    prepare(args.source, args.output, args.size, args.seed)


if __name__ == '__main__':
    main()
