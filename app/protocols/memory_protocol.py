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
    ) -> List[Memory]:
        ...
    async def create_memory(
            self,
            user_id: UUID, 
            memory: MemoryCreate
    ) -> Memory:
        ...
    async def create_links_batch(
            self,
            user_id: UUID,
            source_id: int,
            target_ids: List[int],
    ) -> List[int]:
        ...
    async def get_memory_by_id(
            self,
            user_id: UUID,
            memory_id: int,
    ) -> Memory:
        ...
    async def update_memory(
            self,
            user_id: UUID,
            memory_id: int,
            updated_memory: MemoryUpdate,
            existing_memory: Memory,
            search_fields_changed: bool,
    ) -> Memory | None:
        ...
    async def mark_obsolete(
            self,
            user_id: UUID,
            memory_id: int,
            reason: str,
            superseded_by: int
    ) -> bool:
        ...
    async def get_linked_memories(
            self,
            user_id: UUID,
            memory_id: int,
            project_ids: List[int] | None,
            max_links: int = 5,
    ) -> List[Memory]:
        ...
    async def find_similar_memories(
            self,
            user_id: UUID,
            memory_id: int,
            max_links: int
    ) -> List[Memory]:
        ...

    async def get_recent_memories(
            self,
            user_id: UUID,
            limit: int,
            project_ids: List[int] | None = None
    ) -> List[Memory]:
        ...


