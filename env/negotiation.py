

from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional

from env.constants import MAX_NEGOTIATION_ROUNDS
from env.models import NegotiationResult, Vendor

logger = logging.getLogger("procurement_env.negotiation")


class NegotiationEngine:

    def __init__(self, vendors: List[Vendor], seed: int = 42) -> None:
        self._vendors: Dict[str, Vendor] = {v.name: v for v in vendors}
        self._history: List[NegotiationResult] = []
        self._rounds: Dict[str, int] = {v.name: 0 for v in vendors}
        self._rng = random.Random(seed)

    @property
    def history(self) -> List[NegotiationResult]:
        return list(self._history)

    def rounds_used(self, vendor_name: str) -> int:
        return self._rounds.get(vendor_name, 0)

    def can_negotiate(self, vendor_name: str) -> bool:
        if vendor_name not in self._vendors:
            return False
        return self._rounds.get(vendor_name, 0) < MAX_NEGOTIATION_ROUNDS

    def negotiate_discount(
        self,
        vendor_name: str,
        requested_discount_pct: float,
        message: str = "",
    ) -> NegotiationResult:
        vendor = self._vendors.get(vendor_name)
        if vendor is None:
            return NegotiationResult(
                vendor_name=vendor_name,
                round_number=0,
                requested_discount_pct=requested_discount_pct,
                offered_discount_pct=0.0,
                accepted=False,
                message=f"Vendor '{vendor_name}' not found.",
            )

        round_num = self._rounds[vendor_name] + 1
        if round_num > MAX_NEGOTIATION_ROUNDS:
            return NegotiationResult(
                vendor_name=vendor_name,
                round_number=round_num,
                requested_discount_pct=requested_discount_pct,
                offered_discount_pct=0.0,
                accepted=False,
                message=f"Maximum negotiation rounds ({MAX_NEGOTIATION_ROUNDS}) reached with {vendor_name}.",
            )

        self._rounds[vendor_name] = round_num

        offered = self._compute_offer(vendor, requested_discount_pct, round_num)
        accepted = offered >= requested_discount_pct * 0.8  # accept if within 80% of request
        new_price: Optional[float] = None
        if accepted:
            new_price = vendor.base_price * (1.0 - offered / 100.0)
            vendor.base_price = new_price
            response_msg = (
                f"{vendor_name} agrees to a {offered:.1f}% discount. "
                f"New price: ${new_price:,.2f}."
            )
        else:
            response_msg = (
                f"{vendor_name} counters with {offered:.1f}% discount "
                f"(you asked for {requested_discount_pct:.1f}%). "
                f"They are not willing to go further this round."
            )

        result = NegotiationResult(
            vendor_name=vendor_name,
            round_number=round_num,
            requested_discount_pct=requested_discount_pct,
            offered_discount_pct=offered,
            accepted=accepted,
            new_price=new_price,
            message=response_msg,
        )
        self._history.append(result)
        logger.info("Negotiation round %d with %s: accepted=%s", round_num, vendor_name, accepted)
        return result

    def request_contract_change(
        self,
        vendor_name: str,
        change_description: str,
    ) -> NegotiationResult:
        vendor = self._vendors.get(vendor_name)
        if vendor is None:
            return NegotiationResult(
                vendor_name=vendor_name,
                round_number=0,
                message=f"Vendor '{vendor_name}' not found.",
            )

        round_num = self._rounds[vendor_name] + 1
        if round_num > MAX_NEGOTIATION_ROUNDS:
            return NegotiationResult(
                vendor_name=vendor_name,
                round_number=round_num,
                accepted=False,
                message=f"Maximum rounds reached with {vendor_name}.",
            )
        self._rounds[vendor_name] = round_num

        accept_prob = vendor.negotiation_flexibility * 0.7 + self._rng.random() * 0.3
        accepted = accept_prob > 0.5

        contract_changes: Dict = {}
        if accepted:
            contract_changes = self._apply_contract_change(vendor, change_description)
            msg = (
                f"{vendor_name} has agreed to modify contract terms: "
                f"{change_description}. Changes applied: {contract_changes}"
            )
        else:
            msg = (
                f"{vendor_name} declined the contract change request: "
                f"{change_description}. They are unable to accommodate this at present."
            )

        result = NegotiationResult(
            vendor_name=vendor_name,
            round_number=round_num,
            accepted=accepted,
            message=msg,
            contract_changes=contract_changes,
        )
        self._history.append(result)
        return result

    def request_delivery_guarantee(
        self,
        vendor_name: str,
        required_days: int,
    ) -> NegotiationResult:
        vendor = self._vendors.get(vendor_name)
        if vendor is None:
            return NegotiationResult(
                vendor_name=vendor_name,
                round_number=0,
                message=f"Vendor '{vendor_name}' not found.",
            )

        round_num = self._rounds[vendor_name] + 1
        if round_num > MAX_NEGOTIATION_ROUNDS:
            return NegotiationResult(
                vendor_name=vendor_name,
                round_number=round_num,
                accepted=False,
                message=f"Maximum rounds reached with {vendor_name}.",
            )
        self._rounds[vendor_name] = round_num

        can_meet = vendor.delivery_days <= required_days
        if can_meet:
            msg = (
                f"{vendor_name} confirms delivery within {vendor.delivery_days} days, "
                f"meeting your {required_days}-day requirement."
            )
        else:
            # Vendor may stretch based on flexibility
            stretch = int(vendor.negotiation_flexibility * (vendor.delivery_days - required_days))
            new_days = vendor.delivery_days - stretch
            if new_days <= required_days:
                vendor.delivery_days = new_days
                can_meet = True
                msg = (
                    f"{vendor_name} agrees to expedite delivery to {new_days} days "
                    f"(originally {vendor.delivery_days + stretch} days)."
                )
            else:
                msg = (
                    f"{vendor_name} cannot guarantee delivery within {required_days} days. "
                    f"Earliest possible delivery: {new_days} days."
                )

        result = NegotiationResult(
            vendor_name=vendor_name,
            round_number=round_num,
            accepted=can_meet,
            message=msg,
            contract_changes={"delivery_days": vendor.delivery_days} if can_meet else {},
        )
        self._history.append(result)
        return result

    def _compute_offer(
        self,
        vendor: Vendor,
        requested_pct: float,
        round_num: int,
    ) -> float:
        base = vendor.negotiation_flexibility * vendor.max_discount_pct
        round_decay = 1.0 - (round_num - 1) * 0.2
        noise = self._rng.uniform(-1.0, 1.0)
        raw_offer = base * max(round_decay, 0.3) + noise

        offered = min(raw_offer, vendor.max_discount_pct)
        offered = max(0.0, offered)
        return round(offered, 2)

    def _apply_contract_change(
        self,
        vendor: Vendor,
        description: str,
    ) -> Dict:
        changes: Dict = {}
        desc_lower = description.lower()

        if "auto_renewal" in desc_lower or "auto-renewal" in desc_lower or "renewal" in desc_lower:
            vendor.contract.auto_renewal = False
            vendor.contract.renewal_price_increase_pct = 0.0
            changes["auto_renewal"] = False
            changes["renewal_price_increase_pct"] = 0.0

        if "termination" in desc_lower or "exit" in desc_lower:
            vendor.contract.termination_fee_pct = max(0.0, vendor.contract.termination_fee_pct - 5.0)
            changes["termination_fee_pct"] = vendor.contract.termination_fee_pct

        if "hidden" in desc_lower or "fee" in desc_lower or "onboarding" in desc_lower:
            if vendor.contract.hidden_fees:
                removed_key = next(iter(vendor.contract.hidden_fees))
                removed_val = vendor.contract.hidden_fees.pop(removed_key)
                changes[f"removed_fee_{removed_key}"] = removed_val

        if "lock" in desc_lower or "lock-in" in desc_lower:
            vendor.contract.lock_in_risk = False
            changes["lock_in_risk"] = False

        if "data" in desc_lower and "portability" in desc_lower:
            vendor.contract.data_portability = True
            changes["data_portability"] = True

        # Generic goodwill change if nothing specific matched
        if not changes:
            vendor.contract.sla_uptime_pct = min(99.99, vendor.contract.sla_uptime_pct + 0.5)
            changes["sla_uptime_pct"] = vendor.contract.sla_uptime_pct

        return changes
