"""Read-only corpus access with a separate indexed application metadata database."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Iterator

import numpy as np
from .prepare_metadata import folded
from .schemas import Filters, Paper, Category, CategoryResponse


class PaperRepository:
    def __init__(self, database: Path, metadata: Path, ids: list[str]):
        self.database, self.metadata = database, metadata
        self.positions = {paper_id: i for i, paper_id in enumerate(ids)}
        with self.connection() as db:
            self.provenance = {key: json.loads(value) for key, value in db.execute('SELECT key,value FROM application.provenance')}
            self.categories = CategoryResponse(
                categories=[Category(code=code, count=count) for code, count in db.execute('SELECT category,COUNT(*) FROM application.paper_categories GROUP BY category ORDER BY category')],
                subjects=[Category(code=code, count=count) for code, count in db.execute('SELECT subject,COUNT(*) FROM application.lookup GROUP BY subject ORDER BY subject')])

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        # Connections are request-local and closed; no cross-thread SQLite handles.
        db = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, timeout=5)
        try:
            db.execute('ATTACH DATABASE ? AS application', (self.metadata.as_uri() + '?mode=ro',))
            db.execute('PRAGMA query_only=ON')
            yield db
        finally:
            db.close()

    def eligible(self, filters: Filters) -> np.ndarray | None:
        clauses, values = [], []
        if filters.category:
            clauses.append('EXISTS (SELECT 1 FROM application.paper_categories c WHERE c.paper_id=l.id AND c.category=?)')
            values.append(filters.category)
        for field, expression, value in [('subject', 'l.subject=?', filters.subject),
                                          ('year_from', 'l.year>=?', filters.year_from),
                                          ('year_to', 'l.year<=?', filters.year_to)]:
            if value is not None:
                clauses.append(expression)
                values.append(value)
        if filters.author:
            clauses.append('instr(l.author_search,?)>0')
            values.append(folded(filters.author))
        if not clauses:
            return None
        with self.connection() as db:
            rows = db.execute('SELECT l.id FROM application.lookup l WHERE ' + ' AND '.join(clauses), values)
            return np.array(sorted(self.positions[row[0]] for row in rows), dtype=np.int64)

    def fetch_many(self, ids: list[str]) -> dict[str, Paper]:
        result = {}
        with self.connection() as db:
            for start in range(0, len(ids), 500):
                batch = ids[start:start + 500]
                placeholders = ','.join('?' for _ in batch)
                rows = db.execute(f'SELECT p.id,p.metadata_json,l.authors_json,l.authors_source FROM papers p JOIN application.lookup l ON l.id=p.id WHERE p.id IN ({placeholders})', batch)
                for paper_id, payload, authors, authors_source in rows:
                    paper = json.loads(payload)
                    paper.pop('stratum', None)
                    paper['authors_text'] = paper.pop('authors')
                    paper['authors'] = json.loads(authors)
                    paper['authors_source'] = authors_source
                    result[paper_id] = Paper.model_validate(paper)
        return result

    def get(self, paper_id: str) -> Paper | None:
        return self.fetch_many([paper_id]).get(paper_id)
