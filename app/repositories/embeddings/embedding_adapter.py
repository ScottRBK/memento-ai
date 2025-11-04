"""Embedding Adapter to abstract provider specific implementation details"""
from typing import Protocol, List
from fastembed import TextEmbedding

from app.config.settings import settings

import logging
logger = logging.getLogger(__name__)

class EmbeddingsAdapter(Protocol):
    """Contract for an Embeddings Adapter"""
    async def generate_embedding(self, text: str) -> List[float]:
        ...

class FastEmbeddingAdapter:
    """Generate embeddings using the fastembed libary"""
    
    def __init__(self):
        self.model = TextEmbedding(settings.EMBEDDING_MODEL)
        
    async def generate_embedding(self, text: str) -> List[float]:
        try:
            embeddings = list(self.model.embed(text))
        except Exception as e:
            logger.error("Error generating embeddings", exc_info=True, extra={
                "embedding provider": "fastembed",
                "embedding model": settings.EMBEDDING_MODEL
            })
            raise
        
        if embeddings is None:
            raise RuntimeError("FastEmbedding response did not contain embedding vector")
        
        return list(map(float, embeddings[0]))
