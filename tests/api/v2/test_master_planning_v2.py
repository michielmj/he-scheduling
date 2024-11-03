# tests/test_master_planning.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from he_scheduling.main import app  # Assuming main.py has FastAPI instance with router added
from celery import states

client = TestClient(app)


@pytest.fixture
def mock_mp_model_request():
    # Mock data for the MPModelRequest schema
    return {
        "projects": [
            {
                "id": "project1",
                "product_type": "type1",
                "target_date": 10,
                "latest_date": 15,
                "weight_positive": 10,
                "weight_negative": 5,
                "weight_late": 2,
                "tasks": {
                    "task1": {
                        "id": "task1",
                        "duration": 5,
                        "load": 3,
                        "predecessors": [],
                        "alternative_resources": [1],
                    }
                },
                "finish_task_id": "task1"
            }
        ],
        "resources": [
            {"id": 1, "name": "Resource1", "capacity_per_day": 10}
        ],
        "period_constraints": [],
        "horizon": 20,
        "time_limit": 10,
        "overload_penalty_coefficient": 1000,
        "fixed_violation_penalty_coefficient": 1000
    }


@pytest.fixture
def mock_async_result(mocker):
    # Mock the Celery task's apply_async method to return a test job ID
    mock_task = mocker.patch("he_scheduling.tasks.master_planning.solve_scheduling_problem.apply_async")
    mock_task.return_value.id = "test-job-id"
    return mock_task.return_value


def test_submit_problem(mock_mp_model_request, mock_async_result):
    response = client.post("/api/v2/master-planning/submit_problem/", json=mock_mp_model_request)
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == mock_async_result.id
    assert data["status"] == "submitted"


def test_get_job_status_pending(mocker):
    # Mock the AsyncResult to simulate a task in PENDING state
    mock_result = MagicMock()
    mock_result.state = states.PENDING
    mocker.patch("celery.result.AsyncResult", return_value=mock_result)

    response = client.get("/api/v2/master-planning/job_status/test-job-id")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-id"
    assert data["status"] == "pending"


def test_get_job_status_completed(mocker):
    # Mock the AsyncResult to simulate a task in SUCCESS state with a result
    mock_result = MagicMock()
    mock_result.state = states.SUCCESS
    mock_result.result = {
        "solver_status": {"status_code": 0, "status_text": "Optimal", "objective_value": 123.0},
        "solution": [
            {"project_id": "project1", "task_id": "task1", "start": 0, "end": 5, "resource_assigned": "Resource1"}
        ]
    }
    mocker.patch("celery.result.AsyncResult", return_value=mock_result)

    response = client.get("/api/v2/master-planning/job_status/test-job-id")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-id"
    assert data["status"] == "completed"
    assert data["result"]["solver_status"]["status_code"] == 0
    assert data["result"]["solver_status"]["status_text"] == "Optimal"


def test_get_job_status_failed(mocker):
    # Mock the AsyncResult to simulate a task in FAILURE state with an error message
    mock_result = MagicMock()
    mock_result.state = states.FAILURE
    mock_result.result = "Task failed due to an error."
    mocker.patch("celery.result.AsyncResult", return_value=mock_result)

    response = client.get("/api/v2/master-planning/job_status/test-job-id")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-id"
    assert data["status"] == "failed"
    assert data["result"] == "Task failed due to an error."


def test_cancel_job_pending(mocker):
    # Mock the AsyncResult to simulate a task in PENDING state
    mock_result = MagicMock()
    mock_result.state = states.PENDING
    mocker.patch("celery.result.AsyncResult", return_value=mock_result)

    response = client.delete("/api/v2/master-planning/cancel_job/test-job-id")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-id"
    assert data["status"] == "canceled"


def test_cancel_job_started(mocker):
    # Mock the AsyncResult to simulate a task in STARTED state
    mock_result = MagicMock()
    mock_result.state = states.STARTED
    mocker.patch("celery.result.AsyncResult", return_value=mock_result)

    response = client.delete("/api/v2/master-planning/cancel_job/test-job-id")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-id"
    assert data["status"] == "canceled"


def test_cancel_job_completed(mocker):
    # Mock the AsyncResult to simulate a task in SUCCESS state (completed)
    mock_result = MagicMock()
    mock_result.state = states.SUCCESS
    mocker.patch("celery.result.AsyncResult", return_value=mock_result)

    response = client.delete("/api/v2/master-planning/cancel_job/test-job-id")
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Job already completed and cannot be canceled."
