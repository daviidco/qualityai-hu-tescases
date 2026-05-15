"""Módulo 3 — Quality Orchestrator.

Pipeline unificado e independiente que combina:
  - RequirementsAgent v5: refinamiento HITL con Gemini + RAG híbrido
  - TestArchitectAgent v4: generación de tests con EP/BVA/DT + ISO 25010
  - HybridRetriever: HyDE + BM25 + Dense + RRF + CrossEncoder
  - HtmlReporter: reporte ejecutivo combinado (Contract A + B + C)

Sin dependencias en modulo1_requirements_refiner ni modulo2_test_architect.
"""
