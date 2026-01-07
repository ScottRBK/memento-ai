"""
Memory Service - Core business logic for memory operations

This service implements the primary functionality for the Forgetful Memory System:
    - Semantic search with token budget management
    - Memory creation with auto-linking
    - Memory updates
    - Manual linking between memories
    - Retrieval with project associations
"""
from typing import TYPE_CHECKING, List
from uuid import UUID

from app.config.logging_config import logging
from app.protocols.memory_protocol import MemoryRepository
from app.models.memory_models import (
    Memory,
    MemoryCreate,
    MemoryUpdate,
    MemoryQueryResult,
    MemoryQueryRequest,
    LinkedMemory,
    MemorySummary
)
from app.models.activity_models import ActivityEvent, EntityType, ActionType, ActorType
from app.config.settings import settings
from app.utils.token_counter import TokenCounter
from app.utils.pydantic_helper import get_changed_fields

if TYPE_CHECKING:
    from app.events import EventBus

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Service layer for memory operations

    Handles business logic for creating, updating, querying and linking memories.
    Uses repository protocol for data access.

    Optionally emits activity events via event bus for tracking.
    """

    def __init__(self, memory_repo: MemoryRepository, event_bus: "EventBus | None" = None):
        self.memory_repo = memory_repo
        self._event_bus = event_bus
        logger.info("Memory service initialised")    
        
    async def query_memory(
            self,
            user_id: UUID,
            memory_query: MemoryQueryRequest,
    ) -> MemoryQueryResult:
        """
            Queries memories with token budget managmeent 

            Performs two-tier retrieval:
            1. Primary memories from search (top-k)
            2. Linked memories (1-hop neighbors) for each primary result

            Applies token budget limits to ensure results fit within context window.
            
            Args:
                user_id: User ID for isolation
                memory_query: Memory Query Request 

            Returns: 
                MemoryQueryResults with primary memories, linked memories, and metadata
        """
        
        logger.info("querying primary memories", extra={"query": memory_query.query})
        primary_memories = await self.memory_repo.search(
            user_id=user_id,
            query=memory_query.query,
            query_context=memory_query.query_context,
            k=memory_query.k,
            importance_threshold=memory_query.importance_threshold,
            project_ids=memory_query.project_ids,
            exclude_ids=None
         )
        logger.info("primary memory query completed", extra={"number of messages found": len(primary_memories)})

        linked_memories = []
        if memory_query.include_links and memory_query.max_links_per_primary > 0:
            logger.info("querying linked memories", extra={"number of primary memories": len(primary_memories)})
            
            linked_memory_projects = None
            if memory_query.strict_project_filter:
                linked_memory_projects = memory_query.project_ids

            linked_memories = await self._fetch_linked_memories(
                user_id=user_id,
                primary_memories=primary_memories,
                max_links_per_primary=memory_query.max_links_per_primary,
                project_ids=linked_memory_projects,
            )
            logger.info("linked memory query completed", extra={"number of linked memories": len(linked_memories)})
        
        logger.info("applying token budget")
        (
            final_primaries,
            final_linked,
            token_count,
            truncated
        ) = await self._apply_token_budget(
            primary_memories=primary_memories,
            linked_memories=linked_memories,
            max_tokens=settings.MEMORY_TOKEN_BUDGET,
            max_memories=settings.MEMORY_MAX_MEMORIES
        )
        logger.info("token budget applied")

        logger.info(
            "returning memories",
            extra={
                "number of primary": len(final_primaries),
                "number of linked": len(final_linked),
                "token_count": token_count,
                "truncated": truncated
            }
        )
        
        return MemoryQueryResult(
            query=memory_query.query,
            primary_memories=final_primaries,
            linked_memories=final_linked,
            total_count=len(final_primaries) + len(final_linked),
            token_count=token_count,
            truncated=truncated
        )
        
    async def create_memory(
            self,
            user_id: UUID,
            memory_data: MemoryCreate
    ) -> tuple[Memory, List[MemorySummary]]:
        """
        Create a new memory in the system

        Args:
            user_id: User ID
            memory_data: Memory Create object with data to be created
        """

        memory = await self.memory_repo.create_memory(
            user_id=user_id,
            memory=memory_data
        )

        similar_memories = []
        linked_ids = []
        if settings.MEMORY_NUM_AUTO_LINK > 0:
            similar_memories_full = await self.memory_repo.find_similar_memories(
                memory_id=memory.id,
                user_id=user_id,
                max_links=settings.MEMORY_NUM_AUTO_LINK
            )

            if similar_memories_full:
                target_ids = [m.id for m in similar_memories_full]
                linked_ids = await self.memory_repo.create_links_batch(
                    user_id=user_id,
                    source_id=memory.id,
                    target_ids=target_ids
                )
                memory.linked_memory_ids = linked_ids

                # Convert to MemorySummary for response
                similar_memories = [
                    MemorySummary(
                        id=m.id,
                        title=m.title,
                        keywords=m.keywords,
                        tags=m.tags,
                        importance=m.importance,
                        created_at=m.created_at,
                        updated_at=m.updated_at
                    )
                    for m in similar_memories_full
                ]

                logger.info("Automatically linked memories", extra={
                    "user_id": user_id,
                    "memory_id": memory.id,
                    "number linked": len(target_ids)
                })

        # Emit created event
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.MEMORY,
            entity_id=memory.id,
            action=ActionType.CREATED,
            snapshot=memory.model_dump(mode="json"),
        )

        return memory, similar_memories 
    
    async def update_memory(
            self,
            user_id: UUID,
            memory_id: int,
            updated_memory: MemoryUpdate
    ) -> Memory | None:
        """
        Update an existing memory

        Args:
            user_id: user_id 
            memory_id: memory_id of the memory being updated
            updated_memory: Memory Update object containg the data to be updated
        """
        
        existing_memory = await self.memory_repo.get_memory_by_id(
            memory_id=memory_id,
            user_id=user_id
        )
        
        
        changed_fields = get_changed_fields(
            input_model=updated_memory,
            existing_model=existing_memory
        ) 
        
        if not changed_fields:
            logger.info("no changes detected, returning existing memory",
                        extra={
                            "memory_id": memory_id,
                            "user_id": user_id
                        })
            return existing_memory
        
        search_fields = {"title", "content", "context", "keywords", "tags"}
        search_fields_changed = bool(search_fields & changed_fields.keys())
        
        modified_memory = await self.memory_repo.update_memory(
            memory_id=memory_id,
            user_id=user_id,
            updated_memory=updated_memory,
            existing_memory=existing_memory,
            search_fields_changed=search_fields_changed
        )

        # Emit updated event with changes
        if modified_memory:
            changes_dict = {
                field: {"old": old, "new": new}
                for field, (old, new) in changed_fields.items()
            }
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.MEMORY,
                entity_id=memory_id,
                action=ActionType.UPDATED,
                snapshot=modified_memory.model_dump(mode="json"),
                changes=changes_dict,
            )

        return modified_memory

    async def mark_memory_obsolete(
            self,
            user_id: UUID,
            memory_id: int,
            reason: str,
            superseded_by: int | None = None,
    ) -> bool:
        """
        Mark a memory as obsolete (soft delete)
        
        Args:
            user_id: User ID
            memory_id: Memory ID to mark obsolete
            reason: Why this memory is obsolete
            superseded_by: Optional ID of memories that have superseded this one

        Returns:
            True if marked obsolete, False if not found
        """
        
        logger.info("Marking memory as obsolete", extra={
            "memory_id": memory_id,
            "user_id": user_id
        })

        # Get memory before marking obsolete for snapshot
        memory = await self.memory_repo.get_memory_by_id(
            memory_id=memory_id,
            user_id=user_id
        )

        success = await self.memory_repo.mark_obsolete(
            memory_id=memory_id,
            user_id=user_id,
            reason=reason,
            superseded_by=superseded_by
        )

        # Emit deleted event with snapshot
        if success and memory:
            snapshot = memory.model_dump(mode="json")
            snapshot["obsolete_reason"] = reason
            snapshot["superseded_by"] = superseded_by
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.MEMORY,
                entity_id=memory_id,
                action=ActionType.DELETED,
                snapshot=snapshot,
            )

        return success

    async def get_memory(
            self,
            user_id: int,
            memory_id: int
    )  -> Memory | None:
        """
        Retrieve a single emmory by id

        Args:
            user_id: User Id
            memory_id: Memory id to retrieve

        Returns:
            Memory object or None if not found
        """

        return await self.memory_repo.get_memory_by_id(
            memory_id=memory_id,
            user_id=user_id
        )

    async def get_recent_memories(
            self,
            user_id: UUID,
            limit: int = 10,
            offset: int = 0,
            project_ids: List[int] | None = None,
            include_obsolete: bool = False,
            sort_by: str = "created_at",
            sort_order: str = "desc",
            tags: List[str] | None = None,
    ) -> tuple[List[Memory], int]:
        """
        Retrieve memories with pagination, sorting, and filtering.

        Args:
            user_id: User ID
            limit: Maximum number of memories to return
            offset: Skip N results for pagination
            project_ids: Optional filter to only retrieve memories from specific projects
            include_obsolete: Include soft-deleted memories (default False)
            sort_by: Sort field - created_at, updated_at, importance
            sort_order: Sort direction - asc, desc
            tags: Filter by ANY of these tags (OR logic)

        Returns:
            Tuple of (memories, total_count) where total_count is count before pagination
        """
        return await self.memory_repo.get_recent_memories(
            user_id=user_id,
            limit=limit,
            offset=offset,
            project_ids=project_ids,
            include_obsolete=include_obsolete,
            sort_by=sort_by,
            sort_order=sort_order,
            tags=tags,
        )

    async def link_memories(
            self,
            user_id: UUID,
            memory_id: int,
            related_ids: List[int]
    ) -> List[int]:
        """
        Creates a bidirectional links between memories

        Duplicate links and self-links are automatically removed

        Args:
            user_id: User ID for isolation
            memory_id: Source memory id
            related_ids: List of target memory IDs to link

        Returns:
            List of target memory IDs that were successfully linked
        """

        source_memory = await self.memory_repo.get_memory_by_id(
            memory_id=memory_id,
            user_id=user_id
        )

        links_created = await self.memory_repo.create_links_batch(
            user_id=user_id,
            source_id=source_memory.id,
            target_ids=related_ids,
        )

        # Emit link.created events for each link
        for target_id in links_created:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.LINK,
                entity_id=0,  # Links use metadata for source/target
                action=ActionType.CREATED,
                snapshot={"source_id": memory_id, "target_id": target_id},
                metadata={"source_id": memory_id, "target_id": target_id},
            )

        return links_created

    async def unlink_memories(
            self,
            user_id: UUID,
            memory_id: int,
            target_id: int,
    ) -> bool:
        """
        Remove link between two memories.

        Args:
            user_id: User ID for isolation
            memory_id: Source memory ID
            target_id: Target memory ID to unlink

        Returns:
            True if link was removed, False if link didn't exist

        Raises:
            NotFoundError: If source memory doesn't exist
        """
        # Verify source memory exists (raises NotFoundError if not)
        await self.get_memory(user_id=user_id, memory_id=memory_id)

        success = await self.memory_repo.unlink_memories(
            user_id=user_id,
            source_id=memory_id,
            target_id=target_id
        )

        # Emit link.deleted event
        if success:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.LINK,
                entity_id=0,
                action=ActionType.DELETED,
                snapshot={"source_id": memory_id, "target_id": target_id},
                metadata={"source_id": memory_id, "target_id": target_id},
            )

        return success

    async def _fetch_linked_memories(
            self,
            user_id,
            primary_memories: List[Memory],
            max_links_per_primary: int,
            project_ids: List[int] | None
    ) -> List[LinkedMemory]:
        """
        Fetch linked memories for each primary result

        Args:
            user_id: User ID for whom to link the memories for
            primary memories: list of the primary Memories objects to link from
            max_links_per_primary: Maximum links per primary memory
        
        Returns:
            List of LinkedMemory objects
        """
        linked_memories = []
        seen_ids = {m.id for m in primary_memories}

        for primary in primary_memories:
            try:
                links = await self.memory_repo.get_linked_memories(
                    memory_id=primary.id,
                    user_id=user_id,
                    project_ids=project_ids,
                    max_links=max_links_per_primary
                )

                for linked_memory in links:
                    if linked_memory.id in seen_ids:
                        continue

                    linked_memories.append(
                        LinkedMemory(
                            memory=linked_memory,
                            link_source_id=primary.id
                        )
                    )
                    
                    seen_ids.add(linked_memory.id)
            except Exception:
                logger.warning(
                    "failed to fetch memories",
                    exc_info=True,
                    extra={
                        "primary_id": primary.id
                    }
                )     
        
        return linked_memories
                

    async def _apply_token_budget(
            self,
            primary_memories: List[Memory],
            linked_memories: List[LinkedMemory],
            max_tokens: int,
            max_memories: int,
    ) -> tuple[List[Memory], List[LinkedMemory], int, bool]:
        """
        Apply token budget and count limits to memory results

        Stategy: 
        1. Priortise primary memories (sorted by importance)
        2. Add linked memories if space remains
        3. Enforce hard limit of max_total_count memories

        Args:
            primary_memories: List of Memory objects of the primary memories
            linked_memories: List of LinkedMemory objects of the linked memories
            max_tokens: maxium total tokens allowed
            max_memories: the maximum number of Memory objects to return

        Returns:
            Tuple of (list primary memories, list linked memories, token count and was truncated)
        """
        
        truncated_primary, primary_tokens, primary_truncated = await self.truncate_memories_by_budget(
            memories=primary_memories,
            max_tokens=max_tokens,
            max_count=max_memories
        )

        remaining_tokens = max_tokens - primary_tokens
        remaining_count = max_memories - len(truncated_primary)

        if primary_truncated:
            return truncated_primary, [], primary_tokens, True

        truncated_linked = []
        linked_tokens = 0
        linked_truncated = False

        if linked_memories:
            linked_memory_objects = [lm.memory for lm in linked_memories]
            truncated_memory_objects, linked_tokens, linked_truncated = await self.truncate_memories_by_budget(
                memories=linked_memory_objects,
                max_tokens=remaining_tokens,
                max_count=remaining_count
            )

            truncated_ids = {m.id for m in truncated_memory_objects}
            truncated_linked = [lm for lm in linked_memories if lm.memory.id in truncated_ids]

        total_tokens = primary_tokens + linked_tokens

        return truncated_primary, truncated_linked, total_tokens, linked_truncated
        
    def _count_memory_tokens(self, memory: Memory) -> int:
        """
        Count total tokens for a memory

        Args: 
            Memory object to count tokens for

        Returns:
            token count
        """
        text_parts = [
            memory.title,
            memory.content,
            memory.context,
            " ".join(memory.keywords),
            " ".join(memory.tags)
        ]

        total_text = " ".join(text_parts)

        token_counter = TokenCounter()

        return token_counter.count_tokens(total_text)
    
    async def truncate_memories_by_budget(
            self,
            memories: List[Memory],
            max_tokens: int,
            max_count: int
    ) -> tuple[List[Memory], int, bool]:
        """
        Truncate memory list to fit within token budget

        Prioritises by importance score (higher = kept first)

        Args:
            memories: List of Memory Objects
            max_tokens: Maximum allowed tokens

        Returns:
            Tuple of (truncated memories, actual_token_count, was_truncated)
        """
        
        if not memories:
            return [], 0, False
        
        sorted_memories = sorted(
            memories,
            key=lambda m: m.importance,
            reverse=True
        )
        
        sorted_memories = sorted_memories[:max_count]
        
        selected = []
        running_total = 0

        for memory in sorted_memories:
            memory_tokens = self._count_memory_tokens(memory=memory)
            
            if running_total + memory_tokens > max_tokens:
                logger.info(
                    "Truncated returned memories",
                    extra={
                        "returned memories": len(selected),
                        "skipped memories": len(memories) - len(selected),
                        "total returned tokens": running_total
                    }
                )

                return selected, running_total, True 

            selected.append(memory)
            running_total += memory_tokens

        return selected, running_total, False

    async def _emit_event(
            self,
            user_id: UUID,
            entity_type: EntityType,
            entity_id: int,
            action: ActionType,
            snapshot: dict,
            changes: dict | None = None,
            metadata: dict | None = None,
    ) -> None:
        """
        Emit an activity event to the event bus.

        This is a no-op if no event bus is configured.

        Args:
            user_id: User ID for the event
            entity_type: Type of entity (memory, link, etc.)
            entity_id: ID of the entity
            action: Action that occurred (created, updated, deleted)
            snapshot: Full entity state at event time
            changes: Field changes for updates
            metadata: Additional context
        """
        if self._event_bus is None:
            return

        event = ActivityEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes,
            snapshot=snapshot,
            actor=ActorType.USER,
            metadata=metadata,
            user_id=str(user_id),
        )

        await self._event_bus.emit(event)