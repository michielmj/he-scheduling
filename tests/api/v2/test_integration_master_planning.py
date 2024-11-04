import pytest
from time import sleep
from fastapi.testclient import TestClient
from psycopg2 import connect as pg_connect, OperationalError as PGOperationalError
import pika
from he_scheduling.main import app
from he_scheduling.core.config import config

client = TestClient(app)


def is_postgres_running():
    try:
        conn = pg_connect(
            dbname=config.postgres_db,
            user=config.postgres_user,
            password=config.postgres_password,
            host=config.postgres_host,
            port=config.postgres_port
        )
        conn.close()
        return True
    except PGOperationalError:
        return False


def is_rabbitmq_running():
    try:
        credentials = pika.PlainCredentials(config.rabbitmq_user, config.rabbitmq_password)
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=config.rabbitmq_host,
            port=config.rabbitmq_port,
            credentials=credentials
        ))
        connection.close()
        return True
    except pika.exceptions.AMQPConnectionError:
        return False


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


@pytest.mark.integration
def test_integration(mock_mp_model_request):
    if not is_postgres_running() or not is_rabbitmq_running():
        pytest.skip("Skipping integration test since PostgreSQL or RabbitMQ is not available.")

    response = client.post("/api/v2/master-planning/submit_problem/", json=mock_mp_model_request)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "submitted"

    sleep(2)

    job_id = data['job_id']
    response = client.get(f"/api/v2/master-planning/job_status/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
