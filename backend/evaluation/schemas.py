from typing import Literal
from pydantic import Field, field_validator, model_validator
from backend.api.schemas import StrictModel, Filters


class EvaluationQuery(StrictModel):
    id: str = Field(pattern=r'^Q[0-9A-Za-z_-]{1,40}$')
    query: str = Field(min_length=1, max_length=1000)
    information_need: str = Field(min_length=10, max_length=4000)
    domain: str = Field(min_length=1, max_length=80)
    query_type: str = Field(min_length=1, max_length=80)
    notes: str = Field(default='', max_length=4000)

    @field_validator('query', 'information_need', 'domain', 'query_type')
    @classmethod
    def meaningful(cls, value):
        if not any(c.isalnum() for c in value):
            raise ValueError('Meaningful text required')
        return value


class QueryCollection(StrictModel):
    queries: list[EvaluationQuery] = Field(min_length=1, max_length=200)

    @model_validator(mode='after')
    def unique(self):
        if len({q.id for q in self.queries}) != len(self.queries) or len({' '.join(q.query.lower().split()) for q in self.queries}) != len(self.queries):
            raise ValueError('Duplicate query ID or query text')
        return self


class PoolRequest(StrictModel):
    query_set_version: str | None = None
    query_ids: list[str] | None = Field(default=None, min_length=1, max_length=200)
    depth: int = Field(default=10, ge=1, le=100)
    random_seed: int = Field(default=42, ge=0, le=2**31-1)
    filters: Filters = Field(default_factory=Filters)

    @field_validator('query_ids')
    @classmethod
    def unique_ids(cls, value):
        if value and len(set(value)) != len(value):
            raise ValueError('Duplicate query IDs')
        return value


class Judgment(StrictModel):
    query_id: str
    paper_id: str = Field(min_length=1, max_length=80)
    relevance_grade: Literal[0, 1, 2] | None


class RunRequest(StrictModel):
    pool_id: str
    cutoff: int = Field(default=10, ge=1, le=100)
    relevance_threshold: Literal[1, 2] = 1


class BenchmarkRequest(PoolRequest):
    warmup_iterations: int = Field(default=2, ge=0, le=10)
    measured_iterations: int = Field(default=10, ge=1, le=30)
