

from __future__ import annotations

import pytest

from env.constants import Difficulty, EpisodeTerminationReason, VendorStatus
from env.models import Action
from env.procurement_env import ProcurementEnv
from env.tasks import load_all_tasks


class TestReset:

    def test_reset_default_task(self) -> None:
        env = ProcurementEnv(seed=42)
        obs = env.reset()

        assert obs.task_id is not None
        assert obs.remaining_steps > 0
        assert obs.budget > 0
        assert len(obs.vendors) > 0
        assert obs.finalized is False
        assert obs.selected_vendor is None
        assert obs.current_reward == 0.0
        assert obs.termination_reason == EpisodeTerminationReason.NOT_TERMINATED

    def test_reset_specific_task(self) -> None:
        env = ProcurementEnv(seed=42)
        obs = env.reset(task_id="easy-001")

        assert obs.task_id == "easy-001"
        assert obs.task_difficulty == Difficulty.EASY
        assert obs.budget == 50000.00
        assert len(obs.vendors) == 3

    def test_reset_unknown_task_raises(self) -> None:
        env = ProcurementEnv(seed=42)
        with pytest.raises(ValueError, match="Unknown task_id"):
            env.reset(task_id="nonexistent-999")

    def test_reset_clears_previous_state(self) -> None:
        env = ProcurementEnv(seed=42)
        obs = env.reset(task_id="easy-001")

        # Take some actions
        from env.constants import ActionType
        env.step(Action(action_type=ActionType.COMPARE_VENDORS))

        # Reset again
        obs2 = env.reset(task_id="medium-001")
        assert obs2.task_id == "medium-001"
        assert obs2.current_reward == 0.0
        assert obs2.remaining_steps > 0
        assert len(obs2.shortlisted_vendors) == 0
        assert len(obs2.rejected_vendors) == 0

    def test_reset_vendors_are_available(self) -> None:
        env = ProcurementEnv(seed=42)
        obs = env.reset(task_id="easy-001")

        for vendor in obs.vendors:
            assert vendor.status == VendorStatus.AVAILABLE

    def test_reset_all_tasks(self) -> None:
        env = ProcurementEnv(seed=42)
        tasks = load_all_tasks()
        assert len(tasks) >= 10, f"Expected at least 10 tasks, got {len(tasks)}"

        for task in tasks:
            obs = env.reset(task_id=task.task_id)
            assert obs.task_id == task.task_id
            assert obs.budget == task.budget
            assert len(obs.vendors) == len(task.vendor_ids)

    def test_reset_reproducibility(self) -> None:
        env1 = ProcurementEnv(seed=42)
        obs1 = env1.reset(task_id="easy-001")

        env2 = ProcurementEnv(seed=42)
        obs2 = env2.reset(task_id="easy-001")

        assert obs1.task_id == obs2.task_id
        assert obs1.budget == obs2.budget
        assert obs1.remaining_steps == obs2.remaining_steps
        assert len(obs1.vendors) == len(obs2.vendors)
        for v1, v2 in zip(obs1.vendors, obs2.vendors):
            assert v1.name == v2.name
            assert v1.base_price == v2.base_price
