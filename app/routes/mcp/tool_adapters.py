"""Tool Adapters - Bridge between services and tool registry

This module provides adapter classes that wrap service methods as registry-compatible
callables, ensuring user context is properly extracted and preserved.
"""

from typing import Any

from fastmcp import Context

from app.config.logging_config import logging
from app.config.settings import settings
from app.middleware.auth import get_user_from_auth
from app.models.code_artifact_models import (
    CodeArtifact,
    CodeArtifactCreate,
    CodeArtifactUpdate,
)
from app.models.document_models import Document, DocumentCreate, DocumentUpdate
from app.models.entity_models import (
    Entity,
    EntityCreate,
    EntityRelationship,
    EntityRelationshipCreate,
    EntityRelationshipUpdate,
    EntityType,
    EntityUpdate,
)
from app.models.memory_models import (
    Memory,
    MemoryCreate,
    MemoryCreateResponse,
    MemoryQueryRequest,
    MemoryQueryResult,
    MemoryUpdate,
)
from app.models.project_models import (
    Project,
    ProjectCreate,
    ProjectStatus,
    ProjectType,
    ProjectUpdate,
)
from app.models.user_models import UserResponse, UserUpdate
from app.services.code_artifact_service import CodeArtifactService
from app.services.document_service import DocumentService
from app.services.entity_service import EntityService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService
from app.services.user_service import UserService
from app.utils.pydantic_helper import filter_none_values

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
                "external_id": user.external_id,
            },
        )
        return UserResponse(**user.model_dump())

    async def update_user_notes(self, user_notes: str, ctx: Context) -> UserResponse:
        """Adapter for update_user_notes tool"""
        user = await get_user_from_auth(ctx)

        user_update = UserUpdate(external_id=user.external_id, notes=user_notes)

        updated_user = await self.user_service.update_user(user_update=user_update)
        return UserResponse(**updated_user.model_dump())


