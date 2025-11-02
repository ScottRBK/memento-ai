from typing import Protocol, List
from uuid import UUID

from app.models.memory_models import Memory, MemoryCreate, MemoryUpdate


class MemoryRepository(Protocol):
    "Contract for the Memory Repository"
    
    async def search(
            self,
            user_id: UUID,
            query: str, 
            query_context: str,
            k: int, 
            importance_threshold: int | None,
            project_ids: List[int] | None,
            exclude_ids: List[int] | None
    ) -> Memory:
        ...
    async def create_memory(
            self,
            user_id: UUID, 
            memory: MemoryCreate
    ) -> Memory:
        ...
    async def create_links_batch(
            self,
            user_id: int,
            source_id: int,
            target_ids: List[int],
    ) -> int:
        ...
    async def get_memory_by_id(
            self,
            memory_id: int,
            user_id: UUID
    ) -> Memory | None:
        ...
    async def update_memory(
            self,
            memory_id: int,
            user_id: UUID,
            updated_memory: MemoryUpdate
    ) -> Memory | None:
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
    async def find_similar_memories(
            self,
            memory_id: int,
            user_id: UUID,
            max_links: int
    ) -> List[Memory]:
        ...
            

