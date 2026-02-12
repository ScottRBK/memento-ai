"""
End-to-end test for health endpoint

Tests the /health endpoint via HTTP to validate the complete stack is operational.
"""
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.e2e
async def test_health_endpoint_returns_200(http_client):
    """Test /health endpoint returns 200 and is accessible"""
    response = await http_client.get("/health")

    assert response.status_code == 200
