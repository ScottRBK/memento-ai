"""
Tool Metadata Registry - Registration helpers for tool metadata

This module provides helper functions for registering tools with the registry,
including detailed parameter metadata for discovery and documentation.
"""
from typing import Dict, List, Any

from app.routes.mcp.tool_registry import ToolRegistry
from app.models.tool_registry_models import ToolCategory, ToolParameter
from app.routes.mcp.tool_adapters import create_user_adapters, create_memory_adapters
from app.services.user_service import UserService
from app.services.memory_service import MemoryService
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


def register_simplified_tool(
    registry: ToolRegistry,
    name: str,
    category: ToolCategory,
    description: str,
    parameters: List[dict],
    returns: str,
    implementation: Any,
    examples: List[str] = None,
    tags: List[str] = None,
):
    """
    Helper to register tools with simplified parameter definitions

    Args:
        registry: ToolRegistry instance
        name: Tool name
        category: Tool category
        description: Tool description
        parameters: List of parameter dicts with simplified format
        returns: Return value description
        implementation: Async callable
        examples: Usage examples
        tags: Tags for categorization
    """
    tool_params = [
        ToolParameter(
            name=p["name"],
            type=p["type"],
            description=p.get("description", ""),
            required=p.get("required", False),
            default=p.get("default"),
            example=p.get("example"),
        )
        for p in parameters
    ]

    registry.register(
        name=name,
        category=category,
        description=description,
        parameters=tool_params,
        returns=returns,
        implementation=implementation,
        examples=examples or [],
        tags=tags or [],
    )


# ============================================================================
# User Tools Metadata
# ============================================================================

