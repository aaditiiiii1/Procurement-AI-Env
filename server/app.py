from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import logging
import os
import random
from typing import Optional

random.seed(42)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    print("FastAPI imports successful", flush=True)
except Exception as e:
    print(f"ERROR: FastAPI import failed: {e}", flush=True)
    raise

try:
    from env.constants import DEFAULT_PORT
    from env.models import (
        Action,
        EnvironmentState,
        HealthResponse,
        Observation,
        ResetResponse,
        Reward,
        StepResponse,
        TaskListResponse,
    )
    from env.procurement_env import ProcurementEnv
    from env.tasks import load_all_tasks
    from env.utils import setup_logging
    print("Env imports successful", flush=True)
except Exception as e:
    print(f"ERROR: Env import failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
    raise

try:
    setup_logging()
    logger = logging.getLogger("procurement_env.app")
except Exception as e:
    # If logging setup fails, use basic logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("procurement_env.app")
    logger.warning("Failed to setup file logging: %s", e)

app = FastAPI(
    title="ProcurementAI-Env",
    description=(
        "An OpenEnv-compatible environment simulating real-world procurement "
        "and vendor selection workflows. An AI agent acts as a procurement "
        "manager - comparing vendors, negotiating discounts, evaluating risk, "
        "and selecting the best vendor under budget constraints."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Global Safety Net: Handle ANY unexpected error as a clean JSON response
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=400,
        content={"detail": [{"msg": f"Internal Error: {str(exc)}", "type": "server_error"}]}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to ProcurementAI-Env!",
        "version": "1.0.0",
        "documentation": "/docs",
        "description": "An OpenEnv-compatible environment for AI procurement agents."
    }

env = None

def get_env():
    """Lazy initialization of environment"""
    global env
    if env is None:
        try:
            env = ProcurementEnv(seed=42)
            logger.info("Environment initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize environment: %s", e, exc_info=True)
            raise
    return env


class ResetRequest(BaseModel):
    task_id: Optional[str] = Field(
        None, description="Task ID to load. ``null`` selects the first task."
    )
    seed: int = Field(42, description="Random seed for reproducibility.")


@app.post("/reset", response_model=ResetResponse)
async def reset_endpoint(body: ResetRequest = ResetRequest()) -> ResetResponse:
    global env
    try:
        env = ProcurementEnv(seed=body.seed)
        observation = env.reset(task_id=body.task_id)
        return ResetResponse(
            observation=observation,
            info={"message": "Environment reset successfully.", "task_id": observation.task_id},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error in /reset")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@app.post("/step", response_model=StepResponse)
async def step_endpoint(action: Action) -> StepResponse:
    current_env = get_env()
    if not hasattr(current_env, "current_task") or current_env.current_task is None:
         raise HTTPException(status_code=400, detail="Environment not reset. Call /reset first.")
    try:
        observation, reward, done, info = current_env.step(action)
        return StepResponse(
            observation=observation,
            reward=reward,
            done=done,
            info=info,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error in /step")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@app.get("/state", response_model=EnvironmentState)
async def state_endpoint() -> EnvironmentState:
    current_env = get_env()
    if not hasattr(current_env, "current_task") or current_env.current_task is None:
         raise HTTPException(status_code=400, detail="Environment not reset. Call /reset first.")
    try:
        return current_env.state()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error in /state")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@app.get("/health", response_model=HealthResponse)
async def health_endpoint() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment="ProcurementAI-Env",
    )


@app.get("/tasks", response_model=TaskListResponse)
async def tasks_endpoint() -> TaskListResponse:
    try:
        tasks = load_all_tasks()
        return TaskListResponse(tasks=tasks, total=len(tasks))
    except Exception as exc:
        logger.exception("Unexpected error in /tasks")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


def main():
    import uvicorn
    from env.constants import DEFAULT_PORT
    try:
        uvicorn.run(
            "server.app:app",
            host="0.0.0.0",
            port=DEFAULT_PORT,
            reload=False,
            log_level="info",
        )
    except Exception as e:
        import traceback
        print(f"ERROR: Failed to start server: {e}", flush=True)
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
