"""Unified LLM client — supports Ollama (free/local), Gemini (free tier), OpenAI, Anthropic."""

from __future__ import annotations
import httpx
from app.config import get_settings


def _ollama_complete(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    settings = get_settings()
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    resp = httpx.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120.0)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _gemini_complete(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    settings = get_settings()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    resp = httpx.post(url, json=payload, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _openai_complete(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    from openai import OpenAI
    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL, max_tokens=max_tokens, temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content


def _anthropic_complete(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    import anthropic
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=settings.ANTHROPIC_MODEL, max_tokens=max_tokens, temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text


def _huggingface_complete(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    """DeepSeek (or any HF chat model) via the Hugging Face Inference Providers
    OpenAI-compatible router. The model runs server-side — nothing is downloaded.
    The HF token is read from settings only and is never logged or returned."""
    import json as _json

    settings = get_settings()
    if not settings.HF_TOKEN:
        raise ValueError("HF_TOKEN not set")
    resp = httpx.post(
        f"{settings.HF_BASE_URL.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.HF_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.HF_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            # DeepSeek-V4.1-Flash is a REASONING model: it emits hidden
            # reasoning_content before the answer, so the budget must cover
            # both or the visible content comes back empty.
            "max_tokens": max(max_tokens, 1200),
            "temperature": temperature,
        },
        timeout=90.0,
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        msg = data["choices"][0]["message"] or {}
        content = (msg.get("content") or "").strip()
        if not content:
            # Reasoning models can spend the whole budget reasoning; if any
            # reasoning text exists, surface that rather than silently
            # returning an empty answer (it usually contains the conclusion).
            content = (msg.get("reasoning_content") or "").strip()
        if not content:
            raise ValueError("HF model returned an empty completion (reasoning budget exhausted)")
        return content
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected HF router response shape: {exc}") from exc


def _providers() -> dict:
    settings = get_settings()
    return {
        "huggingface": _huggingface_complete,
        "ollama": _ollama_complete,
        "gemini": _gemini_complete,
        "openai": _openai_complete,
        "anthropic": _anthropic_complete,
    }


def llm_complete(system_prompt: str, user_prompt: str, *, max_tokens: int = 2048, temperature: float = 0.3) -> str:
    """Run the configured provider, with optional one-level fallback.

    Fallback chain: LLM_PROVIDER -> LLM_FALLBACK_PROVIDER (if configured).
    Raises the last error when no provider succeeds — callers own their
    deterministic fallbacks (the app never hard-fails on LLM errors).
    """
    import logging

    settings = get_settings()
    registry = _providers()
    chain: list[str] = [settings.LLM_PROVIDER.lower()]
    if settings.LLM_FALLBACK_PROVIDER:
        fb = settings.LLM_FALLBACK_PROVIDER.lower()
        if fb not in chain:
            chain.append(fb)

    last_exc: Exception | None = None
    for i, provider in enumerate(chain):
        fn = registry.get(provider)
        if fn is None:
            last_exc = ValueError(f"Unknown provider: {provider}")
            continue
        try:
            out = fn(system_prompt, user_prompt, max_tokens, temperature)
            if i > 0:
                logging.getLogger("setu.llm").info("llm fallback used", extra={"fallback_provider": provider})
            return out
        except Exception as exc:  # noqa: BLE001 — fallback is the point
            last_exc = exc
            # Never log tokens or full prompts; provider + error class only.
            logging.getLogger("setu.llm").warning(
                "llm provider failed", extra={"provider": provider, "error": type(exc).__name__}
            )
    assert last_exc is not None
    raise last_exc