def create_user_adapters(user_service: UserService) -> dict[str, Any]:
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
        keywords: list[str],
        tags: list[str],
        importance: int,
        ctx: Context,
        project_ids: list[int] | None = None,
        code_artifact_ids: list[int] | None = None,
        document_ids: list[int] | None = None,
        # Provenance tracking fields
        source_repo: str | None = None,
        source_files: list[str] | None = None,
        source_url: str | None = None,
        confidence: float | None = None,
        encoding_agent: str | None = None,
        encoding_version: str | None = None,
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
            source_repo=source_repo,
            source_files=source_files,
            source_url=source_url,
            confidence=confidence,
            encoding_agent=encoding_agent,
            encoding_version=encoding_version,
        )

        memory, similar_memories = await self.memory_service.create_memory(
            user_id=user.id, memory_data=memory_data,
        )

        logger.info(
            "MCP Tool Call -> create memory completed",
            extra={
                "user_id": user.id,
                "memory_id": memory.id,
                "title": memory.title,
                "linked_memory_ids": memory.linked_memory_ids,
                "similar_memories_count": len(similar_memories),
            },
        )

        return MemoryCreateResponse(
            id=memory.id,
            title=memory.title,
            linked_memory_ids=memory.linked_memory_ids,
            project_ids=memory.project_ids,
            code_artifact_ids=memory.code_artifact_ids,
            document_ids=memory.document_ids,
            similar_memories=similar_memories,
        )

    async def query_memory(
        self,
        query: str,
        query_context: str,
        ctx: Context,
        k: int = 3,
        include_links: bool = True,
        max_links_per_primary: int = 5,
        importance_threshold: int | None = None,
        project_ids: list[int] | None = None,
        strict_project_filter: bool = False,
    ) -> MemoryQueryResult:
        """Adapter for query_memory tool"""
        logger.info(
            "MCP Tool -> query_memory",
            extra={"query": query[:50], "k": k, "include_links": include_links},
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
                strict_project_filter=strict_project_filter,
            ),
        )

        logger.info(
            "MCP Tool -> query memory completed",
            extra={
                "total_memories_returned": result.total_count,
                "token_count": result.token_count,
            },
        )

        return result

    async def update_memory(
        self,
        memory_id: int,
        ctx: Context,
        title: str | None = None,
        content: str | None = None,
        context: str | None = None,
        keywords: list[str] | None = None,
        tags: list[str] | None = None,
        importance: int | None = None,
        project_ids: list[int] | None = None,
        code_artifact_ids: list[int] | None = None,
        document_ids: list[int] | None = None,
        # Provenance tracking fields
        source_repo: str | None = None,
        source_files: list[str] | None = None,
        source_url: str | None = None,
        confidence: float | None = None,
        encoding_agent: str | None = None,
        encoding_version: str | None = None,
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
            source_repo=source_repo,
            source_files=source_files,
            source_url=source_url,
            confidence=confidence,
            encoding_agent=encoding_agent,
            encoding_version=encoding_version,
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
        related_ids: list[int],
        ctx: Context,
    ) -> dict:
        """Adapter for link_memories tool"""
        logger.info(
            "MCP Tool -> link_memories",
            extra={"memory_id": memory_id, "related_ids": related_ids},
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
            extra={"memory_id": memory_id, "memories_linked": links_created},
        )

        return {"linked_memory_ids": links_created}

    async def unlink_memories(
        self,
        source_id: int,
        target_id: int,
        ctx: Context,
    ) -> dict:
        """Adapter for unlink_memories tool"""
        logger.info(
            "MCP Tool -> unlink_memories",
            extra={"source_id": source_id, "target_id": target_id},
        )

        user = await get_user_from_auth(ctx)

        success = await self.memory_service.unlink_memories(
            user_id=user.id,
            memory_id=source_id,
            target_id=target_id,
        )

        logger.info(
            "MCP Tool - memories unlinked",
            extra={"source_id": source_id, "target_id": target_id, "success": success},
        )

        return {"success": success}

    async def get_memory(
        self,
        memory_id: int,
        ctx: Context,
    ) -> Memory:
        """Adapter for get_memory tool"""
        logger.info("MCP Tool -> get_memory", extra={"memory_id": memory_id})

        user = await get_user_from_auth(ctx)

        memory = await self.memory_service.get_memory(
            user_id=user.id, memory_id=memory_id,
        )

        logger.info(
            "MCP Tool - successfully retrieved memory",
            extra={"memory_id": memory.id, "user_id": user.id},
        )

        return memory

    async def mark_memory_obsolete(
        self,
        memory_id: int,
        reason: str,
        ctx: Context,
        superseded_by: int | None = None,
    ) -> dict:
        """Adapter for mark_memory_obsolete tool"""
        logger.info("MCP Tool -> mark_memory_obsolete", extra={"memory_id": memory_id})

        user = await get_user_from_auth(ctx)

        success = await self.memory_service.mark_memory_obsolete(
            user_id=user.id,
            memory_id=memory_id,
            reason=reason,
            superseded_by=superseded_by,
        )

        return {"success": success}

    async def get_recent_memories(
        self,
        ctx: Context,
        limit: int = 10,
        project_ids: list[int] | None = None,
    ) -> list[Memory]:
        """Adapter for get_recent_memories tool"""
        logger.info(
            "MCP Tool -> get_recent_memories",
            extra={"limit": limit, "project_ids": project_ids},
        )

        user = await get_user_from_auth(ctx)

        # Service returns (memories, total_count) tuple; MCP tool only needs memories
        memories, _ = await self.memory_service.get_recent_memories(
            user_id=user.id, limit=limit, project_ids=project_ids,
        )

        return memories


