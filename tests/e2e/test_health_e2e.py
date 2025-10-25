"""
End-to-end test for health endpoint

Tests the /health endpoint via HTTP to validate the complete stack is operational.
"""
import pytest
import httpx

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_health_endpoint_returns_200(docker_services, server_base_url):
    """Test /health endpoint returns 200 and is accessible"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{server_base_url}/health")

        assert response.status_code == 200
