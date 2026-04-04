

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from env.constants import (
    GRADER_WEIGHT_BUDGET,
    GRADER_WEIGHT_DELIVERY,
    GRADER_WEIGHT_NEGOTIATION,
    GRADER_WEIGHT_QUALITY,
    GRADER_WEIGHT_RISK,
    GRADER_WEIGHT_STAKEHOLDER,
    Difficulty,
)
from env.models import (
    NegotiationResult,
    StakeholderProfile,
    TaskDefinition,
    Vendor,
)
from env.reward import compute_stakeholder_satisfaction
from env.utils import clamp, safe_task_score
from env.vendor_logic import (
    compute_total_vendor_cost,
    delivery_score as _vendor_delivery_score,
    quality_score as _vendor_quality_score,
    risk_score as _vendor_risk_score,
)

logger = logging.getLogger("procurement_env.graders")


# Sub-scores

def budget_score(vendor: Vendor, budget: float) -> float:
    total_cost = compute_total_vendor_cost(vendor)
    if budget <= 0:
        return 0.01
    ratio = total_cost / budget
    if ratio <= 0.6:
        return 0.99
    if ratio >= 1.2:
        return 0.01
    return clamp(1.0 - (ratio - 0.6) / 0.6)


def quality_score(vendor: Vendor) -> float:
    return _vendor_quality_score(vendor)


def delivery_score(vendor: Vendor, max_days: int = 60) -> float:
    return _vendor_delivery_score(vendor, max_days)


def risk_score(vendor: Vendor) -> float:
    return _vendor_risk_score(vendor)


def negotiation_score(negotiation_history: List[NegotiationResult]) -> float:
    if not negotiation_history:
        return 0.5
    accepted = sum(1 for n in negotiation_history if n.accepted)
    score = clamp(accepted / len(negotiation_history))
    # Ensure score is strictly between 0 and 1
    if score <= 0:
        return 0.01
    if score >= 1:
        return 0.99
    return score


def stakeholder_satisfaction_score(
    vendor: Vendor,
    budget: float,
    stakeholders: List[StakeholderProfile],
) -> float:
    return compute_stakeholder_satisfaction(vendor, budget, stakeholders)


# Final grading

_ZERO_BREAKDOWN = {
    "budget_score": 0.01,
    "quality_score": 0.01,
    "delivery_score": 0.01,
    "risk_score": 0.01,
    "negotiation_score": 0.01,
    "stakeholder_score": 0.01,
}


def grade_episode(
    vendor: Optional[Vendor],
    budget: float,
    task: TaskDefinition,
    negotiation_history: List[NegotiationResult],
    stakeholders: List[StakeholderProfile],
) -> Tuple[float, Dict[str, float]]:
    if vendor is None:
        return 0.01, dict(_ZERO_BREAKDOWN)

    if vendor.is_blacklisted:
        return 0.01, dict(_ZERO_BREAKDOWN)

    bs = budget_score(vendor, budget)
    qs = quality_score(vendor)
    ds = delivery_score(vendor)
    rs = risk_score(vendor)
    ns = negotiation_score(negotiation_history)
    ss = stakeholder_satisfaction_score(vendor, budget, stakeholders)

    final = (
        bs * GRADER_WEIGHT_BUDGET
        + qs * GRADER_WEIGHT_QUALITY
        + ds * GRADER_WEIGHT_DELIVERY
        + rs * GRADER_WEIGHT_RISK
        + ns * GRADER_WEIGHT_NEGOTIATION
        + ss * GRADER_WEIGHT_STAKEHOLDER
    )
    final = clamp(final)

    # Bonus/penalty for optimal vs non-acceptable vendor
    if vendor.name == task.optimal_vendor:
        final = clamp(final + 0.05)
    elif vendor.name not in task.acceptable_vendors:
        final = clamp(final - 0.10)

    breakdown = {
        "budget_score": round(bs * GRADER_WEIGHT_BUDGET, 4),
        "quality_score": round(qs * GRADER_WEIGHT_QUALITY, 4),
        "delivery_score": round(ds * GRADER_WEIGHT_DELIVERY, 4),
        "risk_score": round(rs * GRADER_WEIGHT_RISK, 4),
        "negotiation_score": round(ns * GRADER_WEIGHT_NEGOTIATION, 4),
        "stakeholder_score": round(ss * GRADER_WEIGHT_STAKEHOLDER, 4),
    }

    # Ensure final score is strictly between 0 and 1
    final = safe_task_score(final)

    logger.info("Episode graded: final=%.4f breakdown=%s", final, breakdown)
    return round(safe_task_score(final), 4), breakdown


# Difficulty-specific graders

def grade_easy(
    vendor: Optional[Vendor],
    budget: float,
    task: TaskDefinition,
    negotiation_history: List[NegotiationResult],
    stakeholders: List[StakeholderProfile],
) -> Tuple[float, Dict[str, float]]:
    return grade_episode(vendor, budget, task, negotiation_history, stakeholders)


def grade_medium(
    vendor: Optional[Vendor],
    budget: float,
    task: TaskDefinition,
    negotiation_history: List[NegotiationResult],
    stakeholders: List[StakeholderProfile],
) -> Tuple[float, Dict[str, float]]:
    return grade_episode(vendor, budget, task, negotiation_history, stakeholders)


def grade_hard(
    vendor: Optional[Vendor],
    budget: float,
    task: TaskDefinition,
    negotiation_history: List[NegotiationResult],
    stakeholders: List[StakeholderProfile],
) -> Tuple[float, Dict[str, float]]:
    score, breakdown = grade_episode(
        vendor, budget, task, negotiation_history, stakeholders
    )

    # Extra penalty for missing critical compliance certs in hard mode
    if vendor is not None and not vendor.is_blacklisted:
        certs = set(vendor.contract.compliance_certifications)
        required_hard = {"SOC2", "ISO27001"}
        missing = required_hard - certs
        if missing:
            compliance_penalty = 0.05 * len(missing)
            score = clamp(score - compliance_penalty)
            breakdown["compliance_penalty"] = round(-compliance_penalty, 4)

    return round(safe_task_score(score), 4), breakdown


def grade_by_difficulty(
    difficulty: Difficulty,
    vendor: Optional[Vendor],
    budget: float,
    task: TaskDefinition,
    negotiation_history: List[NegotiationResult],
    stakeholders: List[StakeholderProfile],
) -> Tuple[float, Dict[str, float]]:
    dispatch = {
        Difficulty.EASY: grade_easy,
        Difficulty.MEDIUM: grade_medium,
        Difficulty.HARD: grade_hard,
    }
    grader = dispatch.get(difficulty, grade_episode)
    return grader(vendor, budget, task, negotiation_history, stakeholders)
