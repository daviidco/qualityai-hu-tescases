from pathlib import Path

from pydantic_settings import BaseSettings

_MODULE_DIR = Path(__file__).parent


class Settings(BaseSettings):
    # ── Selector de proveedor ─────────────────────────────────────────────────
    llm_provider: str = "gemini"          # "gemini" | "groq"

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_generation_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    embedding_dimensions: int = 3072

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # ── DeepSeek ──────────────────────────────────────────────────────────────
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # ── Cerebras ──────────────────────────────────────────────────────────────
    cerebras_api_key: str = ""
    cerebras_model: str = "llama3.1-8b"

    chroma_persist_dir: str = str(_MODULE_DIR / "chroma_db_m3")
    stories_collection_name: str = "m3_stories_chunked"
    patterns_collection_name: str = "m3_patterns_chunked"

    stories_kb_path: str = str(_MODULE_DIR / "knowledge_bases" / "stories_kb.json")
    patterns_kb_path: str = str(_MODULE_DIR / "knowledge_bases" / "patterns_kb.json")

    rag_bm25_top_k: int = 20
    rag_dense_top_k: int = 20
    rag_rrf_k: int = 60
    rag_reranker_top_n: int = 5
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    generation_temperature: float = 0.3
    max_retries: int = 3
    output_dir: str = str(_MODULE_DIR / "output")

    # ── Modo eco ──────────────────────────────────────────────────────────────
    eco_mode: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
