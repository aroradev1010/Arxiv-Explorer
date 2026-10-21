"""FastAPI lifespan, bounded CPU dispatch, explicit errors, and public routes."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import logging
import sqlite3
from typing import Annotated

import faiss
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette.exceptions import HTTPException

from .config import Settings
from .errors import APIError, AssetError
from .resources import load_resources
from .schemas import (CategoryResponse, CompareRequest, CompareResponse, ErrorResponse, Health,
                      Mode, Paper, PaperRequest, SearchRequest, SearchResponse, SimilarRequest,
                      SimilarResponse, Stats)
from .services import SearchService

logger = logging.getLogger('arxiv.api')


def create_app(settings: Settings | None = None, resource_loader=load_resources) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        pool = ThreadPoolExecutor(max_workers=settings.worker_threads, thread_name_prefix='arxiv-search',
                                  initializer=lambda: faiss.omp_set_num_threads(settings.compute_threads))
        application.state.pool = pool
        application.state.admission = asyncio.Semaphore(settings.worker_threads)
        application.state.service = None
        application.state.startup_error = 'Search assets not initialized'
        resources = None
        try:
            try:
                resources = await asyncio.get_running_loop().run_in_executor(pool, resource_loader, settings)
                application.state.service = SearchService(resources)
                application.state.startup_error = None
                logger.info('search_engine_ready documents=%s', len(resources.indexes.ids))
            except AssetError as exc:
                application.state.startup_error = str(exc)
                logger.error('search_engine_not_ready: %s', exc)
            except Exception:
                application.state.startup_error = 'Search engine initialization failed; consult server logs'
                logger.exception('search_engine_initialization_failed')
            yield
        finally:
            application.state.service = None
            await asyncio.to_thread(pool.shutdown, wait=True, cancel_futures=True)
            if resources is not None:
                resources.close()
            logger.info('search_engine_closed')

    application = FastAPI(title='ArXiv Explorer API', version='2.0.0', lifespan=lifespan,
                          description='Search the verified local ArXiv corpus. Scores are native relevance scores, not probabilities.')
    application.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                               allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])
    errors = {422: {'model': ErrorResponse}, 503: {'model': ErrorResponse}, 500: {'model': ErrorResponse}}

    def error(status: int, code: str, message: str, details=None):
        return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message, 'details': details or []}})

    @application.exception_handler(APIError)
    async def api_error(request: Request, exc: APIError):
        return error(exc.status, exc.code, exc.message)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{'location': list(item['loc']), 'message': item['msg'], 'type': item['type']} for item in exc.errors()]
        return error(422, 'validation_error', 'Request validation failed', details)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error(exc.status_code, 'http_error', 'Resource not found' if exc.status_code == 404 else 'HTTP request failed')

    @application.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        logger.error('request_failed', exc_info=(type(exc), exc, exc.__traceback__))
        return error(500, 'internal_error', 'Unexpected search service error')

    async def dispatch(function, *args):
        if application.state.service is None:
            raise APIError(503, 'not_ready', application.state.startup_error or 'Search engine unavailable')
        semaphore = application.state.admission
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=settings.queue_timeout_seconds)
        except TimeoutError:
            raise APIError(503, 'search_busy', 'Search capacity is busy; retry shortly')
        try:
            future = asyncio.get_running_loop().run_in_executor(application.state.pool, function, *args)
            try:
                return await asyncio.shield(future)
            except sqlite3.Error as exc:
                raise APIError(503, 'metadata_unavailable', 'Search metadata storage is unavailable') from exc
            except asyncio.CancelledError:
                # Keep the admission slot until the actual CPU job stops.
                await asyncio.shield(future)
                raise
        finally:
            semaphore.release()

    def service():
        value = application.state.service
        if value is None:
            raise APIError(503, 'not_ready', application.state.startup_error or 'Search engine unavailable')
        return value

    class ConfiguredSearch(SearchRequest):
        mode: Mode = settings.default_search_mode
        limit: int = Field(default=settings.default_result_limit, ge=1, le=settings.max_result_limit)

    @application.get('/api/v1/search', response_model=SearchResponse, responses=errors)
    async def search(query: Annotated[ConfiguredSearch, Query()]):
        return await dispatch(service().search, query)

    @application.get('/api/v1/papers', response_model=Paper, responses={**errors, 404: {'model': ErrorResponse}})
    async def paper(query: Annotated[PaperRequest, Query()]):
        return await dispatch(service().paper, query.arxiv_id)

    @application.get('/api/v1/papers/similar', response_model=SimilarResponse, responses={**errors, 404: {'model': ErrorResponse}})
    async def similar(query: Annotated[SimilarRequest, Query()]):
        return await dispatch(service().similar, query.arxiv_id, query.limit)

    @application.post('/api/v1/compare', response_model=CompareResponse, responses=errors)
    async def compare(request: CompareRequest):
        return await dispatch(service().compare, request)

    @application.get('/api/v1/categories', response_model=CategoryResponse, responses=errors)
    async def categories():
        return await dispatch(lambda: service().repository.categories)

    @application.get('/api/v1/system/stats', response_model=Stats, responses=errors)
    async def stats():
        return await dispatch(service().stats)

    @application.get('/api/v1/health/live', response_model=Health)
    async def live():
        return Health(status='live')

    @application.get('/api/v1/health/ready', response_model=Health, responses={503: {'model': Health}})
    async def ready():
        if application.state.service is None:
            return JSONResponse(status_code=503, content=Health(status='not_ready', reason=application.state.startup_error).model_dump())
        try:
            def ping():
                with service().repository.connection() as db:
                    db.execute('SELECT p.id FROM papers p JOIN application.lookup l ON l.id=p.id LIMIT 1').fetchone()
            await dispatch(ping)
        except Exception:
            return JSONResponse(status_code=503, content=Health(status='not_ready', reason='Search metadata unavailable or capacity busy').model_dump())
        return Health(status='ready')

    return application


app = create_app()
