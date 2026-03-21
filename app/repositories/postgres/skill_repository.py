"""
PostgreSQL repository for Skill data access operations
"""
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select

from app.repositories.postgres.postgres_tables import (
    MemoryTable,
    SkillsTable,
    memory_skill_association,
)
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.repositories.embeddings.embedding_adapter import EmbeddingsAdapter
from app.repositories.embeddings.reranker_adapter import RerankAdapter
from app.repositories.helpers import build_skill_embedding_text
from app.models.skill_models import Skill, SkillCreate, SkillUpdate, SkillSummary
from app.exceptions import NotFoundError
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


class PostgresSkillRepository:
    """Repository for Skill operations in PostgreSQL"""

    def __init__(
        self,
        db_adapter: PostgresDatabaseAdapter,
        embedding_adapter: EmbeddingsAdapter,
        rerank_adapter: RerankAdapter | None = None,
    ):
        """Initialize with database and embedding adapters

        Args:
            db_adapter: PostgreSQL database adapter for session management
            embedding_adapter: Adapter for generating embeddings
            rerank_adapter: Optional cross-encoder reranker for search
        """
        self.db_adapter = db_adapter
        self.embedding_adapter = embedding_adapter
        self.rerank_adapter = rerank_adapter
        logger.info("Postgres skill repository initialized")

    async def create_skill(
        self,
        user_id: UUID,
        skill_data: SkillCreate
    ) -> Skill:
        """Create a new skill with embedding

        Args:
            user_id: User ID for ownership
            skill_data: SkillCreate with skill details

        Returns:
            Created Skill with generated ID and timestamps
        """
        try:
            embedding_text = build_skill_embedding_text(skill_data)
            embedding = await self.embedding_adapter.generate_embedding(embedding_text)

            async with self.db_adapter.session(user_id) as session:
                skill_table = SkillsTable(
                    user_id=user_id,
                    name=skill_data.name,
                    description=skill_data.description,
                    content=skill_data.content,
                    license=skill_data.license,
                    compatibility=skill_data.compatibility,
                    allowed_tools=skill_data.allowed_tools,
                    skill_metadata=skill_data.metadata,
                    tags=skill_data.tags,
                    importance=skill_data.importance,
                    project_id=skill_data.project_id,
                    embedding=embedding,
                )

                session.add(skill_table)
                await session.commit()
                await session.refresh(skill_table)

                return self._to_skill(skill_table)

        except Exception as e:
            logger.error(
                "Failed to create skill",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def get_skill_by_id(
        self,
        user_id: UUID,
        skill_id: int
    ) -> Skill | None:
        """Get skill by ID with ownership check

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to retrieve

        Returns:
            Skill if found and owned by user, None otherwise
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(SkillsTable).where(
                    SkillsTable.id == skill_id,
                    SkillsTable.user_id == user_id
                )

                result = await session.execute(stmt)
                skill_table = result.scalar_one_or_none()

                if not skill_table:
                    return None

                return self._to_skill(skill_table)

        except Exception as e:
            logger.error(
                f"Failed to get skill {skill_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                    "error": str(e)
                }
            )
            raise

    async def list_skills(
        self,
        user_id: UUID,
        project_id: int | None = None,
        tags: list[str] | None = None,
        importance_threshold: int | None = None
    ) -> list[SkillSummary]:
        """List skills with optional filtering

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            tags: Optional filter by tags (returns skills with ANY of these tags)
            importance_threshold: Optional minimum importance level

        Returns:
            List of SkillSummary (lightweight, excludes full content)
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(SkillsTable).where(
                    SkillsTable.user_id == user_id
                )

                if project_id is not None:
                    stmt = stmt.where(SkillsTable.project_id == project_id)

                if tags:
                    stmt = stmt.where(SkillsTable.tags.overlap(tags))

                if importance_threshold is not None:
                    stmt = stmt.where(SkillsTable.importance >= importance_threshold)

                stmt = stmt.order_by(SkillsTable.created_at.desc())

                result = await session.execute(stmt)
                skills = result.scalars().all()

                return [SkillSummary.model_validate(s) for s in skills]

        except Exception as e:
            logger.error(
                "Failed to list skills",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def update_skill(
        self,
        user_id: UUID,
        skill_id: int,
        skill_data: SkillUpdate
    ) -> Skill:
        """Update skill (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.
        If description changes, the embedding is regenerated.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to update
            skill_data: SkillUpdate with fields to change

        Returns:
            Updated Skill

        Raises:
            NotFoundError: If skill not found or not owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(SkillsTable).where(
                    SkillsTable.id == skill_id,
                    SkillsTable.user_id == user_id
                )

                result = await session.execute(stmt)
                skill_table = result.scalar_one_or_none()

                if not skill_table:
                    raise NotFoundError(f"Skill {skill_id} not found")

                update_data = skill_data.model_dump(exclude_unset=True)

                # Map Pydantic 'metadata' field to ORM 'skill_metadata' column
                if "metadata" in update_data:
                    update_data["skill_metadata"] = update_data.pop("metadata")

                # Regenerate embedding if description changed
                if "description" in update_data:
                    embedding_text = build_skill_embedding_text(skill_data)
                    embedding = await self.embedding_adapter.generate_embedding(embedding_text)
                    update_data["embedding"] = embedding

                for field, value in update_data.items():
                    setattr(skill_table, field, value)

                skill_table.updated_at = datetime.now(timezone.utc)

                await session.commit()
                await session.refresh(skill_table)

                return self._to_skill(skill_table)

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update skill {skill_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                    "error": str(e)
                }
            )
            raise

    async def delete_skill(
        self,
        user_id: UUID,
        skill_id: int
    ) -> bool:
        """Delete skill with ownership check

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(SkillsTable).where(
                    SkillsTable.id == skill_id,
                    SkillsTable.user_id == user_id
                )

                result = await session.execute(stmt)
                skill_table = result.scalar_one_or_none()

                if not skill_table:
                    return False

                await session.delete(skill_table)
                await session.commit()

                return True

        except Exception as e:
            logger.error(
                f"Failed to delete skill {skill_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                    "error": str(e)
                }
            )
            raise

    async def search_skills(
        self,
        user_id: UUID,
        query: str,
        k: int = 5,
        project_id: int | None = None
    ) -> list[SkillSummary]:
        """Search skills by semantic similarity

        Generates a query embedding and uses cosine distance for vector
        similarity search. Optionally applies cross-encoder reranking.

        Args:
            user_id: User ID for ownership filtering
            query: Search query string
            k: Number of results to return (default: 5)
            project_id: Optional filter by project

        Returns:
            List of SkillSummary ranked by relevance
        """
        try:
            query_embedding = await self.embedding_adapter.generate_embedding(query)

            # Fetch more candidates if reranking is enabled
            candidates_k = k * 3 if self.rerank_adapter is not None else k

            async with self.db_adapter.session(user_id) as session:
                stmt = select(SkillsTable).where(
                    SkillsTable.user_id == user_id
                )

                if project_id is not None:
                    stmt = stmt.where(SkillsTable.project_id == project_id)

                stmt = stmt.order_by(
                    SkillsTable.embedding.cosine_distance(query_embedding)
                )
                stmt = stmt.limit(candidates_k)

                result = await session.execute(stmt)
                skills = result.scalars().all()

                if not skills:
                    return []

                # Apply cross-encoder reranking if available
                if self.rerank_adapter is not None and len(skills) > k:
                    documents = [s.description for s in skills]
                    ranked = await self.rerank_adapter.rerank(
                        query=query, documents=documents
                    )
                    skills = [skills[idx] for idx, score in ranked[:k]]

                return [SkillSummary.model_validate(s) for s in skills]

        except Exception as e:
            logger.error(
                "Failed to search skills",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "query": query,
                    "error": str(e)
                }
            )
            raise

    async def link_skill_to_memory(
        self,
        user_id: UUID,
        skill_id: int,
        memory_id: int,
    ) -> dict:
        """Link a skill to a memory via the association table.

        Args:
            user_id: User ID for ownership verification.
            skill_id: Skill ID to link.
            memory_id: Memory ID to link.

        Returns:
            Dict confirming the link was created.

        Raises:
            NotFoundError: If skill or memory not found or not owned by user.
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Verify skill exists and is owned by user
                skill_stmt = select(SkillsTable).where(
                    SkillsTable.id == skill_id,
                    SkillsTable.user_id == user_id,
                )
                skill_result = await session.execute(skill_stmt)
                if skill_result.scalar_one_or_none() is None:
                    msg = f"Skill {skill_id} not found"
                    raise NotFoundError(msg)

                # Verify memory exists and is owned by user
                memory_stmt = select(MemoryTable).where(
                    MemoryTable.id == memory_id,
                    MemoryTable.user_id == user_id,
                )
                memory_result = await session.execute(memory_stmt)
                if memory_result.scalar_one_or_none() is None:
                    msg = f"Memory {memory_id} not found"
                    raise NotFoundError(msg)

                # Insert into the association table
                await session.execute(
                    memory_skill_association.insert().values(
                        skill_id=skill_id,
                        memory_id=memory_id,
                    ),
                )
                await session.commit()

                return {
                    "skill_id": skill_id,
                    "memory_id": memory_id,
                    "linked": True,
                }

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to link skill {skill_id} to memory {memory_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                    "memory_id": memory_id,
                    "error": str(e),
                },
            )
            raise

    async def unlink_skill_from_memory(
        self,
        user_id: UUID,
        skill_id: int,
        memory_id: int,
    ) -> dict:
        """Remove the link between a skill and a memory.

        Args:
            user_id: User ID for ownership verification.
            skill_id: Skill ID to unlink.
            memory_id: Memory ID to unlink.

        Returns:
            Dict confirming the link was removed.
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                await session.execute(
                    memory_skill_association.delete().where(
                        memory_skill_association.c.skill_id == skill_id,
                        memory_skill_association.c.memory_id == memory_id,
                    ),
                )
                await session.commit()

                return {
                    "skill_id": skill_id,
                    "memory_id": memory_id,
                    "unlinked": True,
                }

        except Exception as e:
            logger.error(
                f"Failed to unlink skill {skill_id} from memory {memory_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                    "memory_id": memory_id,
                    "error": str(e),
                },
            )
            raise

    @staticmethod
    def _to_skill(row: SkillsTable) -> Skill:
        """Convert ORM row to Skill model.

        Handles the skill_metadata -> metadata field name mapping.
        SQLAlchemy models have a class-level .metadata attribute (MetaData),
        so we cannot rely on model_validate(row) for this field.
        """
        return Skill(
            id=row.id,
            name=row.name,
            description=row.description,
            content=row.content,
            license=row.license,
            compatibility=row.compatibility,
            allowed_tools=row.allowed_tools,
            metadata=row.skill_metadata,
            tags=row.tags,
            importance=row.importance,
            project_id=row.project_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
