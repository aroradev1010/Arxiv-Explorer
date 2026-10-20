"""Typed public response contracts included in generated OpenAPI."""
from pydantic import BaseModel, ConfigDict
from backend.api.schemas import Paper
from .schemas import EvaluationQuery


class Contract(BaseModel):
    model_config = ConfigDict(extra='allow')


class CollectionResponse(Contract):
    version: str
    queries: list[EvaluationQuery]
    versions: list[dict[str,str]]


class ConfigResponse(Contract):
    enabled: bool
    mutations_enabled: bool


class PoolMetadata(Contract):
    corpus_version: str
    index_fingerprint: str
    algorithm_configuration: dict
    query_set_version: str
    queries: list[EvaluationQuery]
    depth: int
    random_seed: int
    filters: dict


class PoolResponse(Contract):
    id: str
    status: str
    metadata: PoolMetadata
    candidate_count: int
    stale: bool
    error: str | None


class BlindDocument(Contract):
    query_id: str
    paper_id: str
    relevance_grade: int | None
    annotation_order: int
    paper: Paper


class DocumentsResponse(Contract):
    total: int
    offset: int
    items: list[BlindDocument]


class SavedJudgment(Contract):
    saved: bool
    query_id: str
    paper_id: str
    relevance_grade: int | None


class QueryProgress(Contract):
    query_id: str
    total: int
    judged: int
    unjudged: int
    required: int
    missing_required: int
    missing_paper_ids: list[str]
    known_relevant: int
    percent: float
    status: str
    grades: dict[str,int]


class ProgressResponse(Contract):
    pool_id: str
    total: int
    judged: int
    unjudged: int
    required: int
    missing_required: int
    eligible_queries: int
    queries: list[QueryProgress]


class CurvePoint(Contract):
    rank: int
    precision: float
    pooled_recall: float | None


class QueryMetric(Contract):
    query_id: str
    algorithm: str
    precision: float | None
    pooled_recall: float | None
    ap: float | None
    dcg: float | None
    ndcg: float | None
    coverage: float
    known_relevant: int
    status: str
    curves: list[CurvePoint]


class AggregateMetric(Contract):
    precision: float | None
    pooled_recall: float | None
    ap: float | None
    dcg: float | None
    ndcg: float | None
    query_count: int
    precision_query_count: int
    pooled_recall_query_count: int
    ap_query_count: int
    ndcg_query_count: int


class RunMetadata(Contract):
    corpus_version: str
    index_fingerprint: str
    query_set_version: str
    queries: list[EvaluationQuery]
    cutoff: int
    relevance_threshold: int
    judgment_snapshot_version: str
    judgment_policy: str
    eligible_queries: list[str]
    excluded_queries: list[dict]
    aggregate: dict[str,AggregateMetric]


class RunResponse(Contract):
    id: str
    pool_id: str
    status: str
    stale: bool
    metadata: RunMetadata
    judgment_snapshot: dict | None
    created_at: str
    completed_at: str | None
    metrics: list[QueryMetric] | None = None
    rankings: list[dict] | None = None


class MetricsResponse(Contract):
    aggregate: dict[str,AggregateMetric]
    per_query: list[QueryMetric]
    excluded_queries: list[dict]
    stale: bool


class RunQueriesResponse(Contract):
    queries: list[EvaluationQuery]
    metrics: list[QueryMetric]
    rankings: list[dict]


class CurvesResponse(Contract):
    points: list[CurvePoint]
    aggregate: list[CurvePoint]
    convention: str


class LatencySummary(Contract):
    count: int
    mean: float | None
    p50: float | None
    p95: float | None
    minimum: float | None
    maximum: float | None
    stddev: float | None


class BenchmarkResponse(Contract):
    id: str
    status: str
    metadata: dict
    error: str | None
    samples: list[dict]
    completed_samples: int
    failed_samples: int
    summary: dict[str,LatencySummary]
