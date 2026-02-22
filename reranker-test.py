import asyncio
import httpx
from app.repositories.embeddings.reranker_adapter import FastEmbedCrossEncoderAdapter, HttpRerankAdapter

from app.config.settings import settings 

QUERY = "How many legs do cats have?"
DOCS = ["one", "two", "three", "four"]

async def main():
    model = "~/.cache/huggingface/hub/models--ggml-org--Qwen3-Reranker-0.6B-Q8_0-GGUF/snapshots/a02f48bb4f057028298c21fa033da2b30d7742d5/qwen3-reranker-0.6b-q8_0.gguf"
    base_url = "http://localhost:8012/v1/rerank"

    headers = {
        "Authorization": f"Bearer {settings.RERANKING_API_KEY}"
    }

  
    payload = {
        "query": QUERY,
        "documents": DOCS,
        "model": model,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url=base_url, headers=headers, json=payload)

    results = response.json()
    ranked = [(r["index"], r["relevance_score"]) for r in results["results"]]

    print(response.status_code)
    print(ranked)
    
async def jina():
    model = "jina-reranker-v3" 
    base_url = "https://api.jina.ai/v1/rerank"
   
    headers = {
        "Authorization": f"Bearer {settings.RERANKING_API_KEY}"
    }

    payload = {
        "query": QUERY,
        "documents": DOCS,
        "model": model,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url=base_url, headers=headers, json=payload)

    results = response.json()
    ranked = [(r["index"], r["relevance_score"]) for r in results["results"]]

    print(response.status_code)
    print(ranked)


async def fast_embed_rank():

    reranker = FastEmbedCrossEncoderAdapter(
       model=settings.RERANKING_MODEL,
       threads=1,
       cache_dir=settings.FASTEMBED_CACHE_DIR 
    ) 
    
    ranked = await reranker.rerank(
        query=QUERY,
        documents=DOCS,
    )
    
    print(ranked)
    
async def http_rank():
    reranker = HttpRerankAdapter(
        model=settings.RERANKING_MODEL,
        url= settings.RERANKING_URL,
    )
    
    ranked = await reranker.rerank(
        query=QUERY,
        documents=DOCS,
    )
    
    print(ranked)
    

if __name__ == "__main__":
    # asyncio.run(main())
    # asyncio.run(fast_embed_rank())
    asyncio.run(http_rank())
    # asyncio.run(jina()) 