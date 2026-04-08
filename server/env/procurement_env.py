from __future__ import annotations
print(" USING UPDATED PROCUREMENT_ENV FILE ")


import logging
from typing import Any, Dict, List, Optional, Tuple

from env.constants import (
    MAX_INVALID_ACTIONS,
    ActionType,
    Difficulty,
    EpisodeTerminationReason,
    VendorStatus,
)
from env.graders import grade_by_difficulty
from env.models import (
    Action,
    EnvironmentState,
    NegotiationResult,
    Observation,
    Reward,
    StakeholderProfile,
    TaskDefinition,
    Vendor,
)
from env.negotiation import NegotiationEngine
from env.reward import (
    build_step_reward,
    penalty_repeated_invalid,
    penalty_wasted_action,
    reward_reject_risky_vendor,
    reward_select_vendor,
    reward_shortlist_good_vendor,
    reward_stakeholder_satisfaction,
    reward_successful_negotiation,
)
from env.tasks import (
    get_stakeholders_for_task,
    get_task_by_id,
    get_vendors_for_task,
    load_all_tasks,
)
from env.vendor_logic import compare_vendors, is_blacklisted, is_risky_vendor

logger = logging.getLogger("procurement_env")


class ProcurementEnv:

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._task: Optional[TaskDefinition] = None
        self._vendors: List[Vendor] = []
        self._stakeholders: List[StakeholderProfile] = []
        self._negotiation_engine: Optional[NegotiationEngine] = None
        self._step_count: int = 0
        self._remaining_steps: int = 0
        self._cumulative_reward: float = 0.0
        self._invalid_action_count: int = 0
        self._selected_vendor: Optional[str] = None
        self._finalized: bool = False
        self._done: bool = False
        self._termination_reason = EpisodeTerminationReason.NOT_TERMINATED
        self._messages: List[str] = []
        self._comparison_result: Optional[Dict[str, Any]] = None
        self._clarification_response: Optional[str] = None

    @property
    def current_task(self):
        return self._task

    @current_task.setter
    def current_task(self, value):
        self._task = value

    def reset(self, task_id: Optional[str] = None) -> Observation:
        if task_id:
            task = get_task_by_id(task_id)
            if task is None:
                raise ValueError(f"Unknown task_id: {task_id}")
        else:
            all_tasks = load_all_tasks()
            if not all_tasks:
                raise ValueError("No tasks available.")
            task = all_tasks[0]

        self._task = task

        self._vendors = [v.model_copy(deep=True) for v in get_vendors_for_task(task)]
        for v in self._vendors:
            v.status = VendorStatus.AVAILABLE

        self._stakeholders = get_stakeholders_for_task(task)
        self._negotiation_engine = NegotiationEngine(self._vendors, seed=self._seed)

        self._step_count = 0
        self._remaining_steps = task.max_steps
        self._cumulative_reward = 0.0
        self._invalid_action_count = 0
        self._selected_vendor = None
        self._finalized = False
        self._done = False
        self._termination_reason = EpisodeTerminationReason.NOT_TERMINATED

        self._messages = [f"Episode started: {task.title}"]
        self._comparison_result = None
        self._clarification_response = None

        logger.info("Environment reset with task '%s'", task.task_id)

        return self._build_observation()

    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict[str, Any]]:
        if self._task is None:
            raise RuntimeError("Environment has not been reset. Call reset() first.")

        if self._done:
            obs = self._build_observation()
            rew = build_step_reward(0.0, self._cumulative_reward, {})
            return obs, rew, True, {"message": "Episode already finished."}

        self._messages = []
        self._comparison_result = None
        self._clarification_response = None

        step_reward = 0.0
        breakdown: Dict[str, float] = {}

        handler = self._ACTION_HANDLERS.get(action.action_type)
        if handler is None:
            step_reward, breakdown = self._handle_invalid(action, "Unknown action type.")
        else:
            step_reward, breakdown = handler(self, action)

        self._step_count += 1
        self._remaining_steps = max(0, self._remaining_steps - 1)
        self._cumulative_reward += step_reward

        self._check_termination()

        obs = self._build_observation()
        rew = build_step_reward(step_reward, self._cumulative_reward - step_reward, breakdown)
        info: Dict[str, Any] = {"step": self._step_count}

        if self._done:
            final_score, grading = self._compute_final_grade()
            info["final_score"] = final_score
            info["grading_breakdown"] = grading
            info["termination_reason"] = self._termination_reason.value

        return obs, rew, self._done, info

    def state(self) -> EnvironmentState:
        if self._task is None:
            raise RuntimeError("Environment has not been reset. Call reset() first.")

        return EnvironmentState(
            task_id=self._task.task_id,
            difficulty=self._task.difficulty,
            step_count=self._step_count,
            remaining_steps=self._remaining_steps,
            budget=self._task.budget,
            cumulative_reward=round(self._cumulative_reward, 4),
            shortlisted_vendors=self._get_vendor_names(VendorStatus.SHORTLISTED),
            rejected_vendors=self._get_vendor_names(VendorStatus.REJECTED),
            selected_vendor=self._selected_vendor,
            finalized=self._finalized,
            termination_reason=self._termination_reason,
            negotiation_history=(
                self._negotiation_engine.history if self._negotiation_engine else []
            ),
            invalid_action_count=self._invalid_action_count,
            vendors=[v.model_copy(deep=True) for v in self._vendors],
            stakeholder_priorities=[s.model_copy(deep=True) for s in self._stakeholders],
        )

    # Action handlers
    def _handle_shortlist(self, action: Action) -> Tuple[float, Dict[str, float]]:
        vendor = self._find_vendor(action.vendor_name)
        if vendor is None:
            return self._handle_invalid(action, f"Vendor '{action.vendor_name}' not found.")
        if vendor.status != VendorStatus.AVAILABLE:
            return self._handle_invalid(
                action, f"Vendor '{vendor.name}' is already {vendor.status.value}."
            )

        vendor.status = VendorStatus.SHORTLISTED
        r = reward_shortlist_good_vendor(vendor)
        self._messages.append(f"Shortlisted vendor: {vendor.name}")
        return r, {"shortlist_good_vendor": r}

    def _handle_reject(self, action: Action) -> Tuple[float, Dict[str, float]]:
        vendor = self._find_vendor(action.vendor_name)
        if vendor is None:
            return self._handle_invalid(action, f"Vendor '{action.vendor_name}' not found.")
        if vendor.status not in (VendorStatus.AVAILABLE, VendorStatus.SHORTLISTED):
            return self._handle_invalid(
                action,
                f"Vendor '{vendor.name}' cannot be rejected (status: {vendor.status.value}).",
            )

        vendor.status = VendorStatus.REJECTED
        r = reward_reject_risky_vendor(vendor)
        self._messages.append(f"Rejected vendor: {vendor.name}")
        return r, {"reject_risky_vendor": r}

    def _handle_negotiate(self, action: Action) -> Tuple[float, Dict[str, float]]:
        vendor = self._find_vendor(action.vendor_name)
        if vendor is None:
            return self._handle_invalid(action, f"Vendor '{action.vendor_name}' not found.")
        if not self._negotiation_engine:
            return self._handle_invalid(action, "Negotiation engine not initialised.")
        if not self._negotiation_engine.can_negotiate(vendor.name):
            return self._handle_invalid(
                action, f"Max negotiation rounds reached for '{vendor.name}'."
            )

        requested_pct = action.parameters.get("requested_discount_pct", 10.0)
        if isinstance(requested_pct, str):
            try:
                requested_pct = float(requested_pct)
            except ValueError:
                requested_pct = 10.0

        result = self._negotiation_engine.negotiate_discount(
            vendor.name, requested_pct, action.message or ""
        )
        r = reward_successful_negotiation(result)
        self._messages.append(result.message)
        return r, {"negotiation": r}

    def _handle_contract_change(self, action: Action) -> Tuple[float, Dict[str, float]]:
        vendor = self._find_vendor(action.vendor_name)
        if vendor is None:
            return self._handle_invalid(action, f"Vendor '{action.vendor_name}' not found.")
        if not self._negotiation_engine:
            return self._handle_invalid(action, "Negotiation engine not initialised.")
        if not self._negotiation_engine.can_negotiate(vendor.name):
            return self._handle_invalid(action, f"Max rounds reached for '{vendor.name}'.")

        result = self._negotiation_engine.request_contract_change(
            vendor.name, action.message or "Improve contract terms"
        )
        r = reward_successful_negotiation(result)
        self._messages.append(result.message)
        return r, {"contract_change": r}

    def _handle_delivery_guarantee(self, action: Action) -> Tuple[float, Dict[str, float]]:
        vendor = self._find_vendor(action.vendor_name)
        if vendor is None:
            return self._handle_invalid(action, f"Vendor '{action.vendor_name}' not found.")
        if not self._negotiation_engine:
            return self._handle_invalid(action, "Negotiation engine not initialised.")
        if not self._negotiation_engine.can_negotiate(vendor.name):
            return self._handle_invalid(action, f"Max rounds reached for '{vendor.name}'.")

        required_days = action.parameters.get("required_days", 14)
        if isinstance(required_days, str):
            try:
                required_days = int(required_days)
            except ValueError:
                required_days = 14

        result = self._negotiation_engine.request_delivery_guarantee(
            vendor.name, required_days
        )
        r = reward_successful_negotiation(result)
        self._messages.append(result.message)
        return r, {"delivery_guarantee": r}

    def _handle_clarification(self, action: Action) -> Tuple[float, Dict[str, float]]:
        assert self._task is not None
        response_parts = [
            f"Task: {self._task.title}",
            f"Budget: ${self._task.budget:,.2f}",
            f"Category: {self._task.category}",
            f"Difficulty: {self._task.difficulty.value}",
            f"Vendors available: {len(self._vendors)}",
            f"Stakeholders: {', '.join(s.name for s in self._stakeholders)}",
        ]
        if action.vendor_name:
            vendor = self._find_vendor(action.vendor_name)
            if vendor:
                response_parts.append(
                    f"\nVendor '{vendor.name}': price=${vendor.base_price:,.2f}, "
                    f"quality={vendor.quality_rating}/10, delivery={vendor.delivery_days}d, "
                    f"risk={vendor.risk_level.value}, blacklisted={vendor.is_blacklisted}"
                )

        self._clarification_response = "\n".join(response_parts)
        self._messages.append("Clarification provided.")
        # Lighter penalty for information gathering
        r = penalty_wasted_action() * 0.5
        return r, {"clarification": r}

    def _handle_compare(self, action: Action) -> Tuple[float, Dict[str, float]]:
        active = [
            v for v in self._vendors
            if v.status in (VendorStatus.AVAILABLE, VendorStatus.SHORTLISTED)
        ]
        if not active:
            return self._handle_invalid(action, "No vendors available to compare.")

        self._comparison_result = {"vendors": compare_vendors(active)}
        self._messages.append(f"Compared {len(active)} vendors.")
        r = penalty_wasted_action() * 0.5
        return r, {"compare": r}

    def _handle_select(self, action: Action) -> Tuple[float, Dict[str, float]]:
        vendor = self._find_vendor(action.vendor_name)
        if vendor is None:
            return self._handle_invalid(action, f"Vendor '{action.vendor_name}' not found.")
        if vendor.status == VendorStatus.REJECTED:
            return self._handle_invalid(
                action, f"Vendor '{vendor.name}' was previously rejected."
            )

        self._selected_vendor = vendor.name
        vendor.status = VendorStatus.SELECTED
        self._messages.append(
            f"Selected vendor: {vendor.name}. Call 'finalize_decision' to confirm."
        )

        assert self._task is not None
        r = reward_select_vendor(vendor, self._task.budget, self._task.optimal_vendor)
        breakdown: Dict[str, float] = {"select_vendor": r}

        # Stakeholder satisfaction reward
        sat_r = reward_stakeholder_satisfaction(vendor, self._task.budget, self._stakeholders)
        r += sat_r
        breakdown["stakeholder_satisfaction"] = sat_r

        return r, breakdown

    def _handle_finalize(self, action: Action) -> Tuple[float, Dict[str, float]]:
        if self._selected_vendor is None:
            return self._handle_invalid(
                action, "No vendor has been selected. Call 'select_vendor' first."
            )

        self._finalized = True
        self._done = True
        self._termination_reason = EpisodeTerminationReason.FINALIZED
        self._messages.append(f"Procurement finalized with vendor: {self._selected_vendor}")
        return 0.0, {"finalize": 0.0}

    def _handle_invalid(self, action: Action, reason: str) -> Tuple[float, Dict[str, float]]:
        self._invalid_action_count += 1
        self._messages.append(f"Invalid action: {reason}")
        logger.warning("Invalid action (count=%d): %s", self._invalid_action_count, reason)

        if self._invalid_action_count >= 2:
            r = penalty_repeated_invalid()
            return r, {"repeated_invalid": r}
        r = penalty_wasted_action()
        return r, {"wasted_action": r}

    _ACTION_HANDLERS = {
        ActionType.SHORTLIST_VENDOR: _handle_shortlist,
        ActionType.REJECT_VENDOR: _handle_reject,
        ActionType.NEGOTIATE_VENDOR: _handle_negotiate,
        ActionType.REQUEST_CONTRACT_CHANGE: _handle_contract_change,
        ActionType.REQUEST_DELIVERY_GUARANTEE: _handle_delivery_guarantee,
        ActionType.REQUEST_CLARIFICATION: _handle_clarification,
        ActionType.COMPARE_VENDORS: _handle_compare,
        ActionType.SELECT_VENDOR: _handle_select,
        ActionType.FINALIZE_DECISION: _handle_finalize,
    }

    # Termination checks
    def _check_termination(self) -> None:
        if self._done:
            return

        if self._invalid_action_count >= MAX_INVALID_ACTIONS:
            self._done = True
            self._termination_reason = EpisodeTerminationReason.MAX_INVALID_ACTIONS
            self._messages.append("Episode terminated: too many invalid actions.")
            return

        if self._remaining_steps <= 0:
            self._done = True
            self._termination_reason = EpisodeTerminationReason.NO_STEPS_REMAINING
            self._messages.append("Episode terminated: no steps remaining.")
            return

        if self._selected_vendor:
            vendor = self._find_vendor(self._selected_vendor)
            if vendor and is_blacklisted(vendor):
                self._done = True
                self._termination_reason = EpisodeTerminationReason.BLACKLISTED_VENDOR_SELECTED
                self._messages.append("Episode terminated: blacklisted vendor selected.")
                return

        # All remaining vendors cost more than 1.5x the budget
        assert self._task is not None
        active = [
            v for v in self._vendors
            if v.status in (VendorStatus.AVAILABLE, VendorStatus.SHORTLISTED)
        ]
        if active:
            from env.vendor_logic import compute_total_vendor_cost

            cheapest = min(compute_total_vendor_cost(v) for v in active)
            if cheapest > self._task.budget * 1.5:
                self._done = True
                self._termination_reason = EpisodeTerminationReason.IMPOSSIBLE_BUDGET
                self._messages.append(
                    "Episode terminated: no vendor is affordable within budget."
                )
                return

    # Helpers
    def _find_vendor(self, name: Optional[str]) -> Optional[Vendor]:
        if not name:
            return None
        name_lower = name.strip().lower()
        for v in self._vendors:
            if v.name.lower() == name_lower:
                return v
        return None

    def _get_vendor_names(self, status: VendorStatus) -> List[str]:
        return [v.name for v in self._vendors if v.status == status]

    def _build_observation(self) -> Observation:
        assert self._task is not None
        return Observation(
            task_id=self._task.task_id,
            task_difficulty=self._task.difficulty,
            task_description=self._task.description,
            budget=self._task.budget,
            remaining_steps=self._remaining_steps,
            vendors=[v.model_copy(deep=True) for v in self._vendors],
            negotiation_history=(
                self._negotiation_engine.history if self._negotiation_engine else []
            ),
            shortlisted_vendors=self._get_vendor_names(VendorStatus.SHORTLISTED),
            rejected_vendors=self._get_vendor_names(VendorStatus.REJECTED),
            stakeholder_priorities=[s.model_copy(deep=True) for s in self._stakeholders],
            current_reward=round(self._cumulative_reward, 4),
            selected_vendor=self._selected_vendor,
            finalized=self._finalized,
            termination_reason=self._termination_reason,
            comparison_result=self._comparison_result,
            clarification_response=self._clarification_response,
            messages=list(self._messages),
        )

    def _compute_final_grade(self) -> Tuple[float, Dict[str, float]]:
        assert self._task is not None
        selected_v: Optional[Vendor] = None
        if self._selected_vendor:
            selected_v = self._find_vendor(self._selected_vendor)

        return grade_by_difficulty(
            self._task.difficulty,
            selected_v,
            self._task.budget,
            self._task,
            self._negotiation_engine.history if self._negotiation_engine else [],
            self._stakeholders,
        )
