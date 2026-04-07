

from __future__ import annotations

import pytest

from env.constants import ActionType, EpisodeTerminationReason, VendorStatus
from env.models import Action, EnvironmentState
from env.procurement_env import ProcurementEnv


class TestState:

    def test_state_without_reset_raises(self) -> None:
        env = ProcurementEnv(seed=42)
        with pytest.raises(RuntimeError, match="not been reset"):
            env.state()

    def test_state_after_reset(self) -> None:
        env = ProcurementEnv(seed=42)
        env.reset(task_id="easy-001")
        state = env.state()

        assert isinstance(state, EnvironmentState)
        assert state.task_id == "easy-001"
        assert state.step_count == 0
        assert state.cumulative_reward == 0.0
        assert state.finalized is False
        assert state.termination_reason == EpisodeTerminationReason.NOT_TERMINATED

    def test_state_updates_after_step(self) -> None:
        env = ProcurementEnv(seed=42)
        env.reset(task_id="easy-001")

        env.step(Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name="TechVault Solutions"))
        state = env.state()

        assert state.step_count == 1
        assert "TechVault Solutions" in state.shortlisted_vendors
        assert state.remaining_steps > 0

    def test_state_reflects_negotiation(self) -> None:
        env = ProcurementEnv(seed=42)
        env.reset(task_id="easy-001")

        env.step(
            Action(
                action_type=ActionType.NEGOTIATE_VENDOR,
                vendor_name="TechVault Solutions",
                parameters={"requested_discount_pct": 8.0},
            )
        )
        state = env.state()

        assert len(state.negotiation_history) == 1
        assert state.negotiation_history[0].vendor_name == "TechVault Solutions"

    def test_state_serialisation(self) -> None:
        env = ProcurementEnv(seed=42)
        env.reset(task_id="easy-001")
        state = env.state()

        json_str = state.model_dump_json()
        assert len(json_str) > 0

        # Round-trip
        restored = EnvironmentState.model_validate_json(json_str)
        assert restored.task_id == state.task_id
        assert restored.step_count == state.step_count

    def test_state_vendors_deep_copy(self) -> None:
        env = ProcurementEnv(seed=42)
        env.reset(task_id="easy-001")

        state1 = env.state()
        # Mutate the returned vendor
        state1.vendors[0].base_price = 0.0

        state2 = env.state()
        # Original should be unaffected
        assert state2.vendors[0].base_price > 0

    def test_state_after_finalization(self) -> None:
        env = ProcurementEnv(seed=42)
        env.reset(task_id="easy-001")

        env.step(Action(action_type=ActionType.SELECT_VENDOR, vendor_name="TechVault Solutions"))
        env.step(Action(action_type=ActionType.FINALIZE_DECISION))

        state = env.state()
        assert state.finalized is True
        assert state.selected_vendor == "TechVault Solutions"
        assert state.termination_reason == EpisodeTerminationReason.FINALIZED
