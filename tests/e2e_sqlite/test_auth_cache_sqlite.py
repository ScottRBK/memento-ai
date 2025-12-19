"""
End-to-end tests for token caching with SQLite backend

Tests complete token cache flow with real SQLite database to validate
cache integration doesn't interfere with user provisioning.

Note: The token cache itself is in-memory and doesn't persist to SQLite.
These tests validate that the cache works correctly alongside the real
database for user management.
"""
import pytest
from unittest.mock import patch, AsyncMock

from app.middleware.auth import TokenCache, get_user_from_request
from starlette.requests import Request


class MockAccessToken:
    """Mock AccessToken for testing auth-enabled mode"""
    def __init__(self, claims: dict):
        self.claims = claims


def create_mock_request(token: str) -> Request:
    """Create a mock Starlette Request with Authorization header"""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_token_cache_with_real_database(http_client, sqlite_app):
    """
    Test that token caching works correctly with real SQLite database

    Validates:
    - Cache reduces verify_token calls
    - User is still correctly provisioned in SQLite on first call
    - Subsequent calls return same user from cache without DB query
    """
    from app.config.settings import settings

    # Track verify_token calls
    call_count = 0

    async def verify_token_tracker(token):
        nonlocal call_count
        call_count += 1
        return MockAccessToken(claims={
            "sub": "sqlite-cache-e2e-user",
            "name": "SQLite Cache E2E",
            "email": "cache-e2e@sqlite.test"
        })

    mock_auth = AsyncMock()
    mock_auth.verify_token = verify_token_tracker

    # Create and attach cache to app
    cache = TokenCache(ttl_seconds=300, max_size=100)
    sqlite_app.auth = mock_auth
    sqlite_app.token_cache = cache

    with patch.object(settings, 'TOKEN_CACHE_ENABLED', True):
        request = create_mock_request("e2e-cache-test-token")

        # First call - should verify token and provision user to SQLite
        user1 = await get_user_from_request(request, sqlite_app)
        assert call_count == 1
        assert user1.external_id == "sqlite-cache-e2e-user"
        assert user1.name == "SQLite Cache E2E"

        # Second call - should use cache (no verify_token call)
        user2 = await get_user_from_request(request, sqlite_app)
        assert call_count == 1  # Still 1, cache hit!

        # Same user returned
        assert user2.external_id == user1.external_id
        assert user2.id == user1.id

        # Verify cache stats
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


@pytest.mark.asyncio
async def test_sequential_requests_use_cache(http_client, sqlite_app):
    """
    Test that sequential requests with same token use cache

    Validates:
    - First request provisions user and populates cache
    - Subsequent requests use cache (no verify_token call)
    - All requests return same user
    """
    from app.config.settings import settings

    call_count = 0

    async def verify_token_counter(token):
        nonlocal call_count
        call_count += 1
        return MockAccessToken(claims={
            "sub": "sequential-user",
            "name": "Sequential Test",
            "email": "sequential@test.com"
        })

    mock_auth = AsyncMock()
    mock_auth.verify_token = verify_token_counter

    cache = TokenCache(ttl_seconds=300, max_size=100)
    sqlite_app.auth = mock_auth
    sqlite_app.token_cache = cache

    with patch.object(settings, 'TOKEN_CACHE_ENABLED', True):
        # First request - provisions user and populates cache
        request1 = create_mock_request("sequential-token")
        user1 = await get_user_from_request(request1, sqlite_app)
        assert call_count == 1

        # Subsequent requests should use cache
        for i in range(4):
            request = create_mock_request("sequential-token")
            user = await get_user_from_request(request, sqlite_app)
            assert user.external_id == user1.external_id

        # Only 1 verify_token call (first request)
        assert call_count == 1

        # 4 cache hits (subsequent requests)
        assert cache.stats["hits"] == 4


@pytest.mark.asyncio
async def test_cache_expiration_re_provisions_user(http_client, sqlite_app):
    """
    Test that expired cache entries trigger re-validation

    Validates:
    - Expired entries are evicted
    - Re-validation creates new cache entry
    - User still retrieved correctly from database
    """
    from app.config.settings import settings
    import time

    call_count = 0

    async def verify_token_counter(token):
        nonlocal call_count
        call_count += 1
        return MockAccessToken(claims={
            "sub": "expiry-test-user",
            "name": "Expiry Test",
            "email": "expiry@test.com"
        })

    mock_auth = AsyncMock()
    mock_auth.verify_token = verify_token_counter

    # Very short TTL for testing
    cache = TokenCache(ttl_seconds=1, max_size=100)
    sqlite_app.auth = mock_auth
    sqlite_app.token_cache = cache

    with patch.object(settings, 'TOKEN_CACHE_ENABLED', True):
        request = create_mock_request("expiry-test-token")

        # First call
        user1 = await get_user_from_request(request, sqlite_app)
        assert call_count == 1

        # Second call - should be cached
        user2 = await get_user_from_request(request, sqlite_app)
        assert call_count == 1  # Cache hit

        # Wait for expiration
        time.sleep(1.1)

        # Third call - cache expired, should re-validate
        user3 = await get_user_from_request(request, sqlite_app)
        assert call_count == 2  # New validation

        # All should be same user
        assert user1.external_id == user2.external_id == user3.external_id
