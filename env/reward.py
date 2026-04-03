

from __future__ import annotations

import logging
from typing import Dict, List

from env.constants import (
    PENALTY_EXCEED_BUDGET,
    PENALTY_REPEATED_INVALID_ACTION,
    PENALTY_SELECT_BLACKLISTED,
    PENALTY_SELECT_RISKY_VENDOR,
    PENALTY_WASTED_ACTION,
    REWARD_REJECT_RISKY_VENDOR,
    REWARD_SELECT_OPTIMAL_VENDOR,
    REWARD_SELECT_WITHIN_BUDGET,
    REWARD_SHORTLIST_GOOD_VENDOR,
    REWARD_STAKEHOLDER_SATISFACTION,
    REWARD_SUCCESSFUL_NEGOTIATION,
)
from env.models import NegotiationResult, Reward, StakeholderProfile, Vendor
from env.utils import clamp, safe_task_score
from env.vendor_logic import (
    compute_total_vendor_cost,
    is_blacklisted,
    is_risky_vendor,
)

logger = logging.getLogger("procurement_env.reward")


# Step-level rewards

def reward_shortlist_good_vendor(vendor: Vendor) -> float:
    if not is_risky_vendor(vendor) and not is_blacklisted(vendor):
        return REWARD_SHORTLIST_GOOD_VENDOR
    return 0.0


def reward_reject_risky_vendor(vendor: Vendor) -> float:
    if is_risky_vendor(vendor) or is_blacklisted(vendor):
        return REWARD_REJECT_RISKY_VENDOR
    return 0.0


def reward_successful_negotiation(result: NegotiationResult) -> float:
    return REWARD_SUCCESSFUL_NEGOTIATION if result.accepted else 0.0


def reward_select_vendor(
    vendor: Vendor,
    budget: float,
    optimal_vendor_name: str,
) -> float:
    total = 0.0

    if is_blacklisted(vendor):
        return PENALTY_SELECT_BLACKLISTED

    if is_risky_vendor(vendor):
        total += PENALTY_SELECT_RISKY_VENDOR

    vendor_cost = compute_total_vendor_cost(vendor)
    if vendor_cost <= budget:
        total += REWARD_SELECT_WITHIN_BUDGET
    else:
        total += PENALTY_EXCEED_BUDGET

    if vendor.name == optimal_vendor_name:
        total += REWARD_SELECT_OPTIMAL_VENDOR

    return total


def penalty_wasted_action() -> float:
    return PENALTY_WASTED_ACTION


def penalty_repeated_invalid() -> float:
    return PENALTY_REPEATED_INVALID_ACTION


# Stakeholder satisfaction

def compute_stakeholder_satisfaction(
    vendor: Vendor,
    budget: float,
    stakeholders: List[StakeholderProfile],
    max_delivery_days: int = 60,
) -> float:
    if not stakeholders:
        return 0.5

    vendor_cost = compute_total_vendor_cost(vendor)
    from env.vendor_logic import risk_score as _risk_score

    scores_map = {
        "cost": clamp(1.0 - vendor_cost / max(budget, 1.0)),
        "quality": vendor.quality_rating / 10.0,
        "delivery": clamp(1.0 - vendor.delivery_days / max(max_delivery_days, 1)),
        "risk": _risk_score(vendor),
        "sustainability": vendor.sustainability_score / 10.0,
    }

    total_sat = 0.0
    for sh in stakeholders:
        weighted = 0.0
        weight_sum = 0.0
        for criterion, weight in sh.priority_weights.items():
            if criterion in scores_map:
                weighted += weight * scores_map[criterion]
                weight_sum += weight
        total_sat += (weighted / weight_sum) if weight_sum > 0 else 0.5

    result = clamp(total_sat / len(stakeholders))
    # Ensure score is strictly between 0 and 1
    return safe_task_score(result)


def reward_stakeholder_satisfaction(
    vendor: Vendor,
    budget: float,
    stakeholders: List[StakeholderProfile],
) -> float:
    sat = compute_stakeholder_satisfaction(vendor, budget, stakeholders)
    return REWARD_STAKEHOLDER_SATISFACTION * sat


# Reward aggregator

def build_step_reward(
    step_reward: float,
    cumulative: float,
    breakdown: Dict[str, float],
) -> Reward:
    return Reward(
        step_reward=round(step_reward, 4),
        cumulative_reward=round(cumulative + step_reward, 4),
        breakdown=breakdown,
    )
