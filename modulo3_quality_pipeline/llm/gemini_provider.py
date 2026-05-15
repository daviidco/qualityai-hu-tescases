"""GeminiProvider — implementación concreta de ILLMProvider.

Usa el nuevo SDK google-genai (google.genai) con gemini-2.0-flash.
JSON mode garantizado con response_mime_type="application/json".
Incluye exponential backoff para rate limit del tier gratuito (15 RPM).
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from json_repair import repair_json

from google import genai
from google.genai import types

from .interfaces import ILLMProvider
from ..config import Settings


class GeminiProvider(ILLMProvider):
    """Implementación Gemini del nuevo SDK. Sustituible por cualquier ILLMProvider."""

    def __init__(self, settings: Settings) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_generation_model
        self._temperature = settings.generation_temperature
        self._max_retries = settings.max_retries

        self._json_config = types.GenerateContentConfig(
            temperature=self._temperature,
            response_mime_type="application/json",
            max_output_tokens=8192,
        )
        self._text_config = types.GenerateContentConfig(
            temperature=self._temperature,
        )

    def generate(self, system_prompt: str, user_message: str) -> str:
        config = types.GenerateContentConfig(
            temperature=self._temperature,
            system_instruction=system_prompt,
        )
        response = self._call_with_backoff(
            lambda: self._client.models.generate_content(
                model=self._model,
                contents=user_message,
                config=config,
            )
        )
        return response.text

    def generate_json(self, system_prompt: str, user_message: str) -> dict[str, Any]:
        config = types.GenerateContentConfig(
            temperature=self._temperature,
            system_instruction=system_prompt,
            response_mime_type="application/json",
            max_output_tokens=8192,
        )
        response = self._call_with_backoff(
            lambda: self._client.models.generate_content(
                model=self._model,
                contents=user_message,
                config=config,
            )
        )
        raw = response.text
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return self._extract_json_fallback(raw)

    def generate_text(self, prompt: str) -> str:
        """One-shot sin system prompt — usado por HyDEQueryExpander."""
        response = self._call_with_backoff(
            lambda: self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=self._text_config,
            )
        )
        return response.text

    def _call_with_backoff(self, fn, base_wait: int = 15) -> Any:
        """Reintenta con exponential backoff en HTTP 429 por minuto y 5xx transitorios.

        No reintenta en cuota diaria agotada (PerDay) — fallar rápido con mensaje claro.
        Usa el retryDelay sugerido por la API cuando está disponible en el mensaje de error.
        """
        for attempt in range(self._max_retries):
            try:
                return fn()
            except Exception as e:
                err_str = str(e)

                # Cuota diaria agotada — reintentar no sirve de nada
                if "PerDay" in err_str or "per_day" in err_str.lower():
                    raise RuntimeError(
                        "Cuota diaria del free tier de Gemini agotada.\n"
                        "  → Espera hasta mañana (reset a medianoche hora del Pacífico)\n"
                        "  → O habilita billing en console.cloud.google.com para cuota pay-as-you-go\n"
                        "  → O usa una API key de otro proyecto Google Cloud\n"
                        f"  [error original: {err_str[:300]}]"
                    ) from e

                is_rate_limit = "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower()
                is_transient = "503" in err_str or "502" in err_str or "500" in err_str

                if (is_rate_limit or is_transient) and attempt < self._max_retries - 1:
                    match = re.search(r"retry in (\d+)", err_str, re.IGNORECASE)
                    wait = int(match.group(1)) + 5 if match else base_wait * (2 ** attempt)
                    label = "Rate limit por minuto" if is_rate_limit else "Error transitorio"
                    print(f"  [GeminiProvider] {label} — esperando {wait}s (intento {attempt + 1}/{self._max_retries})...")
                    time.sleep(wait)
                elif is_rate_limit:
                    match = re.search(r"retry in (\d+)", err_str, re.IGNORECASE)
                    retry_hint = f"Reintenta en ~{match.group(1)}s." if match else "Reintenta en unos minutos."
                    raise RuntimeError(
                        f"RATE_LIMIT: Gemini rate limit agotado tras {self._max_retries} intentos. {retry_hint}"
                    ) from e
                else:
                    raise

    @staticmethod
    def _extract_json_fallback(raw: str) -> dict[str, Any]:
        """Repara JSON malformado o truncado (p.ej. por límite de tokens)."""
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        start = cleaned.find("{")
        if start != -1:
            cleaned = cleaned[start:]
        repaired = repair_json(cleaned, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
        raise ValueError(f"No se pudo reparar el JSON de la respuesta: {raw[:200]}")
