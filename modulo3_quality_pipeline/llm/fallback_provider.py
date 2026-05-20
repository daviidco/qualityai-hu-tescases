"""FallbackLLMProvider — encadena múltiples proveedores en orden de prioridad.

Itera sobre la lista en orden (proveedor 1 key 1, proveedor 1 key 2, proveedor 2 key 1, ...)
y avanza al siguiente cuando uno falla. Sólo lanza RuntimeError si TODOS fallan.
"""
from __future__ import annotations

import logging
from typing import Any

from .interfaces import ILLMProvider

logger = logging.getLogger(__name__)


class FallbackLLMProvider(ILLMProvider):
    """Wraps an ordered list of (label, ILLMProvider) and falls back on any exception."""

    def __init__(self, chain: list[tuple[str, ILLMProvider]]) -> None:
        if not chain:
            raise ValueError("FallbackLLMProvider necesita al menos un proveedor en la cadena.")
        self._chain = chain
        print(
            f"🔗 FallbackLLMProvider — cadena de {len(chain)} proveedor(es): "
            + " → ".join(label for label, _ in chain)
        )

    def _try_all(self, method: str, *args: Any) -> Any:
        last_exc: Exception | None = None
        for label, provider in self._chain:
            try:
                return getattr(provider, method)(*args)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Proveedor '%s' falló en %s (%s: %s). Intentando siguiente…",
                    label, method, type(exc).__name__, exc,
                )
                print(f"  ⚠️  {label} falló: {type(exc).__name__}: {exc}. Intentando siguiente…")
                last_exc = exc
        raise RuntimeError(
            f"Todos los proveedores ({len(self._chain)}) fallaron. "
            f"Último error: {type(last_exc).__name__}: {last_exc}"
        ) from last_exc

    def generate(self, system_prompt: str, user_message: str) -> str:
        return self._try_all("generate", system_prompt, user_message)

    def generate_json(self, system_prompt: str, user_message: str) -> dict[str, Any]:
        return self._try_all("generate_json", system_prompt, user_message)

    def generate_text(self, prompt: str) -> str:
        return self._try_all("generate_text", prompt)
