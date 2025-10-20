"""
    Test for health check endpoint
"""

import pytest

from fastapi.testclient import TestClient

class TestBasicHealthEndpoint:
    
    def test_health_endpoint_returns_200(self, client: TestClient):
        response = client.get("/health/")
        assert response.status_code == 200