def create_memory_adapters(
    memory_service: MemoryService, user_service: UserService,
) -> dict[str, Any]:
    """Create all memory tool adapters and return as dict"""
    adapters = MemoryToolAdapters(memory_service, user_service)
    return {
        "create_memory": adapters.create_memory,
        "query_memory": adapters.query_memory,
        "update_memory": adapters.update_memory,
        "link_memories": adapters.link_memories,
        "unlink_memories": adapters.unlink_memories,
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
        repo_name: str | None = None,
        notes: str | None = None,
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
            user_id=user.id, project_data=project_data,
        )

        return project

    async def update_project(
        self,
        project_id: int,
        ctx: Context,
        name: str | None = None,
        description: str | None = None,
        project_type: ProjectType | None = None,
        status: ProjectStatus | None = None,
        repo_name: str | None = None,
        notes: str | None = None,
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

    async def delete_project(self, project_id: int, ctx: Context) -> dict:
        """Adapter for delete_project tool"""
        user = await get_user_from_auth(ctx)

        result = await self.project_service.delete_project(
            user_id=user.id, project_id=project_id,
        )

        return {"success": result, "project_id": project_id}

    async def list_projects(
        self,
        ctx: Context,
        status: str | None = None,
        repo_name: str | None = None,
        name: str | None = None,
    ) -> dict:
        """Adapter for list_projects tool"""
        user = await get_user_from_auth(ctx)

        # Convert string to enum if provided
        status_enum = ProjectStatus(status) if status else None

        result = await self.project_service.list_projects(
            user_id=user.id,
            status=status_enum,
            repo_name=repo_name,
            name=name,
        )

        count = len(result)
        return {
            "projects": result,
            "total_count": count,
            "count": count,
            "name_filter": name,
        }

    async def get_project(self, project_id: int, ctx: Context) -> Project:
        """Adapter for get_project tool"""
        user = await get_user_from_auth(ctx)

        project = await self.project_service.get_project(
            user_id=user.id, project_id=project_id,
        )

        return project


def create_project_adapters(
    project_service: ProjectService, user_service: UserService,
) -> dict[str, Any]:
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

    def __init__(
        self, code_artifact_service: CodeArtifactService, user_service: UserService,
    ):
        self.code_artifact_service = code_artifact_service
        self.user_service = user_service

    async def create_code_artifact(
        self,
        title: str,
        description: str,
        code: str,
        language: str,
        ctx: Context,
        tags: list[str] | None = None,
        project_id: int | None = None,
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
            user_id=user.id, artifact_data=artifact_data,
        )

        return artifact

    async def get_code_artifact(self, artifact_id: int, ctx: Context) -> CodeArtifact:
        """Adapter for get_code_artifact tool"""
        user = await get_user_from_auth(ctx)

        artifact = await self.code_artifact_service.get_code_artifact(
            user_id=user.id, artifact_id=artifact_id,
        )

        return artifact

    async def list_code_artifacts(
        self,
        ctx: Context,
        project_id: int | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
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
        title: str | None = None,
        description: str | None = None,
        code: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
        project_id: int | None = None,
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

    async def delete_code_artifact(self, artifact_id: int, ctx: Context) -> dict:
        """Adapter for delete_code_artifact tool"""
        user = await get_user_from_auth(ctx)

        result = await self.code_artifact_service.delete_code_artifact(
            user_id=user.id, artifact_id=artifact_id,
        )

        return {"success": result, "deleted_id": artifact_id}


def create_code_artifact_adapters(
    code_artifact_service: CodeArtifactService, user_service: UserService,
) -> dict[str, Any]:
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
        filename: str | None = None,
        tags: list[str] | None = None,
        project_id: int | None = None,
    ) -> Document:
        """Adapter for create_document tool"""
        user = await get_user_from_auth(ctx)

        document_data = DocumentCreate(
            title=title,
            description=description,
            content=content,
            document_type=document_type,
            filename=filename,
            tags=tags or [],
            project_id=project_id,
        )

        document = await self.document_service.create_document(
            user_id=user.id, document_data=document_data,
        )

        return document

    async def get_document(self, document_id: int, ctx: Context) -> Document:
        """Adapter for get_document tool"""
        user = await get_user_from_auth(ctx)

        document = await self.document_service.get_document(
            user_id=user.id, document_id=document_id,
        )

        return document

    async def list_documents(
        self,
        ctx: Context,
        project_id: int | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
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
        title: str | None = None,
        description: str | None = None,
        content: str | None = None,
        document_type: str | None = None,
        filename: str | None = None,
        tags: list[str] | None = None,
        project_id: int | None = None,
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

    async def delete_document(self, document_id: int, ctx: Context) -> dict:
        """Adapter for delete_document tool"""
        user = await get_user_from_auth(ctx)

        result = await self.document_service.delete_document(
            user_id=user.id, document_id=document_id,
        )

        return {"success": result, "deleted_id": document_id}


def create_document_adapters(
    document_service: DocumentService, user_service: UserService,
) -> dict[str, Any]:
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
        custom_type: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        aka: list[str] | None = None,
        project_ids: list[int] | None = None,
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
            aka=aka,
            project_ids=project_ids,
        )
        entity_data = EntityCreate(**entity_dict)

        entity = await self.entity_service.create_entity(
            user_id=user.id, entity_data=entity_data,
        )

        return entity

    async def get_entity(self, entity_id: int, ctx: Context) -> Entity:
        """Adapter for get_entity tool"""
        user = await get_user_from_auth(ctx)

        entity = await self.entity_service.get_entity(
            user_id=user.id, entity_id=entity_id,
        )

        return entity

    async def list_entities(
        self,
        ctx: Context,
        project_ids: list[int] | None = None,
        entity_type: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Adapter for list_entities tool"""
        user = await get_user_from_auth(ctx)

        # Convert string to enum if provided
        entity_type_enum = EntityType(entity_type) if entity_type else None

        # MCP adapter returns all entities (no pagination params exposed)
        entities, total = await self.entity_service.list_entities(
            user_id=user.id,
            project_ids=project_ids,
            entity_type=entity_type_enum,
            tags=tags,
            limit=10000,  # High limit to return all entities for MCP
        )

        return {"entities": entities, "total_count": total}

    async def search_entities(
        self,
        query: str,
        ctx: Context,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
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
            limit=limit,
        )

        return {
            "entities": result,
            "total_count": len(result),
            "search_query": query,
            "filters": {"entity_type": entity_type, "tags": tags, "limit": limit},
        }

    async def update_entity(
        self,
        entity_id: int,
        ctx: Context,
        name: str | None = None,
        entity_type: str | None = None,
        custom_type: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        aka: list[str] | None = None,
        project_ids: list[int] | None = None,
    ) -> Entity:
        """Adapter for update_entity tool"""
        user = await get_user_from_auth(ctx)

        updated_dict = filter_none_values(
            name=name,
            entity_type=entity_type,
            custom_type=custom_type,
            notes=notes,
            tags=tags,
            aka=aka,
            project_ids=project_ids,
        )

        entity_data = EntityUpdate(**updated_dict)

        entity = await self.entity_service.update_entity(
            user_id=user.id,
            entity_id=entity_id,
            entity_data=entity_data,
        )

        return entity

    async def delete_entity(self, entity_id: int, ctx: Context) -> dict:
        """Adapter for delete_entity tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.delete_entity(
            user_id=user.id, entity_id=entity_id,
        )

        return {"success": result, "deleted_id": entity_id}

    async def link_entity_to_memory(
        self, entity_id: int, memory_id: int, ctx: Context,
    ) -> dict:
        """Adapter for link_entity_to_memory tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.link_entity_to_memory(
            user_id=user.id, entity_id=entity_id, memory_id=memory_id,
        )

        return {"success": result}

    async def unlink_entity_from_memory(
        self, entity_id: int, memory_id: int, ctx: Context,
    ) -> dict:
        """Adapter for unlink_entity_from_memory tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.unlink_entity_from_memory(
            user_id=user.id, entity_id=entity_id, memory_id=memory_id,
        )

        return {"success": result}

    async def link_entity_to_project(
        self, entity_id: int, project_id: int, ctx: Context,
    ) -> dict:
        """Adapter for link_entity_to_project tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.link_entity_to_project(
            user_id=user.id, entity_id=entity_id, project_id=project_id,
        )

        return {"success": result}

    async def unlink_entity_from_project(
        self, entity_id: int, project_id: int, ctx: Context,
    ) -> dict:
        """Adapter for unlink_entity_from_project tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.unlink_entity_from_project(
            user_id=user.id, entity_id=entity_id, project_id=project_id,
        )

        return {"success": result}

    async def create_entity_relationship(
        self,
        source_entity_id: int,
        target_entity_id: int,
        relationship_type: str,
        ctx: Context,
        strength: float | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
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
            user_id=user.id, relationship_data=relationship_data,
        )

        return relationship

    async def get_entity_relationships(
        self,
        entity_id: int,
        ctx: Context,
        direction: str | None = None,
        relationship_type: str | None = None,
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
        relationship_type: str | None = None,
        strength: float | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
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
        self, relationship_id: int, ctx: Context,
    ) -> dict:
        """Adapter for delete_entity_relationship tool"""
        user = await get_user_from_auth(ctx)

        result = await self.entity_service.delete_entity_relationship(
            user_id=user.id, relationship_id=relationship_id,
        )

        return {"success": result, "deleted_id": relationship_id}

    async def get_entity_memories(self, entity_id: int, ctx: Context) -> dict:
        """Adapter for get_entity_memories tool"""
        user = await get_user_from_auth(ctx)

        memory_ids, count = await self.entity_service.get_entity_memories(
            user_id=user.id, entity_id=entity_id,
        )

        return {"memory_ids": memory_ids, "count": count}


def create_entity_adapters(
    entity_service: EntityService, user_service: UserService,
) -> dict[str, Any]:
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
        "link_entity_to_project": adapters.link_entity_to_project,
        "unlink_entity_from_project": adapters.unlink_entity_from_project,
        "create_entity_relationship": adapters.create_entity_relationship,
        "get_entity_relationships": adapters.get_entity_relationships,
        "update_entity_relationship": adapters.update_entity_relationship,
        "delete_entity_relationship": adapters.delete_entity_relationship,
        "get_entity_memories": adapters.get_entity_memories,
    }


# ============================================================================
# Plan Tool Adapters
# ============================================================================


class PlanToolAdapters:
    """Wraps plan service methods as registry-compatible callables"""

    def __init__(self, plan_service, user_service):
        self.plan_service = plan_service
        self.user_service = user_service

    async def create_plan(
        self,
        title: str,
        project_id: int,
        ctx: Context,
        goal: str | None = None,
        context: str | None = None,
        status: str = "draft",
    ):
        from app.models.plan_models import PlanCreate, PlanStatus
        user = await get_user_from_auth(ctx)
        plan_data = PlanCreate(
            title=title,
            project_id=project_id,
            goal=goal,
            context=context,
            status=PlanStatus(status),
        )
        return await self.plan_service.create_plan(user_id=user.id, plan_data=plan_data)

    async def update_plan(
        self,
        plan_id: int,
        ctx: Context,
        title: str | None = None,
        goal: str | None = None,
        context: str | None = None,
        status: str | None = None,
    ):
        from app.models.plan_models import PlanStatus, PlanUpdate
        user = await get_user_from_auth(ctx)
        updated_dict = filter_none_values(
            title=title, goal=goal, context=context,
            status=PlanStatus(status) if status else None,
        )
        plan_data = PlanUpdate(**updated_dict)
        plan = await self.plan_service.update_plan(
            user_id=user.id, plan_id=plan_id, plan_data=plan_data,
        )
        return plan

    async def get_plan(self, plan_id: int, ctx: Context):
        user = await get_user_from_auth(ctx)
        return await self.plan_service.get_plan(user_id=user.id, plan_id=plan_id)

    async def list_plans(
        self,
        ctx: Context,
        project_id: int | None = None,
        status: str | None = None,
    ):
        from app.models.plan_models import PlanStatus
        user = await get_user_from_auth(ctx)
        status_enum = PlanStatus(status) if status else None
        plans = await self.plan_service.list_plans(
            user_id=user.id, project_id=project_id, status=status_enum,
        )
        return {"plans": plans, "total_count": len(plans)}


def create_plan_adapters(plan_service, user_service) -> dict[str, Any]:
    """Create all plan tool adapters and return as dict"""
    adapters = PlanToolAdapters(plan_service, user_service)
    return {
        "create_plan": adapters.create_plan,
        "update_plan": adapters.update_plan,
        "get_plan": adapters.get_plan,
        "list_plans": adapters.list_plans,
    }


# ============================================================================
# Task Tool Adapters
# ============================================================================


class TaskToolAdapters:
    """Wraps task service methods as registry-compatible callables"""

    def __init__(self, task_service, user_service):
        self.task_service = task_service
        self.user_service = user_service

    async def create_task(
        self,
        title: str,
        plan_id: int,
        ctx: Context,
        description: str | None = None,
        priority: str = "P2",
        assigned_agent: str | None = None,
        criteria: list[dict[str, Any]] | None = None,
        dependency_ids: list[int] | None = None,
    ):
        from app.models.plan_models import CriterionCreate, TaskCreate, TaskPriority
        user = await get_user_from_auth(ctx)
        criteria_models = None
        if criteria:
            criteria_models = [CriterionCreate(**c) for c in criteria]
        task_data = TaskCreate(
            title=title,
            plan_id=plan_id,
            description=description,
            priority=TaskPriority(priority),
            assigned_agent=assigned_agent,
            criteria=criteria_models,
            dependency_ids=dependency_ids,
        )
        return await self.task_service.create_task(user_id=user.id, task_data=task_data)

    async def update_task(
        self,
        task_id: int,
        ctx: Context,
        title: str | None = None,
        description: str | None = None,
        priority: str | None = None,
    ):
        from app.models.plan_models import TaskPriority, TaskUpdate
        user = await get_user_from_auth(ctx)
        updated_dict = filter_none_values(
            title=title, description=description,
            priority=TaskPriority(priority) if priority else None,
        )
        task_data = TaskUpdate(**updated_dict)
        return await self.task_service.update_task(
            user_id=user.id, task_id=task_id, task_data=task_data,
        )

    async def get_task(self, task_id: int, ctx: Context):
        user = await get_user_from_auth(ctx)
        return await self.task_service.get_task(user_id=user.id, task_id=task_id)

    async def query_tasks(
        self,
        plan_id: int,
        ctx: Context,
        state: str | None = None,
        priority: str | None = None,
        assigned_agent: str | None = None,
    ):
        from app.models.plan_models import TaskPriority, TaskState
        user = await get_user_from_auth(ctx)
        state_enum = TaskState(state) if state else None
        priority_enum = TaskPriority(priority) if priority else None
        tasks = await self.task_service.list_tasks(
            user_id=user.id, plan_id=plan_id,
            state=state_enum, priority=priority_enum,
            assigned_agent=assigned_agent,
        )
        return {"tasks": tasks, "total_count": len(tasks)}

    async def claim_task(
        self,
        task_id: int,
        agent_id: str,
        version: int,
        ctx: Context,
    ):
        user = await get_user_from_auth(ctx)
        return await self.task_service.claim_task(
            user_id=user.id, task_id=task_id,
            agent_id=agent_id, expected_version=version,
        )

    async def transition_task(
        self,
        task_id: int,
        state: str,
        version: int,
        ctx: Context,
    ):
        from app.models.plan_models import TaskState
        user = await get_user_from_auth(ctx)
        return await self.task_service.transition_task(
            user_id=user.id, task_id=task_id,
            new_state=TaskState(state), expected_version=version,
        )

    async def add_criterion(
        self,
        task_id: int,
        description: str,
        ctx: Context,
    ):
        from app.models.plan_models import CriterionCreate
        user = await get_user_from_auth(ctx)
        return await self.task_service.add_criterion(
            user_id=user.id, task_id=task_id,
            criterion_data=CriterionCreate(description=description),
        )

    async def verify_criterion(
        self,
        criterion_id: int,
        met: bool,
        ctx: Context,
    ):
        from app.models.plan_models import CriterionUpdate
        user = await get_user_from_auth(ctx)
        return await self.task_service.update_criterion(
            user_id=user.id, criterion_id=criterion_id,
            criterion_data=CriterionUpdate(met=met),
        )

    async def delete_criterion(self, criterion_id: int, ctx: Context):
        user = await get_user_from_auth(ctx)
        success = await self.task_service.delete_criterion(
            user_id=user.id, criterion_id=criterion_id,
        )
        return {"success": success}

    async def add_dependency(
        self,
        task_id: int,
        depends_on_task_id: int,
        ctx: Context,
    ):
        user = await get_user_from_auth(ctx)
        return await self.task_service.add_dependency(
            user_id=user.id, task_id=task_id,
            depends_on_task_id=depends_on_task_id,
        )

    async def remove_dependency(
        self,
        task_id: int,
        depends_on_task_id: int,
        ctx: Context,
    ):
        user = await get_user_from_auth(ctx)
        success = await self.task_service.remove_dependency(
            user_id=user.id, task_id=task_id,
            depends_on_task_id=depends_on_task_id,
        )
        return {"success": success}


def create_task_adapters(task_service, user_service) -> dict[str, Any]:
    """Create all task tool adapters and return as dict"""
    adapters = TaskToolAdapters(task_service, user_service)
    return {
        "create_task": adapters.create_task,
        "update_task": adapters.update_task,
        "get_task": adapters.get_task,
        "query_tasks": adapters.query_tasks,
        "claim_task": adapters.claim_task,
        "transition_task": adapters.transition_task,
        "add_criterion": adapters.add_criterion,
        "verify_criterion": adapters.verify_criterion,
        "delete_criterion": adapters.delete_criterion,
        "add_dependency": adapters.add_dependency,
        "remove_dependency": adapters.remove_dependency,
    }


# ============================================================================
# File Tool Adapters
# ============================================================================


class FileToolAdapters:
    """Wraps file service methods as registry-compatible callables"""

    def __init__(self, file_service, user_service: UserService):
        self.file_service = file_service
        self.user_service = user_service

    async def create_file(
        self,
        filename: str,
        description: str,
        data: str,
        mime_type: str,
        ctx: Context,
        tags: list[str] | None = None,
        project_id: int | None = None,
    ):
        """Adapter for create_file tool"""
        from app.models.file_models import FileCreate

        user = await get_user_from_auth(ctx)

        file_data = FileCreate(
            filename=filename,
            description=description,
            data=data,
            mime_type=mime_type,
            tags=tags,
            project_id=project_id,
        )

        file = await self.file_service.create_file(
            user_id=user.id, file_data=file_data,
        )

        return file

    async def get_file(self, file_id: int, ctx: Context):
        """Adapter for get_file tool"""
        user = await get_user_from_auth(ctx)

        file = await self.file_service.get_file(
            user_id=user.id, file_id=file_id,
        )

        return file

    async def list_files(
        self,
        ctx: Context,
        project_id: int | None = None,
        mime_type: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Adapter for list_files tool"""
        user = await get_user_from_auth(ctx)

        result = await self.file_service.list_files(
            user_id=user.id,
            project_id=project_id,
            mime_type=mime_type,
            tags=tags,
        )

        return {"files": result, "total_count": len(result)}

    async def update_file(
        self,
        file_id: int,
        ctx: Context,
        filename: str | None = None,
        description: str | None = None,
        data: str | None = None,
        mime_type: str | None = None,
        tags: list[str] | None = None,
        project_id: int | None = None,
    ):
        """Adapter for update_file tool"""
        from app.models.file_models import FileUpdate

        user = await get_user_from_auth(ctx)

        updated_dict = filter_none_values(
            filename=filename,
            description=description,
            data=data,
            mime_type=mime_type,
            tags=tags,
            project_id=project_id,
        )

        file_data = FileUpdate(**updated_dict)

        file = await self.file_service.update_file(
            user_id=user.id,
            file_id=file_id,
            file_data=file_data,
        )

        return file

    async def delete_file(self, file_id: int, ctx: Context) -> dict:
        """Adapter for delete_file tool"""
        user = await get_user_from_auth(ctx)

        result = await self.file_service.delete_file(
            user_id=user.id, file_id=file_id,
        )

        return {"success": result, "deleted_id": file_id}


def create_file_adapters(file_service, user_service: UserService) -> dict[str, Any]:
    """Create all file tool adapters and return as dict"""
    adapters = FileToolAdapters(file_service, user_service)
    return {
        "create_file": adapters.create_file,
        "get_file": adapters.get_file,
        "list_files": adapters.list_files,
        "update_file": adapters.update_file,
        "delete_file": adapters.delete_file,
    }


# ============================================================================
# Skill Tool Adapters
# ============================================================================


class SkillToolAdapters:
    """Wraps skill service methods as registry-compatible callables"""

    def __init__(self, skill_service, user_service: UserService):
        self.skill_service = skill_service
        self.user_service = user_service

    async def create_skill(
        self,
        name: str,
        description: str,
        content: str,
        ctx: Context,
        license: str | None = None,
        compatibility: str | None = None,
        allowed_tools: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        importance: int = 7,
        project_id: int | None = None,
    ):
        """Adapter for create_skill tool"""
        from app.models.skill_models import SkillCreate

        user = await get_user_from_auth(ctx)

        skill_data = SkillCreate(
            name=name,
            description=description,
            content=content,
            license=license,
            compatibility=compatibility,
            allowed_tools=allowed_tools,
            metadata=metadata,
            tags=tags or [],
            importance=importance,
            project_id=project_id,
        )

        skill = await self.skill_service.create_skill(
            user_id=user.id, skill_data=skill_data,
        )

        return skill

    async def get_skill(self, skill_id: int, ctx: Context):
        """Adapter for get_skill tool"""
        user = await get_user_from_auth(ctx)

        skill = await self.skill_service.get_skill(
            user_id=user.id, skill_id=skill_id,
        )

        return skill

    async def list_skills(
        self,
        ctx: Context,
        project_id: int | None = None,
        tags: list[str] | None = None,
        importance_threshold: int | None = None,
    ) -> dict:
        """Adapter for list_skills tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.list_skills(
            user_id=user.id,
            project_id=project_id,
            tags=tags,
            importance_threshold=importance_threshold,
        )

        return {"skills": result, "total_count": len(result)}

    async def update_skill(
        self,
        skill_id: int,
        ctx: Context,
        name: str | None = None,
        description: str | None = None,
        content: str | None = None,
        license: str | None = None,
        compatibility: str | None = None,
        allowed_tools: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        importance: int | None = None,
        project_id: int | None = None,
    ):
        """Adapter for update_skill tool"""
        from app.models.skill_models import SkillUpdate

        user = await get_user_from_auth(ctx)

        updated_dict = filter_none_values(
            name=name,
            description=description,
            content=content,
            license=license,
            compatibility=compatibility,
            allowed_tools=allowed_tools,
            metadata=metadata,
            tags=tags,
            importance=importance,
            project_id=project_id,
        )

        skill_data = SkillUpdate(**updated_dict)

        skill = await self.skill_service.update_skill(
            user_id=user.id,
            skill_id=skill_id,
            skill_data=skill_data,
        )

        return skill

    async def delete_skill(self, skill_id: int, ctx: Context) -> dict:
        """Adapter for delete_skill tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.delete_skill(
            user_id=user.id, skill_id=skill_id,
        )

        return {"success": result, "deleted_id": skill_id}

    async def search_skills(
        self,
        query: str,
        ctx: Context,
        k: int = 5,
        project_id: int | None = None,
    ) -> dict:
        """Adapter for search_skills tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.search_skills(
            user_id=user.id,
            query=query,
            k=k,
            project_id=project_id,
        )

        return {
            "skills": result,
            "total_count": len(result),
            "search_query": query,
        }

    async def import_skill(
        self,
        skill_md_content: str,
        ctx: Context,
        project_id: int | None = None,
        importance: int = 7,
    ):
        """Adapter for import_skill tool"""
        user = await get_user_from_auth(ctx)

        skill = await self.skill_service.import_skill(
            user_id=user.id,
            skill_md_content=skill_md_content,
            project_id=project_id,
            importance=importance,
        )

        return skill

    async def export_skill(self, skill_id: int, ctx: Context) -> str:
        """Adapter for export_skill tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.export_skill(
            user_id=user.id, skill_id=skill_id,
        )

        return result

    async def link_skill_to_memory(
        self, skill_id: int, memory_id: int, ctx: Context,
    ) -> dict:
        """Adapter for link_skill_to_memory tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.link_skill_to_memory(
            user_id=user.id, skill_id=skill_id, memory_id=memory_id,
        )

        return result

    async def unlink_skill_from_memory(
        self, skill_id: int, memory_id: int, ctx: Context,
    ) -> dict:
        """Adapter for unlink_skill_from_memory tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.unlink_skill_from_memory(
            user_id=user.id, skill_id=skill_id, memory_id=memory_id,
        )

        return result

    async def link_skill_to_file(
        self, skill_id: int, file_id: int, ctx: Context,
    ) -> dict:
        """Adapter for link_skill_to_file tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.link_skill_to_file(
            user_id=user.id, skill_id=skill_id, file_id=file_id,
        )

        return result

    async def unlink_skill_from_file(
        self, skill_id: int, file_id: int, ctx: Context,
    ) -> dict:
        """Adapter for unlink_skill_from_file tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.unlink_skill_from_file(
            user_id=user.id, skill_id=skill_id, file_id=file_id,
        )

        return result

    async def link_skill_to_code_artifact(
        self, skill_id: int, code_artifact_id: int, ctx: Context,
    ) -> dict:
        """Adapter for link_skill_to_code_artifact tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.link_skill_to_code_artifact(
            user_id=user.id, skill_id=skill_id, code_artifact_id=code_artifact_id,
        )

        return result

    async def unlink_skill_from_code_artifact(
        self, skill_id: int, code_artifact_id: int, ctx: Context,
    ) -> dict:
        """Adapter for unlink_skill_from_code_artifact tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.unlink_skill_from_code_artifact(
            user_id=user.id, skill_id=skill_id, code_artifact_id=code_artifact_id,
        )

        return result

    async def link_skill_to_document(
        self, skill_id: int, document_id: int, ctx: Context,
    ) -> dict:
        """Adapter for link_skill_to_document tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.link_skill_to_document(
            user_id=user.id, skill_id=skill_id, document_id=document_id,
        )

        return result

    async def unlink_skill_from_document(
        self, skill_id: int, document_id: int, ctx: Context,
    ) -> dict:
        """Adapter for unlink_skill_from_document tool"""
        user = await get_user_from_auth(ctx)

        result = await self.skill_service.unlink_skill_from_document(
            user_id=user.id, skill_id=skill_id, document_id=document_id,
        )

        return result


def create_skill_adapters(skill_service, user_service: UserService) -> dict[str, Any]:
    """Create all skill tool adapters and return as dict"""
    adapters = SkillToolAdapters(skill_service, user_service)
    return {
        "create_skill": adapters.create_skill,
        "get_skill": adapters.get_skill,
        "list_skills": adapters.list_skills,
        "update_skill": adapters.update_skill,
        "delete_skill": adapters.delete_skill,
        "search_skills": adapters.search_skills,
        "import_skill": adapters.import_skill,
        "export_skill": adapters.export_skill,
        "link_skill_to_memory": adapters.link_skill_to_memory,
        "unlink_skill_from_memory": adapters.unlink_skill_from_memory,
        "link_skill_to_file": adapters.link_skill_to_file,
        "unlink_skill_from_file": adapters.unlink_skill_from_file,
        "link_skill_to_code_artifact": adapters.link_skill_to_code_artifact,
        "unlink_skill_from_code_artifact": adapters.unlink_skill_from_code_artifact,
        "link_skill_to_document": adapters.link_skill_to_document,
        "unlink_skill_from_document": adapters.unlink_skill_from_document,
    }
