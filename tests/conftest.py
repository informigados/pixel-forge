import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session", autouse=True)
def disable_sentinel_for_tests():
    os.environ["PIXEL_FORGE_DISABLE_SENTINEL"] = "1"


@pytest.fixture
def client():
    with TestClient(app, base_url="http://localhost") as test_client:
        yield test_client


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent
