"""Cliente HTTP hacia el backend FastAPI."""

import re

import httpx
import streamlit as st


def get(url: str, timeout: int = 30) -> dict | None:
    """GET al backend. Devuelve el JSON o None si hay error."""
    try:
        r = httpx.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def post(url: str, payload: dict, timeout: int = 120) -> dict | None:
    """POST al backend. Devuelve el JSON o None si hay error."""
    try:
        r = httpx.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()

    except httpx.ConnectError:
        st.error(
            "No se puede conectar al backend. "
            "¿Está corriendo `uvicorn main:app --reload` en el puerto 8000?"
        )

    except httpx.HTTPStatusError as exc:
        _handle_http_error(exc)

    except Exception as exc:
        st.error(f"Error inesperado: {exc}")

    return None


def _handle_http_error(exc: httpx.HTTPStatusError) -> None:
    detail = ""
    try:
        detail = exc.response.json().get("detail", "")
    except Exception:
        detail = exc.response.text[:300]

    is_rate_limit = (
        exc.response.status_code == 429
        or "rate limit" in detail.lower()
        or "rate_limit" in detail.lower()
        or "ratelimit" in detail.lower()
    )

    if is_rate_limit:
        match = re.search(
            r"(?:try again in|Reintenta en ~?)\s*([\d]+m[\d.]+s|[\d]+s|[\d]+m|unos minutos)",
            detail, re.IGNORECASE,
        )
        retry_in = match.group(1).strip() if match else "unos minutos"
        st.session_state.rate_limit_error = {
            "retry_in": retry_in,
            "detail": detail[:200],
        }
    else:
        st.error(f"Error del backend ({exc.response.status_code}): {detail[:300]}")
