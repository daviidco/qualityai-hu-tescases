"""HyDEQueryExpander — Hypothetical Document Embeddings.

En lugar de embedear el query corto ("login seguro"), genera un documento
hipotético ideal (una historia de usuario completa o un patrón de testing)
y embedea ESO. El vector resultante está mucho más cerca de los documentos
del KB que el query corto original.

Referencia: Gao et al. 2022 — "Precise Zero-Shot Dense Retrieval without
Relevance Labels" (HyDE).
"""
from __future__ import annotations

from ..llm.interfaces import ILLMProvider


_STORIES_EXPANSION_PROMPT = """Eres un analista de requerimientos CMMI-DEV L3 de Katary Software (19 años de experiencia).
Genera UNA historia de usuario de referencia que sea ideal para el siguiente requerimiento.
Sé específico y concreto. Incluye métricas medibles.

Formato OBLIGATORIO (una sola historia):
"Como [rol específico], quiero [acción concreta y medible], para que [beneficio verificable].
Criterios: GIVEN [precondición concreta] WHEN [acción específica] THEN [resultado con métricas concretas]."

Solo la historia, sin explicaciones adicionales.

Requerimiento: {query}"""

_PATTERNS_EXPANSION_PROMPT = """Eres un experto QA de Katary Software con 19 años en testing de software.
Describe el patrón de testing ideal para el siguiente criterio de aceptación.
Sé específico sobre técnicas, escenarios y lecciones aprendidas en producción.

Formato OBLIGATORIO:
"Dominio: [categoría]. Técnicas: [EP/BVA/DT según aplique].
Escenarios típicos: [lista de 4-6 escenarios: positivo, negativo, frontera, error].
Lecciones Katary: [bugs de producción comunes en este dominio y cómo detectarlos]."

Solo el patrón, sin explicaciones adicionales.

Criterio: {query}"""


class HyDEQueryExpander:
    """Expande queries usando generación hipotética de documentos (HyDE).

    Responsabilidad única: solo expande queries (SOLID-S).
    Depende de ILLMProvider inyectado (SOLID-D).
    """

    def __init__(self, llm: ILLMProvider) -> None:
        self._llm = llm

    def expand_for_stories(self, query: str) -> str:
        """Genera una historia de usuario hipotética ideal para el query."""
        prompt = _STORIES_EXPANSION_PROMPT.format(query=query)
        return self._llm.generate_text(prompt)

    def expand_for_patterns(self, query: str) -> str:
        """Genera un patrón de testing hipotético ideal para el criterio."""
        prompt = _PATTERNS_EXPANSION_PROMPT.format(query=query)
        return self._llm.generate_text(prompt)
