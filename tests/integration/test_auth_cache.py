"""
Integration tests for TokenCache

Tests token caching functionality with mock auth providers
"""
import asyncio
import pytest
import time
from unittest.mock import patch, AsyncMock
from starlette.requests import Request

from app.middleware.auth import TokenCache, get_user_from_request
from app.models.user_models import User
from app.config.settings import settings


class MockFastMCP:
    """Mock FastMCP instance for testing"""
    def __init__(self, user_service, auth_provider=None, token_cache=None):
        self.user_service = user_service
        self.auth = auth_provider
        self.token_cache = token_cache


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


# ============================================
# TokenCache Unit Tests
# ============================================


@pytest.mark.asyncio
async def test_token_cache_basic_set_get():
    """Test basic cache set and get operations"""
    cache = TokenCache(ttl_seconds=300, max_size=100)

    # Create a mock user
    user = User(
        external_id="test-user-123",
        name="Test User",
        email="test@example.com"
    )

    # Set and get
    await cache.set("test-token", user)
    cached_user = await cache.get("test-token")

    assert cached_user is not None
    assert cached_user.external_id == "test-user-123"
    assert cached_user.name == "Test User"


@pytest.mark.asyncio
async def test_token_cache_miss():
    """Test cache miss returns None"""
    cache = TokenCache(ttl_seconds=300, max_size=100)

    result = await cache.get("nonexistent-token")

    assert result is None
    assert cache.stats["misses"] == 1


@pytest.mark.asyncio
async def test_token_cache_expiration():
    """Test that expired entries are not returned"""
    # Create cache with very short TTL
    cache = TokenCache(ttl_seconds=1, max_size=100)

    user = User(
        external_id="test-user-expire",
        name="Expiring User",
        email="expire@example.com"
    )

    await cache.set("expiring-token", user)

    # Should be cached initially
    assert await cache.get("expiring-token") is not None

    # Wait for expiration (use asyncio.sleep to avoid blocking the event loop)
    await asyncio.sleep(1.5)

    # Should be expired now
    result = await cache.get("expiring-token")
    assert result is None


@pytest.mark.asyncio
async def test_token_cache_lru_eviction():
    """Test that oldest entries are evicted when max_size is reached"""
    cache = TokenCache(ttl_seconds=300, max_size=3)

    # Add 3 users
    for i in range(3):
        user = User(external_id=f"user-{i}", name=f"User {i}", email=f"u{i}@example.com")
        await cache.set(f"token-{i}", user)

    # Verify cache size is 3
    assert cache.stats["size"] == 3

    # Add a 4th user - should evict oldest (token-0)
    user4 = User(external_id="user-3", name="User 3", email="u3@example.com")
    await cache.set("token-3", user4)

    # Cache size should still be 3
    assert cache.stats["size"] == 3

    # token-0 should be evicted (oldest entry)
    assert await cache.get("token-0") is None
    assert await cache.get("token-1") is not None
    assert await cache.get("token-2") is not None
    assert await cache.get("token-3") is not None


@pytest.mark.asyncio
async def test_token_cache_hash_security():
    """Test that tokens are hashed for security"""
    cache = TokenCache(ttl_seconds=300, max_size=100)

    user = User(external_id="secure-user", name="Secure", email="secure@example.com")
    token = "secret-bearer-token-12345"

    await cache.set(token, user)

    # Verify raw token is not stored in cache keys
    for key in cache._cache.keys():
        assert token not in key
        # Key should be a 64-char SHA-256 hash
        assert len(key) == 64


@pytest.mark.asyncio
async def test_token_cache_stats():
    """Test cache statistics tracking"""
    cache = TokenCache(ttl_seconds=300, max_size=100)

    user = User(external_id="stats-user", name="Stats", email="stats@example.com")
    await cache.set("stats-token", user)

    # 1 hit
    await cache.get("stats-token")
    # 1 miss
    await cache.get("nonexistent")
    # Another hit
    await cache.get("stats-token")

    stats = cache.stats
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["size"] == 1
    assert stats["hit_rate"] == pytest.approx(2/3)


@pytest.mark.asyncio
async def test_token_cache_invalidate():
    """Test manual cache invalidation"""
    cache = TokenCache(ttl_seconds=300, max_size=100)

    user = User(external_id="invalidate-user", name="Invalidate", email="inv@example.com")
    await cache.set("inv-token", user)

    # Should be cached
    assert await cache.get("inv-token") is not None

    # Invalidate
    await cache.invalidate("inv-token")

    # Should be gone
    assert await cache.get("inv-token") is None


@pytest.mark.asyncio
async def test_token_cache_clear():
    """Test clearing all cache entries"""
    cache = TokenCache(ttl_seconds=300, max_size=100)

    # Add multiple entries
    for i in range(5):
        user = User(external_id=f"clear-{i}", name=f"Clear {i}", email=f"c{i}@example.com")
        await cache.set(f"clear-token-{i}", user)

    assert cache.stats["size"] == 5

    await cache.clear()

    assert cache.stats["size"] == 0
    for i in range(5):
        assert await cache.get(f"clear-token-{i}") is None


