"""
Tool Adapters - Bridge between services and tool registry

This module provides adapter classes that wrap service methods as registry-compatible
callables, ensuring user context is properly extracted and preserved.
"""
from typing import Dict, Any, List, Optional
from fastmcp import Context

from app.services.user_service import UserService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService
from app.services.code_artifact_service import CodeArtifactService
from app.services.document_service import DocumentService
from app.services.entity_service import EntityService
from app.middleware.auth import get_user_from_auth
from app.models.user_models import UserUpdate, UserResponse
from app.models.memory_models import (
    MemoryCreate,
    MemoryCreateResponse,
    MemoryUpdate,
    MemoryQueryRequest,
    MemoryQueryResult,
    Memory,
)
from app.models.project_models import Project, ProjectCreate, ProjectUpdate, ProjectStatus, ProjectType
from app.models.code_artifact_models import CodeArtifact, CodeArtifactCreate, CodeArtifactUpdate
from app.models.document_models import Document, DocumentCreate, DocumentUpdate
from app.models.entity_models import (
    Entity,
    EntityCreate,
    EntityUpdate,
    EntityRelationship,
    EntityRelationshipCreate,
    EntityRelationshipUpdate,
    EntityType,
)
from app.config.settings import settings
from app.utils.pydantic_helper import filter_none_values
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


# ============================================================================
# User Tool Adapters
# ============================================================================

class UserToolAdapters:
    """Wraps user service methods as registry-compatible callables"""

    def __init__(self, user_service: UserService):
        self.user_service = user_service

    async def get_current_user(self, ctx: Context) -> UserResponse:
        """Adapter for get_current_user tool"""
        user = await get_user_from_auth(ctx)
        logger.info(
            "Successfully retrieved current user",
            extra={
                "user": user.name,
                "user_id": user.id,
                "external_id": user.external_id
            }
        )
        return UserResponse(**user.model_dump())

    async def update_user_notes(
        self,
        user_notes: str,
        ctx: Context
    ) -> UserResponse:
        """Adapter for update_user_notes tool"""
        user = await get_user_from_auth(ctx)

        user_update = UserUpdate(
            external_id=user.external_id,
            notes=user_notes
        )

        updated_user = await self.user_service.update_user(user_update=user_update)
        return UserResponse(**updated_user.model_dump())


def create_user_adapters(user_service: UserService) -> Dict[str, Any]:
    """Create all user tool adapters and return as dict"""
    adapters = UserToolAdapters(user_service)
    return {
        "get_current_user": adapters.get_current_user,
        "update_user_notes": adapters.update_user_notes,
    }


# ============================================================================
# Memory Tool Adapters
# ============================================================================

