"""GroqProvider — implementación de ILLMProvider usando el SDK de Groq.

JSON mode via response_format={"type": "json_object"} (soportado en llama-3.3-70b).
Incluye exponential backoff para rate limit del tier gratuito.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from json_repair import repair_json

from groq import Groq

from .interfaces import ILLMProvider
from ..config import Settings


class GroqProvider(ILLMProvider):
    """Implementación Groq. Sustituible por GeminiProvider vía ILLMProvider."""

    def __init__(self, settings: Settings) -> None:
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_model
        self._temperature = settings.generation_temperature
        self._max_retries = settings.max_retries

    def generate(self, system_prompt: str, user_message: str) -> str:
        response = self._call_with_backoff(
            lambda: self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
        )
        return response.choices[0].message.content

    def generate_json(self, system_prompt: str, user_message: str) -> dict[str, Any]:
        response = self._call_with_backoff(
            lambda: self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                max_tokens=32768,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
        )
        raw = response.choices[0].message.content
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return self._extract_json_fallback(raw)

    def generate_text(self, prompt: str) -> str:
        response = self._call_with_backoff(
            lambda: self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        return response.choices[0].message.content

    def _call_with_backoff(self, fn, base_wait: int = 15) -> Any:
        for attempt in range(self._max_retries):
            try:
                return fn()
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower() or "rate limit" in err_str.lower()
                is_transient = "503" in err_str or "502" in err_str or "500" in err_str

                if (is_rate_limit or is_transient) and attempt < self._max_retries - 1:
                    match = re.search(r"try again in ([\d.]+)s", err_str, re.IGNORECASE)
                    wait = int(float(match.group(1))) + 2 if match else base_wait * (2 ** attempt)
                    label = "Rate limit" if is_rate_limit else "Error transitorio"
                    print(f"  [GroqProvider] {label} — esperando {wait}s (intento {attempt + 1}/{self._max_retries})...")
                    time.sleep(wait)
                elif is_rate_limit:
                    match = re.search(r"try again in ([\d.]+)s", err_str, re.IGNORECASE)
                    retry_hint = f"Reintenta en ~{int(float(match.group(1)))}s." if match else "Reintenta en unos minutos."
                    raise RuntimeError(
                        f"RATE_LIMIT: Groq rate limit agotado tras {self._max_retries} intentos. "
                        f"{retry_hint} (modelo: {self._model})"
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
