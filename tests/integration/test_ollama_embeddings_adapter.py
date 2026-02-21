"""
Integration tests for OllamaEmbeddingsAdapter with mocked Ollama client.

Tests the adapter class in isolation - no real Ollama server required.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def mock_settings():
    """Provide mock settings with valid Ollama config."""
    with patch("app.repositories.embeddings.embedding_adapter.settings") as mock:
        mock.OLLAMA_BASE_URL = "http://localhost:11434"
        mock.EMBEDDING_MODEL = "nomic-embed-text"
        mock.EMBEDDING_DIMENSIONS = 768
        yield mock


@pytest.fixture
def mock_ollama_client():
    """Provide a mock Ollama AsyncClient."""
    with patch("ollama.AsyncClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.embed = AsyncMock()
        mock_cls.return_value = mock_client
        yield mock_cls, mock_client


def test_init_success(mock_settings, mock_ollama_client):
    """Adapter initializes AsyncClient with correct host."""
    from app.repositories.embeddings.embedding_adapter import OllamaEmbeddingsAdapter

    mock_cls, _ = mock_ollama_client

    adapter = OllamaEmbeddingsAdapter()

    mock_cls.assert_called_once_with(host="http://localhost:11434")
    assert adapter.model == "nomic-embed-text"


@pytest.mark.asyncio
async def test_generate_embedding_returns_vector(mock_settings, mock_ollama_client):
    """Correct params passed to client.embed(), vector extracted from response."""
    from app.repositories.embeddings.embedding_adapter import OllamaEmbeddingsAdapter

    _, mock_client = mock_ollama_client

    mock_response = MagicMock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_response

    adapter = OllamaEmbeddingsAdapter()
    result = await adapter.generate_embedding("test text")

    assert result == [0.1, 0.2, 0.3]
    mock_client.embed.assert_called_once_with(
        model="nomic-embed-text",
        input="test text",
        dimensions=768,
    )


@pytest.mark.asyncio
async def test_generate_embedding_passes_dimensions(mock_settings, mock_ollama_client):
    """EMBEDDING_DIMENSIONS setting is forwarded to the embed call."""
    from app.repositories.embeddings.embedding_adapter import OllamaEmbeddingsAdapter

    _, mock_client = mock_ollama_client
    mock_settings.EMBEDDING_DIMENSIONS = 512

    mock_response = MagicMock()
    mock_response.embeddings = [[0.5] * 512]
    mock_client.embed.return_value = mock_response

    adapter = OllamaEmbeddingsAdapter()
    result = await adapter.generate_embedding("test text")

    call_kwargs = mock_client.embed.call_args
    assert call_kwargs.kwargs["dimensions"] == 512
    assert len(result) == 512


@pytest.mark.asyncio
async def test_generate_embedding_api_error_propagates(mock_settings, mock_ollama_client):
    """API exceptions are re-raised."""
    from app.repositories.embeddings.embedding_adapter import OllamaEmbeddingsAdapter

    _, mock_client = mock_ollama_client
    mock_client.embed.side_effect = Exception("Connection refused")

    adapter = OllamaEmbeddingsAdapter()

    with pytest.raises(Exception, match="Connection refused"):
        await adapter.generate_embedding("test text")


@pytest.mark.asyncio
async def test_generate_embedding_empty_response_raises(mock_settings, mock_ollama_client):
    """Empty embeddings response raises RuntimeError."""
    from app.repositories.embeddings.embedding_adapter import OllamaEmbeddingsAdapter

    _, mock_client = mock_ollama_client
    mock_response = MagicMock()
    mock_response.embeddings = []
    mock_client.embed.return_value = mock_response

    adapter = OllamaEmbeddingsAdapter()

    with pytest.raises(RuntimeError, match="Ollama did not return embedding vector"):
        await adapter.generate_embedding("test text")