class MemoryToolAdapters:
    """Wraps memory service methods as registry-compatible callables"""

    def __init__(self, memory_service: MemoryService, user_service: UserService):
        self.memory_service = memory_service
        self.user_service = user_service

    async def create_memory(
        self,
        title: str,
        content: str,
        context: str,
        keywords: List[str],
        tags: List[str],
        importance: int,
        ctx: Context,
        project_ids: Optional[List[int]] = None,
        code_artifact_ids: Optional[List[int]] = None,
        document_ids: Optional[List[int]] = None,
    ) -> MemoryCreateResponse:
        """Adapter for create_memory tool"""
        logger.info("MCP Tool Called -> create memory", extra={"title": title})

        user = await get_user_from_auth(ctx)

        memory_data = MemoryCreate(
            title=title,
            content=content,
            context=context,
            keywords=keywords,
            tags=tags,
            importance=importance,
            project_ids=project_ids,
            code_artifact_ids=code_artifact_ids,
            document_ids=document_ids,
        )

        memory, similar_memories = await self.memory_service.create_memory(
            user_id=user.id,
            memory_data=memory_data
        )

        logger.info(
            "MCP Tool Call -> create memory completed",
            extra={
                "user_id": user.id,
                "memory_id": memory.id,
                "title": memory.title,
                "linked_memory_ids": memory.linked_memory_ids,
                "similar_memories_count": len(similar_memories)
            }
        )

        return MemoryCreateResponse(
            id=memory.id,
            title=memory.title,
            linked_memory_ids=memory.linked_memory_ids,
            project_ids=memory.project_ids,
            code_artifact_ids=memory.code_artifact_ids,
            document_ids=memory.document_ids,
            similar_memories=similar_memories
        )

    async def query_memory(
        self,
        query: str,
        query_context: str,
        ctx: Context,
        k: int = 3,
        include_links: bool = True,
        max_links_per_primary: int = 5,
        importance_threshold: Optional[int] = None,
        project_ids: Optional[List[int]] = None,
        strict_project_filter: bool = False
    ) -> MemoryQueryResult:
        """Adapter for query_memory tool"""
        logger.info(
            "MCP Tool -> query_memory",
            extra={
                "query": query[:50],
                "k": k,
                "include_links": include_links
            }
        )

        user = await get_user_from_auth(ctx)

        k = max(1, min(k, 20))

        if importance_threshold is not None:
            importance_threshold = max(1, min(importance_threshold, 10))

        result = await self.memory_service.query_memory(
            user_id=user.id,
            memory_query=MemoryQueryRequest(
                query=query,
                query_context=query_context,
                k=k,
                include_links=include_links,
                token_context_threshold=settings.MEMORY_TOKEN_BUDGET,
                max_links_per_primary=max_links_per_primary,
                importance_threshold=importance_threshold,
                project_ids=project_ids,
                strict_project_filter=strict_project_filter
            )
        )

        logger.info(
            "MCP Tool -> query memory completed",
            extra={
                "total_memories_returned": result.total_count,
                "token_count": result.token_count
            }
        )

        return result

    async def update_memory(
        self,
        memory_id: int,
        ctx: Context,
        title: Optional[str] = None,
        content: Optional[str] = None,
        context: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        importance: Optional[int] = None,
        project_ids: Optional[List[int]] = None,
        code_artifact_ids: Optional[List[int]] = None,
        document_ids: Optional[List[int]] = None,
    ) -> Memory:
        """Adapter for update_memory tool"""
        logger.info("MCP Tool -> update_memory", extra={"memory_id": memory_id})

        user = await get_user_from_auth(ctx)

        if importance is not None:
            importance = max(1, min(importance, 10))

        updated_dict = filter_none_values(
            title=title,
            content=content,
            context=context,
            keywords=keywords,
            tags=tags,
            importance=importance,
            project_ids=project_ids,
            code_artifact_ids=code_artifact_ids,
            document_ids=document_ids,
        )

        updated_memory = MemoryUpdate(**updated_dict)

        refreshed_memory = await self.memory_service.update_memory(
            user_id=user.id,
            memory_id=memory_id,
            updated_memory=updated_memory,
        )

        return refreshed_memory

    async def link_memories(
        self,
        memory_id: int,
        related_ids: List[int],
        ctx: Context,
    ) -> dict:
        """Adapter for link_memories tool"""
        logger.info(
            "MCP Tool -> link_memories",
            extra={
                "memory_id": memory_id,
                "related_ids": related_ids
            }
        )

        user = await get_user_from_auth(ctx)

        if not related_ids:
            raise ValueError("related_ids cannot be empty")

        related_ids = [rid for rid in related_ids if rid != memory_id]

        if not related_ids:
            raise ValueError("Cannot link memory to itself")

        links_created = await self.memory_service.link_memories(
            user_id=user.id,
            memory_id=memory_id,
            related_ids=related_ids,
        )

        logger.info(
            "MCP Tool - memories linked",
            extra={
                "memory_id": memory_id,
                "memories_linked": links_created
            }
        )

        return {"linked_memory_ids": links_created}

    async def get_memory(
        self,
        memory_id: int,
        ctx: Context,
    ) -> Memory:
        """Adapter for get_memory tool"""
        logger.info("MCP Tool -> get_memory", extra={"memory_id": memory_id})

        user = await get_user_from_auth(ctx)

        memory = await self.memory_service.get_memory(
            user_id=user.id,
            memory_id=memory_id
        )

        logger.info(
            "MCP Tool - successfully retrieved memory",
            extra={
                "memory_id": memory.id,
                "user_id": user.id
            }
        )

        return memory

    async def mark_memory_obsolete(
        self,
        memory_id: int,
        reason: str,
        ctx: Context,
        superseded_by: Optional[int] = None,
    ) -> dict:
        """Adapter for mark_memory_obsolete tool"""
        logger.info(
            "MCP Tool -> mark_memory_obsolete",
            extra={"memory_id": memory_id}
        )

        user = await get_user_from_auth(ctx)

        success = await self.memory_service.mark_memory_obsolete(
            user_id=user.id,
            memory_id=memory_id,
            reason=reason,
            superseded_by=superseded_by
        )

        return {"success": success}

    async def get_recent_memories(
        self,
        ctx: Context,
        limit: int = 10,
        project_ids: Optional[List[int]] = None,
    ) -> List[Memory]:
        """Adapter for get_recent_memories tool"""
        logger.info(
            "MCP Tool -> get_recent_memories",
            extra={"limit": limit, "project_ids": project_ids}
        )

        user = await get_user_from_auth(ctx)

        memories = await self.memory_service.get_recent_memories(
            user_id=user.id,
            limit=limit,
            project_ids=project_ids
        )

        return memories


