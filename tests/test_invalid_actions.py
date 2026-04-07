

from __future__ import annotations

import pytest

from env.constants import ActionType, EpisodeTerminationReason, MAX_INVALID_ACTIONS
from env.models import Action
from env.procurement_env import ProcurementEnv


class TestInvalidActions:

    def _make_env(self, task_id: str = "easy-001") -> ProcurementEnv:
        env = ProcurementEnv(seed=42)
        env.reset(task_id=task_id)
        return env

    def test_unknown_vendor_name(self) -> None:
        env = self._make_env()
        obs, reward, _, _ = env.step(
            Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name="FakeVendor Inc.")
        )
        assert reward.step_reward < 0
        assert any("not found" in m.lower() for m in obs.messages)

    def test_shortlist_already_shortlisted(self) -> None:
        env = self._make_env()
        env.step(Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name="TechVault Solutions"))
        obs, reward, _, _ = env.step(
            Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name="TechVault Solutions")
        )
        assert reward.step_reward < 0

    def test_finalize_without_select(self) -> None:
        env = self._make_env()
        obs, reward, _, _ = env.step(Action(action_type=ActionType.FINALIZE_DECISION))
        assert reward.step_reward < 0
        assert any("no vendor" in m.lower() for m in obs.messages)

    def test_max_invalid_actions_terminates(self) -> None:
        env = self._make_env()
        done = False
        for _ in range(MAX_INVALID_ACTIONS + 2):
            _, _, done, _ = env.step(
                Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name="GhostVendor")
            )
            if done:
                break

        assert done is True
        state = env.state()
        assert state.termination_reason == EpisodeTerminationReason.MAX_INVALID_ACTIONS

    def test_action_after_done_returns_done(self) -> None:
        env = self._make_env()
        env.step(Action(action_type=ActionType.SELECT_VENDOR, vendor_name="TechVault Solutions"))
        env.step(Action(action_type=ActionType.FINALIZE_DECISION))

        # Episode is done, try another action
        obs, _, done, info = env.step(Action(action_type=ActionType.COMPARE_VENDORS))
        assert done is True
        assert "already finished" in info.get("message", "").lower()

    def test_negotiate_beyond_max_rounds(self) -> None:
        env = self._make_env()
        for i in range(4):
            obs, reward, _, _ = env.step(
                Action(
                    action_type=ActionType.NEGOTIATE_VENDOR,
                    vendor_name="TechVault Solutions",
                    parameters={"requested_discount_pct": 5.0},
                )
            )

        # The last call should have been invalid (max 3 rounds)
        assert reward.step_reward < 0

    def test_reject_then_select_invalid(self) -> None:
        env = self._make_env()
        env.step(Action(action_type=ActionType.REJECT_VENDOR, vendor_name="ProGear International"))
        obs, reward, _, _ = env.step(
            Action(action_type=ActionType.SELECT_VENDOR, vendor_name="ProGear International")
        )
        assert reward.step_reward < 0

    def test_no_vendor_name_for_vendor_action(self) -> None:
        env = self._make_env()
        obs, reward, _, _ = env.step(
            Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name=None)
        )
        assert reward.step_reward < 0

    def test_repeated_invalid_escalates_penalty(self) -> None:
        env = self._make_env()
        _, r1, _, _ = env.step(
            Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name="Ghost1")
        )
        _, r2, _, _ = env.step(
            Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name="Ghost2")
        )
        assert r2.step_reward < r1.step_reward  # escalated penalty
