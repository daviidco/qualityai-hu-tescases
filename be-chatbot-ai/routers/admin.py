"""Endpoints de administración: configuración del proveedor LLM (multi-key + orden de prioridad)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, status

from db import get_db
from dependencies import require_admin
from schemas import LLMConfigV2Out, LLMConfigV2Update, LLMKeyPreview, LLMProviderV2Out

router = APIRouter(tags=["Admin"])

_COLLECTION = "llm_config"
_DOC_ID = "llm_config"

_ALL_PROVIDERS = ["gemini", "groq", "cerebras", "deepseek"]

_DEFAULT_MODELS: dict[str, str] = {
    "gemini":   "gemini-2.0-flash",
    "groq":     "llama-3.3-70b-versatile",
    "cerebras": "llama3.1-8b",
    "deepseek": "deepseek-chat",
}

_GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]
_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "mixtral-8x7b-32768",
    "llama3-70b-8192",
]
_CEREBRAS_MODELS = [
    "llama-3.3-70b",
    "llama3.1-70b",
    "llama3.1-8b",
]
_DEEPSEEK_MODELS = [
    "deepseek-chat",
    "deepseek-reasoner",
]


@router.get("/admin/llm-config", response_model=LLMConfigV2Out)
async def get_llm_config(_admin: dict = Depends(require_admin)) -> LLMConfigV2Out:
    db = get_db()
    raw = await db[_COLLECTION].find_one({"_id": _DOC_ID}) or {}
    doc = _migrate(raw)
    return _build_out(doc)


@router.patch("/admin/llm-config", response_model=LLMConfigV2Out)
async def update_llm_config(
    req: LLMConfigV2Update,
    request: Request,
    _admin: dict = Depends(require_admin),
) -> LLMConfigV2Out:
    db = get_db()
    raw = await db[_COLLECTION].find_one({"_id": _DOC_ID}) or {}
    existing = _migrate(raw)
    existing_providers = existing.get("providers", {})

    # Validate order contains at least gemini
    if "gemini" not in req.provider_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini debe estar en el orden de proveedores (es requerido para embeddings)",
        )

    # Build updated providers
    new_providers: dict = {}
    for p in _ALL_PROVIDERS:
        pupdate = req.providers.get(p)
        old_keys: list[str] = existing_providers.get(p, {}).get("keys", [])
        old_model: str = existing_providers.get(p, {}).get("model", _DEFAULT_MODELS.get(p, ""))

        if pupdate is None:
            new_providers[p] = {"keys": old_keys, "model": old_model}
            continue

        rm_set = set(pupdate.remove_indices)
        kept = [k for i, k in enumerate(old_keys) if i not in rm_set]
        added = [k.strip() for k in pupdate.add_keys if k.strip()]
        new_providers[p] = {"keys": kept + added, "model": pupdate.model}

    # Validation: gemini must have at least 1 key
    if not new_providers.get("gemini", {}).get("keys"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API key es obligatoria (se usa siempre para embeddings)",
        )

    # Primary provider (first in order) must have at least 1 key
    primary = req.provider_order[0] if req.provider_order else "gemini"
    if not new_providers.get(primary, {}).get("keys"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El proveedor primario '{primary}' debe tener al menos una API key",
        )

    new_doc = {
        "_id": _DOC_ID,
        "provider_order": req.provider_order,
        "providers": new_providers,
        # backward-compat fields for pipeline hot-swap
        "active_provider": primary,
        "gemini_api_key": _first_key(new_providers, "gemini"),
        "gemini_generation_model": new_providers.get("gemini", {}).get("model", "gemini-2.0-flash"),
        "groq_api_key": _first_key(new_providers, "groq"),
        "groq_model": new_providers.get("groq", {}).get("model", "llama-3.3-70b-versatile"),
        "cerebras_api_key": _first_key(new_providers, "cerebras"),
        "cerebras_model": new_providers.get("cerebras", {}).get("model", "llama-3.3-70b"),
        "deepseek_api_key": _first_key(new_providers, "deepseek"),
        "deepseek_model": new_providers.get("deepseek", {}).get("model", "deepseek-chat"),
    }
    await db[_COLLECTION].replace_one({"_id": _DOC_ID}, new_doc, upsert=True)

    _apply_to_env(new_doc)

    try:
        from modulo3_quality_pipeline.llm.factory import create_provider_chain
        chain = create_provider_chain(new_doc)
        request.app.state.pipeline.swap_llm_provider(chain)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Config guardada pero falló el hot-swap del pipeline: {exc}",
        )

    return _build_out(new_doc)


@router.get("/admin/llm-models")
async def get_available_models(_admin: dict = Depends(require_admin)) -> dict:
    return {
        "gemini":   _GEMINI_MODELS,
        "groq":     _GROQ_MODELS,
        "cerebras": _CEREBRAS_MODELS,
        "deepseek": _DEEPSEEK_MODELS,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _first_key(providers: dict, p: str) -> str:
    keys = providers.get(p, {}).get("keys", [])
    return keys[0] if keys else ""


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 12:
        return "●" * len(key)
    return key[:6] + "…" + key[-4:]


def _migrate(doc: dict) -> dict:
    """Convert old single-key format to multi-key format transparently."""
    if "providers" in doc:
        return doc
    # Old format has active_provider + {p}_api_key flat fields
    providers: dict = {}
    for p in _ALL_PROVIDERS:
        key_field = "gemini_api_key" if p == "gemini" else f"{p}_api_key"
        model_field = "gemini_generation_model" if p == "gemini" else f"{p}_model"
        key = doc.get(key_field, "")
        model = doc.get(model_field, _DEFAULT_MODELS.get(p, ""))
        providers[p] = {"keys": [key] if key else [], "model": model}

    active = doc.get("active_provider", "gemini")
    order = [active] + [p for p in ["gemini", "groq", "cerebras", "deepseek"] if p != active]
    return {**doc, "provider_order": order, "providers": providers}


def _build_out(doc: dict) -> LLMConfigV2Out:
    providers_raw = doc.get("providers", {})
    out: dict[str, LLMProviderV2Out] = {}
    for p in _ALL_PROVIDERS:
        pdata = providers_raw.get(p, {})
        keys = pdata.get("keys", [])
        out[p] = LLMProviderV2Out(
            keys=[LLMKeyPreview(index=i, preview=_mask_key(k)) for i, k in enumerate(keys)],
            model=pdata.get("model", _DEFAULT_MODELS.get(p, "")),
        )
    return LLMConfigV2Out(
        provider_order=doc.get("provider_order", ["gemini", "groq", "cerebras"]),
        providers=out,
    )


def _apply_to_env(doc: dict) -> None:
    order = doc.get("provider_order", ["gemini"])
    os.environ["LLM_PROVIDER"] = order[0] if order else "gemini"
    os.environ["GEMINI_API_KEY"] = doc.get("gemini_api_key", "")
    os.environ["GEMINI_GENERATION_MODEL"] = doc.get("gemini_generation_model", "gemini-2.0-flash")
    if doc.get("groq_api_key"):
        os.environ["GROQ_API_KEY"] = doc["groq_api_key"]
    if doc.get("groq_model"):
        os.environ["GROQ_MODEL"] = doc["groq_model"]
    if doc.get("cerebras_api_key"):
        os.environ["CEREBRAS_API_KEY"] = doc["cerebras_api_key"]
    if doc.get("cerebras_model"):
        os.environ["CEREBRAS_MODEL"] = doc["cerebras_model"]
    if doc.get("deepseek_api_key"):
        os.environ["DEEPSEEK_API_KEY"] = doc["deepseek_api_key"]


def apply_llm_config_to_pipeline(pipeline: object, doc: dict) -> None:
    from modulo3_quality_pipeline.config import Settings

    new_settings = Settings(
        _env_file=None,
        llm_provider=doc.get("active_provider", "gemini"),
        gemini_api_key=doc.get("gemini_api_key", ""),
        gemini_generation_model=doc.get("gemini_generation_model", "gemini-2.0-flash"),
        groq_api_key=doc.get("groq_api_key", ""),
        groq_model=doc.get("groq_model", "llama-3.3-70b-versatile"),
        cerebras_api_key=doc.get("cerebras_api_key", ""),
        cerebras_model=doc.get("cerebras_model", "llama-3.3-70b"),
    )
    pipeline.swap_llm(new_settings)


def _swap_pipeline(request: Request, doc: dict) -> None:
    apply_llm_config_to_pipeline(request.app.state.pipeline, doc)
