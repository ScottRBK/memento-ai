"""
Memory repository for SQLite data access operations with sqlite-vec integration
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
import sqlite_vec

from sqlalchemy import select, update, or_, text
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.repositories.sqlite.sqlite_tables import (
    MemoryTable,
    MemoryLinkTable,
    ProjectsTable,
    CodeArtifactsTable,
    DocumentsTable,
)
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.repositories.embeddings.embedding_adapter import EmbeddingsAdapter
from app.repositories.embeddings.reranker_adapter import RerankAdapter
from app.repositories.helpers import build_embedding_text, build_memory_text, build_contextual_query
from app.config.settings import settings
from app.models.memory_models import Memory, MemoryCreate, MemoryUpdate
from app.exceptions import NotFoundError
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


class SqliteMemoryRepository:
    """
    Repository for Memory entity operations in SQLite with sqlite-vec integration

    Key differences from Postgres:
    - Embeddings stored in separate vec_memories virtual table
    - Vector similarity search uses sqlite-vec's vec_distance_cosine()
    - UUIDs stored as strings
    - No RLS - user isolation via WHERE clauses
    """

    def __init__(
            self,
            db_adapter: SqliteDatabaseAdapter,
            embedding_adapter: EmbeddingsAdapter,
            rerank_adapter: RerankAdapter | None = None,
    ):
        self.db_adapter = db_adapter
        self.embedding_adapter = embedding_adapter
        self.rerank_adapter = rerank_adapter

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
            query: the search term to perform the dense and sparse searches
            query_context: the context in which the memories are being asked (used in cross encoder ranking)
            k: the number of memories to return
            importance_threshold: optional filter to only retrieve memories of a given importance or above
            project_ids: optional list filter to only retrieve memories that belong to certain projects
            exclude_ids: optional list of memory ids to exclude from the search

        Returns:
            List of Memories objects
        """

        if settings.RERANKING_ENABLED:
            candidates_to_return = settings.DENSE_SEARCH_CANDIDATES
        else:
            candidates_to_return = k

        dense_candidates = await self.semantic_search(
            user_id=user_id,
            query=query,
            k=candidates_to_return,
            importance_threshold=importance_threshold,
            project_ids=project_ids,
            exclude_ids=exclude_ids,
        )

        if not dense_candidates or not settings.RERANKING_ENABLED or len(dense_candidates) <= k:
            return dense_candidates

        documents = []
        for memory in dense_candidates:
            memory_text = build_memory_text(memory)
            documents.append(memory_text)

        if query_context:
            rerank_query = build_contextual_query(query=query, context=query_context)
        else:
            rerank_query = query

        scores = await self.rerank_adapter.rerank(query=rerank_query, documents=documents)

        scored_candidates = list(zip(dense_candidates, scores))
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        top_k_memories = [memory for memory, score in scored_candidates[:k]]

        return top_k_memories

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
        Perform semantic search using vector similarity with sqlite-vec

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
        embeddings = await self._generate_embeddings(query_text)

        # Serialize embeddings for sqlite-vec
        embedding_bytes = sqlite_vec.serialize_float32(embeddings)

        # Build the SQL query using sqlite-vec's vec_distance_cosine
        # We need to join with vec_memories virtual table for vector similarity
        async with self.db_adapter.session(user_id) as session:
            # Base query with vector similarity
            sql_parts = [
                """
                SELECT m.id, m.user_id, m.title, m.content, m.context, m.keywords, m.tags,
                       m.importance, m.is_obsolete, m.obsolete_reason, m.superseded_by,
                       m.obsoleted_at, m.created_at, m.updated_at
                FROM memories m
                INNER JOIN vec_memories vm ON m.id = vm.memory_id
                WHERE m.user_id = :user_id AND m.is_obsolete = 0
                """
            ]

            # Build parameters
            params = {"user_id": str(user_id), "query_embedding": embedding_bytes, "k": k}

            # Apply importance filter
            if importance_threshold:
                sql_parts.append(" AND m.importance >= :importance_threshold")
                params["importance_threshold"] = importance_threshold

            # Apply project filter
            if project_ids:
                sql_parts.append(
                    """
                    AND EXISTS (
                        SELECT 1 FROM memory_project_association mpa
                        WHERE mpa.memory_id = m.id
                        AND mpa.project_id IN ({})
                    )
                    """.format(",".join(f":project_{i}" for i in range(len(project_ids))))
                )
                for i, proj_id in enumerate(project_ids):
                    params[f"project_{i}"] = proj_id

            # Apply exclude filter
            if exclude_ids:
                sql_parts.append(
                    " AND m.id NOT IN ({})".format(",".join(f":exclude_{i}" for i in range(len(exclude_ids))))
                )
                for i, excl_id in enumerate(exclude_ids):
                    params[f"exclude_{i}"] = excl_id

            # Add vector similarity ordering and limit
            sql_parts.append(
                """
                ORDER BY vec_distance_cosine(vm.embedding, :query_embedding)
                LIMIT :k
                """
            )

            # Execute raw SQL query
            sql_query = "".join(sql_parts)
            result = await session.execute(text(sql_query), params)
            rows = result.fetchall()

            # Convert rows to Memory IDs, then load via SQLAlchemy with relationships
            if not rows:
                return []

            memory_ids = [row[0] for row in rows]

            # Load full Memory objects with relationships
            stmt = (
                select(MemoryTable)
                .where(MemoryTable.id.in_(memory_ids))
                .options(
                    selectinload(MemoryTable.linked_memories),
                    selectinload(MemoryTable.linking_memories),
                    selectinload(MemoryTable.projects),
                    selectinload(MemoryTable.code_artifacts),
                    selectinload(MemoryTable.documents),
                )
            )

            result = await session.execute(stmt)
            memories_orm = result.scalars().all()

            # Preserve the order from vector similarity search
            memory_dict = {m.id: m for m in memories_orm}
            ordered_memories = [memory_dict[mid] for mid in memory_ids if mid in memory_dict]

            return [Memory.model_validate(memory) for memory in ordered_memories]

    async def create_memory(self, user_id: UUID, memory: MemoryCreate) -> Memory:
        """
        Create a new memory in SQLite with vector storage

        Args:
            user_id: User ID,
            memory: MemoryCreate object containing the data for the memory that is
                    to be created

        Returns:
            Created Memory Object
        """

        embeddings_text = build_embedding_text(memory_data=memory)
        embeddings = await self._generate_embeddings(text=embeddings_text)

        async with self.db_adapter.session(user_id) as session:
            memory_data = memory.model_dump(exclude={"project_ids", "code_artifact_ids", "document_ids"})
            # Note: No embedding column in MemoryTable for SQLite
            new_memory = MemoryTable(**memory_data, user_id=str(user_id))
            session.add(new_memory)
            await session.flush()

            # Store embedding in vec_memories virtual table
            embedding_bytes = sqlite_vec.serialize_float32(embeddings)
            await session.execute(
                text("INSERT INTO vec_memories (memory_id, embedding) VALUES (:memory_id, :embedding)"),
                {"memory_id": str(new_memory.id), "embedding": embedding_bytes},
            )

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
                    selectinload(MemoryTable.linking_memories),
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
        search_fields_changed: bool,
    ) -> Memory:
        """
        Update a memory

        Args:
            user_id: User ID
            memory_id: Memory ID
            updated_memory: MemoryUpdate object containing the changes to be applied
            existing_memory: Existing Memory object
            search_fields_changed: Whether search-relevant fields changed (requires embedding update)

        Returns:
            Updated Memory object

        Raises:
            NotFoundError: If memory not found
        """
        async with self.db_adapter.session(user_id) as session:

            update_data = updated_memory.model_dump(
                exclude_unset=True, exclude={"project_ids", "code_artifact_ids", "document_ids"}
            )

            update_data["updated_at"] = datetime.now(timezone.utc)

            # Update embedding if search fields changed
            if search_fields_changed:
                merged_memory = existing_memory.model_copy(update=update_data)
                embedding_text = build_embedding_text(memory_data=merged_memory)
                embeddings = await self._generate_embeddings(embedding_text)

                # Update vec_memories table
                embedding_bytes = sqlite_vec.serialize_float32(embeddings)
                await session.execute(
                    text("UPDATE vec_memories SET embedding = :embedding WHERE memory_id = :memory_id"),
                    {"embedding": embedding_bytes, "memory_id": str(memory_id)},
                )

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
                    await session.refresh(memory_orm, attribute_names=["id", "projects"])
                    memory_orm.projects.clear()
                    if updated_memory.project_ids:
                        await self._link_projects(session, memory_orm, updated_memory.project_ids, user_id)

                if updated_memory.code_artifact_ids is not None:
                    await session.refresh(memory_orm, attribute_names=["id", "code_artifacts"])
                    memory_orm.code_artifacts.clear()
                    if updated_memory.code_artifact_ids:
                        await self._link_code_artifacts(session, memory_orm, updated_memory.code_artifact_ids, user_id)

                if updated_memory.document_ids is not None:
                    await session.refresh(memory_orm, attribute_names=["id", "documents"])
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
                        selectinload(MemoryTable.linking_memories),
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

    async def mark_obsolete(self, user_id: UUID, memory_id: int, reason: str, superseded_by: int | None = None) -> bool:
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
                    MemoryTable.user_id == str(user_id), MemoryTable.id == superseded_by
                )
                superseding_result = await session.execute(superseding_stmt)
                if not superseding_result.scalar_one_or_none():
                    raise NotFoundError(f"Superseding memory {superseded_by} not found")

            stmt = (
                update(MemoryTable)
                .where(MemoryTable.user_id == str(user_id), MemoryTable.id == memory_id)
                .values(
                    is_obsolete=True,
                    obsolete_reason=reason,
                    superseded_by=superseded_by,
                    obsoleted_at=datetime.now(timezone.utc),
                )
                .returning(MemoryTable)
            )

            result = await session.execute(stmt)
            obsoleted_memory = result.scalar_one_or_none()

            if not obsoleted_memory:
                raise NotFoundError(f"Memory {memory_id} not found")

            return True

    async def find_similar_memories(self, user_id: UUID, memory_id: int, max_links: int) -> List[Memory]:
        """
        Finds similar memories for a given memory using vector similarity

        Args:
            user_id: User ID
            memory_id: Memory ID to find similar memories for
            max_links: Maximum number of similar memories to find
        """

        # Get the source memory's embedding from vec_memories
        async with self.db_adapter.session(user_id) as session:
            # Get the embedding for the source memory
            embedding_result = await session.execute(
                text("SELECT embedding FROM vec_memories WHERE memory_id = :memory_id"),
                {"memory_id": str(memory_id)},
            )
            embedding_row = embedding_result.fetchone()
            if not embedding_row:
                raise NotFoundError(f"Memory {memory_id} not found or has no embedding")

            source_embedding = embedding_row[0]

            # Find similar memories using vector similarity
            sql_query = """
                SELECT m.id
                FROM memories m
                INNER JOIN vec_memories vm ON m.id = vm.memory_id
                WHERE m.user_id = :user_id
                  AND m.is_obsolete = 0
                  AND m.id != :memory_id
                ORDER BY vec_distance_cosine(vm.embedding, :source_embedding)
                LIMIT :max_links
            """

            result = await session.execute(
                text(sql_query),
                {
                    "user_id": str(user_id),
                    "memory_id": memory_id,
                    "source_embedding": source_embedding,
                    "max_links": max_links,
                },
            )
            rows = result.fetchall()
            memory_ids = [row[0] for row in rows]

            if not memory_ids:
                return []

            # Load full Memory objects with relationships
            stmt = (
                select(MemoryTable)
                .where(MemoryTable.id.in_(memory_ids))
                .options(
                    selectinload(MemoryTable.linked_memories),
                    selectinload(MemoryTable.linking_memories),
                    selectinload(MemoryTable.projects),
                    selectinload(MemoryTable.code_artifacts),
                    selectinload(MemoryTable.documents),
                )
            )

            result = await session.execute(stmt)
            memories_orm = result.scalars().all()

            # Preserve order from similarity search
            memory_dict = {m.id: m for m in memories_orm}
            ordered_memories = [memory_dict[mid] for mid in memory_ids if mid in memory_dict]

            return [Memory.model_validate(memory) for memory in ordered_memories]

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
                    (MemoryLinkTable.target_id == memory_id) & (MemoryLinkTable.source_id == MemoryTable.id),
                ),
            )
            .options(
                selectinload(MemoryTable.projects),
                selectinload(MemoryTable.linked_memories),
                selectinload(MemoryTable.linking_memories),
                selectinload(MemoryTable.code_artifacts),
                selectinload(MemoryTable.documents),
            )
            .where(
                MemoryTable.user_id == str(user_id),
                MemoryTable.id != memory_id,
                MemoryTable.is_obsolete.is_(False),
            )
        )

        if project_ids:
            stmt = stmt.join(MemoryTable.projects).where(ProjectsTable.id.in_(project_ids)).distinct()

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

            logger.info(
                "Creating memory link",
                extra={
                    "user_id": str(user_id),
                    "source_id": link_source_id,
                    "target_id": link_target_id,
                },
            )

            link = MemoryLinkTable(source_id=link_source_id, target_id=link_target_id, user_id=str(user_id))

            session.add(link)
            try:
                await session.flush()
                await session.refresh(link)
                logger.info(
                    "Created link between memories",
                    extra={"user_id": str(user_id), "source_id": link_source_id, "target_id": link_target_id},
                )
                return link
            except IntegrityError:
                logger.warning(
                    "Memory link already existed",
                    extra={"user_id": str(user_id), "source_id": link_source_id, "target_id": link_target_id},
                )
                await session.rollback()
                raise

    async def create_links_batch(self, user_id: UUID, source_id: int, target_ids: List[int]) -> List[int]:
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
                await self.create_link(user_id=user_id, source_id=source_id, target_id=target_id)
                links_created.append(target_id)
            except (IntegrityError, NotFoundError):
                # Skip duplicates and invalid target IDs
                continue

        logger.info("Memory links created", extra={"user_id": str(user_id), "source_id": source_id, "links_created": links_created})

        return links_created

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
        from sqlalchemy import delete, or_, and_

        async with self.db_adapter.session(user_id) as session:
            # Delete both directions (source→target and target→source)
            stmt = delete(MemoryLinkTable).where(
                MemoryLinkTable.user_id == str(user_id),
                or_(
                    and_(
                        MemoryLinkTable.source_id == source_id,
                        MemoryLinkTable.target_id == target_id
                    ),
                    and_(
                        MemoryLinkTable.source_id == target_id,
                        MemoryLinkTable.target_id == source_id
                    )
                )
            )
            result = await session.execute(stmt)
            await session.commit()

            deleted = result.rowcount > 0
            logger.info("Memory link removed", extra={
                "user_id": str(user_id),
                "source_id": source_id,
                "target_id": target_id,
                "deleted": deleted
            })

            return deleted

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
            user_id: User ID for ownership filtering
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
        from app.repositories.sqlite.sqlite_tables import memory_project_association

        # Build base query with eager loading
        stmt = (
            select(MemoryTable)
            .options(
                selectinload(MemoryTable.projects),
                selectinload(MemoryTable.linked_memories),
                selectinload(MemoryTable.code_artifacts),
                selectinload(MemoryTable.documents)
            )
            .where(MemoryTable.user_id == str(user_id))
        )

        # Conditional obsolete filter
        if not include_obsolete:
            stmt = stmt.where(MemoryTable.is_obsolete.is_(False))

        # Apply project filter if provided
        if project_ids:
            project_filter = select(memory_project_association.c.memory_id).where(
                memory_project_association.c.memory_id == MemoryTable.id,
                memory_project_association.c.project_id.in_(project_ids)
            ).exists()
            stmt = stmt.where(project_filter)

        # Dynamic sorting
        sort_column_map = {
            "created_at": MemoryTable.created_at,
            "updated_at": MemoryTable.updated_at,
            "importance": MemoryTable.importance
        }
        sort_column = sort_column_map.get(sort_by, MemoryTable.created_at)
        order = sort_column.desc() if sort_order == "desc" else sort_column.asc()
        # Tie-break on id to keep ordering deterministic when timestamps are equal
        id_tiebreak = MemoryTable.id.desc() if sort_order == "desc" else MemoryTable.id.asc()
        stmt = stmt.order_by(order, id_tiebreak)

        async with self.db_adapter.session(user_id) as session:
            # Execute main query
            result = await session.execute(stmt)
            all_memories = result.scalars().all()

            # Tag filtering in Python (SQLite JSON doesn't support efficient array overlap)
            if tags:
                tag_set = set(tags)
                all_memories = [
                    m for m in all_memories
                    if m.tags and tag_set.intersection(m.tags)
                ]

            # Get total count before pagination
            total = len(all_memories)

            # Apply pagination
            paginated_memories = all_memories[offset:offset + limit]

            logger.info("Retrieved recent memories", extra={
                "user_id": str(user_id),
                "count": len(paginated_memories),
                "total": total,
                "limit": limit,
                "offset": offset,
                "project_filtered": project_ids is not None,
                "include_obsolete": include_obsolete,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "tags_filter": tags
            })

            return [Memory.model_validate(m) for m in paginated_memories], total

    async def _link_projects(self, session, memory: MemoryTable, project_ids: List[int], user_id: UUID) -> None:
        """Link memory to projects"""
        stmt = select(ProjectsTable).where(
            ProjectsTable.id.in_(project_ids), ProjectsTable.user_id == str(user_id)
        )
        result = await session.execute(stmt)
        projects = result.scalars().all()

        found_ids = {p.id for p in projects}
        missing_ids = set(project_ids) - found_ids
        if missing_ids:
            raise NotFoundError(f"Projects not found: {missing_ids}")

        await session.run_sync(lambda sync_session: memory.projects.extend(projects))

    async def _link_code_artifacts(self, session, memory: MemoryTable, code_artifact_ids: List[int], user_id: UUID) -> None:
        """Link memory to code artifacts"""
        stmt = select(CodeArtifactsTable).where(
            CodeArtifactsTable.id.in_(code_artifact_ids), CodeArtifactsTable.user_id == str(user_id)
        )
        result = await session.execute(stmt)
        artifacts = result.scalars().all()

        found_ids = {a.id for a in artifacts}
        missing_ids = set(code_artifact_ids) - found_ids
        if missing_ids:
            raise NotFoundError(f"Code artifacts not found: {missing_ids}")

        await session.run_sync(lambda sync_session: memory.code_artifacts.extend(artifacts))

    async def _link_documents(self, session, memory: MemoryTable, document_ids: List[int], user_id: UUID) -> None:
        """Link memory to documents"""
        stmt = select(DocumentsTable).where(
            DocumentsTable.id.in_(document_ids), DocumentsTable.user_id == str(user_id)
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
        # Build the recursive CTE query
        # Each UNION ALL branch handles one edge type
        query = text("""
            WITH RECURSIVE graph_traverse(node_id, node_type, depth, path) AS (
                -- Anchor: the center node
                SELECT
                    :center_id AS node_id,
                    :center_type AS node_type,
                    0 AS depth,
                    :center_type || '_' || CAST(:center_id AS TEXT) AS path

                UNION ALL

                -- Memory -> Memory via memory_links
                SELECT
                    CASE WHEN ml.source_id = gt.node_id THEN ml.target_id ELSE ml.source_id END,
                    'memory',
                    gt.depth + 1,
                    gt.path || ',' || 'memory_' || CAST(CASE WHEN ml.source_id = gt.node_id THEN ml.target_id ELSE ml.source_id END AS TEXT)
                FROM graph_traverse gt
                INNER JOIN memory_links ml ON (
                    gt.node_type = 'memory'
                    AND (ml.source_id = gt.node_id OR ml.target_id = gt.node_id)
                    AND ml.user_id = :user_id
                )
                INNER JOIN memories m ON m.id = CASE WHEN ml.source_id = gt.node_id THEN ml.target_id ELSE ml.source_id END
                WHERE gt.depth < :max_depth
                  AND m.user_id = :user_id
                  AND m.is_obsolete = 0
                  AND :include_memories = 1
                  AND instr(gt.path, 'memory_' || CAST(CASE WHEN ml.source_id = gt.node_id THEN ml.target_id ELSE ml.source_id END AS TEXT)) = 0

                UNION ALL

                -- Memory -> Entity via memory_entity_association
                SELECT
                    mea.entity_id,
                    'entity',
                    gt.depth + 1,
                    gt.path || ',' || 'entity_' || CAST(mea.entity_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN memory_entity_association mea ON (
                    gt.node_type = 'memory'
                    AND mea.memory_id = gt.node_id
                )
                INNER JOIN entities e ON e.id = mea.entity_id
                WHERE gt.depth < :max_depth
                  AND e.user_id = :user_id
                  AND :include_entities = 1
                  AND instr(gt.path, 'entity_' || CAST(mea.entity_id AS TEXT)) = 0

                UNION ALL

                -- Entity -> Memory via memory_entity_association
                SELECT
                    mea.memory_id,
                    'memory',
                    gt.depth + 1,
                    gt.path || ',' || 'memory_' || CAST(mea.memory_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN memory_entity_association mea ON (
                    gt.node_type = 'entity'
                    AND mea.entity_id = gt.node_id
                )
                INNER JOIN memories m ON m.id = mea.memory_id
                WHERE gt.depth < :max_depth
                  AND m.user_id = :user_id
                  AND m.is_obsolete = 0
                  AND :include_memories = 1
                  AND instr(gt.path, 'memory_' || CAST(mea.memory_id AS TEXT)) = 0

                UNION ALL

                -- Entity -> Entity via entity_relationships
                SELECT
                    CASE WHEN er.source_entity_id = gt.node_id THEN er.target_entity_id ELSE er.source_entity_id END,
                    'entity',
                    gt.depth + 1,
                    gt.path || ',' || 'entity_' || CAST(CASE WHEN er.source_entity_id = gt.node_id THEN er.target_entity_id ELSE er.source_entity_id END AS TEXT)
                FROM graph_traverse gt
                INNER JOIN entity_relationships er ON (
                    gt.node_type = 'entity'
                    AND (er.source_entity_id = gt.node_id OR er.target_entity_id = gt.node_id)
                    AND er.user_id = :user_id
                )
                INNER JOIN entities e ON e.id = CASE WHEN er.source_entity_id = gt.node_id THEN er.target_entity_id ELSE er.source_entity_id END
                WHERE gt.depth < :max_depth
                  AND e.user_id = :user_id
                  AND :include_entities = 1
                  AND instr(gt.path, 'entity_' || CAST(CASE WHEN er.source_entity_id = gt.node_id THEN er.target_entity_id ELSE er.source_entity_id END AS TEXT)) = 0

                UNION ALL

                -- Memory -> Project via memory_project_association
                SELECT
                    mpa.project_id,
                    'project',
                    gt.depth + 1,
                    gt.path || ',' || 'project_' || CAST(mpa.project_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN memory_project_association mpa ON (
                    gt.node_type = 'memory'
                    AND mpa.memory_id = gt.node_id
                )
                INNER JOIN projects p ON p.id = mpa.project_id
                WHERE gt.depth < :max_depth
                  AND p.user_id = :user_id
                  AND :include_projects = 1
                  AND instr(gt.path, 'project_' || CAST(mpa.project_id AS TEXT)) = 0

                UNION ALL

                -- Project -> Memory via memory_project_association
                SELECT
                    mpa.memory_id,
                    'memory',
                    gt.depth + 1,
                    gt.path || ',' || 'memory_' || CAST(mpa.memory_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN memory_project_association mpa ON (
                    gt.node_type = 'project'
                    AND mpa.project_id = gt.node_id
                )
                INNER JOIN memories m ON m.id = mpa.memory_id
                WHERE gt.depth < :max_depth
                  AND m.user_id = :user_id
                  AND m.is_obsolete = 0
                  AND :include_memories = 1
                  AND instr(gt.path, 'memory_' || CAST(mpa.memory_id AS TEXT)) = 0

                UNION ALL

                -- Memory -> Document via memory_document_association
                SELECT
                    mda.document_id,
                    'document',
                    gt.depth + 1,
                    gt.path || ',' || 'document_' || CAST(mda.document_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN memory_document_association mda ON (
                    gt.node_type = 'memory'
                    AND mda.memory_id = gt.node_id
                )
                INNER JOIN documents d ON d.id = mda.document_id
                WHERE gt.depth < :max_depth
                  AND d.user_id = :user_id
                  AND :include_documents = 1
                  AND instr(gt.path, 'document_' || CAST(mda.document_id AS TEXT)) = 0

                UNION ALL

                -- Document -> Memory via memory_document_association
                SELECT
                    mda.memory_id,
                    'memory',
                    gt.depth + 1,
                    gt.path || ',' || 'memory_' || CAST(mda.memory_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN memory_document_association mda ON (
                    gt.node_type = 'document'
                    AND mda.document_id = gt.node_id
                )
                INNER JOIN memories m ON m.id = mda.memory_id
                WHERE gt.depth < :max_depth
                  AND m.user_id = :user_id
                  AND m.is_obsolete = 0
                  AND :include_memories = 1
                  AND instr(gt.path, 'memory_' || CAST(mda.memory_id AS TEXT)) = 0

                UNION ALL

                -- Memory -> CodeArtifact via memory_code_artifact_association
                SELECT
                    mca.code_artifact_id,
                    'code_artifact',
                    gt.depth + 1,
                    gt.path || ',' || 'code_artifact_' || CAST(mca.code_artifact_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN memory_code_artifact_association mca ON (
                    gt.node_type = 'memory'
                    AND mca.memory_id = gt.node_id
                )
                INNER JOIN code_artifacts ca ON ca.id = mca.code_artifact_id
                WHERE gt.depth < :max_depth
                  AND ca.user_id = :user_id
                  AND :include_code_artifacts = 1
                  AND instr(gt.path, 'code_artifact_' || CAST(mca.code_artifact_id AS TEXT)) = 0

                UNION ALL

                -- CodeArtifact -> Memory via memory_code_artifact_association
                SELECT
                    mca.memory_id,
                    'memory',
                    gt.depth + 1,
                    gt.path || ',' || 'memory_' || CAST(mca.memory_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN memory_code_artifact_association mca ON (
                    gt.node_type = 'code_artifact'
                    AND mca.code_artifact_id = gt.node_id
                )
                INNER JOIN memories m ON m.id = mca.memory_id
                WHERE gt.depth < :max_depth
                  AND m.user_id = :user_id
                  AND m.is_obsolete = 0
                  AND :include_memories = 1
                  AND instr(gt.path, 'memory_' || CAST(mca.memory_id AS TEXT)) = 0

                UNION ALL

                -- Document -> Project via documents.project_id FK
                SELECT
                    d.project_id,
                    'project',
                    gt.depth + 1,
                    gt.path || ',' || 'project_' || CAST(d.project_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN documents d ON (
                    gt.node_type = 'document'
                    AND d.id = gt.node_id
                    AND d.project_id IS NOT NULL
                )
                INNER JOIN projects p ON p.id = d.project_id
                WHERE gt.depth < :max_depth
                  AND p.user_id = :user_id
                  AND :include_projects = 1
                  AND instr(gt.path, 'project_' || CAST(d.project_id AS TEXT)) = 0

                UNION ALL

                -- Project -> Document via documents.project_id FK
                SELECT
                    d.id,
                    'document',
                    gt.depth + 1,
                    gt.path || ',' || 'document_' || CAST(d.id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN documents d ON (
                    gt.node_type = 'project'
                    AND d.project_id = gt.node_id
                )
                WHERE gt.depth < :max_depth
                  AND d.user_id = :user_id
                  AND :include_documents = 1
                  AND instr(gt.path, 'document_' || CAST(d.id AS TEXT)) = 0

                UNION ALL

                -- CodeArtifact -> Project via code_artifacts.project_id FK
                SELECT
                    ca.project_id,
                    'project',
                    gt.depth + 1,
                    gt.path || ',' || 'project_' || CAST(ca.project_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN code_artifacts ca ON (
                    gt.node_type = 'code_artifact'
                    AND ca.id = gt.node_id
                    AND ca.project_id IS NOT NULL
                )
                INNER JOIN projects p ON p.id = ca.project_id
                WHERE gt.depth < :max_depth
                  AND p.user_id = :user_id
                  AND :include_projects = 1
                  AND instr(gt.path, 'project_' || CAST(ca.project_id AS TEXT)) = 0

                UNION ALL

                -- Project -> CodeArtifact via code_artifacts.project_id FK
                SELECT
                    ca.id,
                    'code_artifact',
                    gt.depth + 1,
                    gt.path || ',' || 'code_artifact_' || CAST(ca.id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN code_artifacts ca ON (
                    gt.node_type = 'project'
                    AND ca.project_id = gt.node_id
                )
                WHERE gt.depth < :max_depth
                  AND ca.user_id = :user_id
                  AND :include_code_artifacts = 1
                  AND instr(gt.path, 'code_artifact_' || CAST(ca.id AS TEXT)) = 0

                UNION ALL

                -- Entity -> Project via entity_project_association
                SELECT
                    epa.project_id,
                    'project',
                    gt.depth + 1,
                    gt.path || ',' || 'project_' || CAST(epa.project_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN entity_project_association epa ON (
                    gt.node_type = 'entity'
                    AND epa.entity_id = gt.node_id
                )
                INNER JOIN projects p ON p.id = epa.project_id
                WHERE gt.depth < :max_depth
                  AND p.user_id = :user_id
                  AND :include_entities = 1
                  AND :include_projects = 1
                  AND instr(gt.path, 'project_' || CAST(epa.project_id AS TEXT)) = 0

                UNION ALL

                -- Project -> Entity via entity_project_association
                SELECT
                    epa.entity_id,
                    'entity',
                    gt.depth + 1,
                    gt.path || ',' || 'entity_' || CAST(epa.entity_id AS TEXT)
                FROM graph_traverse gt
                INNER JOIN entity_project_association epa ON (
                    gt.node_type = 'project'
                    AND epa.project_id = gt.node_id
                )
                INNER JOIN entities e ON e.id = epa.entity_id
                WHERE gt.depth < :max_depth
                  AND e.user_id = :user_id
                  AND :include_entities = 1
                  AND :include_projects = 1
                  AND instr(gt.path, 'entity_' || CAST(epa.entity_id AS TEXT)) = 0
            )
            SELECT node_id, node_type, MIN(depth) as depth
            FROM graph_traverse
            GROUP BY node_id, node_type
            ORDER BY depth, node_type, node_id
            LIMIT :limit_plus_one
        """)

        params = {
            "center_id": center_id,
            "center_type": center_type,
            "user_id": str(user_id),
            "max_depth": depth,
            "include_memories": 1 if include_memories else 0,
            "include_entities": 1 if include_entities else 0,
            "include_projects": 1 if include_projects else 0,
            "include_documents": 1 if include_documents else 0,
            "include_code_artifacts": 1 if include_code_artifacts else 0,
            "limit_plus_one": max_nodes + 1,  # +1 to detect truncation
        }

        async with self.db_adapter.session(user_id=user_id) as session:
            result = await session.execute(query, params)
            rows = result.fetchall()

            # Check if we hit the limit (truncated)
            truncated = len(rows) > max_nodes
            if truncated:
                rows = rows[:max_nodes]

            nodes = [
                {
                    "node_id": row.node_id,
                    "node_type": row.node_type,
                    "depth": row.depth,
                }
                for row in rows
            ]

            logger.info("Subgraph traversal completed", extra={
                "user_id": str(user_id),
                "center_type": center_type,
                "center_id": center_id,
                "depth": depth,
                "nodes_found": len(nodes),
                "truncated": truncated,
            })

            return nodes, truncated
