"""Typed API configuration; all relative paths are anchored to the repository."""
from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode
from typing import Annotated

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    app_env: Literal['development', 'production', 'test'] = 'development'
    host: str = '127.0.0.1'
    port: int = Field(default=8000, ge=1, le=65535)
    dataset_dir: Path = ROOT / 'data/processed'
    index_dir: Path = ROOT / 'data/indexes'
    model_dir: Path = ROOT / 'data/models/all-MiniLM-L6-v2'
    metadata_db: Path = ROOT / 'var/metadata.sqlite'
    default_search_mode: Literal['tfidf', 'bm25', 'semantic', 'hybrid'] = 'hybrid'
    default_result_limit: int = Field(default=10, ge=1, le=100)
    max_result_limit: int = Field(default=100, ge=1, le=100)
    max_ranking_window: int = Field(default=1000, ge=100, le=5000)
    rrf_k: int = Field(default=60, ge=1, le=10000)
    rrf_candidate_depth: int = Field(default=200, ge=1, le=5000)
    worker_threads: int = Field(default=2, ge=1, le=8)
    compute_threads: int = Field(default=2, ge=1, le=8)
    queue_timeout_seconds: float = Field(default=1, gt=0, le=30)
    evaluation_enabled: bool = True
    evaluation_mutations_enabled: bool = False
    evaluation_db_path: Path = ROOT / 'var/evaluation.sqlite'
    cors_origins: Annotated[list[str], NoDecode] = ['http://localhost:3000', 'http://127.0.0.1:3000']

    @field_validator('dataset_dir', 'index_dir', 'model_dir', 'metadata_db', 'evaluation_db_path', mode='before')
    @classmethod
    def paths(cls, value: str | Path) -> Path:
        path = Path(value)
        return (path if path.is_absolute() else ROOT / path).resolve()

    @field_validator('cors_origins', mode='before')
    @classmethod
    def origins(cls, value: str | list[str]) -> list[str]:
        origins = [x.strip() for x in value.split(',') if x.strip()] if isinstance(value, str) else value
        if any(x == '*' or not x.startswith(('http://', 'https://')) for x in origins):
            raise ValueError('CORS origins must be explicit HTTP(S) origins')
        return origins

    @model_validator(mode='after')
    def limits(self):
        if self.default_result_limit > self.max_result_limit or self.rrf_candidate_depth > self.max_ranking_window:
            raise ValueError('Default limits exceed configured maxima')
        if self.evaluation_db_path == self.metadata_db or any(self.evaluation_db_path.is_relative_to(p) for p in (self.dataset_dir, self.index_dir, self.model_dir, ROOT / 'data')):
            raise ValueError('Evaluation database must be separate from protected assets and metadata cache')
        return self
