"""
Memory Service - Core business logic for memory operations

This service implements the primary functionality for the Veridian Memory System:
    - Semantic search with token budget management
    - Memory creation with auto-linking
    - Memory updates 
    - Manual linking between memories
    - Retrieval with project associations
"""
from typing import Optional, List
from uuid import UUID

from app.config.logging_config import logging
from app.protocols.memory_protocol import MemoryRepository
from app.models.memory_models import (
    Memory, 
    MemoryCreate, 
    MemoryUpdate,
    MemoryQueryResult, 
    MemoryQueryRequest, 
    LinkedMemory
)
from app.config.settings import settings
from app.utils.token_counter import TokenCounter
from app.utils.pydantic_helper import get_changed_fields

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Service layer for memory operations

    Handles business logic for creating, updating, querying and linking memories.
    Uses repository protocol for data access
    """
    
    def __init__(self, memory_repo: MemoryRepository):
        self.memory_repo = memory_repo
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
        
        project_ids = [memory_query.project_id]
        
        logger.info("querying primary memories", extra={"query": memory_query.query})
        primary_memories = await self.memory_repo.search(
            user_id=user_id,
            query=memory_query.query,
            query_context=memory_query.query_context,
            k=memory_query.k,
            importance_threshold=memory_query.importance_threshold,
            project_ids=project_ids,
        )
        logger.info("primary memory query completed", extra={"number of messages found": len(primary_memories)})
        
        if memory_query.include_links and memory_query.max_links_per_primary > 0:
            logger.info("querying linked memories", extra={"number of primary memories": len(primary_memories)})
            linked_memories = await self._fetch_linked_memories(
                user_id=user_id,
                primary_memories=primary_memories,
                max_links_per_primary=memory_query.max_links_per_primary
            )
            logger.info("linked memory query completed", extra={"number of linked memories": len(linked_memories)})
        
        logger.info("applying token budget")
        (
            final_primaries,
            final_linked,
            token_count,
            truncated
        ) = self._apply_token_budget(
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
    ) -> Memory:
        """
        Create a new memory in the system

        Args:
            user_id: User ID
            memory_data: Memory Create object with data to be created
        """
        logger.info("Creating memory", extra={"user_id": user_id, "memory_title": memory_data.title})
            
        memory = await self.memory_repo.create_memory(
            user_id=user_id,
            memory=memory_data            
        )
        
        linked_ids = []
        if settings.MEMORY_NUM_AUTO_LINK > 0:
            linked_ids = await self._auto_link_new_memory(memory_id=memory.id, user_id=user_id)
            memory.linked_memory_ids = linked_ids
            
        # TODO: Implement Project Linking once projects implemented
        # TODO: Implement Document Linking once documents implemented
        # TODO: Implement Code Artifact linking once code artifacts implemented
        
        logger.info("Memory successfully created", extra={"memory_id": memory.id, "user_id": user_id})
        
        return memory 
    
    async def update_memory(
            self,
            user_id: UUID,
            memory_id: int,
            updated_memory: MemoryUpdate
    ) -> Optional[Memory]:
        """
        Update an existing memory

        Args:
            user_id: user_id 
            memory_id: memory_id of the memory being updated
            updated_memory: Memory Update object containg the data to be updated
        """
        # TODO: Remember to update embeddings once repo implemented if the following
        # fields are part of the update: title, content, context, tags, keyword
        
        existing_memory = self.memory_repo.get_memory_by_id(
            memory_id=memory_id,
            user_id=user_id
        )
        
        if not existing_memory:
            logger.warning("Memory not found", extra={
                "memory_id": memory_id,
                "user_id": user_id
            })
            raise KeyError(f"Memory not found {memory_id}")
        
        
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
        
        modified_memory = await self.memory_repo.update_memory(
            memory_id=memory_id,
            user_id=user_id,
            updated_memory=updated_memory
        )
        
        if not modified_memory:
            logger.warning("Failed to update memory", extra={
                "memory_id": memory_id,
                "user_id": user_id
            })
            
        logger.info("Successfully updated memory", extra={
            "memory_id": modified_memory.id,
            "user_id": user_id
        })

        return modified_memory
    
    async def mark_memory_obsolete(
            self,
            user_id: UUID,
            memory_id: int,
            reason: str,
            superseeded_by: Optional[int] = None,
    ) -> bool:
        """
        Mark a memory as obsolete (soft delete)
        
        Args:
            user_id: User ID
            memory_id: Memory ID to mark obsolete
            reason: Why this memory is obsolete
            superseeded by: Optional ID of memories that have superseded this one

        Returns:
            True if marked obsolete, False if not found
        """
        
        logger.info("Marking memory as obsolete", extra={
            "memory_id": memory_id,
            "user_id": user_id
        })
        
        success = await self.memory_repo.mark_obsolete(
            memory_id=memory_id,
            user_id=user_id,
            reason=reason,
            superseded_by=superseeded_by
        ) 
        
        if success:
            logger.info("Successfully marked memory as obsolete", extra={
                "memory_id": memory_id,
                "user_id": user_id
            })
        else:
            logger.warning("Failed to mark memory obsolete", extra={
                "memory_id": memory_id,
                "user_id": user_id
            })
            
        return success

    async def get_memory(
            self,
            user_id: int,
            memory_id: int
    )  -> Optional[Memory]:
        """
        Retrieve a single emmory by id

        Args:
            user_id: User Id
            memory_id: Memory id to retrieve

        Returns:
            Memory object or None if not found
        """
        logger.info("Retrieving memory", extra={
            "user_id": user_id,
            "memory_id": memory_id
        })
        
        memory = await self.memory_repo.get_memory_by_id(
            memory_id=memory_id,
            user_id=user_id
        )

        if not memory:
            logger.info("Memory not found", extra={
                "user_id": user_id,
                "memory_id": memory_id
            }) 
            raise KeyError(f"Memory {memory_id} not found")
            
        return memory
    
    async def link_memories(
            self,
            user_id: UUID,
            memory_id: int,
            related_ids: List[int]
    ) -> int:
        """"
        Creates a bidirectional links between memories

        Duplicate links and self-lnks are automatically removed
        
        Args:
            user_id: User ID for isolation
            memory_id: Source memory id
            related_ids: List of target memmory IDs to link

        Returns:
            Number of links successfully created 
        """
        
        logger.info("Linking memories", extra={
            "user_id": user_id,
            "source_memory_id": memory_id,
            "number of links to add": len(related_ids)
        })
        
        source_memory = self.memory_repo.get_memory_by_id(
            memory_id=memory_id,
            user_id=user_id
        )
        
        if not source_memory:
            logger.warning("Source memory not found", extra={
                "user_id": user_id,
                "memory_id": memory_id
            })
            raise KeyError(f"source memory {memory_id} not found")
        
        links_created = await self.memory_repo.create_links_batch(
            source_id=source_memory.id,
            target_ids=related_ids,
        )
        
        logger.info("Memory links successfully created", extra={
            "user_id": user_id,
            "source_memory_id": source_memory.id,
            "number of links added": links_created,
        })
                    
        return links_created

    async def _auto_link_new_memory(
            self,
            memory_id: int,
            user_id: UUID
    ) -> Optional[List[int]]: 
        """
        Automatically link new memory to similar memories
        
        Args:
            memory_id: memory_id to automatically memories too
            user_id: User ID
        
        Return:
            List of linked memories
        """

        similar_memories = await self.memory_repo.find_similar_memories(
            memory_id=memory_id,
            user_id=user_id,
            max_links=settings.MEMORY_NUM_AUTO_LINK
        )
        
        if similar_memories:
            target_ids = [m.id for m in similar_memories]
            links_created = await self.memory_repo.create_links_batch(
                user_id=user_id,
                source_id=memory_id,
                target_ids=target_ids
            )
            logger.info("Automatically linked memories", extra={
                "user_id": user_id,
                "memory_id": memory_id,
                "number linked": len(target_ids)
            })
        else:
            logger.info("autolinking failed, no similar memories found", extra={
                "user_id": user_id,
                "memory_id": memory_id
            })

        return similar_memories
            

    async def _fetch_linked_memories(
            self,
            user_id,
            primary_memories: List[Memory],
            max_links_per_primary: int
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
            except Exception as e:
                logger.warning(
                    "failed to fetch memories",
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
    ) -> tuple [List[Memory], List[LinkedMemory], int, bool]:
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
        
        truncated_primary, primary_tokens, primary_truncated = self.truncate_memories_by_budget(
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
        
        truncated_linked, linked_tokens, linked_truncated = self.truncate_memories_by_budget(
            memories=linked_memories,
            max_tokens=remaining_tokens,
            max_count=remaining_count
        )

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
               