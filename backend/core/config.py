"""Backend configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Groq LLM
    groq_api_key: str = Field(default="", description="Groq API key")
    groq_model: str = Field(default="llama-3.3-70b-versatile", description="Primary LLM model")
    groq_fallback_model: str = Field(default="mixtral-8x7b-32768", description="Fallback LLM model")
    groq_timeout: int = Field(default=30, description="LLM request timeout in seconds")

    # File handling
    max_file_size_mb: int = Field(default=100, description="Maximum upload file size in MB")
    upload_dir: str = Field(default="uploads", description="Temporary upload directory")
    output_dir: str = Field(default="outputs", description="Generated output directory")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000", description="Comma-separated allowed origins")

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    sentry_dsn: str = Field(default="", description="Sentry DSN for error tracking")

    # Session
    session_ttl_seconds: int = Field(default=3600, description="Session TTL in seconds")

    # Rate limiting
    rate_limit_uploads: str = Field(default="10/minute", description="Upload rate limit")
    rate_limit_pipelines: str = Field(default="5/minute", description="Pipeline rate limit")

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
