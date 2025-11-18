import asyncio
from typing import Protocol, List
from concurrent.futures import ThreadPoolExecutor
from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config.settings import settings


class RerankAdapter(Protocol): 
    """Contract for a Reranker Adapter"""
    async def rerank(self, 
                     query: str,
                     documents: List[str],
    ) -> List[float]:
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
    ) -> List[float]:
        """Score documents by relevance to query"""
        
        if not documents:
            return []
        
        loop = asyncio.get_event_loop()

        scores = await loop.run_in_executor(
            self._executor,
            self._rerank_sync,
            query,
            documents
        )
        
        return scores
    
    def _rerank_sync(self, query: str, documents: List[str])-> List[float]:
        """Synchronus reranking implementation"""
        scores = list(self._model.rerank(query=query, documents=documents))
        return scores 
    
    def __del__(self): 
        """CLeanup thread ppol on deletion."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
