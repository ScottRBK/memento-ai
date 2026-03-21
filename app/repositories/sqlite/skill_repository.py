"""SQLite repository for Skill data access operations with sqlite-vec."""
from datetime import datetime, timezone
from uuid import UUID

import sqlite_vec
from sqlalchemy import func, or_, select, text

from app.config.logging_config import logging
from app.config.settings import settings
from app.exceptions import NotFoundError
from app.models.skill_models import (
    Skill,
    SkillCreate,
    SkillSummary,
    SkillUpdate,
)
from app.repositories.embeddings.embedding_adapter import EmbeddingsAdapter
from app.repositories.embeddings.reranker_adapter import RerankAdapter
from app.repositories.helpers import build_skill_embedding_text
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.repositories.sqlite.sqlite_tables import (
    MemoryTable,
    SkillsTable,
    memory_skill_association,
)

logger = logging.getLogger(__name__)


class SqliteSkillRepository:
    """SQLite skill repository with sqlite-vec vector search.

    Key differences from Postgres:
    - Embeddings stored in separate vec_skills virtual table.
    - Vector similarity search uses sqlite-vec's vec_distance_cosine().
    - UUIDs stored as strings.
    - Tags and allowed_tools stored as JSON arrays.
    - Column name is skill_metadata (not metadata) to avoid conflict.
    - No RLS - user isolation via WHERE clauses.
    """

    def __init__(
        self,
        db_adapter: SqliteDatabaseAdapter,
        embedding_adapter: EmbeddingsAdapter,
        rerank_adapter: RerankAdapter | None = None,
    ) -> None:
        self.db_adapter = db_adapter
        self.embedding_adapter = embedding_adapter
        self.rerank_adapter = rerank_adapter
        logger.info("SQLite skill repository initialized")

    async def create_skill(
        self,
        user_id: UUID,
        skill_data: SkillCreate,
    ) -> Skill:
        """Create a new skill with embedding.

        Args:
            user_id: User ID for ownership.
            skill_data: SkillCreate with skill details.

        Returns:
            Created Skill with generated ID and timestamps.
        """
        try:
            embedding_text = build_skill_embedding_text(skill_data)
            embeddings = (
                await self.embedding_adapter.generate_embedding(
                    text=embedding_text,
                )
            )

            async with self.db_adapter.session(user_id) as session:
                skill_table = SkillsTable(
                    user_id=str(user_id),
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
                )

                session.add(skill_table)
                await session.flush()

                embedding_bytes = sqlite_vec.serialize_float32(
                    embeddings,
                )
                await session.execute(
                    text(
                        "INSERT INTO vec_skills "
                        "(skill_id, embedding) "
                        "VALUES (:skill_id, :embedding)"
                    ),
                    {
                        "skill_id": str(skill_table.id),
                        "embedding": embedding_bytes,
                    },
                )

                await session.commit()
                await session.refresh(skill_table)

                return self._to_skill(skill_table)

        except Exception:
            logger.exception(
                "Failed to create skill",
                extra={
                    "user_id": str(user_id),
                },
            )
            raise

    async def get_skill_by_id(
        self,
        user_id: UUID,
        skill_id: int,
    ) -> Skill | None:
        """Get skill by ID with ownership check.

        Args:
            user_id: User ID for ownership verification.
            skill_id: Skill ID to retrieve.

        Returns:
            Skill if found and owned by user, None otherwise.
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(SkillsTable).where(
                    SkillsTable.id == skill_id,
                    SkillsTable.user_id == str(user_id),
                )

                result = await session.execute(stmt)
                skill_table = result.scalar_one_or_none()

                if not skill_table:
                    return None

                return self._to_skill(skill_table)

        except Exception:
            logger.exception(
                "Failed to get skill %s",
                skill_id,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                },
            )
            raise

    async def list_skills(
        self,
        user_id: UUID,
        project_id: int | None = None,
        tags: list[str] | None = None,
        importance_threshold: int | None = None,
    ) -> list[SkillSummary]:
        """List skills with optional filtering.

        Args:
            user_id: User ID for ownership filtering.
            project_id: Optional filter by project.
            tags: Optional filter by tags (ANY match).
            importance_threshold: Optional minimum importance.

        Returns:
            List of SkillSummary sorted newest first.
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(SkillsTable).where(
                    SkillsTable.user_id == str(user_id),
                )

                if project_id is not None:
                    stmt = stmt.where(
                        SkillsTable.project_id == project_id,
                    )

                if tags:
                    tag_conditions = [
                        func.json_extract(
                            SkillsTable.tags, "$",
                        ).like(f'%"{tag}"%')
                        for tag in tags
                    ]
                    stmt = stmt.where(or_(*tag_conditions))

                if importance_threshold is not None:
                    stmt = stmt.where(
                        SkillsTable.importance
                        >= importance_threshold,
                    )

                stmt = stmt.order_by(
                    SkillsTable.created_at.desc(),
                )

                result = await session.execute(stmt)
                skills = result.scalars().all()

                return [
                    SkillSummary.model_validate(s)
                    for s in skills
                ]

        except Exception:
            logger.exception(
                "Failed to list skills",
                extra={
                    "user_id": str(user_id),
                },
            )
            raise

    async def update_skill(
        self,
        user_id: UUID,
        skill_id: int,
        skill_data: SkillUpdate,
    ) -> Skill:
        """Update skill (PATCH semantics).

        Only provided fields are updated. None/omitted fields
        remain unchanged. If description changes, regenerates
        embedding.

        Args:
            user_id: User ID for ownership verification.
            skill_id: Skill ID to update.
            skill_data: SkillUpdate with fields to change.

        Returns:
            Updated Skill.

        Raises:
            NotFoundError: If skill not found or not owned.
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(SkillsTable).where(
                    SkillsTable.id == skill_id,
                    SkillsTable.user_id == str(user_id),
                )

                result = await session.execute(stmt)
                skill_table = result.scalar_one_or_none()

                if not skill_table:
                    raise NotFoundError(
                        f"Skill {skill_id} not found",
                    )

                update_data = skill_data.model_dump(
                    exclude_unset=True,
                )

                # Map metadata -> skill_metadata column
                if "metadata" in update_data:
                    update_data["skill_metadata"] = (
                        update_data.pop("metadata")
                    )

                # Regenerate embedding if description changed
                if "description" in update_data:
                    embedding_text = (
                        build_skill_embedding_text(skill_data)
                    )
                    embeddings = (
                        await self.embedding_adapter.generate_embedding(
                            text=embedding_text,
                        )
                    )

                    embedding_bytes = (
                        sqlite_vec.serialize_float32(embeddings)
                    )
                    await session.execute(
                        text(
                            "UPDATE vec_skills "
                            "SET embedding = :embedding "
                            "WHERE skill_id = :skill_id"
                        ),
                        {
                            "embedding": embedding_bytes,
                            "skill_id": str(skill_id),
                        },
                    )

                for field, value in update_data.items():
                    setattr(skill_table, field, value)

                skill_table.updated_at = datetime.now(
                    timezone.utc,
                )

                await session.commit()
                await session.refresh(skill_table)

                return self._to_skill(skill_table)

        except NotFoundError:
            raise
        except Exception:
            logger.exception(
                "Failed to update skill %s",
                skill_id,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                },
            )
            raise

    async def delete_skill(
        self,
        user_id: UUID,
        skill_id: int,
    ) -> bool:
        """Delete skill and its embedding.

        Args:
            user_id: User ID for ownership verification.
            skill_id: Skill ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(SkillsTable).where(
                    SkillsTable.id == skill_id,
                    SkillsTable.user_id == str(user_id),
                )

                result = await session.execute(stmt)
                skill_table = result.scalar_one_or_none()

                if not skill_table:
                    return False

                # Delete from vec_skills virtual table first
                await session.execute(
                    text(
                        "DELETE FROM vec_skills "
                        "WHERE skill_id = :skill_id"
                    ),
                    {"skill_id": str(skill_id)},
                )

                await session.delete(skill_table)
                await session.commit()

                return True

        except Exception:
            logger.exception(
                "Failed to delete skill %s",
                skill_id,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                },
            )
            raise

    async def search_skills(
        self,
        user_id: UUID,
        query: str,
        k: int = 5,
        project_id: int | None = None,
    ) -> list[SkillSummary]:
        """Search skills by semantic similarity.

        Uses vec_skills virtual table with vec_distance_cosine
        for vector similarity search.

        Args:
            user_id: User ID for ownership filtering.
            query: Search query string.
            k: Number of results to return (default: 5).
            project_id: Optional filter by project.

        Returns:
            List of SkillSummary ranked by relevance.
        """
        try:
            query_text = query.strip()
            embeddings = (
                await self.embedding_adapter.generate_embedding(
                    text=query_text,
                )
            )
            embedding_bytes = sqlite_vec.serialize_float32(
                embeddings,
            )

            if (
                settings.RERANKING_ENABLED
                and self.rerank_adapter
            ):
                candidates_to_return = (
                    settings.DENSE_SEARCH_CANDIDATES
                )
            else:
                candidates_to_return = k

            async with self.db_adapter.session(
                user_id,
            ) as session:
                sql_parts = [
                    """
                    SELECT s.id
                    FROM skills s
                    INNER JOIN vec_skills vs
                        ON s.id = vs.skill_id
                    WHERE s.user_id = :user_id
                    """,
                ]

                params: dict = {
                    "user_id": str(user_id),
                    "query_embedding": embedding_bytes,
                    "k": candidates_to_return,
                }

                if project_id is not None:
                    sql_parts.append(
                        " AND s.project_id = :project_id",
                    )
                    params["project_id"] = project_id

                sql_parts.append(
                    """
                    ORDER BY vec_distance_cosine(
                        vs.embedding, :query_embedding
                    )
                    LIMIT :k
                    """,
                )

                sql_query = "".join(sql_parts)
                result = await session.execute(
                    text(sql_query), params,
                )
                rows = result.fetchall()

                if not rows:
                    return []

                skill_ids = [row[0] for row in rows]

                stmt = select(SkillsTable).where(
                    SkillsTable.id.in_(skill_ids),
                )

                result = await session.execute(stmt)
                skills_orm = result.scalars().all()

                skill_dict = {s.id: s for s in skills_orm}
                ordered_skills = [
                    skill_dict[sid]
                    for sid in skill_ids
                    if sid in skill_dict
                ]

                summaries = [
                    SkillSummary.model_validate(s)
                    for s in ordered_skills
                ]

                # Apply reranking if enabled
                if (
                    settings.RERANKING_ENABLED
                    and self.rerank_adapter
                    and len(summaries) > k
                ):
                    documents = [
                        f"Name: {s.name}\n"
                        f"Description: {s.description}"
                        for s in summaries
                    ]

                    ranked = await self.rerank_adapter.rerank(
                        query=query_text,
                        documents=documents,
                    )

                    summaries = [
                        summaries[idx]
                        for idx, _score in ranked[:k]
                    ]

                return summaries

        except Exception:
            logger.exception(
                "Failed to search skills",
                extra={
                    "user_id": str(user_id),
                    "query": query,
                },
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
            NotFoundError: If skill or memory not found or not
                owned by user.
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Verify skill exists and is owned by user
                skill_stmt = select(SkillsTable).where(
                    SkillsTable.id == skill_id,
                    SkillsTable.user_id == str(user_id),
                )
                skill_result = await session.execute(skill_stmt)
                if skill_result.scalar_one_or_none() is None:
                    msg = f"Skill {skill_id} not found"
                    raise NotFoundError(msg)

                # Verify memory exists and is owned by user
                memory_stmt = select(MemoryTable).where(
                    MemoryTable.id == memory_id,
                    MemoryTable.user_id == str(user_id),
                )
                memory_result = await session.execute(
                    memory_stmt,
                )
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
        except Exception:
            logger.exception(
                "Failed to link skill %s to memory %s",
                skill_id,
                memory_id,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                    "memory_id": memory_id,
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
            async with self.db_adapter.session(
                user_id,
            ) as session:
                await session.execute(
                    memory_skill_association.delete().where(
                        memory_skill_association.c.skill_id
                        == skill_id,
                        memory_skill_association.c.memory_id
                        == memory_id,
                    ),
                )
                await session.commit()

                return {
                    "skill_id": skill_id,
                    "memory_id": memory_id,
                    "unlinked": True,
                }

        except Exception:
            logger.exception(
                "Failed to unlink skill %s from memory %s",
                skill_id,
                memory_id,
                extra={
                    "user_id": str(user_id),
                    "skill_id": skill_id,
                    "memory_id": memory_id,
                },
            )
            raise

    @staticmethod
    def _to_skill(skill_table: SkillsTable) -> Skill:
        """Convert SkillsTable ORM to Skill Pydantic model.

        Handles the skill_metadata -> metadata field name
        mapping since the DB column is 'skill_metadata' but
        the Pydantic model uses 'metadata'.
        """
        return Skill(
            id=skill_table.id,
            name=skill_table.name,
            description=skill_table.description,
            content=skill_table.content,
            license=skill_table.license,
            compatibility=skill_table.compatibility,
            allowed_tools=skill_table.allowed_tools,
            metadata=skill_table.skill_metadata,
            tags=skill_table.tags,
            importance=skill_table.importance,
            project_id=skill_table.project_id,
            created_at=skill_table.created_at,
            updated_at=skill_table.updated_at,
        )
