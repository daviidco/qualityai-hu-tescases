"""LLMFactory — crea el ILLMProvider correcto según LLM_PROVIDER en config.

Uso:
    LLM_PROVIDER=gemini   → GeminiProvider  (default)
    LLM_PROVIDER=groq     → GroqProvider
    LLM_PROVIDER=deepseek → DeepSeekProvider
    LLM_PROVIDER=cerebras → CerebrasProvider
"""
from __future__ import annotations

from .interfaces import ILLMProvider
from ..config import Settings

_PROVIDERS = ("gemini", "groq", "deepseek", "cerebras")


def create_llm(settings: Settings) -> ILLMProvider:
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(settings)

    if provider == "groq":
        from .groq_provider import GroqProvider
        return GroqProvider(settings)

    if provider == "deepseek":
        from .deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(settings)

    if provider == "cerebras":
        from .cerebras_provider import CerebrasProvider
        return CerebrasProvider(settings)

    raise ValueError(
        f"LLM_PROVIDER='{provider}' no reconocido. Opciones: {', '.join(_PROVIDERS)}"
    )
