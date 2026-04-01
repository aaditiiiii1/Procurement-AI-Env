

from enum import Enum


class ActionType(str, Enum):
    SHORTLIST_VENDOR = "shortlist_vendor"
    REJECT_VENDOR = "reject_vendor"
    NEGOTIATE_VENDOR = "negotiate_vendor"
    REQUEST_CONTRACT_CHANGE = "request_contract_change"
    REQUEST_DELIVERY_GUARANTEE = "request_delivery_guarantee"
    REQUEST_CLARIFICATION = "request_clarification"
    COMPARE_VENDORS = "compare_vendors"
    SELECT_VENDOR = "select_vendor"
    FINALIZE_DECISION = "finalize_decision"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VendorStatus(str, Enum):
    AVAILABLE = "available"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    SELECTED = "selected"
    BLACKLISTED = "blacklisted"


class EpisodeTerminationReason(str, Enum):
    FINALIZED = "finalized"
    NO_STEPS_REMAINING = "no_steps_remaining"
    MAX_INVALID_ACTIONS = "max_invalid_actions"
    IMPOSSIBLE_BUDGET = "impossible_budget"
    BLACKLISTED_VENDOR_SELECTED = "blacklisted_vendor_selected"
    NOT_TERMINATED = "not_terminated"


# Reward shaping constants

REWARD_REJECT_RISKY_VENDOR = 0.05
REWARD_SHORTLIST_GOOD_VENDOR = 0.05
REWARD_SUCCESSFUL_NEGOTIATION = 0.10
REWARD_STAKEHOLDER_SATISFACTION = 0.10
REWARD_SELECT_WITHIN_BUDGET = 0.15
REWARD_SELECT_OPTIMAL_VENDOR = 0.15

PENALTY_WASTED_ACTION = -0.05
PENALTY_REPEATED_INVALID_ACTION = -0.10
PENALTY_SELECT_RISKY_VENDOR = -0.15
PENALTY_EXCEED_BUDGET = -0.20
PENALTY_SELECT_BLACKLISTED = -0.25

# Grader weights

GRADER_WEIGHT_BUDGET = 0.25
GRADER_WEIGHT_QUALITY = 0.20
GRADER_WEIGHT_DELIVERY = 0.15
GRADER_WEIGHT_RISK = 0.20
GRADER_WEIGHT_NEGOTIATION = 0.10
GRADER_WEIGHT_STAKEHOLDER = 0.10

# Environment defaults

DEFAULT_MAX_STEPS_EASY = 10
DEFAULT_MAX_STEPS_MEDIUM = 15
DEFAULT_MAX_STEPS_HARD = 25
MAX_INVALID_ACTIONS = 5
MAX_NEGOTIATION_ROUNDS = 3
DEFAULT_RANDOM_SEED = 42
DEFAULT_PORT = 7860
