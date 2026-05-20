"""Cliente HTTP hacia el backend FastAPI."""

import re

import httpx
import streamlit as st


# ── Helpers de auth ───────────────────────────────────────────────────────────

def _headers() -> dict:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _handle_401() -> None:
    st.session_state.token = None
    st.session_state.user_email = None
    st.session_state.user_role = None
    st.session_state.view = "login"
    st.rerun()


# ── Métodos HTTP ──────────────────────────────────────────────────────────────

def get(url: str, timeout: int = 30) -> dict | None:
    """GET al backend con token Bearer. Devuelve el JSON o None si hay error."""
    try:
        r = httpx.get(url, headers=_headers(), timeout=timeout)
        if r.status_code == 401:
            _handle_401()
            return None
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        _handle_http_error(exc)
    except Exception:
        return None
    return None


def post(url: str, payload: dict, timeout: int = 120,
         suppress_codes: tuple = ()) -> dict | None:
    """POST al backend con token Bearer. Devuelve el JSON o None si hay error.

    suppress_codes: HTTP status codes handled silently (error stored in
    st.session_state['_api_last_http_error'] but no st.error() shown).
    """
    try:
        r = httpx.post(url, json=payload, headers=_headers(), timeout=timeout)
        if r.status_code == 401:
            _handle_401()
            return None
        r.raise_for_status()
        return r.json()

    except httpx.ConnectError:
        st.error(
            "No se puede conectar al backend. "
            "¿Está corriendo `uvicorn main:app --reload` en el puerto 8000?"
        )
    except httpx.HTTPStatusError as exc:
        _handle_http_error(exc, suppress_display=exc.response.status_code in suppress_codes)
    except Exception as exc:
        st.error(f"Error inesperado: {exc}")

    return None


def post_login(url: str, payload: dict, timeout: int = 30) -> dict | None:
    """POST sin token (usado solo para /auth/login). Stores errors in session_state."""
    try:
        r = httpx.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            detail = exc.response.text[:200]
        if exc.response.status_code == 401:
            st.session_state["_login_err"] = "Correo o contraseña incorrectos."
        else:
            st.session_state["_login_err"] = f"Error ({exc.response.status_code}): {detail}"
    except httpx.ConnectError:
        st.session_state["_login_err"] = "No se puede conectar al servidor. ¿Está activo el backend?"
    except Exception as exc:
        st.session_state["_login_err"] = f"Error inesperado: {exc}"
    return None


def delete(url: str, timeout: int = 30) -> bool:
    """DELETE al backend con token Bearer. Devuelve True si exitoso."""
    try:
        r = httpx.delete(url, headers=_headers(), timeout=timeout)
        if r.status_code == 401:
            _handle_401()
            return False
        r.raise_for_status()
        return True
    except httpx.HTTPStatusError as exc:
        _handle_http_error(exc)
    except Exception as exc:
        st.error(f"Error: {exc}")
    return False


def get_bytes(url: str, timeout: int = 30) -> bytes | None:
    """GET que devuelve bytes crudos (imágenes, archivos). None en caso de error."""
    try:
        r = httpx.get(url, headers=_headers(), timeout=timeout)
        if r.status_code == 401:
            _handle_401()
            return None
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def upload_file(
    url: str,
    file_bytes: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    timeout: int = 30,
) -> dict | None:
    """POST multipart/form-data con un archivo. Devuelve JSON o None."""
    try:
        files = {"file": (filename, file_bytes, content_type)}
        r = httpx.post(url, files=files, headers=_headers(), timeout=timeout)
        if r.status_code == 401:
            _handle_401()
            return None
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        _handle_http_error(exc)
    except Exception as exc:
        st.error(f"Error subiendo archivo: {exc}")
    return None


def patch(url: str, payload: dict, timeout: int = 30) -> dict | None:
    """PATCH al backend con token Bearer."""
    try:
        r = httpx.patch(url, json=payload, headers=_headers(), timeout=timeout)
        if r.status_code == 401:
            _handle_401()
            return None
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        _handle_http_error(exc)
    except Exception as exc:
        st.error(f"Error: {exc}")
    return None


# ── Error handler ─────────────────────────────────────────────────────────────

def _handle_http_error(exc: httpx.HTTPStatusError, suppress_display: bool = False) -> None:
    detail = ""
    try:
        raw = exc.response.json().get("detail", "")
        detail = str(raw) if not isinstance(raw, str) else raw
    except Exception:
        detail = exc.response.text[:300]

    # Always store the last HTTP error so callers can inspect it.
    st.session_state["_api_last_http_error"] = {
        "status": exc.response.status_code,
        "detail": detail,
    }

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
    elif not suppress_display:
        st.error(f"Error del backend ({exc.response.status_code}): {detail[:300]}")
