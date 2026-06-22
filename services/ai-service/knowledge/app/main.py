"""
Aifya Knowledge RAG — FastAPI application entry point.
Institutional document RAG for hospital policies, SOPs, guidelines.
"""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog import get_logger

from app.config import get_settings
from app.middleware import (
    AuditLoggingMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.database import engine
from app.models.document import Base
from app.models.schemas import HealthResponse
from app.routers import documents, query
from app.services.document_service import check_minio_health, ensure_bucket
from app.services.retrieval_service import check_health as check_qdrant_health
from app.services.retrieval_service import ensure_collection

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup/shutdown lifecycle.
    Initializes Qdrant collection and MinIO bucket.
    """
    logger.info("app_startup", status="starting", service="knowledge-rag")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await ensure_collection()
    await ensure_bucket()

    logger.info("app_startup", status="complete", service="knowledge-rag")
    yield
    logger.info("app_shutdown", status="complete", service="knowledge-rag")


_is_dev: bool = settings.app_env == "development" or settings.debug
_docs_url: str | None = "/docs" if _is_dev else None
_redoc_url: str | None = "/redoc" if _is_dev else None
_openapi_url: str | None = f"{settings.api_v1_str}/openapi.json" if _is_dev else None

app = FastAPI(
    title=settings.project_name,
    description="Institutional knowledge RAG service for Aifya HMIS",
    version="1.0.0",
    openapi_url=_openapi_url,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    lifespan=lifespan,
)

# --- Middleware (order: last added = first executed) ---
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- API router ---
api_router = APIRouter(prefix=settings.api_v1_str)
api_router.include_router(documents.router)
api_router.include_router(query.router)
app.include_router(api_router)


# --- Health check ---
@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Service health check.
    Reports connectivity to Qdrant and MinIO.

    @returns HealthResponse with component statuses
    """
    from app.services.generation_service import check_health as check_vllm_health

    qdrant_status = check_qdrant_health()
    minio_status = check_minio_health()
    vllm_status = await check_vllm_health()

    overall = "ok"
    if any(s == "disconnected" for s in [qdrant_status, minio_status]):
        overall = "degraded"

    return HealthResponse(
        status=overall,
        service="aifya-knowledge-rag",
        components={
            "qdrant": qdrant_status,
            "minio": minio_status,
            "vllm": vllm_status,
        },
    )
