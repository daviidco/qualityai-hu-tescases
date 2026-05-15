"""ILLMProvider — Interface Segregation (SOLID-I).

Contrato mínimo para cualquier proveedor de LLM.
Permite sustituir GeminiProvider por GroqProvider, OllamaProvider, etc.
sin cambiar los agentes (SOLID-D).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ILLMProvider(ABC):

    @abstractmethod
    def generate(self, system_prompt: str, user_message: str) -> str:
        """Genera texto libre dado un par system/user."""
        ...

    @abstractmethod
    def generate_json(self, system_prompt: str, user_message: str) -> dict[str, Any]:
        """Genera y parsea una respuesta JSON. Lanza ValueError si el output es inválido."""
        ...

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        """Generación one-shot sin separación system/user. Usado por HyDEQueryExpander."""
        ...
