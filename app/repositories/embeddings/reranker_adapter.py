import asyncio
import httpx
from typing import Protocol, List
from concurrent.futures import ThreadPoolExecutor
from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config.settings import settings


class RerankAdapter(Protocol): 
    """Contract for a Reranker Adapter"""
    async def rerank(self, 
                     query: str,
                     documents: List[str],
    ) -> List[tuple[int, float]]:
        ...

class FastEmbedCrossEncoderAdapter: 
    """Cross-encoder reranker using FastEmbeds TextCrossEncoder"""
    
    def __init__(
            self,
            model: str = settings.RERANKING_MODEL,
            threads: int = 1,
            cache_dir: str | None  = None,
    ): 
        """Intialise FastEmbed cross encoder"""
        self.model_name = model
        self.threads = threads 
        self.cache_dir = cache_dir 
        
        self._model = TextCrossEncoder(
            model_name=model,
            threads=threads,
            cache_dir=cache_dir
        )
        self._executor = ThreadPoolExecutor(max_workers=1)
        
    async def rerank(
            self,
            query: str,
            documents: List[str],
    ) -> List[tuple[int, float]]:
        """Score documents by relevance to query"""
        
        if not documents:
            return []
        
        loop = asyncio.get_event_loop()

        ranked = await loop.run_in_executor(
            self._executor,
            self._rerank_sync,
            query,
            documents
        )
        
        return ranked
    
    def _rerank_sync(self, query: str, documents: List[str])-> List[tuple[int,float]]:
        """Synchronus reranking implementation"""
        scores = list(self._model.rerank(query=query, documents=documents))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked
    
    def __del__(self): 
        """CLeanup thread ppol on deletion."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
            
    
class HttpRerankAdapter:
    """Cross-encoder reranker using http"""
    
    def __init__(
            self,
            model: str | None = None,
            url: str | None = None,
            api_key: str | None = None,
    ):
        self.model = model if model is not None else settings.RERANKING_MODEL
        self.url = url if url is not None else settings.RERANKING_URL
        self.api_key = api_key if api_key is not None else settings.RERANKING_API_KEY
        

    async def rerank(
            self,
            query: str,
            documents: List[str]
    ) -> List[tuple[int, float]]:

        if not documents:
            return []

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "query": query,
            "documents": documents,
            "model": self.model,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url=self.url, headers=headers, json=payload)
            response.raise_for_status()

        response_json = response.json()

        ranked = [(r["index"], r["relevance_score"]) for r in response_json["results"]]

        return ranked


