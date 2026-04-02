

from __future__ import annotations

import random
from typing import Dict, List, Optional

from env.constants import DEFAULT_RANDOM_SEED, Difficulty
from env.models import StakeholderProfile, TaskDefinition, Vendor
from env.utils import load_json

# Module-level caches

_ALL_TASKS: Optional[List[TaskDefinition]] = None
_ALL_VENDORS: Optional[Dict[str, Vendor]] = None
_ALL_STAKEHOLDERS: Optional[Dict[str, StakeholderProfile]] = None


def _load_all_vendors() -> Dict[str, Vendor]:
    global _ALL_VENDORS
    if _ALL_VENDORS is None:
        raw = load_json("vendors.json")
        _ALL_VENDORS = {v["name"]: Vendor(**v) for v in raw}
    return _ALL_VENDORS


def _load_all_stakeholders() -> Dict[str, StakeholderProfile]:
    global _ALL_STAKEHOLDERS
    if _ALL_STAKEHOLDERS is None:
        raw = load_json("stakeholder_profiles.json")
        _ALL_STAKEHOLDERS = {s["name"]: StakeholderProfile(**s) for s in raw}
    return _ALL_STAKEHOLDERS


def _load_tasks_from_file(filename: str) -> List[TaskDefinition]:
    raw = load_json(filename)
    return [TaskDefinition(**t) for t in raw]


def load_all_tasks(*, force_reload: bool = False) -> List[TaskDefinition]:
    global _ALL_TASKS
    if _ALL_TASKS is not None and not force_reload:
        return _ALL_TASKS

    tasks: List[TaskDefinition] = []
    for fname in ("easy_tasks.json", "medium_tasks.json", "hard_tasks.json"):
        tasks.extend(_load_tasks_from_file(fname))

    tasks.sort(key=lambda t: t.task_id)
    _ALL_TASKS = tasks
    return _ALL_TASKS


def get_tasks_by_difficulty(difficulty: Difficulty) -> List[TaskDefinition]:
    return [t for t in load_all_tasks() if t.difficulty == difficulty]


def get_task_by_id(task_id: str) -> Optional[TaskDefinition]:
    for t in load_all_tasks():
        if t.task_id == task_id:
            return t
    return None


def choose_random_task(
    difficulty: Optional[Difficulty] = None,
    seed: int = DEFAULT_RANDOM_SEED,
) -> TaskDefinition:
    rng = random.Random(seed)
    pool = get_tasks_by_difficulty(difficulty) if difficulty else load_all_tasks()
    if not pool:
        raise ValueError(f"No tasks available for difficulty={difficulty}")
    return rng.choice(pool)


def get_vendors_for_task(task: TaskDefinition) -> List[Vendor]:
    all_vendors = _load_all_vendors()
    return [all_vendors[vid] for vid in task.vendor_ids if vid in all_vendors]


def get_stakeholders_for_task(task: TaskDefinition) -> List[StakeholderProfile]:
    all_sh = _load_all_stakeholders()
    return [all_sh[sid] for sid in task.stakeholder_ids if sid in all_sh]


def reset_caches() -> None:
    global _ALL_TASKS, _ALL_VENDORS, _ALL_STAKEHOLDERS
    _ALL_TASKS = None
    _ALL_VENDORS = None
    _ALL_STAKEHOLDERS = None
