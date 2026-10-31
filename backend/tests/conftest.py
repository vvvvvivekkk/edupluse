"""Test setup. Tests always use a SEPARATE database so they never touch your real data.

Which test database is used:
  1. TEST_DATABASE_URL (from the shell or backend/.env), if set;
  2. otherwise, if DATABASE_URL is SQLite, a file backend/test.db;
  3. otherwise PostgreSQL database edupulse_test.
In-memory SQLite ("sqlite://") cannot work here (each connection would get a new empty database),
so it is replaced with the file backend/test.db.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND / ".env", override=False)
SQLITE_FILE = f"sqlite:///{(BACKEND / 'test.db').as_posix()}"

test_url = os.getenv("TEST_DATABASE_URL")
if not test_url:
    test_url = (SQLITE_FILE if os.getenv("DATABASE_URL", "").startswith("sqlite")
                else "postgresql+psycopg2://edupulse:edupulse@localhost:5432/edupulse_test")
if test_url.startswith("sqlite") and (test_url.rstrip("/") == "sqlite:" or ":memory:" in test_url):
    test_url = SQLITE_FILE
os.environ["DATABASE_URL"] = test_url
sys.path.insert(0, str(BACKEND))

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
