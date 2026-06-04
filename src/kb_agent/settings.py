from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    use_openai: bool = Field(default=False, alias="KB_AGENT_USE_OPENAI")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4.1-mini", alias="OPENROUTER_MODEL")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    use_openrouter: bool = Field(default=True, alias="KB_AGENT_USE_OPENROUTER")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")
    graph_mode: str = Field(default="neo4j", alias="KB_AGENT_GRAPH_MODE")

    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")
    data_dir: Path = Field(default=Path("./data/raw"), alias="DATA_DIR")
    embedding_dimensions: int = Field(default=128, alias="EMBEDDING_DIMENSIONS")

    @property
    def mock_mode(self) -> bool:
        return self.graph_mode.lower() in {"memory", "mock", "demo"}

    @property
    def llm_enabled(self) -> bool:
        return bool(self.use_openrouter and self.openrouter_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
