"""IReportGenerator — Interface Segregation (SOLID-I).

Un método, una responsabilidad: generar un reporte.
Permite agregar MarkdownReporter, PDFReporter, etc. sin cambiar el Orquestador.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..contracts.contract_a import RefinedRequirements
from ..contracts.contract_b import GherkinTestSuite
from ..contracts.contract_c import ExecutiveReport


class IReportGenerator(ABC):

    @abstractmethod
    def generate(
        self,
        contract_a: RefinedRequirements,
        contract_b: GherkinTestSuite,
        contract_c: ExecutiveReport,
        output_path: Path,
    ) -> Path:
        """Genera el reporte y devuelve el path del archivo generado."""
        ...
