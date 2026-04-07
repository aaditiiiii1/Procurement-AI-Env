

from __future__ import annotations

import pytest

from env.constants import RiskLevel, VendorStatus
from env.models import NegotiationResult, StakeholderProfile, Vendor, VendorContract
from env.reward import (
    compute_stakeholder_satisfaction,
    penalty_repeated_invalid,
    penalty_wasted_action,
    reward_reject_risky_vendor,
    reward_select_vendor,
    reward_shortlist_good_vendor,
    reward_successful_negotiation,
    reward_stakeholder_satisfaction,
)


def _make_vendor(
    name: str = "TestVendor",
    base_price: float = 10000.0,
    quality: float = 8.0,
    delivery_days: int = 14,
    risk_level: RiskLevel = RiskLevel.LOW,
    blacklisted: bool = False,
    lock_in: bool = False,
    data_portability: bool = True,
) -> Vendor:
    return Vendor(
        name=name,
        category="test",
        base_price=base_price,
        quality_rating=quality,
        delivery_days=delivery_days,
        reliability_score=8.0,
        risk_level=risk_level,
        customer_rating=4.0,
        sustainability_score=7.0,
        is_blacklisted=blacklisted,
        contract=VendorContract(
            duration_months=12,
            lock_in_risk=lock_in,
            data_portability=data_portability,
        ),
        negotiation_flexibility=0.5,
        max_discount_pct=15.0,
    )


class TestRewardHelpers:

    def test_shortlist_good_vendor_positive(self) -> None:
        vendor = _make_vendor(risk_level=RiskLevel.LOW)
        assert reward_shortlist_good_vendor(vendor) > 0

    def test_shortlist_risky_vendor_zero(self) -> None:
        vendor = _make_vendor(risk_level=RiskLevel.HIGH)
        assert reward_shortlist_good_vendor(vendor) == 0.0

    def test_reject_risky_vendor_positive(self) -> None:
        vendor = _make_vendor(risk_level=RiskLevel.HIGH)
        assert reward_reject_risky_vendor(vendor) > 0

    def test_reject_good_vendor_zero(self) -> None:
        vendor = _make_vendor(risk_level=RiskLevel.LOW)
        assert reward_reject_risky_vendor(vendor) == 0.0

    def test_reject_blacklisted_vendor_positive(self) -> None:
        vendor = _make_vendor(blacklisted=True)
        assert reward_reject_risky_vendor(vendor) > 0

    def test_successful_negotiation_reward(self) -> None:
        result = NegotiationResult(
            vendor_name="Test", round_number=1, accepted=True
        )
        assert reward_successful_negotiation(result) > 0

    def test_failed_negotiation_zero(self) -> None:
        result = NegotiationResult(
            vendor_name="Test", round_number=1, accepted=False
        )
        assert reward_successful_negotiation(result) == 0.0

    def test_select_within_budget_positive(self) -> None:
        vendor = _make_vendor(base_price=5000.0)
        r = reward_select_vendor(vendor, budget=10000.0, optimal_vendor_name="Other")
        assert r > 0

    def test_select_over_budget_negative(self) -> None:
        vendor = _make_vendor(base_price=20000.0)
        r = reward_select_vendor(vendor, budget=10000.0, optimal_vendor_name="Other")
        assert r < 0

    def test_select_blacklisted_heavy_penalty(self) -> None:
        vendor = _make_vendor(blacklisted=True)
        r = reward_select_vendor(vendor, budget=100000.0, optimal_vendor_name="Other")
        assert r <= -0.20

    def test_select_optimal_vendor_bonus(self) -> None:
        vendor = _make_vendor(name="Optimal", base_price=5000.0)
        r = reward_select_vendor(vendor, budget=10000.0, optimal_vendor_name="Optimal")
        # Should include both within-budget and optimal bonuses
        assert r >= 0.25

    def test_wasted_action_penalty(self) -> None:
        assert penalty_wasted_action() < 0

    def test_repeated_invalid_penalty(self) -> None:
        assert penalty_repeated_invalid() < penalty_wasted_action()


class TestStakeholderSatisfaction:

    def test_satisfaction_range(self) -> None:
        vendor = _make_vendor()
        stakeholders = [
            StakeholderProfile(
                name="Finance",
                department="Finance",
                priority_weights={"cost": 0.5, "quality": 0.3, "delivery": 0.2},
            )
        ]
        sat = compute_stakeholder_satisfaction(vendor, 20000.0, stakeholders)
        assert 0.0 <= sat <= 1.0

    def test_satisfaction_no_stakeholders(self) -> None:
        vendor = _make_vendor()
        sat = compute_stakeholder_satisfaction(vendor, 20000.0, [])
        assert sat == 0.5

    def test_cheap_vendor_satisfies_finance(self) -> None:
        vendor = _make_vendor(base_price=1000.0)
        stakeholders = [
            StakeholderProfile(
                name="Finance",
                department="Finance",
                priority_weights={"cost": 0.9, "quality": 0.05, "delivery": 0.05},
            )
        ]
        sat = compute_stakeholder_satisfaction(vendor, 20000.0, stakeholders)
        assert sat > 0.7
