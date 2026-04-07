# LOCAL_TESTING.md — ProcurementAI-Env Local Testing Guide

> **Platform:** Windows + PowerShell  
> **Goal:** Fully test the project locally before deploying to Hugging Face Spaces.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Setup](#2-project-setup)
3. [Running the App Locally](#3-running-the-app-locally)
4. [Testing API Endpoints](#4-testing-api-endpoints)
5. [Running inference.py](#5-running-inferencepy)
6. [Running Tests](#6-running-tests)
7. [Docker Testing](#7-docker-testing)
8. [Troubleshooting](#8-troubleshooting)
9. [Pre-Deployment Checklist](#9-pre-deployment-checklist)

---

## 1. Prerequisites

### Python 3.10+

Check your Python version:

```powershell
python --version
```

Expected output: `Python 3.10.x` or higher.

If Python is not installed, download it from [python.org](https://www.python.org/downloads/).
During installation, **check "Add Python to PATH"**.

### Docker Desktop

Check if Docker is installed:

```powershell
docker --version
```

Expected output: `Docker version 24.x.x` or higher.

If not installed, download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
After installing, make sure Docker Desktop is **running** before any Docker commands.

### Git

Check if Git is installed:

```powershell
git --version
```

Expected output: `git version 2.x.x`.

If not installed, download from [git-scm.com](https://git-scm.com/).

### Optional: Virtual Environment

It is strongly recommended to use a virtual environment to keep dependencies isolated.

**Create a virtual environment:**

```powershell
python -m venv venv
```

**Activate the virtual environment:**

```powershell
venv\Scripts\activate
```

Your prompt should now show `(venv)` at the start.

**To deactivate:**

```powershell
deactivate
```

---

## 2. Project Setup

### Clone the Repository

```powershell
git clone https://github.com/YOUR_USERNAME/procurement-ai-env.git
```

### Enter the Project Folder

```powershell
cd procurement-ai-env
```

### Create a `.env` File

The project uses a `.env` file for secrets. Never edit `.env.example` directly.

```powershell
Copy-Item .env.example .env
```

Open the file to review or edit it:

```powershell
notepad .env
```

The `.env.example` explains each variable. For local testing **without** an API key, you can leave all keys blank — the heuristic agent will run automatically.

```
# .env — safe to leave blank for local heuristic testing
GROK_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
HF_TOKEN=
```

### Install Production Dependencies

Make sure your virtual environment is active, then:

```powershell
pip install -r requirements.txt
```

This installs: `fastapi`, `uvicorn`, `pydantic`, `openai`, `httpx`, `requests`, `python-dotenv`, `pyyaml`.

### Install Optional Dev / Test Dependencies

```powershell
pip install -r requirements-dev.txt
```

This adds `pytest` and `pytest-asyncio` for running the test suite.

### Verify Installation

```powershell
pip list
```

You should see `fastapi`, `uvicorn`, `pydantic`, and `pytest` listed.

---

## 3. Running the App Locally

### Option A — Using `app.py` directly

```powershell
python app.py
```

### Option B — Using `uvicorn` directly (recommended for production-like testing)

```powershell
uvicorn app:app --host 0.0.0.0 --port 7860 --reload
```

- `--reload` enables hot-reload so code changes are picked up automatically.
- Remove `--reload` to match production behavior.

### Expected Startup Output

```
App started
Loading tasks...
Environment ready
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:7860 (Press CTRL+C to quit)
```

The three lines `App started`, `Loading tasks...`, `Environment ready` confirm the startup
sequence completed correctly.

### Access the App

Open your browser and visit:

- **App root / docs:** `http://localhost:7860/docs` (Swagger UI)
- **ReDoc docs:** `http://localhost:7860/redoc`
- **Health check:** `http://localhost:7860/health`

### Stop the App

Press `Ctrl+C` in the PowerShell window.

---

## 4. Testing API Endpoints

The examples below assume the app is running on `http://localhost:7860`.

Each endpoint is shown in **two formats**:
- `curl` (works in PowerShell if curl is installed)
- `Invoke-RestMethod` (native PowerShell, always works)

---

### GET `/health`

**curl:**
```powershell
curl http://localhost:7860/health
```

**Invoke-RestMethod:**
```powershell
Invoke-RestMethod -Uri "http://localhost:7860/health" -Method GET
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "ProcurementAI-Env"
}
```

---

### POST `/reset`

Starts a new episode for a specific task.

**curl:**
```powershell
curl -X POST http://localhost:7860/reset `
  -H "Content-Type: application/json" `
  -d '{"task_id": "easy-001", "seed": 42}'
```

**Invoke-RestMethod:**
```powershell
$body = @{
    task_id = "easy-001"
    seed    = 42
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:7860/reset" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

**Expected response (truncated):**
```json
{
  "observation": {
    "task_id": "easy-001",
    "task_difficulty": "easy",
    "budget": 50000.0,
    "remaining_steps": 10,
    "vendors": [...],
    "shortlisted_vendors": [],
    "rejected_vendors": [],
    "current_reward": 0.0,
    "selected_vendor": null,
    "finalized": false
  },
  "info": {
    "message": "Environment reset successfully.",
    "task_id": "easy-001"
  }
}
```

---

### GET `/state`

Returns the full current environment state (must call `/reset` first).

**curl:**
```powershell
curl http://localhost:7860/state
```

**Invoke-RestMethod:**
```powershell
Invoke-RestMethod -Uri "http://localhost:7860/state" -Method GET
```

**Expected response:**
```json
{
  "task_id": "easy-001",
  "difficulty": "easy",
  "step_count": 0,
  "remaining_steps": 10,
  "budget": 50000.0,
  "cumulative_reward": 0.0,
  "shortlisted_vendors": [],
  "rejected_vendors": [],
  "selected_vendor": null,
  "finalized": false,
  "termination_reason": "not_terminated"
}
```

---

### POST `/step`

Executes one agent action. Always call `/reset` first.

#### Compare Vendors

**Invoke-RestMethod:**
```powershell
$body = @{ action_type = "compare_vendors" } | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:7860/step" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

#### Shortlist a Vendor

```powershell
$body = @{
    action_type = "shortlist_vendor"
    vendor_name = "TechVault Solutions"
    message     = "Best overall score"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:7860/step" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

#### Negotiate a Discount

```powershell
$body = @{
    action_type = "negotiate_vendor"
    vendor_name = "CloudNova"
    message     = "Please reduce the price by 10%."
    parameters  = @{ requested_discount_pct = 10 }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "http://localhost:7860/step" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

#### Reject a Risky Vendor

```powershell
$body = @{
    action_type = "reject_vendor"
    vendor_name = "RiskySupplierCo"
    message     = "High risk level and no data portability."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:7860/step" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

#### Select a Vendor

```powershell
$body = @{
    action_type = "select_vendor"
    vendor_name = "TechVault Solutions"
    message     = "Best value within budget."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:7860/step" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

#### Finalize the Decision

```powershell
$body = @{ action_type = "finalize_decision" } | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:7860/step" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

**Expected `/step` response format:**
```json
{
  "observation": {
    "remaining_steps": 9,
    "current_reward": 0.05
  },
  "reward": {
    "step_reward": 0.05,
    "cumulative_reward": 0.05,
    "breakdown": { "shortlist": 0.05 }
  },
  "done": false,
  "info": { "step": 1 }
}
```

---

### GET `/tasks`

Lists all 10 available tasks.

**curl:**
```powershell
curl http://localhost:7860/tasks
```

**Invoke-RestMethod:**
```powershell
Invoke-RestMethod -Uri "http://localhost:7860/tasks" -Method GET
```

**Expected response:**
```json
{
  "tasks": [
    { "task_id": "easy-001", "title": "Office Laptop Procurement for Startup", "difficulty": "easy" },
    { "task_id": "easy-002", "title": "Office Supply Vendor Selection", "difficulty": "easy" },
    ...
  ],
  "total": 10
}
```

---

## 5. Running `inference.py`

`inference.py` runs all 10 tasks end-to-end and saves scores to `results/baseline_scores.json`.

### Without API Key (Heuristic Agent — recommended for quick testing)

```powershell
python inference.py
```

No API key is needed. The heuristic agent runs automatically.

### With Grok API (Primary LLM)

```powershell
$env:GROK_API_KEY = "xai-your-key-here"
$env:GEMINI_API_KEY = "your-gemini-key"   # optional: rate-limit fallback
python inference.py
```

### With Gemini Only (No Grok Key)

```powershell
$env:GEMINI_API_KEY = "your-gemini-key"
python inference.py
```

### Expected Console Output

```
INFO: No API key set — running deterministic heuristic fallback agent.
INFO: Set GROK_API_KEY (primary) or GEMINI_API_KEY (fallback) to use LLM inference.

============================================================
  Inference complete: 10 tasks
  Provider: heuristic  |  Model: heuristic
  Average score: 0.5974
  Elapsed time:  0.1s
  Results saved: .\results\baseline_scores.json
============================================================

  [easy  ] easy-001     score=0.6299 vendor=ProGear International     (finalized)
  [easy  ] easy-002     score=0.0000 vendor=NONE                      (impossible_budget)
  [easy  ] easy-003     score=0.7161 vendor=TechVault Solutions       (finalized)
  [hard  ] hard-001     score=0.5102 vendor=Apex Enterprise Solutions (finalized)
  [hard  ] hard-002     score=0.6813 vendor=Meridian Consulting Group (finalized)
  [hard  ] hard-003     score=0.7081 vendor=Meridian Consulting Group (finalized)
  [medium] medium-001   score=0.6367 vendor=NimbusWare                (finalized)
  [medium] medium-002   score=0.7473 vendor=CloudNova                 (finalized)
  [medium] medium-003   score=0.8345 vendor=NimbusWare                (finalized)
  [medium] medium-004   score=0.5102 vendor=NimbusWare                (finalized)
```

### Verify Reproducible Scores

Run inference twice and compare the scores — they must be **identical**:

```powershell
python inference.py
python inference.py
```

If the scores match exactly both times, determinism is confirmed (`random.seed(42)` is working).

### Verify Heuristic Fallback

Confirm that inference runs successfully with **no API keys** set:

```powershell
# Clear any existing keys
Remove-Item Env:GROK_API_KEY   -ErrorAction SilentlyContinue
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue

python inference.py
```

The output should show `Provider: heuristic` and complete all 10 tasks without error.

### Inspect the Results File

```powershell
Get-Content results\baseline_scores.json | ConvertFrom-Json | Select-Object model, agent, average_score
```

---

## 6. Running Tests

Make sure you have installed dev dependencies (`pip install -r requirements-dev.txt`) and the app
is **not** running on port 7860 (the test suite starts its own test client).

### Run All Tests

```powershell
pytest
```

### Run with Verbose Output

```powershell
pytest -v
```

### Run a Specific Test File

```powershell
pytest tests/test_reset.py
pytest tests/test_step.py
pytest tests/test_rewards.py
pytest tests/test_graders.py
pytest tests/test_invalid_actions.py
pytest tests/test_state.py
pytest tests/test_api.py
```

### Run a Specific Test Case

```powershell
pytest tests/test_step.py::TestStep::test_shortlist_vendor -v
```

### What Passing Tests Look Like

```
============================= test session starts ==============================
platform win32 -- Python 3.11.x, pytest-8.x.x, pluggy-1.x.x
collected 42 items

tests/test_reset.py ....                                                  [ 9%]
tests/test_step.py .........                                              [30%]
tests/test_state.py ....                                                  [40%]
tests/test_rewards.py .......                                             [57%]
tests/test_graders.py ......                                              [71%]
tests/test_invalid_actions.py ....                                        [81%]
tests/test_api.py ........                                               [100%]

============================== 42 passed in 3.21s ==============================
```

All tests should show `.` (pass). If you see `F` (fail) or `E` (error), see the
[Troubleshooting](#8-troubleshooting) section.

### Run Tests and Show Coverage (optional)

```powershell
pip install pytest-cov
pytest --cov=env --cov-report=term-missing
```

---

## 7. Docker Testing

### Build the Docker Image

```powershell
docker build -t procurement-ai-env .
```

This reads the `Dockerfile` and installs only production dependencies (`requirements.txt`).
Expected output ends with:
```
Successfully built <image-id>
Successfully tagged procurement-ai-env:latest
```

### Run the Container (No API Key — Heuristic Mode)

```powershell
docker run -p 7860:7860 --name procurement-test procurement-ai-env
```

### Run the Container with Grok + Gemini Keys

```powershell
docker run -p 7860:7860 --name procurement-test `
  -e GROK_API_KEY=xai-your-key `
  -e GEMINI_API_KEY=your-gemini-key `
  procurement-ai-env
```

Secrets are passed at **runtime** via `-e` — they are never baked into the image.

### Expected Container Startup Output

```
App started
Loading tasks...
Environment ready
INFO:     Started server process [1]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:7860
```

### Access the App

```powershell
# In a new PowerShell window:
Invoke-RestMethod -Uri "http://localhost:7860/health"
```

Or open `http://localhost:7860/docs` in your browser.

### Run in Detached Mode (Background)

```powershell
docker run -d -p 7860:7860 --name procurement-test procurement-ai-env
```

### Inspect Container Logs

```powershell
docker logs procurement-test
```

Follow logs in real-time:

```powershell
docker logs -f procurement-test
```

### Stop the Container

```powershell
docker stop procurement-test
```

### Remove the Container

```powershell
docker rm procurement-test
```

### Remove the Image (to force a clean rebuild)

```powershell
docker rmi procurement-ai-env
```

### Full Clean Rebuild

```powershell
docker stop procurement-test 2>$null
docker rm procurement-test 2>$null
docker build --no-cache -t procurement-ai-env .
docker run -p 7860:7860 --name procurement-test procurement-ai-env
```

### Docker Compose (Alternative)

If you prefer Docker Compose:

```powershell
docker-compose up --build
```

To stop:

```powershell
docker-compose down
```

---

## 8. Troubleshooting

### `ModuleNotFoundError: No module named 'env'`

**Cause:** Python cannot find the `env` package because you are not running from the project root.

**Fix:**
```powershell
# Make sure you are in the project root
cd C:\path\to\procurement-ai-env
python app.py
```

Also verify the `env/` folder has an `__init__.py` file:
```powershell
Test-Path env\__init__.py
# Should return: True
```

---

### `ModuleNotFoundError: No module named 'fastapi'`

**Cause:** Dependencies not installed, or the wrong Python environment is active.

**Fix:**
```powershell
# Activate your virtual environment first
venv\Scripts\activate

# Then install
pip install -r requirements.txt

# Verify
python -c "import fastapi; print(fastapi.__version__)"
```

---

### `Address already in use` / Port 7860 Busy

**Cause:** Another process (or a previous app instance) is already using port 7860.

**Fix — find and kill the process:**
```powershell
# Find the process using port 7860
netstat -ano | findstr :7860

# Kill it (replace XXXX with the PID from the output above)
taskkill /PID XXXX /F
```

Or run on a different port:
```powershell
uvicorn app:app --host 0.0.0.0 --port 8000
```

---

### Docker Build Fails with `No such file or directory`

**Cause:** `Dockerfile` references a file that doesn't exist, or you ran `docker build` from the wrong directory.

**Fix:**
```powershell
# Run from the project root (where Dockerfile lives)
cd C:\path\to\procurement-ai-env
docker build -t procurement-ai-env .
```

Also verify the `Dockerfile` exists:
```powershell
Test-Path Dockerfile
# Should return: True
```

---

### Docker Build Fails with `pip install` Error

**Cause:** Network issue downloading packages, or a package version conflict.

**Fix:**
```powershell
# Force a clean rebuild without cache
docker build --no-cache -t procurement-ai-env .
```

If a package fails, check that `requirements.txt` does not contain typos:
```powershell
Get-Content requirements.txt
```

---

### API Endpoint Returns 404

**Cause:** The endpoint path is wrong, or the app is not running.

**Fix:**
1. Confirm the app is running: look for `Uvicorn running on http://0.0.0.0:7860` in the terminal.
2. Check the exact path — note there is no trailing slash.
3. Visit `http://localhost:7860/docs` to see all registered routes.

---

### `POST /step` Returns 400 / `No active episode`

**Cause:** You called `/step` without calling `/reset` first to start an episode.

**Fix:**
```powershell
# Always call /reset before /step
$body = @{ task_id = "easy-001"; seed = 42 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:7860/reset" -Method POST -ContentType "application/json" -Body $body
```

---

### Missing Environment Variable Warning

**Cause:** A key in `.env` is empty or `.env` does not exist.

**Fix:**
```powershell
# Check if .env exists
Test-Path .env

# If not, create it
Copy-Item .env.example .env

# Check its contents
Get-Content .env
```

For heuristic-only testing, all variables can safely remain blank.

---

### `ImportError: cannot import name 'X' from 'env'`

**Cause:** There is a Python cache conflict with the `env` folder name and Python's built-in.

**Fix:** Clear the cache and retry:
```powershell
# Remove all __pycache__ folders
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force

# Remove compiled .pyc files
Get-ChildItem -Recurse -Filter *.pyc | Remove-Item -Force

python app.py
```

---

### `FileNotFoundError: Data file not found: data/vendors.json`

**Cause:** The `data/` directory is missing or the file was not cloned properly.

**Fix:**
```powershell
# List data directory
Get-ChildItem data\

# Should show:
# easy_tasks.json, medium_tasks.json, hard_tasks.json
# vendors.json, contracts.json, stakeholder_profiles.json

# If missing, re-clone the repo
git pull origin main
```

---

### FastAPI Startup Failure / No Output After Starting

**Cause:** A Python import error is silently crashing the app before uvicorn starts.

**Fix:** Run with explicit Python to see the full traceback:
```powershell
python -c "import app"
```

This will print the exact import error. Fix the error and retry.

---

### Uvicorn Command Not Found

**Cause:** `uvicorn` is not installed or the virtual environment is not activated.

**Fix:**
```powershell
venv\Scripts\activate
pip install "uvicorn[standard]"
uvicorn --version
```

---

### `inference.py` Crashes / No Output

**Cause:** Usually an import error or missing data file.

**Fix:**
```powershell
# Check syntax first
python -c "import py_compile; py_compile.compile('inference.py', doraise=True); print('Syntax OK')"

# Run directly to see the full error
python inference.py
```

---

### `pytest` Not Found

**Cause:** Dev dependencies not installed.

**Fix:**
```powershell
pip install -r requirements-dev.txt
pytest --version
```

---

## 9. Pre-Deployment Checklist

Run through this checklist before pushing to GitHub or deploying to Hugging Face Spaces.

```
CATEGORY           CHECK                                               STATUS
─────────────────────────────────────────────────────────────────────────────
Files              [ ] inference.py exists in root
                   [ ] app.py exists in root
                   [ ] openenv.yaml exists in root
                   [ ] Dockerfile exists in root
                   [ ] README.md exists in root
                   [ ] requirements.txt exists in root
                   [ ] requirements-dev.txt exists in root
                   [ ] .env.example exists (placeholder values only)
                   [ ] .env is listed in .gitignore (never committed)

Dependencies       [ ] requirements.txt contains NO pytest / heavy ML libs
                   [ ] requirements-dev.txt contains pytest & pytest-asyncio
                   [ ] Both files install cleanly: pip install -r requirements.txt

Secrets            [ ] .env file is NOT tracked by git
                   [ ] No real API keys hardcoded in any .py file
                   [ ] .env.example has placeholder values only (no real secrets)

Tests              [ ] All pytest tests pass: pytest -v
                   [ ] No test failures or import errors

API Endpoints      [ ] GET  /health   returns {"status": "healthy"}
                   [ ] POST /reset    returns a valid observation
                   [ ] GET  /state    returns current episode state
                   [ ] POST /step     processes actions correctly
                   [ ] GET  /tasks    lists all 10 tasks

Inference          [ ] python inference.py runs to completion
                   [ ] Average score is non-zero (9/10 tasks finalized)
                   [ ] Two consecutive runs produce identical scores (determinism)
                   [ ] Script works with NO API keys set (heuristic fallback)

Docker             [ ] docker build -t procurement-ai-env . completes without error
                   [ ] docker run -p 7860:7860 procurement-ai-env starts the server
                   [ ] Startup prints "App started", "Loading tasks...", "Environment ready"
                   [ ] /health endpoint responds from within the container

Startup Logs       [ ] "App started" printed on startup
                   [ ] "Loading tasks..." printed on startup
                   [ ] "Environment ready" printed on startup
                   [ ] No exception tracebacks on clean startup

Git                [ ] git status shows no untracked .env files
                   [ ] git log shows clean, meaningful commit messages
                   [ ] All changes committed and pushed to the correct branch
```

### Quick Verification Commands

Run all checks in sequence:

```powershell
# 1. Check required files exist
@("inference.py","app.py","openenv.yaml","Dockerfile","README.md",
  "requirements.txt","requirements-dev.txt",".env.example") | ForEach-Object {
    "$_ -> $(if(Test-Path $_){'OK'}else{'MISSING'})"
}

# 2. Check .env is gitignored
git check-ignore -v .env

# 3. Run all tests
pytest -v

# 4. Run inference (no API key)
python inference.py

# 5. Docker build
docker build -t procurement-ai-env .

# 6. Check no secrets in source code
Select-String -Path "*.py","**/*.py" -Pattern "sk-|xai-|AIza" -Recurse
# Should return: no output (no matches)
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start app | `python app.py` |
| Start with uvicorn | `uvicorn app:app --host 0.0.0.0 --port 7860 --reload` |
| Run inference | `python inference.py` |
| Run all tests | `pytest -v` |
| Build Docker image | `docker build -t procurement-ai-env .` |
| Run Docker container | `docker run -p 7860:7860 procurement-ai-env` |
| View container logs | `docker logs procurement-test` |
| Stop container | `docker stop procurement-test` |
| Health check (PS) | `Invoke-RestMethod -Uri http://localhost:7860/health` |
| Reset env (PS) | `Invoke-RestMethod -Uri http://localhost:7860/reset -Method POST -ContentType "application/json" -Body '{"task_id":"easy-001","seed":42}'` |

---

*This guide is for local testing only. For production deployment, see the [README.md](README.md) HF Deployment section.*