# ============================================
# Integration with get_user_from_request
# ============================================


@pytest.mark.asyncio
async def test_cache_hit_avoids_verify_token(test_user_service):
    """Test that cache hit doesn't call verify_token"""
    # Track verify_token calls
    call_count = 0

    async def verify_token_tracker(token):
        nonlocal call_count
        call_count += 1
        return MockAccessToken(claims={
            "sub": "cache-test-user",
            "name": "Cache Test",
            "email": "cache@example.com"
        })

    mock_auth = AsyncMock()
    mock_auth.verify_token = verify_token_tracker

    cache = TokenCache(ttl_seconds=300, max_size=100)
    mcp = MockFastMCP(test_user_service, auth_provider=mock_auth, token_cache=cache)

    request = create_mock_request("test-cache-token")

    # First call - should call verify_token
    with patch.object(settings, 'TOKEN_CACHE_ENABLED', True):
        user1 = await get_user_from_request(request, mcp)
        assert call_count == 1

        # Second call - should use cache
        user2 = await get_user_from_request(request, mcp)
        assert call_count == 1  # Still 1, cache hit!

        # Same user
        assert user1.external_id == user2.external_id


@pytest.mark.asyncio
async def test_different_tokens_different_cache_entries(test_user_service):
    """Test that different tokens don't share cache entries"""
    call_count = 0

    async def verify_token_tracker(token):
        nonlocal call_count
        call_count += 1
        # Return different user based on token
        return MockAccessToken(claims={
            "sub": f"user-for-{token[-5:]}",
            "name": f"User {call_count}",
            "email": f"user{call_count}@example.com"
        })

    mock_auth = AsyncMock()
    mock_auth.verify_token = verify_token_tracker

    cache = TokenCache(ttl_seconds=300, max_size=100)
    mcp = MockFastMCP(test_user_service, auth_provider=mock_auth, token_cache=cache)

    with patch.object(settings, 'TOKEN_CACHE_ENABLED', True):
        # First token
        request1 = create_mock_request("token-aaaaa")
        user1 = await get_user_from_request(request1, mcp)
        assert call_count == 1

        # Second token - should call verify_token
        request2 = create_mock_request("token-bbbbb")
        user2 = await get_user_from_request(request2, mcp)
        assert call_count == 2

        # Different users
        assert user1.external_id != user2.external_id


@pytest.mark.asyncio
async def test_cache_disabled_via_setting(test_user_service):
    """Test that cache is bypassed when TOKEN_CACHE_ENABLED=False"""
    call_count = 0

    async def verify_token_tracker(token):
        nonlocal call_count
        call_count += 1
        return MockAccessToken(claims={
            "sub": "disabled-cache-user",
            "name": "Disabled Cache",
            "email": "disabled@example.com"
        })

    mock_auth = AsyncMock()
    mock_auth.verify_token = verify_token_tracker

    cache = TokenCache(ttl_seconds=300, max_size=100)
    mcp = MockFastMCP(test_user_service, auth_provider=mock_auth, token_cache=cache)

    request = create_mock_request("disabled-test-token")

    with patch.object(settings, 'TOKEN_CACHE_ENABLED', False):
        # First call
        await get_user_from_request(request, mcp)
        assert call_count == 1

        # Second call - should still call verify_token (cache disabled)
        await get_user_from_request(request, mcp)
        assert call_count == 2


@pytest.mark.asyncio
async def test_invalid_token_not_cached(test_user_service):
    """Test that invalid tokens are not cached"""
    async def verify_token_reject(token):
        return None  # Invalid token

    mock_auth = AsyncMock()
    mock_auth.verify_token = verify_token_reject

    cache = TokenCache(ttl_seconds=300, max_size=100)
    mcp = MockFastMCP(test_user_service, auth_provider=mock_auth, token_cache=cache)

    request = create_mock_request("invalid-token")

    with patch.object(settings, 'TOKEN_CACHE_ENABLED', True):
        # Should raise ValueError
        with pytest.raises(ValueError, match="Invalid or expired token"):
            await get_user_from_request(request, mcp)

        # Cache should be empty
        assert cache.stats["size"] == 0


@pytest.mark.asyncio
async def test_no_cache_when_cache_not_attached(test_user_service):
    """Test graceful handling when token_cache not attached to mcp"""
    call_count = 0

    async def verify_token_tracker(token):
        nonlocal call_count
        call_count += 1
        return MockAccessToken(claims={
            "sub": "no-cache-user",
            "name": "No Cache",
            "email": "nocache@example.com"
        })

    mock_auth = AsyncMock()
    mock_auth.verify_token = verify_token_tracker

    # No token_cache attached
    mcp = MockFastMCP(test_user_service, auth_provider=mock_auth, token_cache=None)

    request = create_mock_request("no-cache-token")

    with patch.object(settings, 'TOKEN_CACHE_ENABLED', True):
        # Both calls should verify_token since no cache
        await get_user_from_request(request, mcp)
        await get_user_from_request(request, mcp)
        assert call_count == 2