def create_memory_adapters(
    memory_service: MemoryService,
    user_service: UserService
) -> Dict[str, Any]:
    """Create all memory tool adapters and return as dict"""
    adapters = MemoryToolAdapters(memory_service, user_service)
    return {
        "create_memory": adapters.create_memory,
        "query_memory": adapters.query_memory,
        "update_memory": adapters.update_memory,
        "link_memories": adapters.link_memories,
        "get_memory": adapters.get_memory,
        "mark_memory_obsolete": adapters.mark_memory_obsolete,
        "get_recent_memories": adapters.get_recent_memories,
    }


# ============================================================================
# Project Tool Adapters
# ============================================================================

class ProjectToolAdapters:
    """Wraps project service methods as registry-compatible callables"""

    def __init__(self, project_service: ProjectService, user_service: UserService):
        self.project_service = project_service
        self.user_service = user_service

    async def create_project(
        self,
        name: str,
        description: str,
        project_type: ProjectType,
        ctx: Context,
        status: ProjectStatus = ProjectStatus.ACTIVE,
        repo_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Project:
        """Adapter for create_project tool"""
        user = await get_user_from_auth(ctx)

        project_data = ProjectCreate(
            name=name,
            description=description,
            project_type=project_type,
            status=status,
            repo_name=repo_name,
            notes=notes,
        )

        project = await self.project_service.create_project(
            user_id=user.id,
            project_data=project_data
        )

        return project

    async def update_project(
        self,
        project_id: int,
        ctx: Context,
        name: Optional[str] = None,
        description: Optional[str] = None,
        project_type: Optional[ProjectType] = None,
        status: Optional[ProjectStatus] = None,
        repo_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Project:
        """Adapter for update_project tool"""
        user = await get_user_from_auth(ctx)

        updated_dict = filter_none_values(
            name=name,
            description=description,
            project_type=project_type,
            status=status,
            repo_name=repo_name,
            notes=notes,
        )

        project_data = ProjectUpdate(**updated_dict)

        project = await self.project_service.update_project(
            user_id=user.id,
            project_id=project_id,
            project_data=project_data,
        )

        return project

    async def delete_project(
        self,
        project_id: int,
        ctx: Context
    ) -> dict:
        """Adapter for delete_project tool"""
        user = await get_user_from_auth(ctx)

        result = await self.project_service.delete_project(
            user_id=user.id,
            project_id=project_id
        )

        return {"success": result, "project_id": project_id}

    async def list_projects(
        self,
        ctx: Context,
        status: Optional[str] = None,
        repo_name: Optional[str] = None,
    ) -> dict:
        """Adapter for list_projects tool"""
        user = await get_user_from_auth(ctx)

        # Convert string to enum if provided
        status_enum = ProjectStatus(status) if status else None

        result = await self.project_service.list_projects(
            user_id=user.id,
            status=status_enum,
            repo_name=repo_name,
        )

        count = len(result)
        return {"projects": result, "total_count": count, "count": count}

    async def get_project(
        self,
        project_id: int,
        ctx: Context
    ) -> Project:
        """Adapter for get_project tool"""
        user = await get_user_from_auth(ctx)

        project = await self.project_service.get_project(
            user_id=user.id,
            project_id=project_id
        )

        return project


def create_project_adapters(
    project_service: ProjectService,
    user_service: UserService
) -> Dict[str, Any]:
    """Create all project tool adapters and return as dict"""
    adapters = ProjectToolAdapters(project_service, user_service)
    return {
        "create_project": adapters.create_project,
        "update_project": adapters.update_project,
        "delete_project": adapters.delete_project,
        "list_projects": adapters.list_projects,
        "get_project": adapters.get_project,
    }


# ============================================================================
# CodeArtifact Tool Adapters
# ============================================================================

class CodeArtifactToolAdapters:
    """Wraps code artifact service methods as registry-compatible callables"""

    def __init__(self, code_artifact_service: CodeArtifactService, user_service: UserService):
        self.code_artifact_service = code_artifact_service
        self.user_service = user_service

    async def create_code_artifact(
        self,
        title: str,
        description: str,
        code: str,
        language: str,
        ctx: Context,
        tags: Optional[List[str]] = None,
        project_id: Optional[int] = None,
    ) -> CodeArtifact:
        """Adapter for create_code_artifact tool"""
        user = await get_user_from_auth(ctx)

        artifact_data = CodeArtifactCreate(
            title=title,
            description=description,
            code=code,
            language=language,
            tags=tags,
            project_id=project_id,
        )

        artifact = await self.code_artifact_service.create_code_artifact(
            user_id=user.id,
            artifact_data=artifact_data
        )

        return artifact

    async def get_code_artifact(
        self,
        artifact_id: int,
        ctx: Context
    ) -> CodeArtifact:
        """Adapter for get_code_artifact tool"""
        user = await get_user_from_auth(ctx)

        artifact = await self.code_artifact_service.get_code_artifact(
            user_id=user.id,
            artifact_id=artifact_id
        )

        return artifact

    async def list_code_artifacts(
        self,
        ctx: Context,
        project_id: Optional[int] = None,
        language: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """Adapter for list_code_artifacts tool"""
        user = await get_user_from_auth(ctx)

        result = await self.code_artifact_service.list_code_artifacts(
            user_id=user.id,
            project_id=project_id,
            language=language,
            tags=tags,
        )

        return {"code_artifacts": result, "total_count": len(result)}

    async def update_code_artifact(
        self,
        artifact_id: int,
        ctx: Context,
        title: Optional[str] = None,
        description: Optional[str] = None,
        code: Optional[str] = None,
        language: Optional[str] = None,
        tags: Optional[List[str]] = None,
        project_id: Optional[int] = None,
    ) -> CodeArtifact:
        """Adapter for update_code_artifact tool"""
        user = await get_user_from_auth(ctx)

        updated_dict = filter_none_values(
            title=title,
            description=description,
            code=code,
            language=language,
            tags=tags,
            project_id=project_id,
        )

        artifact_data = CodeArtifactUpdate(**updated_dict)

        artifact = await self.code_artifact_service.update_code_artifact(
            user_id=user.id,
            artifact_id=artifact_id,
            artifact_data=artifact_data,
        )

        return artifact

    async def delete_code_artifact(
        self,
        artifact_id: int,
        ctx: Context
    ) -> dict:
        """Adapter for delete_code_artifact tool"""
        user = await get_user_from_auth(ctx)

        result = await self.code_artifact_service.delete_code_artifact(
            user_id=user.id,
            artifact_id=artifact_id
        )

        return {"success": result, "deleted_id": artifact_id}


def create_code_artifact_adapters(
    code_artifact_service: CodeArtifactService,
    user_service: UserService
) -> Dict[str, Any]:
    """Create all code artifact tool adapters and return as dict"""
    adapters = CodeArtifactToolAdapters(code_artifact_service, user_service)
    return {
        "create_code_artifact": adapters.create_code_artifact,
        "get_code_artifact": adapters.get_code_artifact,
        "list_code_artifacts": adapters.list_code_artifacts,
        "update_code_artifact": adapters.update_code_artifact,
        "delete_code_artifact": adapters.delete_code_artifact,
    }


# ============================================================================
# Document Tool Adapters
# ============================================================================

class DocumentToolAdapters:
    """Wraps document service methods as registry-compatible callables"""

    def __init__(self, document_service: DocumentService, user_service: UserService):
        self.document_service = document_service
        self.user_service = user_service

    async def create_document(
        self,
        title: str,
        description: str,
        content: str,
        ctx: Context,
        document_type: str = "text",
        filename: Optional[str] = None,
        tags: Optional[List[str]] = None,
        project_id: Optional[int] = None,
    ) -> Document:
        """Adapter for create_document tool"""
        user = await get_user_from_auth(ctx)

        document_data = DocumentCreate(
            title=title,
            description=description,
            content=content,
            document_type=document_type,
            filename=filename,
            tags=tags,
            project_id=project_id,
        )

        document = await self.document_service.create_document(
            user_id=user.id,
            document_data=document_data
        )

        return document

    async def get_document(
        self,
        document_id: int,
        ctx: Context
    ) -> Document:
        """Adapter for get_document tool"""
        user = await get_user_from_auth(ctx)

        document = await self.document_service.get_document(
            user_id=user.id,
            document_id=document_id
        )

        return document

    async def list_documents(
        self,
        ctx: Context,
        project_id: Optional[int] = None,
        document_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """Adapter for list_documents tool"""
        user = await get_user_from_auth(ctx)

        result = await self.document_service.list_documents(
            user_id=user.id,
            project_id=project_id,
            document_type=document_type,
            tags=tags,
        )

        return {"documents": result, "total_count": len(result)}

    async def update_document(
        self,
        document_id: int,
        ctx: Context,
        title: Optional[str] = None,
        description: Optional[str] = None,
        content: Optional[str] = None,
        document_type: Optional[str] = None,
        filename: Optional[str] = None,
        tags: Optional[List[str]] = None,
        project_id: Optional[int] = None,
    ) -> Document:
        """Adapter for update_document tool"""
        user = await get_user_from_auth(ctx)

        updated_dict = filter_none_values(
            title=title,
            description=description,
            content=content,
            document_type=document_type,
            filename=filename,
            tags=tags,
            project_id=project_id,
        )

        document_data = DocumentUpdate(**updated_dict)

        document = await self.document_service.update_document(
            user_id=user.id,
            document_id=document_id,
            document_data=document_data,
        )

        return document

    async def delete_document(
        self,
        document_id: int,
        ctx: Context
    ) -> dict:
        """Adapter for delete_document tool"""
        user = await get_user_from_auth(ctx)

        result = await self.document_service.delete_document(
            user_id=user.id,
            document_id=document_id
        )

        return {"success": result, "deleted_id": document_id}


def create_document_adapters(
    document_service: DocumentService,
    user_service: UserService
) -> Dict[str, Any]:
    """Create all document tool adapters and return as dict"""
    adapters = DocumentToolAdapters(document_service, user_service)
    return {
        "create_document": adapters.create_document,
        "get_document": adapters.get_document,
        "list_documents": adapters.list_documents,
        "update_document": adapters.update_document,
        "delete_document": adapters.delete_document,
    }


# ============================================================================
# Entity Tool Adapters
# ============================================================================

class EntityToolAdapters:
    """Wraps entity service methods as registry-compatible callables"""

    def __init__(self, entity_service: EntityService, user_service: UserService):
        self.entity_service = entity_service
        self.user_service = user_service

    async def create_entity(
        self,
        name: str,
        entity_type: str,
        ctx: Context,
        custom_type: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        project_id: Optional[int] = None,
    ) -> Entity:
        """Adapter for create_entity tool"""
        user = await get_user_from_auth(ctx)

        # Use filter_none_values to avoid passing None for fields with defaults
        entity_dict = filter_none_values(
            name=name,
            entity_type=entity_type,
            custom_type=custom_type,
            notes=notes,
            tags=tags,
            project_id=project_id,
        )
        entity_data = EntityCreate(**entity_dict)

        entity = await self.entity_service.create_entity(
            user_id=user.id,
            entity_data=entity_data
        )

        return entity

    async def get_entity(
        self,
        entity_id: int,
        ctx: Context
    ) -> Entity:
        """Adapter for get_entity tool"""
        user = await get_user_from_auth(ctx)

        entity = await self.entity_service.get_entity(
            user_id=user.id,
            entity_id=entity_id
        )

        return entity

    async def list_entities(
        self,
        ctx: Context,
        project_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> dict:
        """Adapter for list_entities tool"""
        user = await get_user_from_auth(ctx)

        # Convert string to enum if provided
        entity_type_enum = EntityType(entity_type) if entity_type else None

        result = await self.entity_service.list_entities(
            user_id=user.id,
            project_id=project_id,
            entity_type=entity_type_enum,
            tags=tags,
        )

        return {"entities": result, "total_count": len(result)}

    async def search_entities(
        self,
        query: str,
        ctx: Context,
        entity_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20
    ) -> dict:
        """Adapter for search_entities tool"""
        user = await get_user_from_auth(ctx)

        # Convert string to enum if provided
        entity_type_enum = EntityType(entity_type) if entity_type else None

        result = await self.entity_service.search_entities(
            user_id=user.id,
            search_query=query,
            entity_type=entity_type_enum,
            tags=tags,
            limit=limit
        )

        return {
            "entities": result,
            "total_count": len(result),
            "search_query": query,
            "filters": {
                "entity_type": entity_type,
                "tags": tags,
                "limit": limit
            }
        }

    async def update_entity(
        self,
        entity_id: int,
        ctx: Context,
        name: Optional[str] = None,
        entity_type: Optional[str] = None,
        custom_type: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        project_id: Optional[int] = None
    ) -> Entity:
        """Adapter for update_entity tool"""
        user = await get_user_from_auth(ctx)

        updated_dict = filter_none_values(
            name=name,
            entity_type=entity_type,
            custom_type=custom_type,
            notes=notes,
            tags=tags,
            project_id=project_id,
        )

        entity_data = EntityUpdate(**updated_dict)

        entity = await self.entity_service.update_entity(
            user_id=user.id,
            entity_id=entity_id,
            entity_data=entity_data,
        )

        return entity

    async def delete_entity(
        self,
        entity_id: int,
        ctx: Context
    ) -> dict:
        """Adapter for delete_entity tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.delete_entity(
            user_id=user.id,
            entity_id=entity_id
        )

        return {"success": result, "deleted_id": entity_id}

    async def link_entity_to_memory(
        self,
        entity_id: int,
        memory_id: int,
        ctx: Context
    ) -> dict:
        """Adapter for link_entity_to_memory tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.link_entity_to_memory(
            user_id=user.id,
            entity_id=entity_id,
            memory_id=memory_id
        )

        return {"success": result}

    async def unlink_entity_from_memory(
        self,
        entity_id: int,
        memory_id: int,
        ctx: Context
    ) -> dict:
        """Adapter for unlink_entity_from_memory tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.unlink_entity_from_memory(
            user_id=user.id,
            entity_id=entity_id,
            memory_id=memory_id
        )

        return {"success": result}

    async def create_entity_relationship(
        self,
        source_entity_id: int,
        target_entity_id: int,
        relationship_type: str,
        ctx: Context,
        strength: Optional[float] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EntityRelationship:
        """Adapter for create_entity_relationship tool"""
        user = await get_user_from_auth(ctx)

        relationship_data = EntityRelationshipCreate(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            strength=strength,
            confidence=confidence,
            metadata=metadata,
        )

        relationship = await self.entity_service.create_entity_relationship(
            user_id=user.id,
            relationship_data=relationship_data
        )

        return relationship

    async def get_entity_relationships(
        self,
        entity_id: int,
        ctx: Context,
        direction: Optional[str] = None,
        relationship_type: Optional[str] = None
    ) -> dict:
        """Adapter for get_entity_relationships tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.get_entity_relationships(
            user_id=user.id,
            entity_id=entity_id,
            direction=direction,
            relationship_type=relationship_type,
        )

        return {"relationships": result}

    async def update_entity_relationship(
        self,
        relationship_id: int,
        ctx: Context,
        relationship_type: Optional[str] = None,
        strength: Optional[float] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EntityRelationship:
        """Adapter for update_entity_relationship tool"""
        user = await get_user_from_auth(ctx)

        updated_dict = filter_none_values(
            relationship_type=relationship_type,
            strength=strength,
            confidence=confidence,
            metadata=metadata,
        )

        relationship_data = EntityRelationshipUpdate(**updated_dict)

        relationship = await self.entity_service.update_entity_relationship(
            user_id=user.id,
            relationship_id=relationship_id,
            relationship_data=relationship_data,
        )

        return relationship

    async def delete_entity_relationship(
        self,
        relationship_id: int,
        ctx: Context
    ) -> dict:
        """Adapter for delete_entity_relationship tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.delete_entity_relationship(
            user_id=user.id,
            relationship_id=relationship_id
        )

        return {"success": result, "deleted_id": relationship_id}


def create_entity_adapters(
    entity_service: EntityService,
    user_service: UserService
) -> Dict[str, Any]:
    """Create all entity tool adapters and return as dict"""
    adapters = EntityToolAdapters(entity_service, user_service)
    return {
        "create_entity": adapters.create_entity,
        "get_entity": adapters.get_entity,
        "list_entities": adapters.list_entities,
        "search_entities": adapters.search_entities,
        "update_entity": adapters.update_entity,
        "delete_entity": adapters.delete_entity,
        "link_entity_to_memory": adapters.link_entity_to_memory,
        "unlink_entity_from_memory": adapters.unlink_entity_from_memory,
        "create_entity_relationship": adapters.create_entity_relationship,
        "get_entity_relationships": adapters.get_entity_relationships,
        "update_entity_relationship": adapters.update_entity_relationship,
        "delete_entity_relationship": adapters.delete_entity_relationship,
    }
