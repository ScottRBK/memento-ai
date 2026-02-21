"""
Integration tests for OpenAIEmbeddingsAdapter with mocked OpenAI client.

Tests the adapter class in isolation - no real API key required.
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_settings():
    """Provide mock settings with valid OpenAI config."""
    with patch("app.repositories.embeddings.embedding_adapter.settings") as mock:
        mock.OPENAI_API_KEY = "sk-test-key-123"
        mock.EMBEDDING_MODEL = "text-embedding-3-small"
        mock.EMBEDDING_DIMENSIONS = 256
        mock.OPENAI_BASE_URL = ""
        mock.OPENAI_SUPPORTS_DIMENSIONS = True
        yield mock


@pytest.fixture
def mock_openai_client():
    """Provide a mock OpenAI client."""
    with patch("app.repositories.embeddings.embedding_adapter.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        yield mock_cls, mock_client


def test_init_success(mock_settings, mock_openai_client):
    """Adapter initializes and passes API key to OpenAI client."""
    from app.repositories.embeddings.embedding_adapter import OpenAIEmbeddingsAdapter

    mock_cls, _ = mock_openai_client

    adapter = OpenAIEmbeddingsAdapter()

    mock_cls.assert_called_once_with(api_key="sk-test-key-123")
    assert adapter.model == "text-embedding-3-small"
    assert adapter.supports_dimensions is True


def test_init_missing_api_key_without_base_url_raises(mock_settings):
    """Empty API key without base_url raises ValueError."""
    from app.repositories.embeddings.embedding_adapter import OpenAIEmbeddingsAdapter

    mock_settings.OPENAI_API_KEY = ""

    with pytest.raises(ValueError, match="OPENAI_API_KEY must be configured"):
        OpenAIEmbeddingsAdapter()


def test_init_with_base_url(mock_settings, mock_openai_client):
    """base_url is passed to OpenAI constructor when configured."""
    from app.repositories.embeddings.embedding_adapter import OpenAIEmbeddingsAdapter

    mock_cls, _ = mock_openai_client
    mock_settings.OPENAI_BASE_URL = "http://localhost:8080/v1"

    adapter = OpenAIEmbeddingsAdapter()

    mock_cls.assert_called_once_with(api_key="sk-test-key-123", base_url="http://localhost:8080/v1")
    assert adapter.model == "text-embedding-3-small"


def test_init_no_api_key_with_base_url_uses_placeholder(mock_settings, mock_openai_client):
    """No ValueError when base_url is set and API key is empty; placeholder key used."""
    from app.repositories.embeddings.embedding_adapter import OpenAIEmbeddingsAdapter

    mock_cls, _ = mock_openai_client
    mock_settings.OPENAI_API_KEY = ""
    mock_settings.OPENAI_BASE_URL = "http://localhost:8080/v1"

    adapter = OpenAIEmbeddingsAdapter()

    mock_cls.assert_called_once_with(api_key="no-key-required", base_url="http://localhost:8080/v1")
    assert adapter.model == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_generate_embedding_returns_vector(mock_settings, mock_openai_client):
    """Correct params passed to client.embeddings.create(), correct response extracted."""
    from app.repositories.embeddings.embedding_adapter import OpenAIEmbeddingsAdapter

    _, mock_client = mock_openai_client

    # Build mock response matching OpenAI SDK structure
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1, 0.2, 0.3]
    mock_response = MagicMock()
    mock_response.data = [mock_embedding]
    mock_client.embeddings.create.return_value = mock_response

    adapter = OpenAIEmbeddingsAdapter()
    result = await adapter.generate_embedding("test text")

    assert result == [0.1, 0.2, 0.3]
    mock_client.embeddings.create.assert_called_once_with(
        input=["test text"],
        model="text-embedding-3-small",
        dimensions=256,
    )


@pytest.mark.asyncio
async def test_generate_embedding_with_dimensions(mock_settings, mock_openai_client):
    """EMBEDDING_DIMENSIONS setting is forwarded to the API when supports_dimensions=True."""
    from app.repositories.embeddings.embedding_adapter import OpenAIEmbeddingsAdapter

    _, mock_client = mock_openai_client
    mock_settings.EMBEDDING_DIMENSIONS = 1536

    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.5] * 1536
    mock_response = MagicMock()
    mock_response.data = [mock_embedding]
    mock_client.embeddings.create.return_value = mock_response

    adapter = OpenAIEmbeddingsAdapter()
    result = await adapter.generate_embedding("test text")

    call_kwargs = mock_client.embeddings.create.call_args
    assert call_kwargs.kwargs["dimensions"] == 1536
    assert len(result) == 1536


@pytest.mark.asyncio
async def test_generate_embedding_without_dimensions(mock_settings, mock_openai_client):
    """dimensions kwarg is absent when supports_dimensions=False (e.g. llama.cpp)."""
    from app.repositories.embeddings.embedding_adapter import OpenAIEmbeddingsAdapter

    _, mock_client = mock_openai_client
    mock_settings.OPENAI_SUPPORTS_DIMENSIONS = False

    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1, 0.2, 0.3]
    mock_response = MagicMock()
    mock_response.data = [mock_embedding]
    mock_client.embeddings.create.return_value = mock_response

    adapter = OpenAIEmbeddingsAdapter()
    result = await adapter.generate_embedding("test text")

    assert result == [0.1, 0.2, 0.3]
    call_kwargs = mock_client.embeddings.create.call_args.kwargs
    assert "dimensions" not in call_kwargs


@pytest.mark.asyncio
async def test_generate_embedding_api_error_propagates(mock_settings, mock_openai_client):
    """API exceptions are re-raised."""
    from app.repositories.embeddings.embedding_adapter import OpenAIEmbeddingsAdapter

    _, mock_client = mock_openai_client
    mock_client.embeddings.create.side_effect = Exception("API rate limit exceeded")

    adapter = OpenAIEmbeddingsAdapter()

    with pytest.raises(Exception, match="API rate limit exceeded"):
        await adapter.generate_embedding("test text")


@pytest.mark.asyncio
async def test_generate_embedding_none_response_raises(mock_settings, mock_openai_client):
    """None response raises RuntimeError."""
    from app.repositories.embeddings.embedding_adapter import OpenAIEmbeddingsAdapter

    _, mock_client = mock_openai_client
    mock_client.embeddings.create.return_value = None

    adapter = OpenAIEmbeddingsAdapter()

    with pytest.raises(RuntimeError, match="OpenAI response did not contain embedding vector"):
        await adapter.generate_embedding("test text")
