"""Embedding Adapter to abstract provider specific implementation details"""
from typing import Protocol, List
import time
import asyncio

from fastembed import TextEmbedding
from openai import AzureOpenAI
import google.generativeai as genai 

from app.config.settings import settings

import logging
logger = logging.getLogger(__name__)

class EmbeddingsAdapter(Protocol):
    """Contract for an Embeddings Adapter"""
    async def generate_embedding(self, text: str) -> List[float]:
        ...

class FastEmbeddingAdapter(EmbeddingsAdapter):
    """Generate embeddings using the fastembed libary"""
    
    def __init__(self):
        logger.info("Initialising Fastembed model", extra={
            "embedding_model": settings.EMBEDDING_MODEL
        })
        
        start_time = time.time()
        self.model = TextEmbedding(settings.EMBEDDING_MODEL)
        elapsed = time.time() - start_time

        logger.info("FasteEmbed model loaded successfully", extra={
            "elapsed_time": f"{elapsed:.2f}s"
        })
        
    async def generate_embedding(self, text: str) -> List[float]:
        try:
            embeddings = list(self.model.embed(text))
        except Exception:
            logger.error("Error generating embeddings", exc_info=True, extra={
                "embedding provider": "fastembed",
                "embedding model": settings.EMBEDDING_MODEL
            })
            raise
        
        if embeddings is None:
            raise RuntimeError("FastEmbedding response did not contain embedding vector")
        
        return list(map(float, embeddings[0]))
    
class AzureOpenAIAdapter(EmbeddingsAdapter):
    """Generate embeddings using Azure Open AI Embeddings Provider"""
    
    def __init__(self):
        logger.info("Intialising Azure Open AI embeddings adapter", extra={
            "embedding_model": settings.EMBEDDING_MODEL
        })
        self.client = AzureOpenAI(
            api_version=settings.AZURE_API_VERSION,
            azure_endpoint=settings.AZURE_ENDPOINT,
            api_key=settings.AZURE_API_KEY
        )
        self.model = settings.AZURE_DEPLOYMENT
        
    async def generate_embedding(self, text) -> List[float]:
        try:
            response = self.client.embeddings.create(
                input=[text],
                model=self.model,
                dimensions=settings.EMBEDDING_DIMENSIONS
            )
        except Exception:
            logger.error("Error generatring embeddings", exc_info=True, extra={
                "embedding provider": "Azure",
                "embedding model": self.model
            })
            raise
        
        if response is None:
            raise RuntimeError("Azure response did not contain embedding vector")

        embeddings  = response.data[0].embedding 

        return embeddings

class GoogleEmbeddingsAdapter(EmbeddingsAdapter):
    """Generate embeddings using Google Generative AI embedding models."""

    def __init__(self):
        logger.info("Initialising Google Generative AI embeddings adapter", extra={
            "embedding_model": settings.EMBEDDING_MODEL
        })

        self.api_key = settings.GOOGLE_AI_API_KEY
        self.model = settings.EMBEDDING_MODEL

        if not self.api_key:
            raise ValueError("GOOGLE_AI_API_KEY must be configured for GoogleEmbeddingsAdapter")

        genai.configure(api_key=self.api_key)

    async def generate_embedding(self, text: str) -> List[float]:
        try:
            result = await asyncio.to_thread(
                genai.embed_content,
                model=self.model,
                content=text,
                output_dimensionality=settings.EMBEDDING_DIMENSIONS
            )
        except Exception:
            logger.error("Error generating embeddings", exc_info=True, extra={
                "embedding_provider": "google",
                "embedding_model": self.model
            })
            raise

        embedding = result.get("embedding")
        if embedding is None:
            raise RuntimeError("Google Generative AI response did not contain embedding vector")
        return list(map(float, embedding))

        
