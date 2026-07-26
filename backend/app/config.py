"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "scoutai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Groq Cloud
    GROQ_API_KEY: str = ""

    # Tavily Search
    TAVILY_API_KEY: str = ""

    # Resend Email
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "ScoutAI <onboarding@resend.dev>"

    # JWT Auth
    JWT_SECRET: str = "scoutai-super-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 72

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # Shared secret an external scheduler (e.g. cron-job.org) must send
    # to trigger POST /api/cron/tick. Empty disables the endpoint.
    CRON_SECRET: str = ""

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def get_llm(temperature: float = 0.7, model: str = None, groq_api_key: str | None = None):
    """Helper to return a ChatOpenAI instance pointed at Groq's OpenAI-compatible endpoint.

    Groq is the sole LLM provider: `langchain_openai.ChatOpenAI` is used as a
    generic OpenAI-protocol client, not because OpenAI itself is called.
    `groq_api_key` lets a caller use a user's own Groq key instead of the
    shared app-level one; falls back to GROQ_API_KEY when omitted.
    """
    from langchain_openai import ChatOpenAI
    settings = get_settings()
    key = groq_api_key or settings.GROQ_API_KEY
    if not key:
        raise RuntimeError("No Groq API key configured (set GROQ_API_KEY or a per-user key)")
    return ChatOpenAI(
        model=model or "llama-3.3-70b-versatile",
        api_key=key,
        base_url="https://api.groq.com/openai/v1",
        temperature=temperature,
    )

