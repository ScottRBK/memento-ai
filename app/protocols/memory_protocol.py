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
            offset: int = 0,
            project_ids: List[int] | None = None,
            include_obsolete: bool = False,
            sort_by: str = "created_at",
            sort_order: str = "desc",
            tags: List[str] | None = None,
    ) -> tuple[List[Memory], int]:
        """
        Get memories with pagination, sorting, and filtering.

        Args:
            user_id: User ID
            limit: Max results to return
            offset: Skip N results for pagination
            project_ids: Filter by project (optional)
            include_obsolete: Include soft-deleted memories
            sort_by: Sort field - created_at, updated_at, importance
            sort_order: Sort direction - asc, desc
            tags: Filter by ANY of these tags (OR logic)

        Returns:
            Tuple of (memories, total_count) where total_count is
            the count BEFORE limit/offset applied (for pagination)
        """
        ...

    async def unlink_memories(
            self,
            user_id: UUID,
            source_id: int,
            target_id: int,
    ) -> bool:
        """
        Remove bidirectional link between two memories.

        Args:
            user_id: User ID for isolation
            source_id: Source memory ID
            target_id: Target memory ID to unlink

        Returns:
            True if link was removed, False if link didn't exist
        """
        ...


