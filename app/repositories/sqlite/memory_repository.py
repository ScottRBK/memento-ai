"""
Memory repository for SQLite data access operations

Key differences from Postgres version:
- Vector similarity computed in Python (fallback, can be optimized with sqlite-vec later)
- JSON serialization/deserialization for array columns (keywords, tags)
- UUID stored as String
- All queries include explicit user_id filtering (no RLS)
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import List
import json
import math

from sqlalchemy import select, update, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.repositories.sqlite.sqlite_tables import (
    MemoryTable,
    MemoryLinkTable,
    ProjectsTable,
    CodeArtifactsTable,
    DocumentsTable,
    memory_project_association
)
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.repositories.embeddings.embedding_adapter import EmbeddingsAdapter
from app.repositories.helpers import build_embedding_text
from app.models.memory_models import Memory, MemoryCreate, MemoryUpdate
from app.exceptions import NotFoundError
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (higher is more similar)
    """
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


class SqliteMemoryRepository:
    """
    Repository for Memory entity operations in SQLite

    Note: Vector similarity search is performed in Python for maximum compatibility.
    This can be optimized with sqlite-vec extension in the future if needed.
    """

    def __init__(
            self,
            db_adapter: SqliteDatabaseAdapter,
            embedding_adapter: EmbeddingsAdapter):
        self.db_adapter = db_adapter
        self.embedding_adapter = embedding_adapter

    async def search(
            self,
            user_id: UUID,
            query: str,
            query_context: str,
            k: int,
            importance_threshold: int | None,
            project_ids: List[int] | None,
            exclude_ids: List[int] | None,
    ) -> List[Memory]:
        """
        Performs four stage memory retrieval
        1 -> performs a dense search for a list of candidate memories based on the query
        2 -> performs a sparse search for a list of candidate memories based on the query
        3 -> combines the candidates and provides a final list using reciprocal ranked fusion
        4 -> uses a cross encoder to score the list of final candidates based on the query
             AND the query context and returns the top k

        Args:
            user_id: user id for isolation
            query: the search term to perform the dense and spare searches
            query_context: the context in which the memories are being asked (used in cross encoder ranking)
            k: the number of memories to return
            importance_threshold: optional filter to only retrieve memories of a given importance or above
            project_ids: optional list filter to only retrieve memories that belong to certain projects
            exclude_ids: optional list of memory ids to exclude from the search

        Returns:
            List of Memories objects
        """

        candidates_to_return = k  # TODO: for now set to k, but once cross encoding enabled switch to settings

        dense_candidates = await self.semantic_search(
            user_id=user_id,
            query=query,
            k=candidates_to_return,
            importance_threshold=importance_threshold,
            project_ids=project_ids,
            exclude_ids=exclude_ids
        )

        return dense_candidates

    async def semantic_search(
            self,
            user_id: UUID,
            query: str,
            k: int,
            importance_threshold: int | None,
            project_ids: List[int] | None,
            exclude_ids: List[int] | None,
    ) -> List[Memory]:
        """
        Perform semantic search using vector similarity (computed in Python)

        Args:
            user_id: User ID (for isolation)
            query: query to generate embeddings from
            k: Number of results to return
            importance_threshold: Minimum importance score
            project_ids: Filter by project IDs (if provided)
            exclude_ids: Memory IDs to exclude from results

        Returns:
            List of Memory objects ordered by similarity
        """
        query_text = query.strip()
        query_embeddings = await self._generate_embeddings(query_text)

        # Build base query with filters
        stmt = (
            select(MemoryTable)
            .options(
                selectinload(MemoryTable.linked_memories),
                selectinload(MemoryTable.linking_memories),
                selectinload(MemoryTable.projects),
                selectinload(MemoryTable.code_artifacts),
                selectinload(MemoryTable.documents),
            )
            .where(
                MemoryTable.user_id == str(user_id),
                MemoryTable.is_obsolete.is_(False)
            )
        )

        # Apply filters first to reduce vector comparisons
        if importance_threshold:
            stmt = stmt.where(MemoryTable.importance >= importance_threshold)

        if project_ids:
            # Use exists() with subquery to avoid DISTINCT+ORDER BY issues
            project_filter = select(memory_project_association.c.memory_id).where(
                memory_project_association.c.memory_id == MemoryTable.id,
                memory_project_association.c.project_id.in_(project_ids)
            ).exists()
            stmt = stmt.where(project_filter)

        if exclude_ids:
            stmt = stmt.where(MemoryTable.id.not_in(exclude_ids))

        # Fetch all candidates (vector similarity will be computed in Python)
        async with self.db_adapter.session(user_id) as session:
            result = await session.execute(stmt)
            memories_orm = result.scalars().all()

            # Compute similarity scores for each memory
            memory_scores = []
            for memory_orm in memories_orm:
                # Deserialize embedding from JSON string
                memory_embedding = json.loads(memory_orm.embedding)
                similarity = cosine_similarity(query_embeddings, memory_embedding)
                memory_scores.append((similarity, memory_orm))

            # Sort by similarity (highest first) and take top k
            memory_scores.sort(key=lambda x: x[0], reverse=True)
            top_memories = [memory for _, memory in memory_scores[:k]]

            return [Memory.model_validate(memory) for memory in top_memories]

    async def create_memory(self, user_id: UUID, memory: MemoryCreate) -> Memory:
        """
        Create a new memory in SQLite

        Args:
            user_id: User ID,
            memory: MemoryCreate object containing the data for the memory that is
                    to be created

        Returns:
            Created Memory Object
        """

        embeddings_text = build_embedding_text(memory_data=memory)
        embeddings = await self._generate_embeddings(text=embeddings_text)

        # Serialize embedding as JSON for SQLite storage
        embeddings_json = json.dumps(embeddings)

        async with self.db_adapter.session(user_id) as session:
            memory_data = memory.model_dump(exclude={"project_ids", "code_artifact_ids", "document_ids"})
            new_memory = MemoryTable(**memory_data, user_id=str(user_id), embedding=embeddings_json)
            session.add(new_memory)
            await session.flush()

            if memory.project_ids:
                await self._link_projects(session, new_memory, memory.project_ids, user_id)
            if memory.code_artifact_ids:
                await self._link_code_artifacts(session, new_memory, memory.code_artifact_ids, user_id)
            if memory.document_ids:
                await self._link_documents(session, new_memory, memory.document_ids, user_id)

            # Re-query with selectinload to ensure all relationships are properly loaded
            stmt = (
                select(MemoryTable)
                .where(MemoryTable.id == new_memory.id)
                .options(
                    selectinload(MemoryTable.projects),
                    selectinload(MemoryTable.code_artifacts),
                    selectinload(MemoryTable.documents),
                    selectinload(MemoryTable.linked_memories),
                    selectinload(MemoryTable.linking_memories)
                )
            )
            result = await session.execute(stmt)
            new_memory = result.scalar_one()

            return Memory.model_validate(new_memory)

    async def update_memory(
            self,
            user_id: UUID,
            memory_id: int,
            updated_memory: MemoryUpdate,
            existing_memory: Memory,
            search_fields_changed: bool
    ) -> Memory:
        """
        Update a memory

        Args:
            user_id: User ID
            memory_id: Memory ID
            updated_memory: MemoryUpdate object containing the changes to be applied
            existing_memory: Existing memory object
            search_fields_changed: Whether embedding needs regeneration

        Returns:
            Updated Memory object

        Raises:
            NotFoundError: If memory not found
        """
        async with self.db_adapter.session(user_id) as session:

            update_data = updated_memory.model_dump(
                exclude_unset=True,
                exclude={"project_ids", "code_artifact_ids", "document_ids"}
            )

            update_data['updated_at'] = datetime.now(timezone.utc)

            if search_fields_changed:
                merged_memory = existing_memory.model_copy(update=update_data)
                embedding_text = build_embedding_text(memory_data=merged_memory)
                embeddings = await self._generate_embeddings(embedding_text)
                # Serialize for SQLite
                update_data["embedding"] = json.dumps(embeddings)

            stmt = (
                update(MemoryTable)
                .where(MemoryTable.user_id == str(user_id), MemoryTable.id == memory_id)
                .values(**update_data)
                .returning(MemoryTable)
            )

            try:
                result = await session.execute(stmt)
                memory_orm = result.scalar_one()

                # Handle relationship updates if provided
                if updated_memory.project_ids is not None:
                    await session.refresh(memory_orm, attribute_names=['id', 'projects'])
                    memory_orm.projects.clear()
                    if updated_memory.project_ids:
                        await self._link_projects(session, memory_orm, updated_memory.project_ids, user_id)

                if updated_memory.code_artifact_ids is not None:
                    await session.refresh(memory_orm, attribute_names=['id', 'code_artifacts'])
                    memory_orm.code_artifacts.clear()
                    if updated_memory.code_artifact_ids:
                        await self._link_code_artifacts(session, memory_orm, updated_memory.code_artifact_ids, user_id)

                if updated_memory.document_ids is not None:
                    await session.refresh(memory_orm, attribute_names=['id', 'documents'])
                    memory_orm.documents.clear()
                    if updated_memory.document_ids:
                        await self._link_documents(session, memory_orm, updated_memory.document_ids, user_id)

                # Re-query with selectinload to ensure all relationships are properly loaded
                stmt = (
                    select(MemoryTable)
                    .where(MemoryTable.id == memory_id)
                    .options(
                        selectinload(MemoryTable.projects),
                        selectinload(MemoryTable.code_artifacts),
                        selectinload(MemoryTable.documents),
                        selectinload(MemoryTable.linked_memories),
                        selectinload(MemoryTable.linking_memories)
                    )
                )
                result = await session.execute(stmt)
                memory_orm = result.scalar_one()

                return Memory.model_validate(memory_orm)

            except NoResultFound:
                raise NotFoundError(f"Memory with id {memory_id} not found")

    async def get_memory_by_id(self, user_id: UUID, memory_id: int) -> Memory:
        """
        Retrieves memory by ID

        Args:
            user_id: User ID
            memory_id: Id of the memory to be returned

        Returns:
            Memory object or None if not found
        """
        memory_orm = await self.get_memory_table_by_id(user_id=user_id, memory_id=memory_id)

        if memory_orm:
            return Memory.model_validate(memory_orm)
        else:
            raise NotFoundError(f"Memory with id {memory_id} not found")

    async def get_memory_table_by_id(self, user_id: UUID, memory_id: int) -> MemoryTable:
        """
        Retrieves memory by ID

        Args:
            user_id: User ID
            memory_id: Id of the memory to be returned

        Returns:
            Memory Table object or None if not found
        """
        stmt = (
            select(MemoryTable)
            .where(MemoryTable.user_id == str(user_id), MemoryTable.id == memory_id)
            .options(
                selectinload(MemoryTable.projects),
                selectinload(MemoryTable.linked_memories),
                selectinload(MemoryTable.linking_memories),
                selectinload(MemoryTable.code_artifacts),
                selectinload(MemoryTable.documents),
            )
        )

        async with self.db_adapter.session(user_id) as session:
            result = await session.execute(stmt)
            memory_orm = result.scalar_one_or_none()

            if memory_orm:
                return memory_orm
            else:
                raise NotFoundError(f"Memory with id {memory_id} not found")

    async def mark_obsolete(
            self,
            user_id: UUID,
            memory_id: int,
            reason: str,
            superseded_by: int | None = None
    ) -> bool:
        """
        Mark a memory as obsolete (soft delete)

        Args:
            user_id: User ID
            memory_id: Memory ID to mark as obsolete
            reason: Why the memory is being made obsolete
            superseded_by: ID of the new memory that supersedes this one (optional)

        Returns:
            True if successfully marked obsolete

        Raises:
            NotFoundError: If memory not found or doesn't belong to user
            NotFoundError: If superseded_by memory not found or doesn't belong to user
        """
        async with self.db_adapter.session(user_id) as session:
            if superseded_by:
                superseding_stmt = select(MemoryTable).where(
                    MemoryTable.user_id == str(user_id),
                    MemoryTable.id == superseded_by
                )
                superseding_result = await session.execute(superseding_stmt)
                if not superseding_result.scalar_one_or_none():
                    raise NotFoundError(f"Superseding memory {superseded_by} not found")

            stmt = (
                update(MemoryTable)
                .where(
                    MemoryTable.user_id == str(user_id),
                    MemoryTable.id == memory_id
                )
                .values(
                    is_obsolete=True,
                    obsolete_reason=reason,
                    superseded_by=superseded_by,
                    obsoleted_at=datetime.now(timezone.utc)
                )
                .returning(MemoryTable)
            )

            result = await session.execute(stmt)
            obsoleted_memory = result.scalar_one_or_none()

            if not obsoleted_memory:
                raise NotFoundError(f"Memory {memory_id} not found")

            return True

    async def find_similar_memories(
            self,
            user_id: UUID,
            memory_id: int,
            max_links: int
    ) -> List[Memory]:
        """
        Finds similar memories for a given memory

        Args:
            user_id: User ID
            memory_id: Memory ID to find similar memories for
            max_links: Maximum number of similar memories to find
        """

        memory_orm = await self.get_memory_table_by_id(user_id=user_id, memory_id=memory_id)
        memory_embedding = json.loads(memory_orm.embedding)

        stmt = (
            select(MemoryTable)
            .options(
                selectinload(MemoryTable.linked_memories),
                selectinload(MemoryTable.linking_memories),
                selectinload(MemoryTable.projects),
                selectinload(MemoryTable.code_artifacts),
                selectinload(MemoryTable.documents),
            )
            .where(
                MemoryTable.user_id == str(user_id),
                MemoryTable.is_obsolete.is_(False),
                MemoryTable.id != memory_id,
            )
        )

        async with self.db_adapter.session(user_id) as session:
            result = await session.execute(stmt)
            candidates = result.scalars().all()

            # Compute similarity scores
            memory_scores = []
            for candidate in candidates:
                candidate_embedding = json.loads(candidate.embedding)
                similarity = cosine_similarity(memory_embedding, candidate_embedding)
                memory_scores.append((similarity, candidate))

            # Sort by similarity and take top max_links
            memory_scores.sort(key=lambda x: x[0], reverse=True)
            top_memories = [memory for _, memory in memory_scores[:max_links]]

            return [Memory.model_validate(memory) for memory in top_memories]

    async def get_linked_memories(
            self,
            user_id: UUID,
            memory_id: int,
            project_ids: List[int] | None,
            max_links: int = 5,
    ) -> List[Memory]:
        """
        Get memories linked to a specific memory (1-hop neighbors)

        Args:
            user_id: User ID,
            memory_id: Memory ID of the memory to retrieve linked memories for
            max_links: Maximum number of linked memories to return
            project_ids: Optional to filter linked memories for projects

        Returns:
            List of linked Memory objects
        """

        stmt = (
            select(MemoryTable)
            .join(
                MemoryLinkTable,
                or_(
                    (MemoryLinkTable.source_id == memory_id) & (MemoryLinkTable.target_id == MemoryTable.id),
                    (MemoryLinkTable.target_id == memory_id) & (MemoryLinkTable.source_id == MemoryTable.id)
                )
            )
            .options(
                selectinload(MemoryTable.projects),
                selectinload(MemoryTable.linked_memories),
                selectinload(MemoryTable.linking_memories),
                selectinload(MemoryTable.code_artifacts),
                selectinload(MemoryTable.documents),
            )
            .where(MemoryTable.user_id == str(user_id), MemoryTable.id != memory_id, MemoryTable.is_obsolete.is_(False))
        )

        if project_ids:
            stmt = stmt.join(MemoryTable.projects).where(
                ProjectsTable.id.in_(project_ids)
            ).distinct()

        stmt = stmt.order_by(MemoryTable.importance.desc()).limit(max_links)

        async with self.db_adapter.session(user_id=user_id) as session:
            try:
                result = await session.execute(stmt)
                memories_orm = result.scalars().all()
                return [Memory.model_validate(memory) for memory in memories_orm]

            except NoResultFound:
                raise NotFoundError(f"No linked memories retrieved for {memory_id}")

    async def create_link(
            self,
            user_id: UUID,
            source_id: int,
            target_id: int,
    ) -> MemoryLinkTable:
        """
        Creates a bidirectional link between two memories

        Args:
            user_id: User ID,
            source_id: Source memory ID
            target_id: Target memory ID

        Returns:
            Memory Link ORM

        Raises:
            NotFoundError: If source or target memory not found
            IntegrityError: If link already exists
        """
        async with self.db_adapter.session(user_id) as session:
            # Query both memories within the same session
            source_memory = await session.get(MemoryTable, source_id)
            if not source_memory:
                raise NotFoundError(f"Source memory with id {source_id} not found")

            target_memory = await session.get(MemoryTable, target_id)
            if not target_memory:
                raise NotFoundError(f"Target memory with id {target_id} not found")

            # Swap IDs if needed to ensure no duplicates
            link_source_id = source_id
            link_target_id = target_id
            if source_id > target_id:
                link_source_id, link_target_id = target_id, source_id

            logger.info("Creating memory link", extra={
                "user_id": user_id,
                "source_id": link_source_id,
                "target_id": link_target_id,
            })

            link = MemoryLinkTable(
                source_id=link_source_id,
                target_id=link_target_id,
                user_id=str(user_id)
            )

            session.add(link)
            try:
                await session.flush()
                await session.refresh(link)
                logger.info("Created link between memories", extra={
                    "user_id": user_id,
                    "source_id": link_source_id,
                    "target_id": link_target_id}
                )
                return link
            except IntegrityError:
                logger.warning("Memory link already existed", extra={
                    "user_id": user_id,
                    "source_id": link_source_id,
                    "target_id": link_target_id,
                })
                await session.rollback()
                raise

    async def create_links_batch(
            self,
            user_id: UUID,
            source_id: int,
            target_ids: List[int]
    ) -> List[int]:
        """
        Create multiple links from one memory to many others

        Args:
            user_id: User ID
            source_id: Source memory ID
            target_ids: List of target memories IDs to link the source memory to

        Returns:
           List of Memory ID's that the memory has been linked with
        """
        if not target_ids:
            return []

        links_created = []

        for target_id in target_ids:
            if source_id == target_id:
                continue
            try:
                await self.create_link(
                    user_id=user_id,
                    source_id=source_id,
                    target_id=target_id
                )
                links_created.append(target_id)
            except (IntegrityError, NotFoundError):
                # Skip duplicates and invalid target IDs
                continue

        logger.info("Memory links created", extra={
            "user_id": user_id,
            "source_id": source_id,
            "links_created": links_created
        })

        return links_created

    async def _link_projects(
            self,
            session,
            memory: MemoryTable,
            project_ids: List[int],
            user_id: UUID
    ) -> None:
        """Link memory to projects"""
        stmt = select(ProjectsTable).where(
            ProjectsTable.id.in_(project_ids),
            ProjectsTable.user_id == str(user_id)
        )
        result = await session.execute(stmt)
        projects = result.scalars().all()

        found_ids = {p.id for p in projects}
        missing_ids = set(project_ids) - found_ids
        if missing_ids:
            raise NotFoundError(f"Projects not found: {missing_ids}")

        await session.run_sync(lambda sync_session: memory.projects.extend(projects))

    async def _link_code_artifacts(
            self,
            session,
            memory: MemoryTable,
            code_artifact_ids: List[int],
            user_id: UUID
    ) -> None:
        """Link memory to code artifacts"""
        stmt = select(CodeArtifactsTable).where(
            CodeArtifactsTable.id.in_(code_artifact_ids),
            CodeArtifactsTable.user_id == str(user_id)
        )
        result = await session.execute(stmt)
        artifacts = result.scalars().all()

        found_ids = {a.id for a in artifacts}
        missing_ids = set(code_artifact_ids) - found_ids
        if missing_ids:
            raise NotFoundError(f"Code artifacts not found: {missing_ids}")

        await session.run_sync(lambda sync_session: memory.code_artifacts.extend(artifacts))

    async def _link_documents(
            self,
            session,
            memory: MemoryTable,
            document_ids: List[int],
            user_id: UUID
    ) -> None:
        """Link memory to documents"""
        stmt = select(DocumentsTable).where(
            DocumentsTable.id.in_(document_ids),
            DocumentsTable.user_id == str(user_id)
        )
        result = await session.execute(stmt)
        documents = result.scalars().all()

        found_ids = {d.id for d in documents}
        missing_ids = set(document_ids) - found_ids
        if missing_ids:
            raise NotFoundError(f"Documents not found: {missing_ids}")

        await session.run_sync(lambda sync_session: memory.documents.extend(documents))

    async def _generate_embeddings(self, text: str) -> List[float]:
        return await self.embedding_adapter.generate_embedding(text=text)
