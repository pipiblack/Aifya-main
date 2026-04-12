"""
Configuration for Aifya Knowledge RAG service.
Uses pydantic-settings for env-based configuration.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_backend_root = Path(__file__).resolve().parent.parent
load_dotenv(_backend_root / ".env")

_INSECURE_DEFAULTS = {
    "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32",
    "CHANGE_ME_IN_PRODUCTION",
    "miniosupersecret",
    "aifyaadmin",
}


class Settings(BaseSettings):
    """
    Knowledge RAG service settings.
    All secrets MUST be overridden via env vars in production.
    """

    # --- Environment ---
    app_env: str = Field("development", validation_alias="APP_ENV")
    debug: bool = Field(False, validation_alias="DEBUG")

    # --- API ---
    api_v1_str: str = "/api/v1"
    project_name: str = "Aifya Knowledge RAG"
    host: str = Field("0.0.0.0", validation_alias="HOST")
    port: int = Field(8025, validation_alias="PORT")

    # --- Auth (Keycloak JWT) ---
    keycloak_url: str = Field(
        "http://localhost:8080", validation_alias="KEYCLOAK_URL"
    )
    keycloak_realm: str = Field("aifya", validation_alias="KEYCLOAK_REALM")
    jwt_algorithm: str = "RS256"

    # --- Database (document metadata) ---
    database_url: str = Field(
        "postgresql+asyncpg://aifya_user:change_me_in_production@localhost:5432/aifya",
        validation_alias="DATABASE_URL",
    )

    # --- Qdrant (vector store) ---
    qdrant_endpoint: str = Field(
        "http://localhost:6333", validation_alias="QDRANT_ENDPOINT"
    )
    qdrant_api_key: str | None = Field(None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(
        "aifya_knowledge", validation_alias="QDRANT_COLLECTION"
    )

    # --- Embedding ---
    embedding_model: str = Field(
        "BAAI/bge-m3", validation_alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(1024, validation_alias="EMBEDDING_DIMENSION")
    embedding_batch_size: int = Field(32, validation_alias="EMBEDDING_BATCH_SIZE")

    # --- MinIO (document storage) ---
    minio_endpoint: str = Field(
        "localhost:9000", validation_alias="MINIO_ENDPOINT"
    )
    minio_access_key: str = Field(
        "aifyaadmin", validation_alias="MINIO_ACCESS_KEY"
    )
    minio_secret_key: str = Field(
        "miniosupersecret", validation_alias="MINIO_SECRET_KEY"
    )
    minio_bucket: str = Field(
        "aifya-knowledge", validation_alias="MINIO_KNOWLEDGE_BUCKET"
    )
    minio_secure: bool = Field(False, validation_alias="MINIO_SECURE")

    # --- vLLM (generation) ---
    vllm_base_url: str = Field(
        "http://localhost:8002/v1", validation_alias="VLLM_BASE_URL"
    )
    generation_model: str = Field(
        "Qwen/Qwen2.5-72B-Instruct", validation_alias="GENERATION_MODEL"
    )
    generation_max_tokens: int = Field(
        2048, validation_alias="GENERATION_MAX_TOKENS"
    )
    generation_temperature: float = Field(
        0.1, validation_alias="GENERATION_TEMPERATURE"
    )

    # --- RAG settings ---
    chunk_size: int = Field(512, validation_alias="CHUNK_SIZE")
    chunk_overlap: int = Field(64, validation_alias="CHUNK_OVERLAP")
    retrieval_top_k: int = Field(8, validation_alias="RETRIEVAL_TOP_K")
    rerank_top_k: int = Field(4, validation_alias="RERANK_TOP_K")
    similarity_threshold: float = Field(
        0.45, validation_alias="SIMILARITY_THRESHOLD"
    )

    # --- Celery ---
    celery_broker_url: str = Field(
        "redis://localhost:6379/3", validation_alias="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        "redis://localhost:6379/4", validation_alias="CELERY_RESULT_BACKEND"
    )

    # --- Rate limiting ---
    rate_limit_per_minute: int = Field(
        60, validation_alias="RATE_LIMIT_PER_MINUTE"
    )

    # --- Upload limits ---
    max_file_size_mb: int = Field(50, validation_alias="MAX_FILE_SIZE_MB")
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".doc", ".txt", ".md", ".rtf"],
    )

    # --- CORS ---
    cors_origins: list[str] = Field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS", "http://localhost:3000"
        ).split(","),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
    )

    @model_validator(mode="after")
    def _reject_insecure_defaults(self) -> "Settings":
        """Crash on startup if critical secrets still use placeholder defaults."""
        if self.app_env != "development":
            if self.minio_access_key in _INSECURE_DEFAULTS:
                raise ValueError(
                    "MINIO_ACCESS_KEY must be set to a secure value in non-development environments."
                )
            if self.minio_secret_key in _INSECURE_DEFAULTS:
                raise ValueError(
                    "MINIO_SECRET_KEY must be set to a secure value in non-development environments."
                )
            if "change_me" in self.database_url.lower():
                raise ValueError(
                    "DATABASE_URL must be set to a real connection string in non-development environments."
                )
        return self


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton.

    @returns Settings instance
    """
    return Settings()
