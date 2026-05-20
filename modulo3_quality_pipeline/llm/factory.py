"""LLMFactory — crea el ILLMProvider correcto según la configuración.

Funciones públicas:
  create_llm(settings)          → proveedor único (Settings-based, modo legado)
  create_provider_chain(doc)    → FallbackLLMProvider desde doc MongoDB con multi-key + orden
"""
from __future__ import annotations

from .interfaces import ILLMProvider
from ..config import Settings

_PROVIDERS = ("gemini", "groq", "deepseek", "cerebras")

_DEFAULT_MODELS: dict[str, str] = {
    "gemini":   "gemini-2.0-flash",
    "groq":     "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
    "cerebras": "llama3.1-8b",
}


def create_llm(settings: Settings) -> ILLMProvider:
    """Crea un proveedor único. Usado internamente y para modo standalone."""
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


def create_provider_chain(doc: dict) -> "FallbackLLMProvider":
    """Construye un FallbackLLMProvider desde el documento MongoDB llm_config.

    Itera sobre provider_order; por cada proveedor itera sobre sus keys.
    El orden de la cadena es: [p0_key0, p0_key1, p1_key0, p1_key1, ...].
    Si ningún proveedor tiene keys configuradas lanza RuntimeError.
    """
    from .fallback_provider import FallbackLLMProvider

    order: list[str] = doc.get("provider_order", ["gemini"])
    providers_data: dict = doc.get("providers", {})

    # La key de Gemini es necesaria para todos (embeddings siempre usan Gemini)
    gemini_keys: list[str] = providers_data.get("gemini", {}).get("keys", [])
    gemini_key_for_embed = gemini_keys[0] if gemini_keys else ""

    chain: list[tuple[str, ILLMProvider]] = []
    chain_meta: list[dict] = []

    for pname in order:
        pdata = providers_data.get(pname, {})
        keys: list[str] = [k for k in pdata.get("keys", []) if k and k.strip()]
        model: str = pdata.get("model", _DEFAULT_MODELS.get(pname, ""))

        for i, key in enumerate(keys):
            label = f"{pname}[{i}]"
            try:
                settings = _settings_for(pname, key, model, gemini_key_for_embed)
                provider = create_llm(settings)
                chain.append((label, provider))
                chain_meta.append({"label": label, "provider": pname, "model": model})
                print(f"  ✅ Proveedor en cadena: {label} — modelo={model}")
            except Exception as exc:  # noqa: BLE001
                print(f"  ⚠️  No se pudo inicializar {label}: {exc}")

    if not chain:
        raise RuntimeError(
            "La cadena de proveedores está vacía. "
            "Configura al menos una API key en la pantalla de Configuración de Modelos LLM."
        )

    return FallbackLLMProvider(chain, chain_meta=chain_meta)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _settings_for(provider: str, key: str, model: str, gemini_embed_key: str) -> Settings:
    """Crea un Settings mínimo para un (provider, key) específico.
    _env_file=None — no lee el archivo .env; los kwargs tienen prioridad sobre os.environ.
    """
    kwargs: dict = {
        "_env_file": None,
        "llm_provider": provider,
        # Gemini key siempre presente (el embedder la necesita aunque no sea proveedor activo)
        "gemini_api_key": gemini_embed_key,
        "gemini_generation_model": _DEFAULT_MODELS["gemini"],
        "groq_api_key": "",
        "groq_model": _DEFAULT_MODELS["groq"],
        "deepseek_api_key": "",
        "deepseek_model": _DEFAULT_MODELS["deepseek"],
        "cerebras_api_key": "",
        "cerebras_model": _DEFAULT_MODELS["cerebras"],
    }
    # Sobreescribir la key y modelo del proveedor activo
    if provider == "gemini":
        kwargs["gemini_api_key"] = key
        kwargs["gemini_generation_model"] = model
    elif provider == "groq":
        kwargs["groq_api_key"] = key
        kwargs["groq_model"] = model
    elif provider == "deepseek":
        kwargs["deepseek_api_key"] = key
        kwargs["deepseek_model"] = model
    elif provider == "cerebras":
        kwargs["cerebras_api_key"] = key
        kwargs["cerebras_model"] = model

    return Settings(**kwargs)  # type: ignore[call-arg]
