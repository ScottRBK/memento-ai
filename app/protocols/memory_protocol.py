from typing import Protocol, Optional, List
from uuid import UUID

from app.models.memory_models import Memory, MemoryUpdate


class MemoryRepository(Protocol):
    "Contract for the Memory Repository"
    
    async def semantic_search(
            self,
            user_id: UUID,
            query: str, 
            k: int, 
            importance_threshold: Optional[int],
            project_ids: Optional[List[int]], 
            exclude_ids: Optional[List[int]]
    ) -> Memory:
        ...
    async def hybrid_search(
            self,
            user_id: UUID, 
            query: str, 
            k: int, 
            importance_threshold: Optional[int],
            project_ids: Optional[List[int]], 
            exclude_ids: Optional[List[int]]
    ) -> Memory:
        ...
    async def create_memory(
            self,
            user_id: UUID, 
            title: str,
            content: str, 
            context: str,
            keywords: List[str],
            tags: List[str],
            importance: int
    ) -> Memory:
        ...
    async def create_links_batch(
            self,
            source_id: int,
            target_ids: List[int],
    ) -> int:
        ...
    async def get_memory_by_id(
            self,
            memory_id: int,
            user_id: UUID
    ) -> Optional[Memory]:
        ...
    async def update_memory(
            self,
            memory_id: int,
            user_id: UUID,
            updated_memory: MemoryUpdate
    ) -> Optional[Memory]:
        ...
    async def mark_obsolete(
            self,
            memory_id: int,
            user_id: UUID,
            reason: str,
            superseded_by: int
    ) -> bool:
        ...
    async def get_linked_memories(
            self,
            memory_id: int,
            user_id: UUID,
            max_links: int = 5,
    ) -> List[Memory]:
        ...
            

