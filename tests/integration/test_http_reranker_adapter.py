"""
Integration tests for HttpRerankAdapter with mocked httpx client.

Tests the adapter class in isolation - no real reranking API required.
"""
import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def mock_settings():
    """Provide mock settings with valid HTTP reranker config."""
    with patch("app.repositories.embeddings.reranker_adapter.settings") as mock:
        mock.RERANKING_MODEL = "jina-reranker-v2-base-multilingual"
        mock.RERANKING_URL = "https://api.jina.ai/v1/rerank"
        mock.RERANKING_API_KEY = "test-api-key-123"
        yield mock


@pytest.fixture
def mock_settings_no_key():
    """Provide mock settings without API key (local server)."""
    with patch("app.repositories.embeddings.reranker_adapter.settings") as mock:
        mock.RERANKING_MODEL = "bge-reranker-v2-m3"
        mock.RERANKING_URL = "http://localhost:8012/v1/rerank"
        mock.RERANKING_API_KEY = ""
        yield mock


def test_init_stores_config(mock_settings):
    """Adapter stores model, url, and api_key from settings."""
    from app.repositories.embeddings.reranker_adapter import HttpRerankAdapter

    adapter = HttpRerankAdapter()

    assert adapter.model == "jina-reranker-v2-base-multilingual"
    assert adapter.url == "https://api.jina.ai/v1/rerank"
    assert adapter.api_key == "test-api-key-123"


def test_init_with_explicit_params(mock_settings):
    """Adapter accepts explicit constructor params over settings defaults."""
    from app.repositories.embeddings.reranker_adapter import HttpRerankAdapter

    adapter = HttpRerankAdapter(
        model="custom-model",
        url="http://custom:8080/rerank",
        api_key="custom-key",
    )

    assert adapter.model == "custom-model"
    assert adapter.url == "http://custom:8080/rerank"
    assert adapter.api_key == "custom-key"


@pytest.mark.asyncio
async def test_rerank_empty_documents_returns_empty_list(mock_settings):
    """Empty document list returns [] without making HTTP call."""
    from app.repositories.embeddings.reranker_adapter import HttpRerankAdapter

    adapter = HttpRerankAdapter()
    result = await adapter.rerank("test query", [])

    assert result == []


@pytest.mark.asyncio
async def test_rerank_posts_correct_payload(mock_settings):
    """POST body contains query, documents, and model."""
    from app.repositories.embeddings.reranker_adapter import HttpRerankAdapter

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.5},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.repositories.embeddings.reranker_adapter.httpx.AsyncClient", return_value=mock_client):
        adapter = HttpRerankAdapter()
        await adapter.rerank("what is AI?", ["doc about AI", "doc about cooking"])

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs.kwargs["json"] == {
        "query": "what is AI?",
        "documents": ["doc about AI", "doc about cooking"],
        "model": "jina-reranker-v2-base-multilingual",
    }
    assert call_kwargs.kwargs["url"] == "https://api.jina.ai/v1/rerank"


@pytest.mark.asyncio
async def test_rerank_returns_sorted_tuples(mock_settings):
    """Response results are returned as List[tuple[int, float]]."""
    from app.repositories.embeddings.reranker_adapter import HttpRerankAdapter

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.42},
            {"index": 2, "relevance_score": 0.10},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.repositories.embeddings.reranker_adapter.httpx.AsyncClient", return_value=mock_client):
        adapter = HttpRerankAdapter()
        result = await adapter.rerank("query", ["a", "b", "c"])

    assert result == [(1, 0.95), (0, 0.42), (2, 0.10)]


@pytest.mark.asyncio
async def test_rerank_with_api_key_sends_auth_header(mock_settings):
    """Bearer token present in headers when api_key is set."""
    from app.repositories.embeddings.reranker_adapter import HttpRerankAdapter

    mock_response = MagicMock()
    mock_response.json.return_value = {"results": [{"index": 0, "relevance_score": 0.5}]}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.repositories.embeddings.reranker_adapter.httpx.AsyncClient", return_value=mock_client):
        adapter = HttpRerankAdapter()
        await adapter.rerank("query", ["doc"])

    call_kwargs = mock_client.post.call_args
    assert call_kwargs.kwargs["headers"] == {"Authorization": "Bearer test-api-key-123"}


@pytest.mark.asyncio
async def test_rerank_without_api_key_no_auth_header(mock_settings_no_key):
    """No Authorization header for local servers without API key."""
    from app.repositories.embeddings.reranker_adapter import HttpRerankAdapter

    mock_response = MagicMock()
    mock_response.json.return_value = {"results": [{"index": 0, "relevance_score": 0.5}]}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.repositories.embeddings.reranker_adapter.httpx.AsyncClient", return_value=mock_client):
        adapter = HttpRerankAdapter()
        await adapter.rerank("query", ["doc"])

    call_kwargs = mock_client.post.call_args
    assert call_kwargs.kwargs["headers"] == {}


@pytest.mark.asyncio
async def test_rerank_http_error_propagates(mock_settings):
    """raise_for_status propagates HTTP errors."""
    from app.repositories.embeddings.reranker_adapter import HttpRerankAdapter

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
    )

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.repositories.embeddings.reranker_adapter.httpx.AsyncClient", return_value=mock_client):
        adapter = HttpRerankAdapter()

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.rerank("query", ["doc"])
