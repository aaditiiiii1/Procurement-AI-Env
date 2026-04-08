from __future__ import annotations
from env.models import Action, Observation
from env.constants import ActionType
import random

class HeuristicAgent:
    def __init__(self, seed: int = 42):
        self.random = random.Random(seed)

    def get_action(self, obs: Observation) -> Action:
        # 1. If not many vendors are shortlisted, compare them
        if len(obs.shortlisted_vendors) < 2:
            return Action(action_type=ActionType.COMPARE_VENDORS)

        # 2. Shortlist a random available vendor
        available_vendors = [v.name for v in obs.vendors if v.status.value == 'available']
        if available_vendors:
            vendor_to_shortlist = self.random.choice(available_vendors)
            return Action(action_type=ActionType.SHORTLIST_VENDOR, vendor_name=vendor_to_shortlist)

        # 3. Negotiate with a random shortlisted vendor
        if obs.shortlisted_vendors:
            vendor_to_negotiate = self.random.choice(obs.shortlisted_vendors)
            return Action(
                action_type=ActionType.NEGOTIATE_VENDOR,
                vendor_name=vendor_to_negotiate,
                parameters={"requested_discount_pct": 10},
            )

        # 4. Select a vendor if one is shortlisted
        if obs.shortlisted_vendors:
            vendor_to_select = self.random.choice(obs.shortlisted_vendors)
            return Action(action_type=ActionType.SELECT_VENDOR, vendor_name=vendor_to_select)

        # 5. Finalize if a vendor is selected
        if obs.selected_vendor:
            return Action(action_type=ActionType.FINALIZE_DECISION)

        # Fallback action
        return Action(action_type=ActionType.COMPARE_VENDORS)
