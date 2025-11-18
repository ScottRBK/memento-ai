"""
Memory repository for postgres data access operations
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, update, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.repositories.postgres.postgres_tables import (
    MemoryTable,
    MemoryLinkTable,
    ProjectsTable,
    CodeArtifactsTable,
    DocumentsTable,
    memory_project_association
)
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.repositories.embeddings.embedding_adapter import EmbeddingsAdapter
from app.repositories.embeddings.reranker_adapter import RerankAdapter
from app.repositories.helpers import build_embedding_text, build_memory_text, build_contextual_query
from app.models.memory_models import Memory, MemoryCreate, MemoryUpdate
from app.exceptions import NotFoundError
from app.config.logging_config import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

class PostgresMemoryRepository:
    """
    Repository for Memory entity operations in Postgres
    """
    
    def __init__(
            self, 
            db_adapter: PostgresDatabaseAdapter,
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
            2 -> performs a sparse search for a list of candiatte memories based on the query
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
            exclude_ids=exclude_ids
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
        Perform semantic search using vector similarity

        Args:
            session: Database session
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
                MemoryTable.user_id==user_id,
                MemoryTable.is_obsolete.is_(False)
            )
        )
        
        # Apply filters first to reduce expensive vector call on all memories unless neccesary
        if importance_threshold:
            stmt = stmt.where(MemoryTable.importance >= importance_threshold)

        if project_ids:
            # Use exists() with subquery to avoid DISTINCT+ORDER BY PostgreSQL error
            project_filter = select(memory_project_association.c.memory_id).where(
                memory_project_association.c.memory_id == MemoryTable.id,
                memory_project_association.c.project_id.in_(project_ids)
            ).exists()
            stmt = stmt.where(project_filter)

        if exclude_ids:
            stmt = stmt.where(MemoryTable.id.not_in(exclude_ids))

        stmt = stmt.order_by(MemoryTable.embedding.cosine_distance(embeddings))
        stmt = stmt.limit(k)

        async with self.db_adapter.session(user_id) as session:
            result = await session.execute(stmt)
            memories_orm = result.scalars().all()
            return [Memory.model_validate(memory) for memory in memories_orm]
        
        
    async def create_memory(self, user_id: UUID, memory: MemoryCreate) -> Memory:
        """
        Create a new memory in postgres 

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
            new_memory = MemoryTable(**memory_data, user_id=user_id, embedding=embeddings)
            session.add(new_memory)
            await session.flush()

            if memory.project_ids:
                await self._link_projects(session, new_memory, memory.project_ids, user_id)
            if memory.code_artifact_ids:
                await self._link_code_artifacts(session, new_memory, memory.code_artifact_ids, user_id)
            if memory.document_ids:
                await self._link_documents(session, new_memory, memory.document_ids, user_id)

            # Re-query with selectinload to ensure all relationships are properly loaded
            # This is the recommended async pattern per SQLAlchemy docs
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
                update_data["embedding"] = embeddings         

            stmt = (
                update(MemoryTable)
                .where(MemoryTable.user_id==user_id, MemoryTable.id==memory_id)
                .values(**update_data)
                .returning(MemoryTable) 
            )
            
            try:
                result = await session.execute(stmt)
                memory_orm = result.scalar_one()

                # Handle relationship updates if provided
                if updated_memory.project_ids is not None:
                    # Load projects relationship for manipulation (must include 'id' for refresh to work)
                    await session.refresh(memory_orm, attribute_names=['id', 'projects'])
                    memory_orm.projects.clear()
                    if updated_memory.project_ids:
                        await self._link_projects(session, memory_orm, updated_memory.project_ids, user_id)

                if updated_memory.code_artifact_ids is not None:
                    # Load code_artifacts relationship for manipulation (must include 'id' for refresh to work)
                    await session.refresh(memory_orm, attribute_names=['id', 'code_artifacts'])
                    memory_orm.code_artifacts.clear()
                    if updated_memory.code_artifact_ids:
                        await self._link_code_artifacts(session, memory_orm, updated_memory.code_artifact_ids, user_id)

                if updated_memory.document_ids is not None:
                    # Load documents relationship for manipulation (must include 'id' for refresh to work)
                    await session.refresh(memory_orm, attribute_names=['id', 'documents'])
                    memory_orm.documents.clear()
                    if updated_memory.document_ids:
                        await self._link_documents(session, memory_orm, updated_memory.document_ids, user_id)

                # Re-query with selectinload to ensure all relationships are properly loaded
                # This is the recommended async pattern per SQLAlchemy docs
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
            .where(MemoryTable.user_id==user_id, MemoryTable.id==memory_id)
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
                    MemoryTable.user_id == user_id,
                    MemoryTable.id == superseded_by
                )
                superseding_result = await session.execute(superseding_stmt)
                if not superseding_result.scalar_one_or_none():
                    raise NotFoundError(f"Superseding memory {superseded_by} not found")
            
            stmt = (
                update(MemoryTable)
                .where(
                    MemoryTable.user_id == user_id,
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
                MemoryTable.user_id==user_id,
                MemoryTable.is_obsolete.is_(False),
                MemoryTable.id!=memory_id,
            )
        )
        stmt = stmt.order_by(MemoryTable.embedding.cosine_distance(memory_orm.embedding))
        stmt = stmt.limit(max_links)

        async with self.db_adapter.session(user_id) as session:
            result = await session.execute(stmt)
            memories_orm = result.scalars().all()
            return [Memory.model_validate(memory) for memory in memories_orm]
        
        
    
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
                    (MemoryLinkTable.source_id==memory_id) & (MemoryLinkTable.target_id==MemoryTable.id),
                    (MemoryLinkTable.target_id==memory_id) & (MemoryLinkTable.source_id==MemoryTable.id)
                )
            )
            .options(
                selectinload(MemoryTable.projects),
                selectinload(MemoryTable.linked_memories),
                selectinload(MemoryTable.linking_memories),
                selectinload(MemoryTable.code_artifacts),
                selectinload(MemoryTable.documents),
            )
            .where(MemoryTable.user_id==user_id, MemoryTable.id!=memory_id, MemoryTable.is_obsolete.is_(False))
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
        # Use a single session for the entire operation to avoid detached object issues
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
                user_id=user_id
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
                # Append the original target_id, not link.target_id
                # (link.target_id may be swapped if source_id > target_id)
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

    async def get_recent_memories(
            self,
            user_id: UUID,
            limit: int,
            project_ids: List[int] | None = None
    ) -> List[Memory]:
        """
        Get most recent memories sorted by creation timestamp

        Args:
            user_id: User ID for ownership filtering
            limit: Maximum number of memories to return
            project_ids: Optional filter to only retrieve memories from specific projects

        Returns:
            List of Memory objects sorted by created_at DESC (newest first)
        """
        stmt = (
            select(MemoryTable)
            .options(
                selectinload(MemoryTable.projects),
                selectinload(MemoryTable.linked_memories),
                selectinload(MemoryTable.code_artifacts),
                selectinload(MemoryTable.documents)
            )
            .where(
                MemoryTable.user_id == user_id,
                MemoryTable.is_obsolete.is_(False)
            )
        )

        # Apply project filter if provided
        if project_ids:
            project_filter = select(memory_project_association.c.memory_id).where(
                memory_project_association.c.memory_id == MemoryTable.id,
                memory_project_association.c.project_id.in_(project_ids)
            ).exists()
            stmt = stmt.where(project_filter)

        # Order by creation date descending and limit results
        stmt = stmt.order_by(MemoryTable.created_at.desc()).limit(limit)

        async with self.db_adapter.session(user_id) as session:
            result = await session.execute(stmt)
            memories = result.scalars().all()

            logger.info("Retrieved recent memories", extra={
                "user_id": user_id,
                "count": len(memories),
                "limit": limit,
                "project_filtered": project_ids is not None
            })

            return [Memory.model_validate(m) for m in memories]

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
            ProjectsTable.user_id == user_id
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
            CodeArtifactsTable.user_id == user_id
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
            DocumentsTable.user_id == user_id
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
    

