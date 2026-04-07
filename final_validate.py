"""Final comprehensive validation before submission."""
import sys
import os

sys.path.insert(0, ".")

print("=== FINAL VALIDATION ===")
print()

# 1. Check all required files exist
required_files = [
    "inference.py", "server/app.py", "openenv.yaml", "Dockerfile",
    "docker-compose.yml", "requirements.txt", "README.md",
    "LICENSE", ".env.example", ".gitignore", ".dockerignore",
    "env/__init__.py", "env/models.py", "env/procurement_env.py",
    "env/graders.py", "env/reward.py", "env/tasks.py",
    "env/negotiation.py", "env/vendor_logic.py", "env/constants.py",
    "env/utils.py",
    "data/easy_tasks.json", "data/medium_tasks.json", "data/hard_tasks.json",
    "data/vendors.json", "data/stakeholder_profiles.json", "data/contracts.json",
    "results/baseline_scores.json",
]
all_exist = True
for f in required_files:
    exists = os.path.isfile(f)
    if not exists:
        print(f"  MISSING: {f}")
        all_exist = False
status = "PASS" if all_exist else "FAIL"
print(f"1. Required files: {status}")

# 2. Check inference.py has correct env vars and log format
with open("inference.py", encoding="utf-8") as f:
    code = f.read()
has_openai = "OPENAI_API_KEY" in code
has_base_url = "API_BASE_URL" in code
has_model = "MODEL_NAME" in code
has_hf_token = "HF_TOKEN" in code
has_log_start = "[START]" in code
has_log_step = "[STEP]" in code
has_log_end = "[END]" in code
has_score = "score=" in code
env_ok = has_openai and has_base_url and has_model and has_hf_token
log_ok = has_log_start and has_log_step and has_log_end and has_score

status = "PASS" if env_ok else "FAIL"
print(f"2. Env vars in inference.py: {status}")
status = "PASS" if log_ok else "FAIL"
print(f"3. Log format [START/STEP/END+score]: {status}")

# 3. Check openenv.yaml
import yaml
with open("openenv.yaml", encoding="utf-8") as f:
    oedata = yaml.safe_load(f)
required_keys = [
    "name", "description", "version", "environment", "endpoints",
    "action_space", "observation_space", "tasks", "reward_design", "deployment",
]
yaml_ok = all(k in oedata for k in required_keys)
status = "PASS" if yaml_ok else "FAIL"
print(f"4. openenv.yaml completeness: {status}")

# 4. Check tasks
from env.tasks import load_all_tasks
tasks = load_all_tasks()
task_ok = len(tasks) >= 3
diffs = set(t.difficulty.value for t in tasks)
diff_ok = diffs == {"easy", "medium", "hard"}
status = "PASS" if (task_ok and diff_ok) else "FAIL"
print(f"5. Tasks: {len(tasks)} total, difficulties={diffs}: {status}")

# 5. Check API endpoints
from fastapi.testclient import TestClient
from server.app import app
c = TestClient(app)
results = {}
results["reset"] = c.post("/reset", json={"task_id": "easy-001", "seed": 42}).status_code
results["step"] = c.post("/step", json={"action_type": "compare_vendors"}).status_code
results["state"] = c.get("/state").status_code
results["health"] = c.get("/health").status_code
results["tasks"] = c.get("/tasks").status_code
api_ok = all(v == 200 for v in results.values())
status = "PASS" if api_ok else "FAIL"
print(f"6. API endpoints: {status} {results}")

# 6. Check Reward object
from env.procurement_env import ProcurementEnv
from env.models import Action
from env.constants import ActionType
env = ProcurementEnv(seed=42)
obs = env.reset(task_id="easy-001")
obs, reward_obj, done, info = env.step(Action(action_type=ActionType.COMPARE_VENDORS))
reward_type_ok = hasattr(reward_obj, "step_reward") and isinstance(reward_obj.step_reward, (float, int))
status = "PASS" if reward_type_ok else "FAIL"
print(f"7. Reward.step_reward is value: {status}")

# 7. Check graders produce 0-1 (strictly between 0 and 1)
from env.constants import DEFAULT_RANDOM_SEED
all_scores_ok = True
for task in tasks:
    env2 = ProcurementEnv(seed=DEFAULT_RANDOM_SEED)
    obs = env2.reset(task_id=task.task_id)
    obs, r, done, info = env2.step(Action(action_type=ActionType.COMPARE_VENDORS))
    if not done:
        v = next((v for v in obs.vendors if not v.is_blacklisted), obs.vendors[0])
        obs, r, done, info = env2.step(
            Action(action_type=ActionType.SELECT_VENDOR, vendor_name=v.name)
        )
        if not done:
            obs, r, done, info = env2.step(Action(action_type=ActionType.FINALIZE_DECISION))
    score = info.get("final_score", 0.0)
    # Scores must be strictly between 0 and 1
    if not (0 < score < 1):
        print(f"  BAD SCORE: {task.task_id} = {score} (must be 0 < score < 1)")
        all_scores_ok = False
status = "PASS" if all_scores_ok else "FAIL"
print(f"8. All grader scores in (0, 1): {status}")

# 8. Dockerfile
with open("Dockerfile", encoding="utf-8") as f:
    df = f.read()
df_ok = "7860" in df and "uvicorn" in df
status = "PASS" if df_ok else "FAIL"
print(f"9. Dockerfile (port 7860 + uvicorn): {status}")

# 9. README no placeholders
with open("README.md", encoding="utf-8") as f:
    readme = f.read()
no_placeholder = "YOUR_USERNAME" not in readme
has_github = "codzzz" in readme
status = "PASS" if (no_placeholder and has_github) else "FAIL"
print(f"10. README links (no placeholders, has username): {status}")

# 10. OpenAI Client usage
uses_openai_client = "from openai import OpenAI" in code
status = "PASS" if uses_openai_client else "FAIL"
print(f"11. Uses OpenAI Client: {status}")

print()
all_checks = [
    all_exist, env_ok, log_ok, yaml_ok, task_ok, diff_ok,
    api_ok, reward_type_ok, all_scores_ok, df_ok, no_placeholder,
    has_github, uses_openai_client,
]
if all(all_checks):
    print("========================================")
    print("  ALL 11 CHECKS PASSED!")
    print("  READY FOR SUBMISSION")
    print("========================================")
else:
    failed = sum(1 for c in all_checks if not c)
    print(f"  {failed} CHECK(S) FAILED")
