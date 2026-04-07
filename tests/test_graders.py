

from __future__ import annotations

import pytest

from env.constants import Difficulty, RiskLevel
from env.graders import (
    budget_score,
    delivery_score,
    grade_by_difficulty,
    grade_episode,
    negotiation_score,
    quality_score,
    risk_score,
)
from env.models import (
    NegotiationResult,
    StakeholderProfile,
    TaskDefinition,
    Vendor,
    VendorContract,
)


def _make_vendor(**overrides) -> Vendor:
    defaults = dict(
        name="GoodVendor",
        category="test",
        base_price=10000.0,
        quality_rating=8.5,
        delivery_days=10,
        reliability_score=9.0,
        risk_level=RiskLevel.LOW,
        customer_rating=4.5,
        sustainability_score=7.0,
        is_blacklisted=False,
        contract=VendorContract(
            duration_months=12,
            compliance_certifications=["SOC2", "ISO27001"],
        ),
        negotiation_flexibility=0.3,
        max_discount_pct=10.0,
    )
    defaults.update(overrides)
    return Vendor(**defaults)


def _make_task(**overrides) -> TaskDefinition:
    defaults = dict(
        task_id="test-001",
        title="Test Task",
        description="A test procurement task.",
        difficulty=Difficulty.EASY,
        budget=50000.0,
        max_steps=10,
        vendor_ids=["GoodVendor"],
        optimal_vendor="GoodVendor",
        acceptable_vendors=["GoodVendor"],
    )
    defaults.update(overrides)
    return TaskDefinition(**defaults)


class TestSubScores:

    def test_budget_score_under_budget(self) -> None:
        vendor = _make_vendor(base_price=20000.0)
        score = budget_score(vendor, 50000.0)
        assert score > 0.5

    def test_budget_score_over_budget(self) -> None:
        vendor = _make_vendor(base_price=70000.0)
        score = budget_score(vendor, 50000.0)
        assert score < 0.3

    def test_budget_score_zero_budget(self) -> None:
        """When budget is zero, score should be small positive (0.01) not exact 0."""
        vendor = _make_vendor(base_price=1000.0)
        score = budget_score(vendor, 0.0)
        assert score == 0.01  # Scores must be > 0

    def test_quality_score_range(self) -> None:
        vendor = _make_vendor(quality_rating=7.0)
        score = quality_score(vendor)
        assert 0.0 <= score <= 1.0
        assert score == 0.7

    def test_delivery_score_fast(self) -> None:
        vendor = _make_vendor(delivery_days=1)
        score = delivery_score(vendor)
        assert score > 0.9

    def test_delivery_score_slow(self) -> None:
        vendor = _make_vendor(delivery_days=55)
        score = delivery_score(vendor)
        assert score < 0.2

    def test_risk_score_low_risk(self) -> None:
        vendor = _make_vendor(risk_level=RiskLevel.LOW)
        score = risk_score(vendor)
        assert score > 0.8

    def test_risk_score_critical(self) -> None:
        vendor = _make_vendor(risk_level=RiskLevel.CRITICAL)
        score = risk_score(vendor)
        assert score < 0.5

    def test_negotiation_score_no_history(self) -> None:
        assert negotiation_score([]) == 0.5

    def test_negotiation_score_all_accepted(self) -> None:
        """When all negotiations succeed, score should be high (0.99) not exact 1."""
        history = [
            NegotiationResult(vendor_name="X", round_number=1, accepted=True),
            NegotiationResult(vendor_name="X", round_number=2, accepted=True),
        ]
        assert negotiation_score(history) == 0.99  # Scores must be < 1


class TestFinalGrading:

    def test_no_vendor_scores_zero(self) -> None:
        """No vendor should score low (0.01) not exact 0."""
        task = _make_task()
        score, _ = grade_episode(None, 50000.0, task, [], [])
        assert score == 0.01  # Scores must be > 0

    def test_blacklisted_vendor_scores_zero(self) -> None:
        """Blacklisted vendor should score low (0.01) not exact 0."""
        vendor = _make_vendor(is_blacklisted=True)
        task = _make_task()
        score, _ = grade_episode(vendor, 50000.0, task, [], [])
        assert score == 0.01  # Scores must be > 0

    def test_optimal_vendor_scores_high(self) -> None:
        """Optimal vendor should score high but still strictly < 1."""
        vendor = _make_vendor(name="GoodVendor", base_price=20000.0)
        task = _make_task(optimal_vendor="GoodVendor")
        stakeholders = [
            StakeholderProfile(
                name="Finance",
                department="Finance",
                priority_weights={"cost": 0.5, "quality": 0.3, "delivery": 0.2},
            )
        ]
        score, breakdown = grade_episode(vendor, 50000.0, task, [], stakeholders)
        assert score > 0.6
        assert 0.0 < score < 1.0  # Strict inequality

    def test_grading_determinism(self) -> None:
        vendor = _make_vendor()
        task = _make_task()

        s1, b1 = grade_episode(vendor, 50000.0, task, [], [])
        s2, b2 = grade_episode(vendor, 50000.0, task, [], [])

        assert s1 == s2
        assert b1 == b2

    def test_grade_by_difficulty_dispatch(self) -> None:
        """Scores from all difficulty levels must be strictly between 0 and 1."""
        vendor = _make_vendor()
        task_easy = _make_task(difficulty=Difficulty.EASY)
        task_hard = _make_task(difficulty=Difficulty.HARD)

        s_easy, _ = grade_by_difficulty(Difficulty.EASY, vendor, 50000.0, task_easy, [], [])
        s_hard, _ = grade_by_difficulty(Difficulty.HARD, vendor, 50000.0, task_hard, [], [])

        assert 0.0 < s_easy < 1.0
        assert 0.0 < s_hard < 1.0

    def test_final_score_clamped(self) -> None:
        """Final scores must be strictly between 0 and 1."""
        vendor = _make_vendor(base_price=1.0, quality_rating=10.0, delivery_days=0)
        task = _make_task(optimal_vendor="GoodVendor")
        score, _ = grade_episode(vendor, 50000.0, task, [], [])
        assert 0.0 < score < 1.0  # Strict inequality
