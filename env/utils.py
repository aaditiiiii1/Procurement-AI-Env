

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("procurement_env")


def get_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def load_json(filename: str) -> Any:
    path = get_data_dir() / filename
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(data: Any, filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    logger.info("Saved JSON to %s", filepath)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def safe_task_score(score: float) -> float:
    """Normalize a task score to be strictly between 0 and 1.

    Evaluation systems require 0 < score < 1, so this function:
    - Converts score <= 0 to 0.01
    - Converts score >= 1 to 0.99
    - Returns the score unchanged if already in valid range
    """
    score = float(score)
    if score <= 0:
        return 0.01
    elif score >= 1:
        return 0.99
    return score


def compute_total_cost(base_price: float, hidden_fees: Dict[str, float]) -> float:
    return base_price + sum(hidden_fees.values())


def setup_logging(log_file: str = "logs/app.log", level: int = logging.INFO) -> None:
    try:
        # Convert to absolute path
        log_path = Path(log_file).resolve()
        log_dir = log_path.parent
        log_dir.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(str(log_path), encoding="utf-8"),
                logging.StreamHandler(),
            ],
        )
    except Exception as e:
        # Fallback: use only StreamHandler if file logging fails
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[logging.StreamHandler()],
        )
        logger.warning("Failed to setup file logging to %s: %s", log_file, e)
