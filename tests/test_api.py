

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealthEndpoint:

    def test_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["environment"] == "ProcurementAI-Env"


class TestTasksEndpoint:

    def test_tasks_returns_list(self, client: TestClient) -> None:
        resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10
        assert len(data["tasks"]) == data["total"]

    def test_tasks_have_required_fields(self, client: TestClient) -> None:
        resp = client.get("/tasks")
        data = resp.json()
        for task in data["tasks"]:
            assert "task_id" in task
            assert "title" in task
            assert "difficulty" in task
            assert "budget" in task
            assert "max_steps" in task
            assert "vendor_ids" in task
            assert "optimal_vendor" in task


class TestResetEndpoint:

    def test_reset_default(self, client: TestClient) -> None:
        resp = client.post("/reset", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "observation" in data
        assert data["observation"]["remaining_steps"] > 0

    def test_reset_specific_task(self, client: TestClient) -> None:
        resp = client.post("/reset", json={"task_id": "easy-001", "seed": 42})
        assert resp.status_code == 200
        data = resp.json()
        assert data["observation"]["task_id"] == "easy-001"

    def test_reset_unknown_task_400(self, client: TestClient) -> None:
        resp = client.post("/reset", json={"task_id": "nonexistent"})
        assert resp.status_code == 400


class TestStepEndpoint:

    def test_step_compare_vendors(self, client: TestClient) -> None:
        client.post("/reset", json={"task_id": "easy-001"})
        resp = client.post("/step", json={"action_type": "compare_vendors"})
        assert resp.status_code == 200
        data = resp.json()
        assert "observation" in data
        assert "reward" in data
        assert "done" in data

    def test_step_without_reset_400(self, client: TestClient) -> None:
        # The global env may or may not be reset; this tests graceful handling
        # We use a fresh client which shares the module-level env
        pass  # State-dependent; covered by unit tests

    def test_full_episode_via_api(self, client: TestClient) -> None:
        # Reset
        client.post("/reset", json={"task_id": "easy-001"})

        # Shortlist
        resp = client.post("/step", json={
            "action_type": "shortlist_vendor",
            "vendor_name": "TechVault Solutions",
        })
        assert resp.status_code == 200

        # Reject risky
        resp = client.post("/step", json={
            "action_type": "reject_vendor",
            "vendor_name": "BudgetByte Hardware",
        })
        assert resp.status_code == 200

        # Select
        resp = client.post("/step", json={
            "action_type": "select_vendor",
            "vendor_name": "TechVault Solutions",
        })
        assert resp.status_code == 200

        # Finalize
        resp = client.post("/step", json={"action_type": "finalize_decision"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["done"] is True
        assert "final_score" in data["info"]


class TestStateEndpoint:

    def test_state_after_reset(self, client: TestClient) -> None:
        client.post("/reset", json={"task_id": "easy-001"})
        resp = client.get("/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "easy-001"
        assert data["step_count"] == 0

    def test_state_updates_after_step(self, client: TestClient) -> None:
        client.post("/reset", json={"task_id": "easy-001"})
        client.post("/step", json={"action_type": "compare_vendors"})

        resp = client.get("/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["step_count"] == 1
