"""
Re-embedding service for batch migration of memory embeddings.

Orchestrates the workflow of re-embedding all memories with the currently
configured embedding provider. Knows nothing about SQLite/PostgreSQL specifics.
"""
from typing import Callable, List, Tuple
from dataclasses import dataclass

from app.protocols.memory_protocol import MemoryRepository, ValidationResult
from app.repositories.embeddings.embedding_adapter import EmbeddingsAdapter
from app.repositories.helpers import build_embedding_text

import logging

logger = logging.getLogger(__name__)


@dataclass
class ReEmbedResult:
    """Result of a re-embedding operation"""
    total_processed: int
    total_memories: int
    validation: ValidationResult | None = None


class ReEmbeddingService:
    """Orchestrates batch re-embedding of all memories"""

    def __init__(
        self,
        memory_repository: MemoryRepository,
        embedding_adapter: EmbeddingsAdapter,
        batch_size: int = 20,
    ):
        self.memory_repository = memory_repository
        self.embedding_adapter = embedding_adapter
        self.batch_size = batch_size

    async def re_embed_all(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ReEmbedResult:
        """
        Orchestrate: count -> reset schema -> batch re-embed -> validate

        Args:
            progress_callback: Optional callback(processed, total) called after each batch

        Returns:
            ReEmbedResult with counts and validation status
        """
        total = await self.memory_repository.count_all_memories()
        logger.info("Starting re-embedding", extra={"total_memories": total})

        if total == 0:
            logger.info("No memories to re-embed")
            return ReEmbedResult(
                total_processed=0,
                total_memories=0,
                validation=ValidationResult(count_ok=True, dimensions_ok=True, search_ok=True),
            )

        # Reset vector storage for new dimensions
        await self.memory_repository.reset_embedding_storage()

        processed = 0
        for offset in range(0, total, self.batch_size):
            memories = await self.memory_repository.get_memories_for_reembedding(
                limit=self.batch_size, offset=offset
            )

            if not memories:
                break

            # Generate embeddings for this batch
            updates: List[Tuple[int, List[float]]] = []
            for memory in memories:
                embedding_text = build_embedding_text(memory)
                embedding = await self.embedding_adapter.generate_embedding(embedding_text)
                updates.append((memory.id, embedding))

            # Write batch
            await self.memory_repository.bulk_update_embeddings(updates)

            processed += len(memories)
            if progress_callback:
                progress_callback(processed, total)

            logger.info("Batch complete", extra={
                "processed": processed,
                "total": total,
                "batch_size": len(memories),
            })

        # Validate
        validation = await self.validate()

        return ReEmbedResult(
            total_processed=processed,
            total_memories=total,
            validation=validation,
        )

    async def validate(self) -> ValidationResult:
        """Post-migration validation checks delegated to repository"""
        count_ok = await self.memory_repository.validate_embedding_count()
        dims_ok = await self.memory_repository.validate_embedding_dimensions()
        search_ok = await self.memory_repository.validate_search_works()

        result = ValidationResult(
            count_ok=count_ok,
            dimensions_ok=dims_ok,
            search_ok=search_ok,
        )

        if result.all_passed:
            logger.info("Validation passed", extra={
                "count_ok": count_ok,
                "dimensions_ok": dims_ok,
                "search_ok": search_ok,
            })
        else:
            logger.error("Validation failed", extra={
                "count_ok": count_ok,
                "dimensions_ok": dims_ok,
                "search_ok": search_ok,
            })

        return result
