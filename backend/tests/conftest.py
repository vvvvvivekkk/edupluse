"""Test setup. Uses a separate database (TEST_DATABASE_URL, default PostgreSQL edupulse_test).
Set TEST_DATABASE_URL=sqlite:///./test.db to run without PostgreSQL."""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg2://edupulse:edupulse@localhost:5432/edupulse_test")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def seeded():
    """Fresh, seeded database for each test that needs one."""
    from scripts.seed import seed
    seed(reset=True)
    yield


@pytest.fixture()
def client(seeded):
    from app.main import app
    with TestClient(app) as c:
        yield c


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def tokens(client):
    return {
        "admin": login(client, "admin@edupulse.edu", "Admin@123"),
        "faculty1": login(client, "faculty1@edupulse.edu", "Faculty@123"),
        "faculty2": login(client, "faculty2@edupulse.edu", "Faculty@123"),
        "student1": login(client, "student1@edupulse.edu", "Student@123"),
        "student2": login(client, "student2@edupulse.edu", "Student@123"),
    }
