"""FallbackLLMProvider — encadena múltiples proveedores en orden de prioridad.

Itera sobre la lista en orden (proveedor 1 key 1, proveedor 1 key 2, proveedor 2 key 1, ...)
y avanza al siguiente cuando uno falla. Sólo lanza RuntimeError si TODOS fallan.

Expone `current_label`, `chain_meta` y `skip_current()` para que el frontend
pueda mostrar qué proveedor está activo y permitir saltar al siguiente.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from .interfaces import ILLMProvider

logger = logging.getLogger(__name__)


class FallbackLLMProvider(ILLMProvider):
    """Wraps an ordered list of (label, ILLMProvider) and falls back on any exception."""

    def __init__(
        self,
        chain: list[tuple[str, ILLMProvider]],
        chain_meta: list[dict] | None = None,
    ) -> None:
        if not chain:
            raise ValueError("FallbackLLMProvider necesita al menos un proveedor en la cadena.")
        self._chain = chain
        # chain_meta: [{"label": "groq[0]", "provider": "groq", "model": "llama-3.3-70b-versatile"}, ...]
        self.chain_meta: list[dict] = chain_meta or [
            {"label": lbl, "provider": lbl.split("[")[0], "model": "?"}
            for lbl, _ in chain
        ]
        self.current_label: str = chain[0][0]
        self._skip_count: int = 0   # número de proveedores a omitir desde el inicio
        self._lock = threading.Lock()
        print(
            f"🔗 FallbackLLMProvider — cadena de {len(chain)} proveedor(es): "
            + " → ".join(lbl for lbl, _ in chain)
        )

    # ── Public API para el frontend ───────────────────────────────────────────

    def skip_current(self) -> None:
        """Avanza el puntero de inicio de la cadena. Thread-safe."""
        with self._lock:
            self._skip_count = min(self._skip_count + 1, len(self._chain) - 1)

    def reset_skip(self) -> None:
        """Resetea el puntero al inicio de la cadena (llamar entre ejecuciones)."""
        with self._lock:
            self._skip_count = 0

    # ── Core: intenta todos los proveedores en orden ──────────────────────────

    def _try_all(self, method: str, *args: Any) -> Any:
        with self._lock:
            skip = self._skip_count

        # Empieza desde el proveedor seleccionado; los anteriores quedan como
        # último recurso al final de la cadena (wrap-around).
        reordered = self._chain[skip:] + self._chain[:skip]

        last_exc: Exception | None = None
        for label, provider in reordered:
            self.current_label = label
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
