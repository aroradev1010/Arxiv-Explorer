"""Public request/response models shared with OpenAPI and future clients."""
from datetime import date
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.pipeline.dataset import ID

Mode = Literal['tfidf', 'bm25', 'semantic', 'hybrid']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Filters(StrictModel):
    category: str | None = Field(default=None, min_length=1, max_length=80)
    subject: Literal['physics', 'math', 'cs', 'stat', 'q-bio', 'q-fin', 'econ', 'eess', 'other'] | None = None
    year_from: int | None = Field(default=None, ge=1991, le=2100)
    year_to: int | None = Field(default=None, ge=1991, le=2100)
    author: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator('category', 'author')
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        if value is not None:
            value = ' '.join(value.split())
            if not value:
                raise ValueError('Filter cannot be blank')
        return value

    @model_validator(mode='after')
    def year_order(self):
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError('year_from must not exceed year_to')
        return self


class SearchRequest(Filters):
    q: str = Field(min_length=1, max_length=1000)
    mode: Mode = 'hybrid'
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=5000)

    @field_validator('q')
    @classmethod
    def meaningful(cls, value: str) -> str:
        value = ' '.join(value.split())
        if not any(char.isalnum() for char in value):
            raise ValueError('Query must contain meaningful text')
        return value

    def filters(self) -> Filters:
        return Filters(**self.model_dump(include=set(Filters.model_fields)))


class PaperRequest(StrictModel):
    arxiv_id: str = Field(max_length=80)

    @field_validator('arxiv_id')
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not ID.fullmatch(value):
            raise ValueError('Invalid stable ArXiv ID')
        return value


class SimilarRequest(PaperRequest):
    limit: int = Field(default=5, ge=1, le=100)


class Paper(StrictModel):
    id: str
    title: str
    abstract: str
    authors: list[str]
    authors_text: str
    authors_source: Literal['authors_parsed', 'raw_only']
    primary_category: str
    categories: list[str]
    published_at: date | None
    updated_at: date | None
    doi: str | None = None
    journal_ref: str | None = None
    comments: str | None = None
    license: str | None = None
    arxiv_url: str
    pdf_url: str


class Contribution(StrictModel):
    rank: int = Field(ge=1)
    native_score: float
    contribution: float


class RankingDetails(StrictModel):
    final_rank: int
    matched_indexed_tokens: list[str] | None = None
    cosine_similarity: float | None = None
    rrf_score: float | None = None
    contributions: dict[str, Contribution] | None = None


class RankedPaper(StrictModel):
    paper: Paper
    rank: int = Field(ge=1)
    score: float = Field(description='Native algorithm score; not a probability')
    algorithm: Mode
    ranking_details: RankingDetails


class Timing(StrictModel):
    preprocessing: float = Field(ge=0)
    eligibility: float = Field(ge=0)
    embedding: float = Field(ge=0)
    tfidf: float = Field(ge=0)
    bm25: float = Field(ge=0)
    semantic: float = Field(ge=0)
    retrieval: float = Field(ge=0)
    fusion: float = Field(ge=0)
    metadata: float = Field(ge=0)
    total: float = Field(ge=0)


class Pagination(StrictModel):
    limit: int
    offset: int
    returned: int
    has_more: bool
    ranking_window_size: int
    ranked_candidate_count: int = Field(description='Count within the bounded ranking window')


class SearchResponse(StrictModel):
    query: str
    mode: Mode
    filters: Filters
    pagination: Pagination
    results: list[RankedPaper]
    timing_ms: Timing
    index_version: str


class CompareRequest(StrictModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=100)
    modes: list[Mode] = Field(default=['tfidf', 'bm25', 'semantic', 'hybrid'], min_length=1, max_length=4)
    filters: Filters = Field(default_factory=Filters)
    _query = field_validator('query')(SearchRequest.meaningful.__func__)

    @field_validator('modes')
    @classmethod
    def unique_modes(cls, value: list[Mode]) -> list[Mode]:
        if len(set(value)) != len(value):
            raise ValueError('Comparison modes must be unique')
        return value


class RankDifference(StrictModel):
    paper_id: str
    ranks: dict[str, int | None]
    delta_by_pair: dict[str, int | None] = Field(description='rank(second mode) minus rank(first mode), null when absent')


class CompareResponse(StrictModel):
    query: str
    filters: Filters
    methods: dict[str, SearchResponse]
    overlaps: dict[str, list[str]]
    rank_differences: list[RankDifference]
    timing_ms: Timing
    index_version: str


class SimilarResponse(StrictModel):
    arxiv_id: str
    results: list[RankedPaper]
    timing_ms: Timing
    index_version: str


class Category(StrictModel):
    code: str
    name: str | None = Field(default=None, description='Null when no authoritative readable name is stored')
    count: int


class CategoryResponse(StrictModel):
    categories: list[Category]
    subjects: list[Category]


class Stats(StrictModel):
    indexed_paper_count: int
    algorithms: list[Mode]
    vocabulary_size: int
    embedding_dimension: int
    embedding_model: str
    model_revision: str | None
    dataset_version: str
    index_version: str
    index_schema_version: int
    index_build_information: dict
    category_counts: CategoryResponse
    process_rss_bytes: int
    startup_ms: float
    worker_threads: int
    compute_threads: int


class Health(StrictModel):
    status: Literal['live', 'ready', 'not_ready']
    reason: str | None = None


class ErrorInfo(StrictModel):
    code: str
    message: str
    details: list[dict] = Field(default_factory=list)


class ErrorResponse(StrictModel):
    error: ErrorInfo
