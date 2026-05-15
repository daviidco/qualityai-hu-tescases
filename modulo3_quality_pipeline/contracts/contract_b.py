"""Contract B — Gherkin Test Suite.

Evolución independiente de Module 2 Contract B.
Mejora: rag_pattern_ids en GherkinScenario para trazabilidad al patrón KB.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    EDGE_CASE = "edge_case"
    ERROR_HANDLING = "error_handling"


class QualityCharacteristic(str, Enum):
    FUNCTIONAL_SUITABILITY = "functional_suitability"
    PERFORMANCE_EFFICIENCY = "performance_efficiency"
    COMPATIBILITY = "compatibility"
    USABILITY = "usability"
    RELIABILITY = "reliability"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    PORTABILITY = "portability"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CHANGES = "needs_changes"


class GherkinStep(BaseModel):
    keyword: str = Field(..., description="Given | When | Then | And | But")
    text: str = Field(..., min_length=5)


class ExamplesTable(BaseModel):
    headers: list[str]
    rows: list[list[str]]


class GherkinScenario(BaseModel):
    name: str = Field(..., min_length=10)
    scenario_type: ScenarioType
    quality_characteristic: QualityCharacteristic
    tags: list[str] = Field(default_factory=list)
    steps: list[GherkinStep] = Field(..., min_length=3)
    is_outline: bool = False
    examples: Optional[ExamplesTable] = None
    acceptance_criterion_id: str
    user_story_id: str
    heuristic_applied: str = Field(
        default="general",
        description="EP | BVA | DT | general",
    )
    rag_pattern_ids: list[str] = Field(
        default_factory=list,
        description="IDs de patrones KB que influyeron en la generación del escenario",
    )


class GherkinFeature(BaseModel):
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    background: Optional[list[GherkinStep]] = None
    scenarios: list[GherkinScenario] = Field(..., min_length=1)
    user_story_id: str


class ReviewChange(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    reviewer: str
    action: str
    notes: Optional[str] = None


class ReviewMetadata(BaseModel):
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    version: int = 1
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    analyst_feedback: Optional[str] = None
    change_history: list[ReviewChange] = Field(default_factory=list)


class CoverageMatrix(BaseModel):
    user_story_id: str
    criterion_id: str
    scenario_names: list[str] = Field(default_factory=list)
    coverage_type: list[ScenarioType] = Field(default_factory=list)
    quality_characteristics_covered: list[QualityCharacteristic] = Field(default_factory=list)


class GherkinTestSuite(BaseModel):
    pipeline_run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = "test_architect_agent"
    agent_version: str = "4.0.0"
    created_at: datetime = Field(default_factory=datetime.now)

    features: list[GherkinFeature] = Field(..., min_length=1)
    coverage_matrix: list[CoverageMatrix] = Field(default_factory=list)
    review: ReviewMetadata = Field(default_factory=ReviewMetadata)

    total_scenarios: int = 0
    total_positive: int = 0
    total_negative: int = 0
    total_boundary: int = 0
    uncovered_criteria: list[str] = Field(default_factory=list)
    coverage_by_characteristic: dict[str, int] = Field(default_factory=dict)