def register_user_tools_metadata(
    registry: ToolRegistry,
    adapters: Dict[str, Any]
):
    """Register user tool metadata and implementations"""

    tools = [
        {
            "name": "get_current_user",
            "description": "Returns information about the current authenticated user",
            "parameters": [
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
            ],
            "returns": "UserResponse with id, external_id, name, email, notes, timestamps",
            "examples": [
                'execute_forgetful_tool("get_current_user", {})',
            ],
            "tags": ["user", "authentication", "context"],
        },
        {
            "name": "update_user_notes",
            "description": "Update the notes field for the current user",
            "parameters": [
                {
                    "name": "user_notes",
                    "type": "str",
                    "description": "The new notes content to store for the user",
                    "required": True,
                    "example": "User prefers TypeScript, uses VSCode, timezone: PST"
                },
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
            ],
            "returns": "Updated UserResponse with new notes value",
            "examples": [
                'execute_forgetful_tool("update_user_notes", {"user_notes": "Prefers React over Vue"})',
            ],
            "tags": ["user", "update", "preferences"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.USER,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
        )

    logger.info(f"Registered {len(tools)} user tools")


# ============================================================================
# Memory Tools Metadata
# ============================================================================

def register_memory_tools_metadata(
    registry: ToolRegistry,
    adapters: Dict[str, Any]
):
    """Register memory tool metadata and implementations"""

    tools = [
        {
            "name": "create_memory",
            "description": "Create atomic memory with auto-linking and lifecycle management. Stores single concepts (<400 words).",
            "parameters": [
                {
                    "name": "title",
                    "type": "str",
                    "description": "Memory title (max 200 characters)",
                    "required": True,
                    "example": "TTS preference: XTTS-v2"
                },
                {
                    "name": "content",
                    "type": "str",
                    "description": "Memory content (max 2000 characters, ~300-400 words) - single concept",
                    "required": True,
                    "example": "Selected XTTS-v2 for voice cloning - provides high quality output with low latency"
                },
                {
                    "name": "context",
                    "type": "str",
                    "description": "WHY this memory matters, HOW it relates, WHAT implications (max 500 characters)",
                    "required": True,
                    "example": "Decision made while implementing voice integration with AI agent"
                },
                {
                    "name": "keywords",
                    "type": "List[str]",
                    "description": "Search keywords for semantic matching (max 10)",
                    "required": True,
                    "example": ["tts", "voice-cloning", "xtts"]
                },
                {
                    "name": "tags",
                    "type": "List[str]",
                    "description": "Categorization tags (max 10)",
                    "required": True,
                    "example": ["decision", "preference", "audio"]
                },
                {
                    "name": "importance",
                    "type": "int",
                    "description": "Score 1-10. 9-10: Personal/foundational, 8-9: Critical solutions, 7-8: Useful patterns, 6-7: Milestones",
                    "required": True,
                    "example": 9
                },
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
                {
                    "name": "project_ids",
                    "type": "Optional[List[int]]",
                    "description": "Project IDs to link (optional)",
                    "required": False,
                    "default": None,
                    "example": [1, 3]
                },
                {
                    "name": "code_artifact_ids",
                    "type": "Optional[List[int]]",
                    "description": "Code artifact IDs to link (optional)",
                    "required": False,
                    "default": None,
                    "example": [5]
                },
                {
                    "name": "document_ids",
                    "type": "Optional[List[int]]",
                    "description": "Document IDs to link (optional)",
                    "required": False,
                    "default": None,
                    "example": [2]
                },
            ],
            "returns": "MemoryCreateResponse with id, title, linked_memory_ids, similar_memories",
            "examples": [
                'execute_forgetful_tool("create_memory", {"title": "FastAPI auth pattern", "content": "Use JWT with httponly cookies...", "context": "Security decision", "keywords": ["auth", "jwt"], "tags": ["security"], "importance": 9})',
            ],
            "tags": ["memory", "create", "linking"],
        },
        {
            "name": "query_memory",
            "description": "Semantic search across memories to find relevant information",
            "parameters": [
                {
                    "name": "query",
                    "type": "str",
                    "description": "Natural language search query",
                    "required": True,
                    "example": "What did we decide about authentication?"
                },
                {
                    "name": "query_context",
                    "type": "str",
                    "description": "Context explaining why you're searching (improves ranking)",
                    "required": True,
                    "example": "Implementing login system for new API"
                },
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
                {
                    "name": "k",
                    "type": "int",
                    "description": "Number of primary results to return (1-20), use INSTEAD of LIMIT", 
                    "required": False,
                    "default": 3,
                    "example": 5
                },
                {
                    "name": "include_links",
                    "type": "bool",
                    "description": "Whether to include linked memories for context",
                    "required": False,
                    "default": True,
                    "example": True
                },
                {
                    "name": "max_links_per_primary",
                    "type": "int",
                    "description": "Maximum number of linked memories per primary memory",
                    "required": False,
                    "default": 5,
                    "example": 3
                },
                {
                    "name": "importance_threshold",
                    "type": "Optional[int]",
                    "description": "Minimum importance score (1-10) to include",
                    "required": False,
                    "default": None,
                    "example": 7
                },
                {
                    "name": "project_ids",
                    "type": "Optional[List[int]]",
                    "description": "Filter results to specific projects",
                    "required": False,
                    "default": None,
                    "example": [1, 2]
                },
                {
                    "name": "strict_project_filter",
                    "type": "bool",
                    "description": "If True, linked memories must also be in specified projects",
                    "required": False,
                    "default": False,
                    "example": False
                },
            ],
            "returns": "MemoryQueryResult with primary_memories, linked_memories, total_count, token_count, truncated flag",
            "examples": [
                'execute_forgetful_tool("query_memory", {"query": "authentication patterns", "query_context": "building API login", "k": 5})',
                'execute_forgetful_tool("query_memory", {"query": "database design", "query_context": "schema review", "importance_threshold": 8, "k": 3})',
            ],
            "tags": ["memory", "search", "semantic", "query"],
        },
        {
            "name": "update_memory",
            "description": "Update existing memory fields using PATCH semantics (only specified fields are updated)",
            "parameters": [
                {
                    "name": "memory_id",
                    "type": "int",
                    "description": "ID of the memory to update",
                    "required": True,
                    "example": 42
                },
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
                {
                    "name": "title",
                    "type": "Optional[str]",
                    "description": "New title (optional)",
                    "required": False,
                    "default": None,
                    "example": "Updated title"
                },
                {
                    "name": "content",
                    "type": "Optional[str]",
                    "description": "New content (optional)",
                    "required": False,
                    "default": None,
                    "example": "Updated content with new information"
                },
                {
                    "name": "context",
                    "type": "Optional[str]",
                    "description": "New context (optional)",
                    "required": False,
                    "default": None,
                    "example": "Updated context explanation"
                },
                {
                    "name": "keywords",
                    "type": "Optional[List[str]]",
                    "description": "New keywords - replaces existing (optional)",
                    "required": False,
                    "default": None,
                    "example": ["new", "keywords"]
                },
                {
                    "name": "tags",
                    "type": "Optional[List[str]]",
                    "description": "New tags - replaces existing (optional)",
                    "required": False,
                    "default": None,
                    "example": ["updated", "tag"]
                },
                {
                    "name": "importance",
                    "type": "Optional[int]",
                    "description": "New importance score 1-10 (optional)",
                    "required": False,
                    "default": None,
                    "example": 8
                },
                {
                    "name": "project_ids",
                    "type": "Optional[List[int]]",
                    "description": "New project IDs - replaces existing links (optional)",
                    "required": False,
                    "default": None,
                    "example": [1, 2]
                },
                {
                    "name": "code_artifact_ids",
                    "type": "Optional[List[int]]",
                    "description": "New code artifact IDs - replaces existing links (optional)",
                    "required": False,
                    "default": None,
                    "example": [5]
                },
                {
                    "name": "document_ids",
                    "type": "Optional[List[int]]",
                    "description": "New document IDs - replaces existing links (optional)",
                    "required": False,
                    "default": None,
                    "example": [3]
                },
            ],
            "returns": "Full Memory object after update",
            "examples": [
                'execute_forgetful_tool("update_memory", {"memory_id": 42, "importance": 9})',
                'execute_forgetful_tool("update_memory", {"memory_id": 42, "content": "Updated content", "tags": ["revised", "important"]})',
            ],
            "tags": ["memory", "update", "patch"],
        },
        {
            "name": "link_memories",
            "description": "Manually create bidirectional links between memories (symmetric linking)",
            "parameters": [
                {
                    "name": "memory_id",
                    "type": "int",
                    "description": "Source memory ID",
                    "required": True,
                    "example": 42
                },
                {
                    "name": "related_ids",
                    "type": "List[int]",
                    "description": "List of target memory IDs to link",
                    "required": True,
                    "example": [10, 15, 20]
                },
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
            ],
            "returns": "List of memory IDs that were successfully linked",
            "examples": [
                'execute_forgetful_tool("link_memories", {"memory_id": 42, "related_ids": [10, 15, 20]})',
            ],
            "tags": ["memory", "linking", "relationships"],
        },
        {
            "name": "get_memory",
            "description": "Retrieve complete memory details by ID",
            "parameters": [
                {
                    "name": "memory_id",
                    "type": "int",
                    "description": "ID of the memory to retrieve",
                    "required": True,
                    "example": 42
                },
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
            ],
            "returns": "Complete Memory object with all fields",
            "examples": [
                'execute_forgetful_tool("get_memory", {"memory_id": 42})',
            ],
            "tags": ["memory", "retrieve", "read"],
        },
        {
            "name": "mark_memory_obsolete",
            "description": "Mark a memory as obsolete (soft delete with audit trail)",
            "parameters": [
                {
                    "name": "memory_id",
                    "type": "int",
                    "description": "ID of the memory to mark as obsolete",
                    "required": True,
                    "example": 42
                },
                {
                    "name": "reason",
                    "type": "str",
                    "description": "Explanation for why this memory is obsolete",
                    "required": True,
                    "example": "Superseded by newer decision in memory #100"
                },
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
                {
                    "name": "superseded_by",
                    "type": "Optional[int]",
                    "description": "Optional ID of the replacement memory",
                    "required": False,
                    "default": None,
                    "example": 100
                },
            ],
            "returns": "Boolean indicating success",
            "examples": [
                'execute_forgetful_tool("mark_memory_obsolete", {"memory_id": 42, "reason": "Outdated approach", "superseded_by": 100})',
            ],
            "tags": ["memory", "delete", "obsolete", "lifecycle"],
        },
        {
            "name": "get_recent_memories",
            "description": "Retrieve most recent memories sorted by creation timestamp (newest first)",
            "parameters": [
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
                {
                    "name": "limit",
                    "type": "int",
                    "description": "Maximum number of memories to return (1-100)",
                    "required": False,
                    "default": 10,
                    "example": 10
                },
                {
                    "name": "project_ids",
                    "type": "Optional[List[int]]",
                    "description": "Optional filter to specific projects",
                    "required": False,
                    "default": None,
                    "example": [1, 3]
                },
            ],
            "returns": "List of Memory objects sorted by created_at DESC",
            "examples": [
                'execute_forgetful_tool("get_recent_memories", {"limit": 5})',
                'execute_forgetful_tool("get_recent_memories", {"limit": 10, "project_ids": [1, 2]})',
            ],
            "tags": ["memory", "query", "recency", "timeline"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.MEMORY,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
        )

    logger.info(f"Registered {len(tools)} memory tools")


# ============================================================================
# Master Registration Function
# ============================================================================

def register_all_tools_metadata(
    registry: ToolRegistry,
    user_service: UserService,
    memory_service: MemoryService,
    project_service,
    code_artifact_service,
    document_service,
    entity_service,
):
    """
    Register all tool metadata and implementations

    Args:
        registry: ToolRegistry instance to register tools with
        user_service: UserService instance
        memory_service: MemoryService instance
        project_service: ProjectService instance
        code_artifact_service: CodeArtifactService instance
        document_service: DocumentService instance
        entity_service: EntityService instance
    """
    logger.info("Starting tool registration")

    # Import adapter factory functions
    from app.routes.mcp.tool_adapters import (
        create_project_adapters,
        create_code_artifact_adapters,
        create_document_adapters,
        create_entity_adapters,
    )

    # Create adapters for all categories
    user_adapters = create_user_adapters(user_service)
    memory_adapters = create_memory_adapters(memory_service, user_service)
    project_adapters = create_project_adapters(project_service, user_service)
    code_artifact_adapters = create_code_artifact_adapters(code_artifact_service, user_service)
    document_adapters = create_document_adapters(document_service, user_service)
    entity_adapters = create_entity_adapters(entity_service, user_service)

    # Register tools by category
    register_user_tools_metadata(registry, user_adapters)
    register_memory_tools_metadata(registry, memory_adapters)
    register_project_tools_metadata(registry, project_adapters)
    register_code_artifact_tools_metadata(registry, code_artifact_adapters)
    register_document_tools_metadata(registry, document_adapters)
    register_entity_tools_metadata(registry, entity_adapters)

    # Log summary
    categories = registry.list_categories()
    total = sum(categories.values())
    logger.info(f"Tool registration complete: {total} tools across {len(categories)} categories")
    logger.info(f"Categories: {categories}")


# ============================================================================
# Project Tools Metadata
# ============================================================================

def register_project_tools_metadata(
    registry: ToolRegistry,
    adapters: Dict[str, Any]
):
    """Register project tool metadata and implementations"""

    tools = [
        {
            "name": "create_project",
            "description": "Create new project for organizing memories, code artifacts, and documents by context",
            "parameters": [
                {"name": "name", "type": "str", "description": "Project name (max 500 chars)", "required": True, "example": "forgetful"},
                {"name": "description", "type": "str", "description": "Purpose/scope overview (max ~5000 chars)", "required": True, "example": "MIT-licensed memory service"},
                {"name": "project_type", "type": "ProjectType", "description": "Project category (personal, work, learning, development, infrastructure, template, product, marketing, finance, documentation, development-environment, third-party-library, open-source)", "required": True, "example": "development"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "status", "type": "ProjectStatus", "description": "Project lifecycle status (active, archived, completed)", "required": False, "default": "active", "example": "active"},
                {"name": "repo_name", "type": "Optional[str]", "description": "GitHub repository in 'owner/repo' format", "required": False, "default": None, "example": "scottrbk/forgetful"},
                {"name": "notes", "type": "Optional[str]", "description": "Workflow notes, setup instructions (max ~4000 chars)", "required": False, "default": None, "example": "Uses uv for dependency management"},
            ],
            "returns": "Complete Project with id, timestamps, and memory_count",
            "examples": [
                'execute_forgetful_tool("create_project", {"name": "my-project", "description": "A new project", "project_type": "development"})',
            ],
            "tags": ["project", "create", "organization"],
        },
        {
            "name": "update_project",
            "description": "Update project metadata using PATCH semantics (only specified fields are updated)",
            "parameters": [
                {"name": "project_id", "type": "int", "description": "ID of the project to update", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "name", "type": "Optional[str]", "description": "New project name", "required": False, "default": None, "example": "updated-project"},
                {"name": "description", "type": "Optional[str]", "description": "New description", "required": False, "default": None, "example": "Updated description"},
                {"name": "project_type", "type": "Optional[ProjectType]", "description": "New project type", "required": False, "default": None, "example": "work"},
                {"name": "status", "type": "Optional[ProjectStatus]", "description": "New status", "required": False, "default": None, "example": "archived"},
                {"name": "repo_name", "type": "Optional[str]", "description": "New repository name", "required": False, "default": None, "example": "user/new-repo"},
                {"name": "notes", "type": "Optional[str]", "description": "New notes", "required": False, "default": None, "example": "Additional notes"},
            ],
            "returns": "Updated Project object",
            "examples": [
                'execute_forgetful_tool("update_project", {"project_id": 1, "status": "archived"})',
            ],
            "tags": ["project", "update", "patch"],
        },
        {
            "name": "delete_project",
            "description": "Delete project while preserving linked memories",
            "parameters": [
                {"name": "project_id", "type": "int", "description": "ID of the project to delete", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with deletion confirmation",
            "examples": [
                'execute_forgetful_tool("delete_project", {"project_id": 1})',
            ],
            "tags": ["project", "delete", "remove"],
        },
        {
            "name": "list_projects",
            "description": "List projects with optional status/repository filtering",
            "parameters": [
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "status", "type": "Optional[ProjectStatus]", "description": "Filter by status (active, archived, completed)", "required": False, "default": None, "example": "active"},
                {"name": "repo_name", "type": "Optional[str]", "description": "Filter by repository name", "required": False, "default": None, "example": "scottrbk/forgetful"},
            ],
            "returns": "Dictionary with projects list and count",
            "examples": [
                'execute_forgetful_tool("list_projects", {})',
                'execute_forgetful_tool("list_projects", {"status": "active"})',
            ],
            "tags": ["project", "list", "query"],
        },
        {
            "name": "get_project",
            "description": "Retrieve complete project details by ID",
            "parameters": [
                {"name": "project_id", "type": "int", "description": "ID of the project to retrieve", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Complete Project object with all details",
            "examples": [
                'execute_forgetful_tool("get_project", {"project_id": 1})',
            ],
            "tags": ["project", "retrieve", "read"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.PROJECT,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
        )

    logger.info(f"Registered {len(tools)} project tools")


# ============================================================================
# CodeArtifact Tools Metadata
# ============================================================================

def register_code_artifact_tools_metadata(
    registry: ToolRegistry,
    adapters: Dict[str, Any]
):
    """Register code artifact tool metadata and implementations"""

    tools = [
        {
            "name": "create_code_artifact",
            "description": "Create code artifact for storing reusable code snippets and patterns",
            "parameters": [
                {"name": "title", "type": "str", "description": "Artifact title", "required": True, "example": "JWT Middleware"},
                {"name": "description", "type": "str", "description": "What the code does and when to use it", "required": True, "example": "FastAPI middleware for JWT authentication"},
                {"name": "code", "type": "str", "description": "The actual code content", "required": True, "example": "async def jwt_middleware(request, call_next): ..."},
                {"name": "language", "type": "str", "description": "Programming language (python, javascript, typescript, etc.)", "required": True, "example": "python"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Tags for categorization", "required": False, "default": None, "example": ["middleware", "auth"]},
                {"name": "project_id", "type": "Optional[int]", "description": "Link to project", "required": False, "default": None, "example": 1},
            ],
            "returns": "CodeArtifact with id and timestamps",
            "examples": [
                'execute_forgetful_tool("create_code_artifact", {"title": "Helper function", "description": "Utility helper", "code": "def helper(): pass", "language": "python"})',
            ],
            "tags": ["code", "create", "artifact"],
        },
        {
            "name": "get_code_artifact",
            "description": "Retrieve code artifact by ID with complete details",
            "parameters": [
                {"name": "artifact_id", "type": "int", "description": "ID of the artifact to retrieve", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Complete CodeArtifact object",
            "examples": [
                'execute_forgetful_tool("get_code_artifact", {"artifact_id": 1})',
            ],
            "tags": ["code", "retrieve", "read"],
        },
        {
            "name": "list_code_artifacts",
            "description": "List code artifacts with optional filtering by project, language, or tags",
            "parameters": [
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "project_id", "type": "Optional[int]", "description": "Filter by project", "required": False, "default": None, "example": 1},
                {"name": "language", "type": "Optional[str]", "description": "Filter by language", "required": False, "default": None, "example": "python"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Filter by tags", "required": False, "default": None, "example": ["auth", "middleware"]},
            ],
            "returns": "Dictionary with artifacts list and count",
            "examples": [
                'execute_forgetful_tool("list_code_artifacts", {})',
                'execute_forgetful_tool("list_code_artifacts", {"language": "python"})',
            ],
            "tags": ["code", "list", "query"],
        },
        {
            "name": "update_code_artifact",
            "description": "Update code artifact (PATCH semantics - only provided fields changed)",
            "parameters": [
                {"name": "artifact_id", "type": "int", "description": "ID of the artifact to update", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "title", "type": "Optional[str]", "description": "New title", "required": False, "default": None, "example": "Updated title"},
                {"name": "description", "type": "Optional[str]", "description": "New description", "required": False, "default": None, "example": "Updated description"},
                {"name": "code", "type": "Optional[str]", "description": "New code", "required": False, "default": None, "example": "def updated(): pass"},
                {"name": "language", "type": "Optional[str]", "description": "New language", "required": False, "default": None, "example": "typescript"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "New tags (replaces existing)", "required": False, "default": None, "example": ["updated"]},
                {"name": "project_id", "type": "Optional[int]", "description": "New project link", "required": False, "default": None, "example": 2},
            ],
            "returns": "Updated CodeArtifact object",
            "examples": [
                'execute_forgetful_tool("update_code_artifact", {"artifact_id": 1, "tags": ["updated", "refactored"]})',
            ],
            "tags": ["code", "update", "patch"],
        },
        {
            "name": "delete_code_artifact",
            "description": "Delete code artifact (cascades memory associations)",
            "parameters": [
                {"name": "artifact_id", "type": "int", "description": "ID of the artifact to delete", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with deletion confirmation",
            "examples": [
                'execute_forgetful_tool("delete_code_artifact", {"artifact_id": 1})',
            ],
            "tags": ["code", "delete", "remove"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.CODE_ARTIFACT,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
        )

    logger.info(f"Registered {len(tools)} code artifact tools")


# ============================================================================
# Document Tools Metadata
# ============================================================================

def register_document_tools_metadata(
    registry: ToolRegistry,
    adapters: Dict[str, Any]
):
    """Register document tool metadata and implementations"""

    tools = [
        {
            "name": "create_document",
            "description": "Create document for storing long-form content and documentation",
            "parameters": [
                {"name": "title", "type": "str", "description": "Document title", "required": True, "example": "API Documentation"},
                {"name": "description", "type": "str", "description": "Brief overview of the document", "required": True, "example": "REST API endpoints documentation"},
                {"name": "content", "type": "str", "description": "The document content (long-form text)", "required": True, "example": "# API Endpoints\n\n## GET /users..."},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "document_type", "type": "str", "description": "Document type (text, markdown, code, etc.)", "required": False, "default": "text", "example": "markdown"},
                {"name": "filename", "type": "Optional[str]", "description": "Optional filename", "required": False, "default": None, "example": "api-docs.md"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Tags for categorization", "required": False, "default": None, "example": ["api", "documentation"]},
                {"name": "project_id", "type": "Optional[int]", "description": "Link to project", "required": False, "default": None, "example": 1},
            ],
            "returns": "Document with id and timestamps",
            "examples": [
                'execute_forgetful_tool("create_document", {"title": "Notes", "description": "Project notes", "content": "# Notes\\n\\nSome content..."})',
            ],
            "tags": ["document", "create", "content"],
        },
        {
            "name": "get_document",
            "description": "Retrieve document by ID with complete content",
            "parameters": [
                {"name": "document_id", "type": "int", "description": "ID of the document to retrieve", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Complete Document object with content",
            "examples": [
                'execute_forgetful_tool("get_document", {"document_id": 1})',
            ],
            "tags": ["document", "retrieve", "read"],
        },
        {
            "name": "list_documents",
            "description": "List documents with optional filtering by project, type, or tags",
            "parameters": [
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "project_id", "type": "Optional[int]", "description": "Filter by project", "required": False, "default": None, "example": 1},
                {"name": "document_type", "type": "Optional[str]", "description": "Filter by type", "required": False, "default": None, "example": "markdown"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Filter by tags", "required": False, "default": None, "example": ["documentation"]},
            ],
            "returns": "Dictionary with documents list and count",
            "examples": [
                'execute_forgetful_tool("list_documents", {})',
                'execute_forgetful_tool("list_documents", {"document_type": "markdown"})',
            ],
            "tags": ["document", "list", "query"],
        },
        {
            "name": "update_document",
            "description": "Update document (PATCH semantics - only provided fields changed)",
            "parameters": [
                {"name": "document_id", "type": "int", "description": "ID of the document to update", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "title", "type": "Optional[str]", "description": "New title", "required": False, "default": None, "example": "Updated title"},
                {"name": "description", "type": "Optional[str]", "description": "New description", "required": False, "default": None, "example": "Updated description"},
                {"name": "content", "type": "Optional[str]", "description": "New content", "required": False, "default": None, "example": "# Updated\\n\\nNew content..."},
                {"name": "document_type", "type": "Optional[str]", "description": "New type", "required": False, "default": None, "example": "text"},
                {"name": "filename", "type": "Optional[str]", "description": "New filename", "required": False, "default": None, "example": "new-file.md"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "New tags (replaces existing)", "required": False, "default": None, "example": ["updated"]},
                {"name": "project_id", "type": "Optional[int]", "description": "New project link", "required": False, "default": None, "example": 2},
            ],
            "returns": "Updated Document object",
            "examples": [
                'execute_forgetful_tool("update_document", {"document_id": 1, "content": "Updated content"})',
            ],
            "tags": ["document", "update", "patch"],
        },
        {
            "name": "delete_document",
            "description": "Delete document (cascades memory associations)",
            "parameters": [
                {"name": "document_id", "type": "int", "description": "ID of the document to delete", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with deletion confirmation",
            "examples": [
                'execute_forgetful_tool("delete_document", {"document_id": 1})',
            ],
            "tags": ["document", "delete", "remove"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.DOCUMENT,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
        )

    logger.info(f"Registered {len(tools)} document tools")


# ============================================================================
# Entity Tools Metadata
# ============================================================================

def register_entity_tools_metadata(
    registry: ToolRegistry,
    adapters: Dict[str, Any]
):
    """Register entity tool metadata and implementations"""

    tools = [
        {
            "name": "create_entity",
            "description": "Create entity representing a real-world entity (organization, individual, team, device)",
            "parameters": [
                {"name": "name", "type": "str", "description": "Entity name", "required": True, "example": "Anthropic"},
                {"name": "entity_type", "type": "str", "description": "Entity type (organization, individual, team, device, other)", "required": True, "example": "organization"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "custom_type", "type": "Optional[str]", "description": "Custom type if 'other' is selected", "required": False, "default": None, "example": "ai-company"},
                {"name": "notes", "type": "Optional[str]", "description": "Additional notes", "required": False, "default": None, "example": "AI safety and research company"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Tags for categorization", "required": False, "default": None, "example": ["ai", "research"]},
                {"name": "project_id", "type": "Optional[int]", "description": "Link to project", "required": False, "default": None, "example": 1},
            ],
            "returns": "Entity with id and timestamps",
            "examples": [
                'execute_forgetful_tool("create_entity", {"name": "Anthropic", "entity_type": "organization"})',
            ],
            "tags": ["entity", "create", "knowledge-graph"],
        },
        {
            "name": "get_entity",
            "description": "Retrieve entity by ID with complete details",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "ID of the entity to retrieve", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Complete Entity object",
            "examples": [
                'execute_forgetful_tool("get_entity", {"entity_id": 1})',
            ],
            "tags": ["entity", "retrieve", "read"],
        },
        {
            "name": "list_entities",
            "description": "List entities with optional filtering by project, type, or tags",
            "parameters": [
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "project_id", "type": "Optional[int]", "description": "Filter by project", "required": False, "default": None, "example": 1},
                {"name": "entity_type", "type": "Optional[str]", "description": "Filter by type", "required": False, "default": None, "example": "organization"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Filter by tags", "required": False, "default": None, "example": ["ai"]},
            ],
            "returns": "Dictionary with entities list and count",
            "examples": [
                'execute_forgetful_tool("list_entities", {})',
                'execute_forgetful_tool("list_entities", {"entity_type": "organization"})',
            ],
            "tags": ["entity", "list", "query"],
        },
        {
            "name": "search_entities",
            "description": "Search entities by name using text matching (case-insensitive)",
            "parameters": [
                {"name": "query", "type": "str", "description": "Text to search for in entity name", "required": True, "example": "tech"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "entity_type", "type": "Optional[str]", "description": "Filter by entity type", "required": False, "default": None, "example": "Organization"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Filter by tags (returns entities with ANY of these)", "required": False, "default": None, "example": ["startup"]},
                {"name": "limit", "type": "int", "description": "Maximum number of results (1-100)", "required": False, "default": 20, "example": 20},
            ],
            "returns": "Dictionary with entities list, total_count, search_query, and filters",
            "examples": [
                'execute_forgetful_tool("search_entities", {"query": "tech"})',
                'execute_forgetful_tool("search_entities", {"query": "server", "entity_type": "Device", "limit": 10})',
            ],
            "tags": ["entity", "search", "query", "text"],
        },
        {
            "name": "update_entity",
            "description": "Update existing entity (PATCH semantics - only provided fields changed)",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "ID of the entity to update", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "name", "type": "Optional[str]", "description": "New name", "required": False, "default": None, "example": "Updated name"},
                {"name": "entity_type", "type": "Optional[str]", "description": "New type", "required": False, "default": None, "example": "team"},
                {"name": "custom_type", "type": "Optional[str]", "description": "New custom type", "required": False, "default": None, "example": "custom"},
                {"name": "notes", "type": "Optional[str]", "description": "New notes", "required": False, "default": None, "example": "Updated notes"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "New tags (replaces existing)", "required": False, "default": None, "example": ["updated"]},
                {"name": "project_id", "type": "Optional[int]", "description": "New project link", "required": False, "default": None, "example": 2},
            ],
            "returns": "Updated Entity object",
            "examples": [
                'execute_forgetful_tool("update_entity", {"entity_id": 1, "notes": "Updated information"})',
            ],
            "tags": ["entity", "update", "patch"],
        },
        {
            "name": "delete_entity",
            "description": "Delete entity (cascade removes memory links and relationships)",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "ID of the entity to delete", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with deletion confirmation",
            "examples": [
                'execute_forgetful_tool("delete_entity", {"entity_id": 1})',
            ],
            "tags": ["entity", "delete", "remove"],
        },
        {
            "name": "link_entity_to_memory",
            "description": "Link entity to memory (establishes reference relationship)",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "ID of the entity", "required": True, "example": 1},
                {"name": "memory_id", "type": "int", "description": "ID of the memory", "required": True, "example": 5},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with link confirmation",
            "examples": [
                'execute_forgetful_tool("link_entity_to_memory", {"entity_id": 1, "memory_id": 5})',
            ],
            "tags": ["entity", "memory", "link"],
        },
        {
            "name": "unlink_entity_from_memory",
            "description": "Unlink entity from memory (removes reference relationship)",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "ID of the entity", "required": True, "example": 1},
                {"name": "memory_id", "type": "int", "description": "ID of the memory", "required": True, "example": 5},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with unlink confirmation",
            "examples": [
                'execute_forgetful_tool("unlink_entity_from_memory", {"entity_id": 1, "memory_id": 5})',
            ],
            "tags": ["entity", "memory", "unlink"],
        },
        {
            "name": "create_entity_relationship",
            "description": "Create typed relationship between two entities (knowledge graph edge)",
            "parameters": [
                {"name": "source_entity_id", "type": "int", "description": "Source entity ID", "required": True, "example": 1},
                {"name": "target_entity_id", "type": "int", "description": "Target entity ID", "required": True, "example": 2},
                {"name": "relationship_type", "type": "str", "description": "Relationship type (works_for, member_of, owns, reports_to, collaborates_with, etc.)", "required": True, "example": "works_for"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "strength", "type": "Optional[float]", "description": "Relationship strength (0.0-1.0)", "required": False, "default": None, "example": 0.9},
                {"name": "confidence", "type": "Optional[float]", "description": "Confidence level (0.0-1.0)", "required": False, "default": None, "example": 0.95},
                {"name": "metadata", "type": "Optional[Dict[str, Any]]", "description": "Additional metadata", "required": False, "default": None, "example": {"since": "2020"}},
            ],
            "returns": "EntityRelationship with id and timestamps",
            "examples": [
                'execute_forgetful_tool("create_entity_relationship", {"source_entity_id": 1, "target_entity_id": 2, "relationship_type": "works_for"})',
            ],
            "tags": ["entity", "relationship", "knowledge-graph"],
        },
        {
            "name": "get_entity_relationships",
            "description": "Get relationships for an entity (knowledge graph edges)",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "Entity ID", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "direction", "type": "Optional[str]", "description": "Filter by direction (outgoing, incoming, both)", "required": False, "default": None, "example": "outgoing"},
                {"name": "relationship_type", "type": "Optional[str]", "description": "Filter by type", "required": False, "default": None, "example": "works_for"},
            ],
            "returns": "Dictionary with relationships list",
            "examples": [
                'execute_forgetful_tool("get_entity_relationships", {"entity_id": 1})',
                'execute_forgetful_tool("get_entity_relationships", {"entity_id": 1, "direction": "outgoing"})',
            ],
            "tags": ["entity", "relationship", "query"],
        },
        {
            "name": "update_entity_relationship",
            "description": "Update entity relationship (PATCH semantics - only provided fields changed)",
            "parameters": [
                {"name": "relationship_id", "type": "int", "description": "Relationship ID", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "relationship_type", "type": "Optional[str]", "description": "New relationship type", "required": False, "default": None, "example": "collaborates_with"},
                {"name": "strength", "type": "Optional[float]", "description": "New strength", "required": False, "default": None, "example": 0.8},
                {"name": "confidence", "type": "Optional[float]", "description": "New confidence", "required": False, "default": None, "example": 0.9},
                {"name": "metadata", "type": "Optional[Dict[str, Any]]", "description": "New metadata", "required": False, "default": None, "example": {"updated": "2024"}},
            ],
            "returns": "Updated EntityRelationship object",
            "examples": [
                'execute_forgetful_tool("update_entity_relationship", {"relationship_id": 1, "strength": 0.95})',
            ],
            "tags": ["entity", "relationship", "update"],
        },
        {
            "name": "delete_entity_relationship",
            "description": "Delete entity relationship (removes knowledge graph edge)",
            "parameters": [
                {"name": "relationship_id", "type": "int", "description": "Relationship ID to delete", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with deletion confirmation",
            "examples": [
                'execute_forgetful_tool("delete_entity_relationship", {"relationship_id": 1})',
            ],
            "tags": ["entity", "relationship", "delete"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.ENTITY,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
        )

    logger.info(f"Registered {len(tools)} entity tools")
