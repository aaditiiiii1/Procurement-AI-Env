# ProcurementAI-Env

**An OpenEnv-compatible environment** where an AI agent acts as a procurement manager - comparing vendors, negotiating contracts, managing risk, and selecting the best vendor under budget constraints.

---

## Table of Contents

- [Overview](#overview)
- [Folder Structure](#folder-structure)
- [Quick Start](#quick-start)
- [Hugging Face Deployment](#hugging-face-deployment)
- [API Endpoint Documentation](#api-endpoint-documentation)
- [curl Examples](#curl-examples)
- [Running Inference](#running-inference)
- [Baseline Scores](#baseline-scores)
- [Task Descriptions](#task-descriptions)
- [Action Space](#action-space)
- [Reward Design](#reward-design)
- [Reproducibility](#reproducibility)
- [Running Tests](#running-tests)

---

## Overview

**ProcurementAI-Env** simulates a realistic procurement workflow where an AI agent must:

- Compare vendors across multiple dimensions (cost, quality, risk, delivery)
- Negotiate discounts and improved contract terms
- Evaluate compliance and legal risks
- Handle hidden fees and vendor lock-in
- Satisfy conflicting stakeholder priorities
- Make optimal vendor selections under budget constraints

| Challenge | What Makes It Hard |
|---|---|
| **Multi-objective optimisation** | Cheapest ≠ best. Balance cost, quality, delivery, risk, and stakeholder satisfaction. |
| **Hidden information** | Some vendors have hidden fees, auto-renewal traps, and lock-in clauses. |
| **Conflicting stakeholders** | Finance wants low cost, Engineering wants quality, Legal wants safe contracts. |
| **Negotiation** | Vendors respond dynamically to discount requests and contract proposals. |
| **Risk assessment** | Blacklisted vendors and compliance gaps must be identified and avoided. |
| **Limited steps** | Wasted actions are penalised - agents must act efficiently. |

---

## Folder Structure

```
procurement-ai-env/
│
├── app.py                        # FastAPI application
├── inference.py                  # Inference script - LLM or heuristic fallback
├── openenv.yaml                  # OpenEnv metadata specification
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── .env.example
├── .gitignore
├── .dockerignore
├── pytest.ini
│
├── env/                          # Core environment package
│   ├── __init__.py
│   ├── constants.py
│   ├── models.py
│   ├── procurement_env.py        # Main env class (reset / step / state)
│   ├── reward.py
│   ├── graders.py
│   ├── tasks.py
│   ├── negotiation.py
│   ├── vendor_logic.py
│   └── utils.py
│
├── data/                         # Task and vendor datasets (JSON)
│   ├── easy_tasks.json
│   ├── medium_tasks.json
│   ├── hard_tasks.json
│   ├── vendors.json
│   ├── contracts.json
│   └── stakeholder_profiles.json
│
├── tests/
│   ├── test_reset.py
│   ├── test_step.py
│   ├── test_state.py
│   ├── test_rewards.py
│   ├── test_graders.py
│   ├── test_invalid_actions.py
│   └── test_api.py
│
├── results/                      # Inference output (git-ignored)
│   └── baseline_scores.json
│
└── logs/                         # Application logs (git-ignored)
    └── app.log
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for containerised deployment)

### Local Development

```powershell
git clone https://github.com/codzzz/procurement-ai-env.git
cd procurement-ai-env

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

copy .env.example .env
# Edit .env - set GROK_API_KEY for LLM inference, or leave blank for heuristic

python app.py
# API available at http://localhost:7860
```

### Docker (Local)

```powershell
docker build -t procurement-ai-env .

# Run without secrets (uses heuristic fallback agent)
docker run -p 7860:7860 procurement-ai-env

# Run with Grok + Gemini fallback
docker run -p 7860:7860 `
  -e GROK_API_KEY=xai-your-key `
  -e GEMINI_API_KEY=your-gemini-key `
  procurement-ai-env
```

### Docker Compose

```powershell
docker-compose up --build
```

---

## Hugging Face Deployment

### Step-by-step

1. **Create a new Space** at [huggingface.co/spaces](https://huggingface.co/spaces)
   - SDK: **Docker**
   - Hardware: CPU Basic (free tier works)

2. **Push your code** to the Space repository:
   ```powershell
   git remote add hf https://huggingface.co/spaces/codzzz/procurement-ai-env
   git push hf main
   ```

3. **Add Secrets** in the Space Settings -> Repository Secrets:
   | Secret | Value |
   |--------|-------|
   | `GROK_API_KEY` | `xai-...` | 
   | `GROK_MODEL` | `grok-2-latest` | 
   | `GEMINI_API_KEY` | `AIza...` | 
   | `GEMINI_MODEL` | `gemini-2.0-flash` | 
   | `OPENAI_API_KEY` | `sk-...` |
   | `HF_TOKEN` | `hf_...` | 

   > **Never commit real secrets.** Use `.env.example` as a template and add real values only via HF Space Secrets.

4. **Wait for build** - watch the build logs for:
   ```
   App started
   Loading tasks...
   Environment ready
   ```

5. **Validate** the deployment:
   ```powershell
   curl.exe https://codzzz-procurement-ai-env.hf.space/health
   ```

### If HF Build Gets Stuck

Try in order:
1. **Restart Space** - Space Settings -> Restart Space
2. **Factory Rebuild** - Space Settings -> Factory Rebuild
3. **Duplicate Space** - create a fresh copy and re-push
4. **Re-upload code** - delete all files in the Space repo and push again

### Live Space URL

```
https://huggingface.co/spaces/codzzz/procurement-ai-env
```

---

## API Endpoint Documentation

### Required Endpoints

| Method | Path | Description | Request Body |
|--------|------|-------------|--------------|
| `POST` | `/reset` | Reset environment, start new episode | `{"task_id": "easy-001", "seed": 42}` |
| `POST` | `/step` | Execute one agent action | `Action` object |
| `GET` | `/state` | Full environment state snapshot | - |

### Optional Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/tasks` | List all 10 available tasks |

### Interactive Docs

Once running, visit:
- **Swagger UI**: `http://localhost:7860/docs`
- **ReDoc**: `http://localhost:7860/redoc`

### Request / Response Schemas

#### `POST /reset`

```json
// Request
{
  "task_id": "easy-001",
  "seed": 42
}

// Response
{
  "observation": {
    "task_id": "easy-001",
    "task_difficulty": "easy",
    "task_description": "...",
    "budget": 50000.0,
    "remaining_steps": 10,
    "vendors": [...],
    "stakeholder_priorities": [...],
    "shortlisted_vendors": [],
    "rejected_vendors": [],
    "current_reward": 0.0,
    "selected_vendor": null,
    "finalized": false,
    "messages": ["Episode started: Office Laptop Procurement for Startup"]
  },
  "info": {
    "message": "Environment reset successfully.",
    "task_id": "easy-001"
  }
}
```

#### `POST /step`

```json
// Request
{
  "action_type": "negotiate_vendor",
  "vendor_name": "CloudNova",
  "message": "Please reduce the price by 10% and waive the onboarding fee.",
  "parameters": {"requested_discount_pct": 10}
}

// Response
{
  "observation": { "remaining_steps": 9, "current_reward": 0.1, ... },
  "reward": {
    "step_reward": 0.1,
    "cumulative_reward": 0.1,
    "breakdown": {"negotiation": 0.1}
  },
  "done": false,
  "info": {"step": 1}
}
```

#### `GET /state`

```json
{
  "task_id": "easy-001",
  "difficulty": "easy",
  "step_count": 3,
  "remaining_steps": 7,
  "budget": 50000.0,
  "cumulative_reward": 0.15,
  "shortlisted_vendors": ["TechVault Solutions"],
  "rejected_vendors": ["RiskySupplierCo"],
  "selected_vendor": null,
  "finalized": false,
  "termination_reason": "not_terminated"
}
```

---

## curl Examples

### Health Check

```powershell
curl.exe http://localhost:7860/health
```
```json
{"status": "healthy", "version": "1.0.0", "environment": "ProcurementAI-Env"}
```

---

### Reset to a specific task

```powershell
curl.exe -X POST http://localhost:7860/reset `
  -H "Content-Type: application/json" `
  -d "{\"task_id\": \"easy-001\", \"seed\": 42}"
```

---

### Compare all vendors

```powershell
curl.exe -X POST http://localhost:7860/step `
  -H "Content-Type: application/json" `
  -d "{\"action_type\": \"compare_vendors\"}"
```

---

### Shortlist a vendor

```powershell
curl.exe -X POST http://localhost:7860/step `
  -H "Content-Type: application/json" `
  -d "{\"action_type\": \"shortlist_vendor\", \"vendor_name\": \"TechVault Solutions\"}"
```

---

### Reject a risky vendor

```powershell
curl.exe -X POST http://localhost:7860/step `
  -H "Content-Type: application/json" `
  -d "{\"action_type\": \"reject_vendor\", \"vendor_name\": \"RiskySupplierCo\", \"message\": \"High risk level and missing compliance certifications.\"}"
```

---

### Negotiate a discount

```powershell
curl.exe -X POST http://localhost:7860/step `
  -H "Content-Type: application/json" `
  -d "{\"action_type\": \"negotiate_vendor\", \"vendor_name\": \"CloudNova\", \"message\": \"Can you offer a 10% discount and remove the onboarding fee?\", \"parameters\": {\"requested_discount_pct\": 10}}"
```

---

### Select and finalize

```powershell
# Select
curl.exe -X POST http://localhost:7860/step `
  -H "Content-Type: application/json" `
  -d "{\"action_type\": \"select_vendor\", \"vendor_name\": \"TechVault Solutions\"}"

# Finalize
curl.exe -X POST http://localhost:7860/step `
  -H "Content-Type: application/json" `
  -d "{\"action_type\": \"finalize_decision\"}"
```

---

### Get current state

```powershell
curl.exe http://localhost:7860/state
```

---

### List all tasks

```powershell
curl.exe http://localhost:7860/tasks
```

---

## Running Inference

`inference.py` uses the OpenAI Client SDK and reads the mandatory hackathon variables.

### Standard Usage (Hackathon)

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:API_BASE_URL="https://router.huggingface.co/v1"
$env:MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"

python inference.py
```

### With HF Token as API Key

```powershell
$env:HF_TOKEN="hf_your-token"
$env:API_BASE_URL="https://router.huggingface.co/v1"
$env:MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"

python inference.py
```

### Output Format

The script emits structured stdout logs for each of the 10 tasks:

```
[START] task=easy-001 env=procurement_env model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=compare_vendors() reward=-0.03 done=false error=null
[STEP] step=2 action=shortlist_vendor('TechVault Solutions') reward=0.05 done=false error=null
...
[END] success=true steps=6 score=0.72 rewards=-0.03,0.05,0.10,0.30,0.00,0.00
```

Results are saved to `results/baseline_scores.json`.

---

## Baseline Scores

> Scores from the **deterministic heuristic agent** (`random.seed(42)`, no API key required). Fully reproducible across runs.

| Task ID | Title | Difficulty | Score | Vendor Selected | Termination |
|---------|-------|-----------|-------|----------------|-------------|
| `easy-001` | Office Laptop Procurement for Startup | Easy | **0.6299** | ProGear International | finalized |
| `easy-002` | Office Supply Vendor Selection | Easy | **0.0000** | - | impossible_budget* |
| `easy-003` | Conference Room AV Equipment Purchase | Easy | **0.7161** | TechVault Solutions | finalized |
| `hard-001` | Enterprise Digital Transformation Services | Hard | **0.5102** | Apex Enterprise Solutions | finalized |
| `hard-002` | Multi-Department IT Infrastructure Overhaul | Hard | **0.6813** | Meridian Consulting Group | finalized |
| `hard-003` | Global Supply Chain Management Platform | Hard | **0.7081** | Meridian Consulting Group | finalized |
| `medium-001` | Cloud CRM Platform Subscription | Medium | **0.6367** | NimbusWare | finalized |
| `medium-002` | Project Management SaaS Selection | Medium | **0.7473** | CloudNova | finalized |
| `medium-003` | Data Analytics Platform Procurement | Medium | **0.8345** | NimbusWare | finalized |
| `medium-004` | Cybersecurity Monitoring Tool Subscription | Medium | **0.5102** | NimbusWare | finalized |

**Average score: 0.5974 | Agent: heuristic | Seed: 42**

> \* `easy-002` is an intentional stress-test: all vendors exceed 150% of the budget. The environment correctly terminates with `impossible_budget`.

### Score Ranges by Difficulty

| Difficulty | Heuristic Baseline | Expected LLM Range |
|------------|-------------------|-------------------|
| Easy | 0.00 - 0.72 | 0.70 - 0.95 |
| Medium | 0.51 - 0.83 | 0.55 - 0.90 |
| Hard | 0.51 - 0.71 | 0.40 - 0.80 |

---

## Task Descriptions

### Easy Tasks (3 tasks, max 10 steps)

| Task ID | Title | Budget | Vendors |
|---------|-------|--------|---------|
| `easy-001` | Office Laptop Procurement for Startup | $50,000 | 3 |
| `easy-002` | Office Supply Vendor Selection | $5,000 | 2 |
| `easy-003` | Conference Room AV Equipment Purchase | $45,000 | 3 |

### Medium Tasks (4 tasks, max 15 steps)

| Task ID | Title | Budget | Vendors |
|---------|-------|--------|---------|
| `medium-001` | Cloud CRM Platform Subscription | $20,000 | 5 |
| `medium-002` | Project Management SaaS Selection | $18,000 | 4 |
| `medium-003` | Data Analytics Platform Procurement | $25,000 | 5 |
| `medium-004` | Cybersecurity Monitoring Tool Subscription | $19,000 | 4 |

### Hard Tasks (3 tasks, max 25 steps)

| Task ID | Title | Budget | Vendors |
|---------|-------|--------|---------|
| `hard-001` | Enterprise Digital Transformation Services | $110,000 | 6 |
| `hard-002` | Multi-Department IT Infrastructure Overhaul | $100,000 | 6 |
| `hard-003` | Global Supply Chain Management Platform | $95,000 | 6 |

---

## Action Space

| Action | Description | Requires `vendor_name` |
|--------|-------------|----------------------|
| `compare_vendors` | Compare all active vendors side-by-side | No |
| `shortlist_vendor` | Add a vendor to the shortlist | Yes |
| `reject_vendor` | Remove a risky or unsuitable vendor | Yes |
| `negotiate_vendor` | Negotiate a discount (param: `requested_discount_pct`) | Yes |
| `request_contract_change` | Ask for contract modifications | Yes |
| `request_delivery_guarantee` | Request delivery within `required_days` | Yes |
| `request_clarification` | Get more info about the task or a vendor | No |
| `select_vendor` | Choose the final vendor | Yes |
| `finalize_decision` | Confirm and lock in the procurement decision | No |

---

## Reward Design

### Step-Level Rewards

| Event | Reward |
|-------|--------|
| Shortlist a non-risky vendor | +0.05 |
| Reject a risky / blacklisted vendor | +0.05 |
| Successful negotiation round | +0.10 |
| Stakeholder satisfaction bonus (at selection) | up to +0.10 |
| Select a vendor within budget | +0.15 |
| Select the optimal vendor | +0.15 |
| Wasted / no-op action | -0.05 |
| Repeated invalid action | -0.10 |
| Select a risky vendor | -0.15 |
| Exceed budget | -0.20 |
| Select a blacklisted vendor | -0.25 |

### Final Grading Formula

```python
final_score = (
    budget_score      * 0.25 +
    quality_score     * 0.20 +
    delivery_score    * 0.15 +
    risk_score        * 0.20 +
    negotiation_score * 0.10 +
    stakeholder_score * 0.10
)
# Clamped to [0.0, 1.0]
# +0.05 bonus for optimal vendor, -0.10 penalty for non-acceptable vendor
```

### Per-Difficulty Grading

| Difficulty | Extra Rules |
|---|---|
| Easy | Standard formula |
| Medium | Standard formula |
| Hard | Additional -0.05 per missing compliance cert (SOC2, ISO27001) |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values. **Never commit `.env`.**

```powershell
copy .env.example .env
```

### Mandatory Hackathon Variables

These variables are read by `inference.py` and must be set for LLM-based evaluation:

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `OPENAI_API_KEY` | _(empty)_ | **Yes** | API key for the LLM (also accepts `HF_TOKEN` as fallback) |
| `API_BASE_URL` | `https://router.huggingface.co/v1` | **Yes** | API endpoint for the LLM |
| `MODEL_NAME` | `Qwen/Qwen2.5-72B-Instruct` | **Yes** | Model identifier to use for inference |
| `HF_TOKEN` | _(empty)_ | No | Hugging Face token (used as API key fallback) |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROK_API_KEY` | _(empty)_ | xAI Grok key (optional alternative provider) |
| `GROK_MODEL` | `grok-2-latest` | Grok model name |
| `GEMINI_API_KEY` | _(empty)_ | Google Gemini key (optional alternative provider) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name |

The inference script uses the OpenAI Client SDK with the configured `API_BASE_URL` and `OPENAI_API_KEY`.

---

## Reproducibility

| Guarantee | Implementation |
|---|---|
| Global RNG seed | `random.seed(42)` in `env/__init__.py`, `app.py`, and `inference.py` |
| Task order | `load_all_tasks()` sorts by `task_id` alphabetically |
| Negotiation outcomes | `NegotiationEngine` uses `random.Random(seed=42)` |
| Final grading | Pure deterministic formula - same inputs = same score |
| API responses | `ProcurementEnv(seed=42)` for every reset |

---

## Running Tests

```powershell
pip install -r requirements-dev.txt

pytest

pytest -v

pytest tests/test_rewards.py

pytest tests/test_step.py::TestStep::test_shortlist_vendor
```

---

## Dependencies

### Production (`requirements.txt`)
```
fastapi, uvicorn, pydantic, openai, httpx, requests, python-dotenv, pyyaml
```

### Development (`requirements-dev.txt`)
```
pytest, pytest-asyncio (+ all production deps)
```

---

## Links

- **Hugging Face Space**: `https://huggingface.co/spaces/codzzz/procurement-ai-env`
- **GitHub Repository**: `https://github.com/codzzz/procurement-ai-env`
- **OpenEnv Spec**: see `openenv.yaml` in this repository
- **Local Testing Guide**: see [LOCAL_TESTING.md](LOCAL_TESTING.md)

---

## License

MIT License. See [LICENSE](LICENSE) for details.
