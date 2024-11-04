# File: tests/api/v1/test_master_planning_v1.py

import pytest
from fastapi.testclient import TestClient
from he_scheduling.main import app  # Adjust the import to your main FastAPI app
from ortools.sat.python import cp_model


# Import the models if needed for constructing request data
# from your_package.models import MPModelRequest, MPProject, MPResource, MPPeriodConstraint, MPTask, MPPredecessor

# Create a TestClient using the FastAPI app
client = TestClient(app)
# client = TestClient(app, base_url='/api/v1/master-planning')


@pytest.fixture
def sample_request_data():
    # Sample data matching MPModelRequest
    resources = [
        {
            "id": 1,
            "name": "R1",
            "capacity_per_day": 10
        },
        {
            "id": 2,
            "name": "R2",
            "capacity_per_day": 8
        },
        {
            "id": 3,
            "name": "R3",
            "capacity_per_day": 15
        }
    ]

    projects = [
        {
            "id": "P1",
            "product_type": "TypeA",
            "target_date": 15,
            "latest_date": 20,
            "weight_positive": 2,
            "weight_negative": 3,
            "weight_late": 30,
            "tasks": {
                "T1": {
                    "id": "T1",
                    "duration": 5,
                    "load": 10.0,
                    "predecessors": [],
                    "alternative_resources": [1, 2]
                },
                "T2": {
                    "id": "T2",
                    "duration": 3,
                    "load": 5.0,
                    "predecessors": [
                        {
                            "task_id": "T1",
                            "min_gap": 0,
                            "max_gap": 0
                        }
                    ],
                    "alternative_resources": [2]
                }
            },
            "finish_task_id": "T2",
        },
        {
            "id": "P2",
            "product_type": "TypeB",
            "target_date": 20,
            "latest_date": 30,
            "weight_positive": 1,
            "weight_negative": 4,
            "weight_late": 40,
            "tasks": {
                "T3": {
                    "id": "T3",
                    "duration": 4,
                    "load": 8.0,
                    "predecessors": [],
                    "alternative_resources": [1]
                },
                "T4": {
                    "id": "T4",
                    "duration": 6,
                    "load": 12.0,
                    "predecessors": [
                        {
                            "task_id": "T3",
                            "min_gap": 0,
                            "max_gap": 0
                        }
                    ],
                    "alternative_resources": [3]
                }
            },
            "finish_task_id": "T4"
        }
    ]

    period_constraints = [
        {
            "start_date": 0,
            "end_date": 10,
            "product_type": "TypeA",
            "max_projects": 1
        },
        {
            "start_date": 0,
            "end_date": 10,
            "product_type": "TypeB",
            "max_projects": 1
        },
        {
            "start_date": 10,
            "end_date": 20,
            "product_type": "TypeA",
            "max_projects": 1
        },
        {
            "start_date": 10,
            "end_date": 20,
            "product_type": "TypeB",
            "max_projects": 1
        },
        {
            "start_date": 20,
            "end_date": 30,
            "product_type": "TypeA",
            "max_projects": 1
        },
        {
            "start_date": 20,
            "end_date": 30,
            "product_type": "TypeB",
            "max_projects": 1
        }
    ]

    return {
        "projects": projects,
        "resources": resources,
        "period_constraints": period_constraints,
        "horizon": 30
    }


def test_schedule_endpoint_success(sample_request_data):
    """Test the /schedule endpoint with valid data."""
    response = client.post("/api/v1/master-planning/schedule", json=sample_request_data)
    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
    data = response.json()
    assert "solver_status" in data, "Response missing 'solver_status'"
    assert "solution" in data, "Response missing 'solution'"

    solver_status = data["solver_status"]
    assert solver_status["status_code"] in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
        "Solver did not find a feasible solution."
    assert solver_status["objective_value"] is not None, "Objective value should not be None."

    solution = data["solution"]
    assert len(solution) > 0, "Solution should contain tasks."

    # Optional: Verify the structure of each task solution
    for task_solution in solution:
        assert "project_id" in task_solution, "Task solution missing 'project_id'"
        assert "task_id" in task_solution, "Task solution missing 'task_id'"
        assert "start" in task_solution, "Task solution missing 'start'"
        assert "end" in task_solution, "Task solution missing 'end'"
        # resource_assigned can be None
        assert "resource_assigned" in task_solution, "Task solution missing 'resource_assigned'"


def test_schedule_endpoint_infeasible(sample_request_data):
    """Test the /schedule endpoint with data leading to an infeasible solution."""
    # Modify sample data to create an infeasible problem
    # For example, set max_projects to zero for all periods for TypeA projects
    for period_constraint in sample_request_data['period_constraints']:
        if period_constraint['product_type'] == 'TypeA':
            period_constraint['max_projects'] = 0  # Disallow TypeA projects in all periods

    # Adjust the target date of the TypeA project to ensure infeasibility
    for project in sample_request_data['projects']:
        if project['product_type'] == 'TypeA':
            project['target_date'] = 10  # Force the project to be scheduled within disallowed periods

    response = client.post("/api/v1/master-planning/schedule", json=sample_request_data)
    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
    data = response.json()
    assert data.get('solver_status', {})['status_code'] == 3, "Expected infeasible"
    assert "solver_status" in data, "Response missing 'solver_status'"
    solver_status = data["solver_status"]
    assert solver_status["status_code"] == cp_model.INFEASIBLE, "Solver status should indicate infeasibility."


def test_schedule_endpoint_invalid_input():
    """Test the /schedule endpoint with invalid input data."""
    invalid_data = {
        "projects": [
            {
                "id": "P1",
                "product_type": "TypeA",
                "target_date": 15,
                "latest_date": 20,
                "weight_positive": 2,
                "weight_negative": 3,
                "weight_late": 30,
                "tasks": {
                    "T1": {
                        "id": "T1",
                        "duration": -5,  # Invalid negative duration
                        "load": 10.0,
                        "predecessors": [],
                        "alternative_resources": [1, 2]
                    }
                }
            }
        ],
        "resources": [
            {
                "id": 1,
                "name": "R1",
                "capacity_per_day": 10
            }
        ],
        "period_constraints": [],
        "horizon": 30
    }
    response = client.post("/api/v1/master-planning/schedule", json=invalid_data)
    assert response.status_code == 422, f"Expected 422 status code for invalid input, got {response.status_code}"
    data = response.json()
    assert "detail" in data, "Response missing 'detail'"
    assert data["detail"][0]["loc"][-1] == "duration", "Validation error should be on 'duration' field."


def test_schedule_endpoint_empty_request():
    """Test the /schedule endpoint with an empty request body."""
    response = client.post("/api/v1/master-planning/schedule", json={})
    assert response.status_code == 422, f"Expected 422 status code for empty request, got {response.status_code}"
    data = response.json()
    assert "detail" in data, "Response missing 'detail'"


def test_schedule_endpoint_missing_fields():
    """Test the /schedule endpoint with missing required fields."""
    incomplete_data = {
        "projects": [],
        "resources": [],
        # 'period_constraints' and 'horizon' are missing
    }
    response = client.post("/api/v1/master-planning/schedule", json=incomplete_data)
    assert response.status_code == 422, f"Expected 422 status code for missing fields, got {response.status_code}"
    data = response.json()
    assert "detail" in data, "Response missing 'detail'"
