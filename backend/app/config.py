"""Application configuration — reads from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- LLM (optional — rule-based flows work without it) ---
    # Options: "huggingface" (DeepSeek via HF Inference Providers) | "ollama" (free, local)
    #          | "gemini" (free tier) | "openai" | "anthropic"
    LLM_PROVIDER: str = "ollama"

    # Hugging Face Inference Providers (OpenAI-compatible router; model runs
    # server-side — nothing is downloaded). Token comes from .env / env only.
    HF_TOKEN: str = ""
    HF_MODEL: str = "deepseek-ai/DeepSeek-V4.1-Flash"
    HF_BASE_URL: str = "https://router.huggingface.co/v1"
    # Optional fallback provider used when the primary LLM fails/missing.
    LLM_FALLBACK_PROVIDER: str = ""

    # Ollama (free, local — no API key needed)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # Google Gemini free tier
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # OpenAI (paid — fallback only)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Anthropic (paid — fallback only)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # --- Embeddings (free, local — no API key) ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # --- App ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    DEBUG: bool = False  # production default; flip via env for local dev only

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
