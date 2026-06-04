"""Tests for the main application."""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    """Test the health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "1835-konsek"}
