"""Contract A — Refined Requirements.

Evolución independiente de Module 1 Contract A.
Mejoras: rag_sources en UserStory, confidence_score en AmbiguityResolution.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class StoryType(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    TECHNICAL = "technical"


class AcceptanceCriterion(BaseModel):
    id: str = Field(..., description="Patrón AC-NNN")
    description: str = Field(..., min_length=20)
    given: str = Field(..., min_length=5)
    when: str = Field(..., min_length=5)
    then: str = Field(..., min_length=5)
    test_data_examples: list[dict] = Field(default_factory=list)
    is_negative_case: bool = False
    boundary_values: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_ac_id(cls, v: str) -> str:
        if not re.match(r"^AC-\d{3}$", v):
            raise ValueError(f"El id del criterio debe tener formato AC-NNN, recibido: {v}")
        return v


class AmbiguityResolution(BaseModel):
    original_text: str
    issue: str
    resolution: str
    assumption_made: bool = False
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="1.0 = analista validó, <1.0 = LLM asumió con cierta certeza",
    )


class UserStory(BaseModel):
    id: str = Field(..., description="Patrón US-NNN")
    title: str = Field(..., min_length=10)
    story_type: StoryType
    priority: Priority
    as_a: str = Field(..., min_length=3)
    i_want: str = Field(..., min_length=5)
    so_that: str = Field(..., min_length=5)
    acceptance_criteria: list[AcceptanceCriterion] = Field(..., min_length=1)
    business_rules: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    ui_elements: list[str] = Field(default_factory=list)
    api_endpoints: list[str] = Field(default_factory=list)
    ambiguities_resolved: list[AmbiguityResolution] = Field(default_factory=list)
    rag_sources: list[str] = Field(
        default_factory=list,
        description="IDs de historias del KB que influyeron en la generación",
    )

    @field_validator("id")
    @classmethod
    def validate_us_id(cls, v: str) -> str:
        if not re.match(r"^US-\d{3}$", v):
            raise ValueError(f"El id de la historia debe tener formato US-NNN, recibido: {v}")
        return v


class RefinedRequirements(BaseModel):
    pipeline_run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = "requirements_agent"
    agent_version: str = "5.0.0"
    created_at: datetime = Field(default_factory=datetime.now)
    original_requirements_text: str
    project_context: str
    user_stories: list[UserStory] = Field(..., min_length=1)
    total_ambiguities_found: int = 0
    total_assumptions_made: int = 0
    coverage_notes: Optional[str] = None
