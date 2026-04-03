

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from env.constants import RiskLevel, VendorStatus
from env.models import Vendor

logger = logging.getLogger("procurement_env.vendor_logic")


def compute_total_vendor_cost(vendor: Vendor) -> float:
    hidden_total = sum(vendor.contract.hidden_fees.values())
    total = vendor.base_price + hidden_total
    if hidden_total > 0:
        logger.debug(
            "Vendor '%s' has $%.2f in hidden fees (total: $%.2f)",
            vendor.name, hidden_total, total,
        )
    return total


def estimate_delivery_risk(vendor: Vendor, required_days: int = 30) -> Tuple[bool, str]:
    if vendor.delivery_days <= required_days:
        return True, f"{vendor.name} can deliver in {vendor.delivery_days} days (within {required_days}-day window)."
    shortfall = vendor.delivery_days - required_days
    return False, (
        f"{vendor.name} needs {vendor.delivery_days} days - "
        f"{shortfall} days over the {required_days}-day requirement."
    )


def delivery_score(vendor: Vendor, max_days: int = 60) -> float:
    score = max(0.0, 1.0 - vendor.delivery_days / max(max_days, 1))
    # Ensure score is strictly between 0 and 1
    if score <= 0:
        return 0.01
    if score >= 1:
        return 0.99
    return score


def is_risky_vendor(vendor: Vendor) -> bool:
    if vendor.is_blacklisted:
        return True
    if vendor.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return True
    if vendor.contract.lock_in_risk and not vendor.contract.data_portability:
        return True
    return False


def risk_score(vendor: Vendor) -> float:
    score = 1.0

    risk_penalties: Dict[RiskLevel, float] = {
        RiskLevel.LOW: 0.0,
        RiskLevel.MEDIUM: 0.15,
        RiskLevel.HIGH: 0.35,
        RiskLevel.CRITICAL: 0.60,
    }
    score -= risk_penalties.get(vendor.risk_level, 0.0)

    if vendor.is_blacklisted:
        score -= 0.30
    if vendor.contract.lock_in_risk:
        score -= 0.10
    if not vendor.contract.data_portability:
        score -= 0.10
    if vendor.contract.hidden_fees:
        score -= 0.05 * min(len(vendor.contract.hidden_fees), 4)
    if vendor.contract.termination_fee_pct > 10.0:
        score -= 0.05
    if len(vendor.contract.penalty_clauses) > 1:
        score -= 0.05

    score = max(0.0, min(1.0, score))
    if score <= 0:
        return 0.01
    if score >= 1:
        return 0.99
    return score


def quality_score(vendor: Vendor) -> float:
    score = vendor.quality_rating / 10.0
    # Ensure score is strictly between 0 and 1
    if score <= 0:
        return 0.01
    if score >= 1:
        return 0.99
    return score


def reliability_score_norm(vendor: Vendor) -> float:
    score = vendor.reliability_score / 10.0
    if score <= 0:
        return 0.01
    if score >= 1:
        return 0.99
    return score


def sustainability_score(vendor: Vendor) -> float:
    score = vendor.sustainability_score / 10.0
    if score <= 0:
        return 0.01
    if score >= 1:
        return 0.99
    return score


def is_blacklisted(vendor: Vendor) -> bool:
    return vendor.is_blacklisted


def has_required_certifications(
    vendor: Vendor, required: List[str]
) -> Tuple[bool, List[str]]:
    held = set(vendor.contract.compliance_certifications)
    missing = [c for c in required if c not in held]
    return len(missing) == 0, missing


def compare_vendors(vendors: List[Vendor]) -> List[Dict]:
    rows = []
    for v in vendors:
        total_cost = compute_total_vendor_cost(v)
        rows.append({
            "name": v.name,
            "base_price": v.base_price,
            "total_cost": total_cost,
            "hidden_fees_total": total_cost - v.base_price,
            "quality_rating": v.quality_rating,
            "delivery_days": v.delivery_days,
            "reliability_score": v.reliability_score,
            "risk_level": v.risk_level.value,
            "customer_rating": v.customer_rating,
            "sustainability_score": v.sustainability_score,
            "is_blacklisted": v.is_blacklisted,
            "lock_in_risk": v.contract.lock_in_risk,
            "data_portability": v.contract.data_portability,
            "certifications": v.contract.compliance_certifications,
            "status": v.status.value,
        })
    return rows


def get_available_vendors(vendors: List[Vendor]) -> List[Vendor]:
    return [v for v in vendors if v.status == VendorStatus.AVAILABLE]


def get_shortlisted_vendors(vendors: List[Vendor]) -> List[Vendor]:
    return [v for v in vendors if v.status == VendorStatus.SHORTLISTED]
