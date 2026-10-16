import os

# Set the test database before importing the application.
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine  # Adjust to your actual module

# Import your model if it isn't already imported by app.main.
from app.models import Task  # Adjust to your actual model module

# Create the tables needed by the tests.
Base.metadata.create_all(bind=engine)

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.json() == {"status": "UP"}


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "TaskBoard API"


def test_create_task_validation():
    response = client.post(
        "/api/tasks",
        json={
            "title": "Deploy application",
            "priority": "HIGH",
            "assignee": "Student",
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Deploy application" 
