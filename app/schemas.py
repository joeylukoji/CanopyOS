from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Ratio = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Action(StrEnum):
    PLANT_TREES = "PLANT_TREES"
    GREEN_WALL = "GREEN_WALL"
    PERMEABLE_PAVEMENT = "PERMEABLE_PAVEMENT"
    BIOSWALE = "BIOSWALE"
    SOLAR_SHADE_CANOPY = "SOLAR_SHADE_CANOPY"
    NO_INTERVENTION = "NO_INTERVENTION"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class Metrics(BaseModel):
    vegetation_percentage: Ratio
    hard_surface_percentage: Ratio
    building_percentage: Ratio
    open_ground_percentage: Ratio
    classified_coverage: Ratio
    tree_presence: bool
    green_score: int = Field(ge=0, le=100)
    priority: Literal["LOW", "MEDIUM", "HIGH"]


class Alternative(BaseModel):
    action: Action
    score: Ratio


class Decision(BaseModel):
    recommended_action: Action
    confidence: Ratio | None = None
    alternatives: list[Alternative] = Field(default_factory=list)
    source: Literal["jev", "rules_fallback"]
    note: str


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=1400)
    main_reasons: list[str] = Field(max_length=4)
    possible_benefits: list[str] = Field(max_length=3)
    disclaimer: str
    source: Literal["gemma", "template_fallback"]


class Report(BaseModel):
    metrics: Metrics
    decision: Decision
    explanation: Explanation
    assets: dict[str, str]
    vision_model: str
    elapsed_seconds: float
