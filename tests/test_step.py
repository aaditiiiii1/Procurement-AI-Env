

from __future__ import annotations

import pytest

from env.constants import ActionType, Difficulty, EpisodeTerminationReason, VendorStatus
from env.models import Action
from env.procurement_env import ProcurementEnv


class TestStep:

    def _make_env(self, task_id: str = "easy-001") -> ProcurementEnv:
        env = ProcurementEnv(seed=42)
        env.reset(task_id=task_id)
        return env

    def test_step_without_reset_raises(self) -> None:
        env = ProcurementEnv(seed=42)
        with pytest.raises(RuntimeError, match="not been reset"):
            env.step(Action(action_type=ActionType.COMPARE_VENDORS))

    def test_shortlist_vendor(self) -> None:
        env = self._make_env()
        action = Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name="TechVault Solutions")
        obs, reward, done, info = env.step(action)

        assert "TechVault Solutions" in obs.shortlisted_vendors
        assert reward.step_reward >= 0

    def test_reject_vendor(self) -> None:
        env = self._make_env()
        action = Action(action_type=ActionType.REJECT_VENDOR, vendor_name="BudgetByte Hardware")
        obs, reward, done, info = env.step(action)

        assert "BudgetByte Hardware" in obs.rejected_vendors

    def test_negotiate_vendor(self) -> None:
        env = self._make_env()
        action = Action(
            action_type=ActionType.NEGOTIATE_VENDOR,
            vendor_name="TechVault Solutions",
            message="Can you offer a 5% discount for bulk purchase?",
            parameters={"requested_discount_pct": 5.0},
        )
        obs, reward, done, info = env.step(action)

        assert len(obs.negotiation_history) == 1
        assert obs.negotiation_history[0].vendor_name == "TechVault Solutions"

    def test_compare_vendors(self) -> None:
        env = self._make_env()
        action = Action(action_type=ActionType.COMPARE_VENDORS)
        obs, reward, done, info = env.step(action)

        assert obs.comparison_result is not None
        assert "vendors" in obs.comparison_result

    def test_select_and_finalize(self) -> None:
        env = self._make_env()

        # Select
        obs, _, done, _ = env.step(
            Action(action_type=ActionType.SELECT_VENDOR, vendor_name="TechVault Solutions")
        )
        assert obs.selected_vendor == "TechVault Solutions"
        assert done is False

        # Finalize
        obs, _, done, info = env.step(
            Action(action_type=ActionType.FINALIZE_DECISION)
        )
        assert done is True
        assert obs.finalized is True
        assert "final_score" in info
        assert 0.0 <= info["final_score"] <= 1.0

    def test_remaining_steps_decrease(self) -> None:
        env = self._make_env()
        obs = env.reset(task_id="easy-001")
        initial_steps = obs.remaining_steps

        obs, _, _, _ = env.step(Action(action_type=ActionType.COMPARE_VENDORS))
        assert obs.remaining_steps == initial_steps - 1

    def test_select_rejected_vendor_invalid(self) -> None:
        env = self._make_env()
        env.step(Action(action_type=ActionType.REJECT_VENDOR, vendor_name="BudgetByte Hardware"))

        obs, reward, _, _ = env.step(
            Action(action_type=ActionType.SELECT_VENDOR, vendor_name="BudgetByte Hardware")
        )
        assert reward.step_reward < 0  # penalty for invalid action

    def test_episode_ends_when_steps_exhausted(self) -> None:
        env = self._make_env()

        # Burn through all steps
        done = False
        for _ in range(20):
            _, _, done, _ = env.step(Action(action_type=ActionType.COMPARE_VENDORS))
            if done:
                break

        assert done is True

    def test_request_clarification(self) -> None:
        env = self._make_env()
        obs, _, _, _ = env.step(Action(action_type=ActionType.REQUEST_CLARIFICATION))

        assert obs.clarification_response is not None
        assert "Task:" in obs.clarification_response

    def test_request_delivery_guarantee(self) -> None:
        env = self._make_env()
        obs, _, _, _ = env.step(
            Action(
                action_type=ActionType.REQUEST_DELIVERY_GUARANTEE,
                vendor_name="TechVault Solutions",
                parameters={"required_days": 10},
            )
        )
        assert len(obs.negotiation_history) >= 1

    def test_request_contract_change(self) -> None:
        env = self._make_env()
        obs, _, _, _ = env.step(
            Action(
                action_type=ActionType.REQUEST_CONTRACT_CHANGE,
                vendor_name="BudgetByte Hardware",
                message="Please remove the auto-renewal clause",
            )
        )
        assert len(obs.negotiation_history) >= 1
