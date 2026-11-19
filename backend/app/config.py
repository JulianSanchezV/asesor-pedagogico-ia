from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Asesor Pedagógico Inteligente"
    DATABASE_URL: str = "sqlite:///./asesor_ia.db"
    SECRET_KEY: str = "dev-secret-key-change-in-production-asesor-pedagogico-ia-2026"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # AI Provider configuration (cloud or local)
    AI_PROVIDER: str = "gemini"  # gemini | groq | openrouter | ollama
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"

    OPENAI_COMPAT_API_KEY: str = ""
    OPENAI_COMPAT_BASE_URL: str = "https://api.groq.com/openai/v1"
    OPENAI_COMPAT_MODEL: str = "llama-3.3-70b-versatile"

    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"

    # Sandbox configuration
    SANDBOX_MODE: str = "subprocess"  # subprocess | docker
    SANDBOX_TIMEOUT_SECONDS: int = 15
    SANDBOX_MEMORY_MB: int = 256

    # File storage configuration
    STORAGE_MODE: str = "local"  # local | supabase
    LOCAL_UPLOAD_DIR: str = "./uploads"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_BUCKET: str = "submissions"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
