from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM — defaults to placeholder until API key provided day-of
    anthropic_api_key: str = ""
    llm_provider: str = "placeholder"   # ← switch to "anthropic" when key arrives
    llm_model: str = "claude-sonnet-4-20250514"

    # Storage
    chroma_path: str = "./data/chroma"
    sqlite_path: str = "./data/chat.db"

    # Server
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # Eval data
    eval_csv_path: str = "./data/eval-ca-vehicle-code.csv"  # ← required by seed_csv.py
    eval_provider: str = "llm_judge"                        # "llm_judge" | "ragas"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
