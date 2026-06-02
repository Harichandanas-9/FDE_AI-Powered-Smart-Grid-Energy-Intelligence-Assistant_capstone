"""Centralized configuration via pydantic-settings."""
from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    app_name: str = Field(default="Smart Grid AI Assistant")
    app_env: Literal["development", "production"] = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    app_log_level: str = Field(default="INFO")

    # --- CORS ---
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    # --- Paths ---
    data_dir: str = Field(default="./datasets")
    chroma_persist_dir: str = Field(default="./chroma_store")

    # --- Embeddings / Models ---
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    reranker_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    fastembed_model: str = Field(default="BAAI/bge-small-en-v1.5")

    # --- LLM ---
    llm_provider: Literal["groq", "gemini", "openai", "anthropic", "ollama", "template"] = Field(default="groq")
    llm_model: str = Field(default="llama-3.3-70b-versatile")
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_model_large: str = Field(default="llama-3.3-70b-versatile")
    groq_model_small: str = Field(default="llama-3.1-8b-instant")
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-1.5-flash")
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    ollama_base_url: str = Field(default="http://localhost:11434")

    # LLM fallback chain: comma-separated, tried in order.
    # Supported: groq_large, groq_small, groq, openai, openai_mini, anthropic, gemini
    llm_fallback_chain: str = Field(default="groq_large")

    # --- Retrieval ---
    retrieval_top_k: int = Field(default=20)
    final_top_k: int = Field(default=5)
    rrf_semantic_weight: float = Field(default=0.6)
    rrf_keyword_weight: float = Field(default=0.4)
    reranker_enabled: bool = Field(default=False)

    # CRAG: reformulate + retry when top score < threshold (0.0 = disabled).
    crag_relevance_threshold: float = Field(default=0.0)

    # --- Semantic cache ---
    semantic_cache_threshold: float = Field(default=0.92)
    semantic_cache_max_items: int = Field(default=500)

    # --- LangSmith tracing (optional) ---
    langchain_tracing_v2: bool = Field(default=False)
    langchain_api_key: str = Field(default="")
    langchain_endpoint: str = Field(default="https://api.smith.langchain.com")
    langchain_project: str = Field(default="smart-grid-energy-assistant")

    # --- Multi-tenancy + JWT ---
    multi_tenancy_enabled: bool = Field(default=False)
    jwt_secret: str = Field(default="change-me-in-production-min-32-chars-long")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiry_minutes: int = Field(default=480)
    demo_users: str = Field(
        default=(
            '{"admin":{"password":"admin","tenant_id":"default","role":"admin"},'
            '"acme":{"password":"acme123","tenant_id":"acme","role":"engineer"},'
            '"globex":{"password":"globex123","tenant_id":"globex","role":"engineer"}}'
        )
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def demo_users_dict(self) -> dict:
        import json
        try:
            return json.loads(self.demo_users)
        except (ValueError, TypeError):
            return {}

    @field_validator("app_log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
