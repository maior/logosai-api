"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "LogosAI API"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/logosai"

    # JWT
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours
    jwt_refresh_token_expire_days: int = 7

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Google AI (Gemini) - for memory extraction
    google_api_key: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # ACP Server
    acp_server_url: str = "http://localhost:8888"

    # ElasticSearch (RAG)
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_docs: str = "logosai_documents"
    elasticsearch_index_images: str = "logosai_images"

    # Embedding Model
    embedding_model_name: str = "jhgan/ko-sroberta-nli"
    embedding_device: str = "cpu"

    # Document Processing
    chunk_size: int = 512
    chunk_overlap: int = 128

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    @property
    def async_database_url(self) -> str:
        """Get async database URL."""
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
