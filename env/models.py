

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from env.constants import (
    ActionType,
    Difficulty,
    EpisodeTerminationReason,
    RiskLevel,
    VendorStatus,
)


# Vendor & Contract

class VendorContract(BaseModel):

    duration_months: int = Field(..., ge=1, description="Contract duration in months.")
    auto_renewal: bool = Field(False, description="Whether the contract auto-renews.")
    renewal_price_increase_pct: float = Field(
        0.0, ge=0.0, description="Percentage price hike on renewal."
    )
    termination_fee_pct: float = Field(
        0.0, ge=0.0, description="Early-termination fee as a percentage of contract value."
    )
    sla_uptime_pct: float = Field(
        99.0, ge=0.0, le=100.0, description="Guaranteed uptime SLA percentage."
    )
    penalty_clauses: List[str] = Field(default_factory=list)
    hidden_fees: Dict[str, float] = Field(
        default_factory=dict, description="Hidden fees keyed by fee name -> USD amount."
    )
    compliance_certifications: List[str] = Field(default_factory=list)
    data_portability: bool = Field(True, description="Whether data export is supported.")
    lock_in_risk: bool = Field(False, description="True if the contract creates vendor lock-in.")


class Vendor(BaseModel):

    name: str = Field(..., min_length=1)
    category: str = Field(...)
    base_price: float = Field(..., gt=0, description="Base quoted price in USD.")
    quality_rating: float = Field(..., ge=0.0, le=10.0)
    delivery_days: int = Field(..., ge=0)
    reliability_score: float = Field(..., ge=0.0, le=10.0)
    risk_level: RiskLevel = Field(...)
    customer_rating: float = Field(..., ge=0.0, le=5.0)
    sustainability_score: float = Field(0.0, ge=0.0, le=10.0)
    is_blacklisted: bool = Field(False)
    contract: VendorContract = Field(...)
    negotiation_flexibility: float = Field(
        0.0, ge=0.0, le=1.0, description="0 = rigid, 1 = very flexible."
    )
    max_discount_pct: float = Field(0.0, ge=0.0, le=50.0)
    status: VendorStatus = Field(VendorStatus.AVAILABLE)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Vendor name must not be blank.")
        return v.strip()


# Stakeholder

class StakeholderProfile(BaseModel):

    name: str = Field(...)
    department: str = Field(...)
    priority_weights: Dict[str, float] = Field(
        ..., description="Criteria -> importance weights (e.g. {'cost': 0.4, 'quality': 0.3})."
    )
    notes: str = Field("")


# Action / Observation / Reward

class Action(BaseModel):

    action_type: ActionType = Field(...)
    vendor_name: Optional[str] = Field(None)
    message: Optional[str] = Field(None)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("vendor_name")
    @classmethod
    def vendor_name_strip(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class NegotiationResult(BaseModel):

    vendor_name: str = Field(...)
    round_number: int = Field(..., ge=1)
    requested_discount_pct: float = Field(0.0)
    offered_discount_pct: float = Field(0.0)
    accepted: bool = Field(False)
    new_price: Optional[float] = Field(None)
    message: str = Field("")
    contract_changes: Dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):

    task_id: str = Field(...)
    task_difficulty: Difficulty = Field(...)
    task_description: str = Field("")
    budget: float = Field(..., ge=0.0)
    remaining_steps: int = Field(..., ge=0)
    vendors: List[Vendor] = Field(default_factory=list)
    negotiation_history: List[NegotiationResult] = Field(default_factory=list)
    shortlisted_vendors: List[str] = Field(default_factory=list)
    rejected_vendors: List[str] = Field(default_factory=list)
    stakeholder_priorities: List[StakeholderProfile] = Field(default_factory=list)
    current_reward: float = Field(0.0)
    selected_vendor: Optional[str] = Field(None)
    finalized: bool = Field(False)
    termination_reason: EpisodeTerminationReason = Field(
        EpisodeTerminationReason.NOT_TERMINATED,
    )
    comparison_result: Optional[Dict[str, Any]] = Field(None)
    clarification_response: Optional[str] = Field(None)
    messages: List[str] = Field(default_factory=list)


class Reward(BaseModel):

    step_reward: float = Field(0.0)
    cumulative_reward: float = Field(0.0)
    breakdown: Dict[str, float] = Field(default_factory=dict)


# Task Definition

class TaskDefinition(BaseModel):

    task_id: str = Field(...)
    title: str = Field(...)
    description: str = Field(...)
    difficulty: Difficulty = Field(...)
    budget: float = Field(..., gt=0)
    max_steps: int = Field(..., gt=0)
    vendor_ids: List[str] = Field(...)
    stakeholder_ids: List[str] = Field(default_factory=list)
    optimal_vendor: str = Field(...)
    acceptable_vendors: List[str] = Field(default_factory=list)
    category: str = Field("general")
    notes: str = Field("")


# Environment State

class EnvironmentState(BaseModel):

    task_id: str = Field(...)
    difficulty: Difficulty = Field(...)
    step_count: int = Field(0, ge=0)
    remaining_steps: int = Field(0, ge=0)
    budget: float = Field(0.0)
    cumulative_reward: float = Field(0.0)
    shortlisted_vendors: List[str] = Field(default_factory=list)
    rejected_vendors: List[str] = Field(default_factory=list)
    selected_vendor: Optional[str] = None
    finalized: bool = False
    termination_reason: EpisodeTerminationReason = EpisodeTerminationReason.NOT_TERMINATED
    negotiation_history: List[NegotiationResult] = Field(default_factory=list)
    invalid_action_count: int = Field(0, ge=0)
    vendors: List[Vendor] = Field(default_factory=list)
    stakeholder_priorities: List[StakeholderProfile] = Field(default_factory=list)


# API Responses

class ResetResponse(BaseModel):
    observation: Observation
    info: Dict[str, Any] = Field(default_factory=dict)


class StepResponse(BaseModel):
    observation: Observation
    reward: Reward
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    environment: str = "ProcurementAI-Env"


class TaskListResponse(BaseModel):
    tasks: List[TaskDefinition]
    total: int
