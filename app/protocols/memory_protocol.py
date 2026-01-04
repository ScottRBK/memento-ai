from typing import Protocol, List, Dict, Any, Tuple
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

    async def get_subgraph_nodes(
            self,
            user_id: UUID,
            center_type: str,
            center_id: int,
            depth: int,
            include_memories: bool,
            include_entities: bool,
            include_projects: bool,
            include_documents: bool,
            include_code_artifacts: bool,
            max_nodes: int
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Traverse graph using recursive CTE from center node.

        Uses a single recursive CTE query to traverse all edge types:
        - memory_links (memory <-> memory)
        - memory_entity_association (memory <-> entity)
        - entity_relationships (entity <-> entity)
        - memory_project_association (memory <-> project)
        - document.project_id (document -> project)
        - code_artifact.project_id (code_artifact -> project)
        - memory_document_association (memory <-> document)
        - memory_code_artifact_association (memory <-> code_artifact)

        Args:
            user_id: User ID for ownership filtering
            center_type: "memory", "entity", "project", "document", or "code_artifact"
            center_id: ID of the center node
            depth: Maximum traversal depth (1-3)
            include_memories: Whether to include memory nodes in traversal
            include_entities: Whether to include entity nodes in traversal
            include_projects: Whether to include project nodes in traversal
            include_documents: Whether to include document nodes in traversal
            include_code_artifacts: Whether to include code_artifact nodes in traversal
            max_nodes: Maximum nodes to return

        Returns:
            Tuple of (nodes_list, truncated) where nodes_list contains dicts
            with node_id, node_type, and depth fields
        """
        ...


