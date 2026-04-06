"""
Inference Script for ProcurementAI-Env
"""

import os
import sys
import json

from openai import OpenAI

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(__file__))

from env.constants import ActionType, DEFAULT_RANDOM_SEED
from env.models import Action, Observation
from env.procurement_env import ProcurementEnv
from env.tasks import load_all_tasks

# Mandatory hackathon environment variables
API_KEY = (
    os.getenv("OPENAI_API_KEY")
    or os.getenv("HF_TOKEN")
    or os.getenv("API_KEY")
    or "fake_key"
)
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
IMAGE_NAME = os.getenv("IMAGE_NAME")  # If you are using docker image
BENCHMARK = "procurement_env"

import logging
logging.basicConfig(level=logging.ERROR)


# Helpers

def _build_system_prompt() -> str:
    return (
        "You are an AI procurement manager. Your goal is to select the best vendor "
        "for the given procurement task while staying within budget.\n\n"
        "Available actions:\n"
        "- shortlist_vendor: Add a good vendor to the shortlist\n"
        "- reject_vendor: Remove a risky or poor vendor\n"
        "- negotiate_vendor: Negotiate a discount with a vendor\n"
        "- request_contract_change: Ask a vendor to change contract terms\n"
        "- request_delivery_guarantee: Ask a vendor to guarantee delivery time\n"
        "- request_clarification: Get more information about the task or a vendor\n"
        "- compare_vendors: Compare all active vendors\n"
        "- select_vendor: Choose a vendor for final selection\n"
        "- finalize_decision: Confirm your final vendor selection\n\n"
        "For each action, respond with a JSON object containing:\n"
        '- "action_type": one of the action names above\n'
        '- "vendor_name": target vendor name (if applicable)\n'
        '- "message": justification or negotiation message\n'
        '- "parameters": additional params (e.g. {"requested_discount_pct": 10})\n\n'
        "Think step-by-step. First compare vendors, reject risky ones, negotiate "
        "discounts with promising vendors, then select and finalize the best choice."
    )


def _observation_to_text(obs: Observation) -> str:
    vendors_summary = [
        f"  - {v.name}: ${v.base_price:,.0f}, quality={v.quality_rating}/10, "
        f"delivery={v.delivery_days}d, risk={v.risk_level.value}, "
        f"rating={v.customer_rating}/5, status={v.status.value}, "
        f"blacklisted={v.is_blacklisted}"
        for v in obs.vendors
    ]
    stakeholder_summary = [
        f"  - {s.name} ({s.department}): {s.notes}"
        for s in obs.stakeholder_priorities
    ]
    parts = [
        f"Task: {obs.task_description}",
        f"Budget: ${obs.budget:,.2f}",
        f"Remaining steps: {obs.remaining_steps}",
        f"Current reward: {obs.current_reward:.4f}",
        f"Finalized: {obs.finalized}",
        "",
        "Vendors:",
        "\n".join(vendors_summary),
        "",
        "Stakeholders:",
        "\n".join(stakeholder_summary),
        "",
        f"Shortlisted: {obs.shortlisted_vendors}",
        f"Rejected: {obs.rejected_vendors}",
        f"Selected: {obs.selected_vendor}",
    ]
    if obs.negotiation_history:
        parts += ["", "Negotiation history:"]
        parts += [
            f"  - Round {n.round_number} with {n.vendor_name}: {n.message}"
            for n in obs.negotiation_history
        ]
    if obs.messages:
        parts += ["", "Messages: " + "; ".join(obs.messages)]
    if obs.comparison_result:
        parts += ["", f"Comparison: {json.dumps(obs.comparison_result, indent=2)}"]
    if obs.clarification_response:
        parts += ["", f"Clarification: {obs.clarification_response}"]
    return "\n".join(parts)


def _parse_action(response_text: str) -> Action:
    text = response_text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            return Action(
                action_type=data.get("action_type", "compare_vendors"),
                vendor_name=data.get("vendor_name"),
                message=data.get("message", ""),
                parameters=data.get("parameters", {}),
            )
        except Exception:
            pass
    return Action(action_type=ActionType.COMPARE_VENDORS)


# Structured stdout logging (strict hackathon format)

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error) -> None:
    error_str = "None" if error is None else str(error).replace("\n", " ")
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={done} error={error_str}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: list) -> None:
    # Ensure score is strictly between 0 and 1
    score = float(score)
    if score <= 0:
        score = 0.01
    elif score >= 1:
        score = 0.99
    rewards_str = str([round(float(r), 4) for r in rewards]) if rewards else "[]"
    print(
        f"[END] success={success} steps={steps} score={score:.4f} "
        f"rewards={rewards_str}",
        flush=True,
    )


# Main inference loop

def main():
    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

    tasks = load_all_tasks()

    for task in tasks:
        env = ProcurementEnv(seed=DEFAULT_RANDOM_SEED)
        obs = env.reset(task_id=task.task_id)
        done = False
        step_count = 0
        rewards = []
        success = False
        score = 0.0

        log_start(task=task.task_id, env=BENCHMARK, model=MODEL_NAME)

        messages = [
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": _observation_to_text(obs)},
        ]

        try:
            while not done and step_count < 25:
                # LLM call via OpenAI Client
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=512,
                )
                assistant_text = response.choices[0].message.content or ""
                action = _parse_action(assistant_text)

                # Build action string for logging
                if action.vendor_name:
                    action_str = f"{action.action_type.value}('{action.vendor_name}')"
                else:
                    action_str = f"{action.action_type.value}()"

                # Environment step
                error = None
                info = {}
                try:
                    obs, reward_obj, done, info = env.step(action)
                    reward = reward_obj.step_reward  # Extract float from Reward model
                except Exception as e:
                    reward = 0.0
                    done = True
                    error = str(e).replace("\n", " ")

                step_count += 1
                rewards.append(reward)

                log_step(
                    step=step_count,
                    action=action_str,
                    reward=reward,
                    done=done,
                    error=error,
                )

                if done:
                    score = info.get("final_score", 0.0)
                    if score > 0:
                        success = True
                    break

                # Append conversation context for next LLM turn
                messages.append({"role": "assistant", "content": assistant_text})
                messages.append({"role": "user", "content": _observation_to_text(obs)})

        except Exception as e:
            # Log the API / outer-loop error as a failed step
            step_count += 1
            rewards.append(0.0)
            log_step(
                step=step_count,
                action="error",
                reward=0.0,
                done=True,
                error=str(e).replace("\n", " "),
            )
        finally:
            log_end(
                success=success,
                steps=step_count,
                score=score,
                rewards=rewards,
            )


if __name__ == "__main__":
    main()
