"""CLI entry point y Dependency Injection wiring de Módulo 3.

Wiring de dependencias (SOLID-D):
    Toda la construcción de objetos concretos ocurre AQUÍ.
    Los agentes y el pipeline solo conocen interfaces.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_retrievers(settings, embedder, query_expander):
    from .rag.repository import KnowledgeRepository
    from .rag.retriever import HybridRetriever

    retriever_kwargs = dict(
        embedder=embedder,
        query_expander=query_expander,
        bm25_top_k=settings.rag_bm25_top_k,
        dense_top_k=settings.rag_dense_top_k,
        rrf_k=settings.rag_rrf_k,
    )

    stories_repo = KnowledgeRepository(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.stories_collection_name,
        embedder=embedder,
    )
    patterns_repo = KnowledgeRepository(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.patterns_collection_name,
        embedder=embedder,
    )

    if stories_repo.count() == 0:
        print(f"  📚 Indexando KB de historias desde {settings.stories_kb_path}...")
        stories_repo.load_stories_from_json(settings.stories_kb_path)
    else:
        print(f"  ✅ KB historias: {stories_repo.count()} chunks ya indexados")

    if patterns_repo.count() == 0:
        print(f"  📚 Indexando KB de patrones desde {settings.patterns_kb_path}...")
        patterns_repo.load_patterns_from_json(settings.patterns_kb_path)
    else:
        print(f"  ✅ KB patrones: {patterns_repo.count()} chunks ya indexados")

    return (
        HybridRetriever(repository=stories_repo, **retriever_kwargs),
        HybridRetriever(repository=patterns_repo, **retriever_kwargs),
    )


def build_pipeline(settings):
    """Construye el pipeline completo con inyección de dependencias."""
    from .llm.factory import create_llm
    from .rag.embedder import GeminiEmbedder
    from .rag.query_expander import HyDEQueryExpander
    from .rag.reranker import CrossEncoderReranker
    from .agents.requirements_agent import RequirementsAgent
    from .agents.test_architect_agent import TestArchitectAgent
    from .reporting.html_reporter import HtmlReporter
    from .pipeline import QualityPipeline

    print("🔧 Inicializando pipeline...")

    llm = create_llm(settings)
    _model_map = {
        "groq": settings.groq_model,
        "deepseek": settings.deepseek_model,
        "cerebras": settings.cerebras_model,
    }
    _model_name = _model_map.get(settings.llm_provider, settings.gemini_generation_model)
    print(f"  ✅ LLM: [{settings.llm_provider}] {_model_name}")

    embedder = GeminiEmbedder(model_name=settings.gemini_embedding_model, api_key=settings.gemini_api_key)
    print(f"  ✅ Embedder: {settings.gemini_embedding_model} ({embedder.dimension}-dim)")

    query_expander = HyDEQueryExpander(llm)
    stories_retriever, patterns_retriever = _build_retrievers(settings, embedder, query_expander)

    reranker = CrossEncoderReranker(model_name=settings.reranker_model)
    print(f"  ✅ Reranker: {settings.reranker_model}")

    return QualityPipeline(
        requirements_agent=RequirementsAgent(llm=llm, retriever=stories_retriever, reranker=reranker, settings=settings),
        test_agent=TestArchitectAgent(llm=llm, retriever=patterns_retriever, reranker=reranker, settings=settings),
        reporter=HtmlReporter(),
        settings=settings,
    )


def _read_requirement(args) -> str | None:
    """Devuelve el requerimiento leído o None si está vacío."""
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"❌ Archivo no encontrado: {args.input}")
            return None
        text = input_path.read_text(encoding="utf-8").strip()
        print(f"\n📄 Requerimiento leído desde: {args.input}")
        return text

    print("\n" + "=" * 60)
    print("🔬 QualityAI — Módulo 3 — Pipeline Unificado")
    print("=" * 60)
    print("\nIngresa el requerimiento a analizar (Enter dos veces para terminar):\n")
    lines: list[str] = []
    try:
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines).strip() or None


def main() -> int:
    """Entry point del CLI."""
    parser = argparse.ArgumentParser(
        description="QualityAI Módulo 3 — Pipeline Unificado con Gemini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python -m modulo3_quality_pipeline
  python -m modulo3_quality_pipeline --auto
  python -m modulo3_quality_pipeline --auto --input reqs/login.txt
        """,
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Modo automático: deshabilita HITL (sin revisión interactiva de ambigüedades)",
    )
    parser.add_argument(
        "--input",
        type=str,
        metavar="FILE",
        help="Ruta a archivo .txt con el requerimiento a procesar",
    )
    args = parser.parse_args()

    module_dir = Path(__file__).parent
    env_file = module_dir / ".env"

    try:
        from .config import Settings
        settings = Settings(_env_file=str(env_file))  # type: ignore[call-arg]
    except ValueError as e:
        print(f"❌ Error de configuración: {e}")
        print(f"   Asegúrate de tener un archivo .env en {module_dir}")
        print("   Copia .env.example como .env y agrega tu GEMINI_API_KEY")
        return 1

    requirement = _read_requirement(args)
    if not requirement:
        print("❌ El requerimiento está vacío.")
        return 1

    print(f"\n📝 Requerimiento ({len(requirement)} chars):")
    print(f"   {requirement[:100]}{'...' if len(requirement) > 100 else ''}")

    interactive = not args.auto
    reviewer_name = ""
    if interactive:
        print()
        try:
            reviewer_name = input("Identificador del revisor (ej: ana.garcia): ").strip()
        except EOFError:
            pass

    try:
        pipeline = build_pipeline(settings)
        results = pipeline.run(requirement, interactive=interactive, reviewer_name=reviewer_name)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"\n❌ Error en el pipeline: {exc}")
        return 1

    print("\n📦 Artefactos generados:")
    for key, path in results.items():
        if key != "pipeline_run_id":
            print(f"   {key}: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
