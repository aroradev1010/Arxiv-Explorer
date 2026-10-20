"""SQLite v1 migration and short-lived transactional connections."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def dump(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError('Unsupported evaluation schema version')
            db.executescript('''
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS query_sets(version TEXT PRIMARY KEY, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evaluation_queries(
              query_set_version TEXT REFERENCES query_sets(version), id TEXT, definition TEXT NOT NULL,
              PRIMARY KEY(query_set_version,id));
            CREATE TABLE IF NOT EXISTS candidate_pools(
              id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, status TEXT NOT NULL,
              query_set_version TEXT NOT NULL REFERENCES query_sets(version), metadata TEXT NOT NULL,
              error TEXT, created_at TEXT NOT NULL, completed_at TEXT);
            CREATE TABLE IF NOT EXISTS pool_documents(
              pool_id TEXT REFERENCES candidate_pools(id), query_id TEXT, paper_id TEXT,
              provenance TEXT NOT NULL, annotation_order INTEGER NOT NULL,
              PRIMARY KEY(pool_id,query_id,paper_id), UNIQUE(pool_id,query_id,annotation_order));
            CREATE INDEX IF NOT EXISTS pool_order ON pool_documents(pool_id,query_id,annotation_order);
            CREATE TABLE IF NOT EXISTS relevance_judgments(
              pool_id TEXT, query_id TEXT, paper_id TEXT, relevance_grade INTEGER NOT NULL CHECK(relevance_grade IN (0,1,2)),
              judgment_source TEXT NOT NULL DEFAULT 'human', judged_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              PRIMARY KEY(pool_id,query_id,paper_id),
              FOREIGN KEY(pool_id,query_id,paper_id) REFERENCES pool_documents(pool_id,query_id,paper_id));
            CREATE TABLE IF NOT EXISTS evaluation_runs(
              id TEXT PRIMARY KEY, pool_id TEXT NOT NULL REFERENCES candidate_pools(id), status TEXT NOT NULL,
              metadata TEXT NOT NULL, judgment_snapshot TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT);
            CREATE TABLE IF NOT EXISTS evaluation_rankings(
              run_id TEXT REFERENCES evaluation_runs(id), query_id TEXT, algorithm TEXT, rank INTEGER,
              paper_id TEXT NOT NULL, native_score REAL NOT NULL, PRIMARY KEY(run_id,query_id,algorithm,rank));
            CREATE TABLE IF NOT EXISTS evaluation_metrics(
              run_id TEXT REFERENCES evaluation_runs(id), query_id TEXT, algorithm TEXT, metrics TEXT NOT NULL,
              PRIMARY KEY(run_id,query_id,algorithm));
            CREATE TABLE IF NOT EXISTS benchmark_runs(
              id TEXT PRIMARY KEY, status TEXT NOT NULL, metadata TEXT NOT NULL, error TEXT,
              created_at TEXT NOT NULL, completed_at TEXT);
            CREATE TABLE IF NOT EXISTS benchmark_samples(
              benchmark_run_id TEXT REFERENCES benchmark_runs(id), query_id TEXT, algorithm TEXT, iteration INTEGER,
              warmup INTEGER NOT NULL, latency_ms REAL, timing_breakdown TEXT, error TEXT, timestamp TEXT NOT NULL,
              PRIMARY KEY(benchmark_run_id,query_id,algorithm,iteration,warmup));
            PRAGMA user_version=1;
            COMMIT;
            ''')
            # A single process is supported. Interrupted jobs must not look complete after restart.
            for table in ('candidate_pools', 'benchmark_runs'):
                db.execute(f"UPDATE {table} SET status='FAILED', error='Interrupted by application shutdown' WHERE status IN ('RUNNING','QUEUED')")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def rows(self, sql, args=()):
        with self.connection() as db:
            return [dict(r) for r in db.execute(sql, args)]
