"""Tool Metadata Registry - Registration helpers for tool metadata

This module provides helper functions for registering tools with the registry,
including detailed parameter metadata for discovery and documentation.
"""
from typing import Any

from app.config.logging_config import logging
from app.models.tool_registry_models import ToolCategory, ToolParameter
from app.routes.mcp.tool_adapters import (
    create_file_adapters,
    create_memory_adapters,
    create_plan_adapters,
    create_skill_adapters,
    create_task_adapters,
    create_user_adapters,
)
from app.routes.mcp.tool_registry import ToolRegistry
from app.services.memory_service import MemoryService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


def register_simplified_tool(
    registry: ToolRegistry,
    name: str,
    category: ToolCategory,
    description: str,
    parameters: list[dict],
    returns: str,
    implementation: Any,
    examples: list[str] = None,
    tags: list[str] = None,
    mutates: bool = False,
):
    """Helper to register tools with simplified parameter definitions

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
        mutates: Whether this tool mutates state (write operation)
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
        mutates=mutates,
    )


# ============================================================================
# User Tools Metadata
# ============================================================================

def register_user_tools_metadata(
    registry: ToolRegistry,
    adapters: dict[str, Any],
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
            "mutates": True,
            "description": "Update the notes field for the current user",
            "parameters": [
                {
                    "name": "user_notes",
                    "type": "str",
                    "description": "The new notes content to store for the user",
                    "required": True,
                    "example": "User prefers TypeScript, uses VSCode, timezone: PST",
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
            mutates=tool_def.get("mutates", False),
        )

    logger.info(f"Registered {len(tools)} user tools")


# ============================================================================
# Memory Tools Metadata
# ============================================================================

def register_memory_tools_metadata(
    registry: ToolRegistry,
    adapters: dict[str, Any],
):
    """Register memory tool metadata and implementations"""
    tools = [
        {
            "name": "create_memory",
            "mutates": True,
            "description": "Create atomic memory with auto-linking and lifecycle management. Stores single concepts (<400 words).",
            "parameters": [
                {
                    "name": "title",
                    "type": "str",
                    "description": "Memory title (max 200 characters)",
                    "required": True,
                    "example": "TTS preference: XTTS-v2",
                },
                {
                    "name": "content",
                    "type": "str",
                    "description": "Memory content (max 2000 characters, ~300-400 words) - single concept",
                    "required": True,
                    "example": "Selected XTTS-v2 for voice cloning - provides high quality output with low latency",
                },
                {
                    "name": "context",
                    "type": "str",
                    "description": "WHY this memory matters, HOW it relates, WHAT implications (max 500 characters)",
                    "required": True,
                    "example": "Decision made while implementing voice integration with AI agent",
                },
                {
                    "name": "keywords",
                    "type": "List[str]",
                    "description": "Search keywords for semantic matching (max 10)",
                    "required": True,
                    "example": ["tts", "voice-cloning", "xtts"],
                },
                {
                    "name": "tags",
                    "type": "List[str]",
                    "description": "Categorization tags (max 10)",
                    "required": True,
                    "example": ["decision", "preference", "audio"],
                },
                {
                    "name": "importance",
                    "type": "int",
                    "description": "Score 1-10. 9-10: Personal/foundational, 8-9: Critical solutions, 7-8: Useful patterns, 6-7: Milestones",
                    "required": True,
                    "example": 9,
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
                    "example": [1, 3],
                },
                {
                    "name": "code_artifact_ids",
                    "type": "Optional[List[int]]",
                    "description": "Code artifact IDs to link (optional)",
                    "required": False,
                    "default": None,
                    "example": [5],
                },
                {
                    "name": "document_ids",
                    "type": "Optional[List[int]]",
                    "description": "Document IDs to link (optional)",
                    "required": False,
                    "default": None,
                    "example": [2],
                },
                {
                    "name": "source_repo",
                    "type": "Optional[str]",
                    "description": "Repository/project source (e.g., 'owner/repo') for provenance tracking",
                    "required": False,
                    "default": None,
                    "example": "scottrbk/forgetful",
                },
                {
                    "name": "source_files",
                    "type": "Optional[List[str]]",
                    "description": "Files that informed this memory (list of paths) for provenance tracking",
                    "required": False,
                    "default": None,
                    "example": ["src/main.py", "tests/test.py"],
                },
                {
                    "name": "source_url",
                    "type": "Optional[str]",
                    "description": "URL to original source material for provenance tracking",
                    "required": False,
                    "default": None,
                    "example": "https://github.com/owner/repo/blob/main/README.md",
                },
                {
                    "name": "confidence",
                    "type": "Optional[float]",
                    "description": "Encoding confidence score (0.0-1.0) for provenance tracking",
                    "required": False,
                    "default": None,
                    "example": 0.85,
                },
                {
                    "name": "encoding_agent",
                    "type": "Optional[str]",
                    "description": "Agent/process that created this memory for provenance tracking",
                    "required": False,
                    "default": None,
                    "example": "claude-sonnet-4-20250514",
                },
                {
                    "name": "encoding_version",
                    "type": "Optional[str]",
                    "description": "Version of encoding process/prompt for provenance tracking",
                    "required": False,
                    "default": None,
                    "example": "0.1.0",
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
                    "example": "What did we decide about authentication?",
                },
                {
                    "name": "query_context",
                    "type": "str",
                    "description": "Context explaining why you're searching (improves ranking)",
                    "required": True,
                    "example": "Implementing login system for new API",
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
                    "example": 5,
                },
                {
                    "name": "include_links",
                    "type": "bool",
                    "description": "Whether to include linked memories for context",
                    "required": False,
                    "default": True,
                    "example": True,
                },
                {
                    "name": "max_links_per_primary",
                    "type": "int",
                    "description": "Maximum number of linked memories per primary memory",
                    "required": False,
                    "default": 5,
                    "example": 3,
                },
                {
                    "name": "importance_threshold",
                    "type": "Optional[int]",
                    "description": "Minimum importance score (1-10) to include",
                    "required": False,
                    "default": None,
                    "example": 7,
                },
                {
                    "name": "project_ids",
                    "type": "Optional[List[int]]",
                    "description": "Filter results to specific projects",
                    "required": False,
                    "default": None,
                    "example": [1, 2],
                },
                {
                    "name": "strict_project_filter",
                    "type": "bool",
                    "description": "If True, linked memories must also be in specified projects",
                    "required": False,
                    "default": False,
                    "example": False,
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
            "mutates": True,
            "description": "Update existing memory fields using PATCH semantics (only specified fields are updated)",
            "parameters": [
                {
                    "name": "memory_id",
                    "type": "int",
                    "description": "ID of the memory to update",
                    "required": True,
                    "example": 42,
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
                    "example": "Updated title",
                },
                {
                    "name": "content",
                    "type": "Optional[str]",
                    "description": "New content (optional)",
                    "required": False,
                    "default": None,
                    "example": "Updated content with new information",
                },
                {
                    "name": "context",
                    "type": "Optional[str]",
                    "description": "New context (optional)",
                    "required": False,
                    "default": None,
                    "example": "Updated context explanation",
                },
                {
                    "name": "keywords",
                    "type": "Optional[List[str]]",
                    "description": "New keywords - replaces existing (optional)",
                    "required": False,
                    "default": None,
                    "example": ["new", "keywords"],
                },
                {
                    "name": "tags",
                    "type": "Optional[List[str]]",
                    "description": "New tags - replaces existing (optional)",
                    "required": False,
                    "default": None,
                    "example": ["updated", "tag"],
                },
                {
                    "name": "importance",
                    "type": "Optional[int]",
                    "description": "New importance score 1-10 (optional)",
                    "required": False,
                    "default": None,
                    "example": 8,
                },
                {
                    "name": "project_ids",
                    "type": "Optional[List[int]]",
                    "description": "New project IDs - replaces existing links (optional)",
                    "required": False,
                    "default": None,
                    "example": [1, 2],
                },
                {
                    "name": "code_artifact_ids",
                    "type": "Optional[List[int]]",
                    "description": "New code artifact IDs - replaces existing links (optional)",
                    "required": False,
                    "default": None,
                    "example": [5],
                },
                {
                    "name": "document_ids",
                    "type": "Optional[List[int]]",
                    "description": "New document IDs - replaces existing links (optional)",
                    "required": False,
                    "default": None,
                    "example": [3],
                },
                {
                    "name": "source_repo",
                    "type": "Optional[str]",
                    "description": "New repository/project source. Unchanged if null.",
                    "required": False,
                    "default": None,
                    "example": "scottrbk/forgetful",
                },
                {
                    "name": "source_files",
                    "type": "Optional[List[str]]",
                    "description": "New source files list. Replaces existing if provided, unchanged if null.",
                    "required": False,
                    "default": None,
                    "example": ["src/main.py", "tests/test.py"],
                },
                {
                    "name": "source_url",
                    "type": "Optional[str]",
                    "description": "New URL to source material. Unchanged if null.",
                    "required": False,
                    "default": None,
                    "example": "https://github.com/owner/repo/blob/main/README.md",
                },
                {
                    "name": "confidence",
                    "type": "Optional[float]",
                    "description": "New encoding confidence score (0.0-1.0). Unchanged if null.",
                    "required": False,
                    "default": None,
                    "example": 0.85,
                },
                {
                    "name": "encoding_agent",
                    "type": "Optional[str]",
                    "description": "New agent/process identifier. Unchanged if null.",
                    "required": False,
                    "default": None,
                    "example": "claude-sonnet-4-20250514",
                },
                {
                    "name": "encoding_version",
                    "type": "Optional[str]",
                    "description": "New encoding process version. Unchanged if null.",
                    "required": False,
                    "default": None,
                    "example": "0.1.0",
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
            "mutates": True,
            "description": "Manually create bidirectional links between memories (symmetric linking)",
            "parameters": [
                {
                    "name": "memory_id",
                    "type": "int",
                    "description": "Source memory ID",
                    "required": True,
                    "example": 42,
                },
                {
                    "name": "related_ids",
                    "type": "List[int]",
                    "description": "List of target memory IDs to link",
                    "required": True,
                    "example": [10, 15, 20],
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
            "name": "unlink_memories",
            "mutates": True,
            "description": "Remove a bidirectional link between two memories",
            "parameters": [
                {
                    "name": "source_id",
                    "type": "int",
                    "description": "Source memory ID",
                    "required": True,
                    "example": 42,
                },
                {
                    "name": "target_id",
                    "type": "int",
                    "description": "Target memory ID to unlink",
                    "required": True,
                    "example": 57,
                },
                {
                    "name": "ctx",
                    "type": "Context",
                    "description": "FastMCP Context (automatically injected)",
                    "required": True,
                },
            ],
            "returns": "Dict with 'success' boolean (True if link was removed, False if link didn't exist)",
            "examples": [
                'execute_forgetful_tool("unlink_memories", {"source_id": 42, "target_id": 57})',
            ],
            "tags": ["memory", "unlink", "graph", "linking"],
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
                    "example": 42,
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
            "mutates": True,
            "description": "Mark a memory as obsolete (soft delete with audit trail)",
            "parameters": [
                {
                    "name": "memory_id",
                    "type": "int",
                    "description": "ID of the memory to mark as obsolete",
                    "required": True,
                    "example": 42,
                },
                {
                    "name": "reason",
                    "type": "str",
                    "description": "Explanation for why this memory is obsolete",
                    "required": True,
                    "example": "Superseded by newer decision in memory #100",
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
                    "example": 100,
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
                    "example": 10,
                },
                {
                    "name": "project_ids",
                    "type": "Optional[List[int]]",
                    "description": "Optional filter to specific projects",
                    "required": False,
                    "default": None,
                    "example": [1, 3],
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
            mutates=tool_def.get("mutates", False),
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
    plan_service=None,
    task_service=None,
    file_service=None,
    skill_service=None,
):
    """Register all tool metadata and implementations

    Args:
        registry: ToolRegistry instance to register tools with
        user_service: UserService instance
        memory_service: MemoryService instance
        project_service: ProjectService instance
        code_artifact_service: CodeArtifactService instance
        document_service: DocumentService instance
        entity_service: EntityService instance
        plan_service: PlanService instance (optional, behind PLANNING_ENABLED)
        task_service: TaskService instance (optional, behind PLANNING_ENABLED)
        file_service: FileService instance (optional, behind FILES_ENABLED)
        skill_service: SkillService instance (optional, behind SKILLS_ENABLED)
    """
    logger.info("Starting tool registration")

    # Import adapter factory functions
    from app.routes.mcp.tool_adapters import (
        create_code_artifact_adapters,
        create_document_adapters,
        create_entity_adapters,
        create_project_adapters,
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

    # Conditionally register plan/task tools (behind PLANNING_ENABLED)
    if plan_service is not None:
        plan_adapters = create_plan_adapters(plan_service, user_service)
        register_plan_tools_metadata(registry, plan_adapters)
        logger.info("Plan tools registered")

    if task_service is not None:
        task_adapters = create_task_adapters(task_service, user_service)
        register_task_tools_metadata(registry, task_adapters)
        logger.info("Task tools registered")

    # Conditionally register file tools (behind FILES_ENABLED)
    if file_service is not None:
        file_adapters = create_file_adapters(file_service, user_service)
        register_file_tools_metadata(registry, file_adapters)
        logger.info("File tools registered")

    # Conditionally register skill tools (behind SKILLS_ENABLED)
    if skill_service is not None:
        skill_adapters = create_skill_adapters(skill_service, user_service)
        register_skill_tools_metadata(registry, skill_adapters)
        logger.info("Skill tools registered")

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
    adapters: dict[str, Any],
):
    """Register project tool metadata and implementations"""
    tools = [
        {
            "name": "create_project",
            "mutates": True,
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
            "mutates": True,
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
            "mutates": True,
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
            mutates=tool_def.get("mutates", False),
        )

    logger.info(f"Registered {len(tools)} project tools")


# ============================================================================
# CodeArtifact Tools Metadata
# ============================================================================

def register_code_artifact_tools_metadata(
    registry: ToolRegistry,
    adapters: dict[str, Any],
):
    """Register code artifact tool metadata and implementations"""
    tools = [
        {
            "name": "create_code_artifact",
            "mutates": True,
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
            "mutates": True,
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
            "mutates": True,
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
            mutates=tool_def.get("mutates", False),
        )

    logger.info(f"Registered {len(tools)} code artifact tools")


# ============================================================================
# Document Tools Metadata
# ============================================================================

def register_document_tools_metadata(
    registry: ToolRegistry,
    adapters: dict[str, Any],
):
    """Register document tool metadata and implementations"""
    tools = [
        {
            "name": "create_document",
            "mutates": True,
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
            "mutates": True,
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
            "mutates": True,
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
            mutates=tool_def.get("mutates", False),
        )

    logger.info(f"Registered {len(tools)} document tools")


# ============================================================================
# Entity Tools Metadata
# ============================================================================

def register_entity_tools_metadata(
    registry: ToolRegistry,
    adapters: dict[str, Any],
):
    """Register entity tool metadata and implementations"""
    tools = [
        {
            "name": "create_entity",
            "mutates": True,
            "description": "Create entity representing a real-world entity (organization, individual, team, device)",
            "parameters": [
                {"name": "name", "type": "str", "description": "Entity name", "required": True, "example": "Anthropic"},
                {"name": "entity_type", "type": "str", "description": "Entity type (organization, individual, team, device, other)", "required": True, "example": "organization"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "custom_type", "type": "Optional[str]", "description": "Custom type if 'other' is selected", "required": False, "default": None, "example": "ai-company"},
                {"name": "notes", "type": "Optional[str]", "description": "Additional notes", "required": False, "default": None, "example": "AI safety and research company"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Tags for categorization", "required": False, "default": None, "example": ["ai", "research"]},
                {"name": "aka", "type": "Optional[List[str]]", "description": "Alternative names/aliases (searchable via search_entities)", "required": False, "default": None, "example": ["Claude AI", "Anthropic AI"]},
                {"name": "project_ids", "type": "Optional[List[int]]", "description": "Link to projects (list of project IDs)", "required": False, "default": None, "example": [1, 2]},
            ],
            "returns": "Entity with id and timestamps",
            "examples": [
                'execute_forgetful_tool("create_entity", {"name": "Anthropic", "entity_type": "organization", "aka": ["Claude AI"]})',
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
                {"name": "project_ids", "type": "Optional[List[int]]", "description": "Filter by projects (list of project IDs)", "required": False, "default": None, "example": [1]},
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
            "description": "Search entities by name or alternative names (aka) using text matching (case-insensitive)",
            "parameters": [
                {"name": "query", "type": "str", "description": "Text to search for in entity name or aka (alternative names)", "required": True, "example": "tech"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "entity_type", "type": "Optional[str]", "description": "Filter by entity type", "required": False, "default": None, "example": "Organization"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Filter by tags (returns entities with ANY of these)", "required": False, "default": None, "example": ["startup"]},
                {"name": "limit", "type": "int", "description": "Maximum number of results (1-100)", "required": False, "default": 20, "example": 20},
            ],
            "returns": "Dictionary with entities list, total_count, search_query, and filters",
            "examples": [
                'execute_forgetful_tool("search_entities", {"query": "tech"})',
                'execute_forgetful_tool("search_entities", {"query": "MSFT"})',  # Finds entity with aka=["MSFT", "Microsoft"]
            ],
            "tags": ["entity", "search", "query", "text", "aka"],
        },
        {
            "name": "update_entity",
            "mutates": True,
            "description": "Update existing entity (PATCH semantics - only provided fields changed)",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "ID of the entity to update", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "name", "type": "Optional[str]", "description": "New name", "required": False, "default": None, "example": "Updated name"},
                {"name": "entity_type", "type": "Optional[str]", "description": "New type", "required": False, "default": None, "example": "team"},
                {"name": "custom_type", "type": "Optional[str]", "description": "New custom type", "required": False, "default": None, "example": "custom"},
                {"name": "notes", "type": "Optional[str]", "description": "New notes", "required": False, "default": None, "example": "Updated notes"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "New tags (replaces existing)", "required": False, "default": None, "example": ["updated"]},
                {"name": "aka", "type": "Optional[List[str]]", "description": "New alternative names (replaces existing, empty list [] clears)", "required": False, "default": None, "example": ["Alias1", "Alias2"]},
                {"name": "project_ids", "type": "Optional[List[int]]", "description": "New project links (list of project IDs, replaces existing)", "required": False, "default": None, "example": [2, 3]},
            ],
            "returns": "Updated Entity object",
            "examples": [
                'execute_forgetful_tool("update_entity", {"entity_id": 1, "aka": ["NewAlias", "AnotherName"]})',
            ],
            "tags": ["entity", "update", "patch"],
        },
        {
            "name": "delete_entity",
            "mutates": True,
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
            "mutates": True,
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
            "mutates": True,
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
            "name": "link_entity_to_project",
            "mutates": True,
            "description": "Link entity to project (organizational grouping)",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "ID of the entity", "required": True, "example": 1},
                {"name": "project_id", "type": "int", "description": "ID of the project", "required": True, "example": 5},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with link confirmation",
            "examples": [
                'execute_forgetful_tool("link_entity_to_project", {"entity_id": 1, "project_id": 5})',
            ],
            "tags": ["entity", "project", "link"],
        },
        {
            "name": "unlink_entity_from_project",
            "mutates": True,
            "description": "Unlink entity from project (removes organizational grouping)",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "ID of the entity", "required": True, "example": 1},
                {"name": "project_id", "type": "int", "description": "ID of the project", "required": True, "example": 5},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with unlink confirmation",
            "examples": [
                'execute_forgetful_tool("unlink_entity_from_project", {"entity_id": 1, "project_id": 5})',
            ],
            "tags": ["entity", "project", "unlink"],
        },
        {
            "name": "create_entity_relationship",
            "mutates": True,
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
            "mutates": True,
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
            "mutates": True,
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
        {
            "name": "get_entity_memories",
            "description": "Get all memories linked to a specific entity (useful for entity deduplication and auditing)",
            "parameters": [
                {"name": "entity_id", "type": "int", "description": "ID of the entity to get memories for", "required": True, "example": 42},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with memory_ids (list of int) and count (int)",
            "examples": [
                'execute_forgetful_tool("get_entity_memories", {"entity_id": 42})',
            ],
            "tags": ["entity", "memory", "query", "linking"],
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
            mutates=tool_def.get("mutates", False),
        )

    logger.info(f"Registered {len(tools)} entity tools")


# ============================================================================
# Plan Tools Metadata
# ============================================================================

def register_plan_tools_metadata(
    registry: ToolRegistry,
    adapters: dict[str, Any],
):
    """Register plan tool metadata and implementations"""
    tools = [
        {
            "name": "create_plan",
            "mutates": True,
            "description": "Create a new plan within a project to organize tasks and track goals",
            "parameters": [
                {"name": "title", "type": "str", "description": "Plan title", "required": True, "example": "Implement auth system"},
                {"name": "project_id", "type": "int", "description": "Project this plan belongs to", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "goal", "type": "Optional[str]", "description": "High-level goal for this plan", "required": False, "default": None, "example": "Add JWT-based authentication"},
                {"name": "context", "type": "Optional[str]", "description": "Background context or constraints", "required": False, "default": None, "example": "Must support OAuth2 providers"},
                {"name": "status", "type": "str", "description": "Plan status (draft, active, completed, abandoned)", "required": False, "default": "draft", "example": "draft"},
            ],
            "returns": "Plan object with id, title, project_id, status, and timestamps",
            "examples": [
                'execute_forgetful_tool("create_plan", {"title": "Auth implementation", "project_id": 1, "goal": "Add JWT auth"})',
            ],
            "tags": ["plan", "create", "planning"],
        },
        {
            "name": "update_plan",
            "mutates": True,
            "description": "Update plan metadata using PATCH semantics (only specified fields are updated)",
            "parameters": [
                {"name": "plan_id", "type": "int", "description": "ID of the plan to update", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "title", "type": "Optional[str]", "description": "New plan title", "required": False, "default": None, "example": "Updated plan title"},
                {"name": "goal", "type": "Optional[str]", "description": "New goal description", "required": False, "default": None, "example": "Revised goal"},
                {"name": "context", "type": "Optional[str]", "description": "New context", "required": False, "default": None, "example": "Updated constraints"},
                {"name": "status", "type": "Optional[str]", "description": "New status (draft, active, completed, abandoned)", "required": False, "default": None, "example": "active"},
            ],
            "returns": "Updated Plan object",
            "examples": [
                'execute_forgetful_tool("update_plan", {"plan_id": 1, "status": "active"})',
            ],
            "tags": ["plan", "update", "patch"],
        },
        {
            "name": "get_plan",
            "description": "Retrieve complete plan details by ID",
            "parameters": [
                {"name": "plan_id", "type": "int", "description": "ID of the plan to retrieve", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Complete Plan object with all details",
            "examples": [
                'execute_forgetful_tool("get_plan", {"plan_id": 1})',
            ],
            "tags": ["plan", "retrieve", "read"],
        },
        {
            "name": "list_plans",
            "description": "List plans with optional project and status filtering",
            "parameters": [
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "project_id", "type": "Optional[int]", "description": "Filter by project ID", "required": False, "default": None, "example": 1},
                {"name": "status", "type": "Optional[str]", "description": "Filter by status (draft, active, completed, abandoned)", "required": False, "default": None, "example": "active"},
            ],
            "returns": "Dictionary with plans list and total_count",
            "examples": [
                'execute_forgetful_tool("list_plans", {})',
                'execute_forgetful_tool("list_plans", {"project_id": 1, "status": "active"})',
            ],
            "tags": ["plan", "list", "query"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.PLAN,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
            mutates=tool_def.get("mutates", False),
        )

    logger.info(f"Registered {len(tools)} plan tools")


# ============================================================================
# Task Tools Metadata
# ============================================================================

def register_task_tools_metadata(
    registry: ToolRegistry,
    adapters: dict[str, Any],
):
    """Register task tool metadata and implementations"""
    tools = [
        {
            "name": "create_task",
            "mutates": True,
            "description": "Create a new task within a plan with optional acceptance criteria and dependencies",
            "parameters": [
                {"name": "title", "type": "str", "description": "Task title", "required": True, "example": "Implement login endpoint"},
                {"name": "plan_id", "type": "int", "description": "Plan this task belongs to", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "description", "type": "Optional[str]", "description": "Detailed task description", "required": False, "default": None, "example": "Create POST /auth/login with JWT response"},
                {"name": "priority", "type": "str", "description": "Task priority (P0, P1, P2, P3)", "required": False, "default": "P2", "example": "P1"},
                {"name": "assigned_agent", "type": "Optional[str]", "description": "Agent ID to assign this task to", "required": False, "default": None, "example": "agent-123"},
                {"name": "criteria", "type": "Optional[List[dict]]", "description": "Acceptance criteria list (each with 'description' key)", "required": False, "default": None, "example": [{"description": "Returns JWT token"}]},
                {"name": "dependency_ids", "type": "Optional[List[int]]", "description": "IDs of tasks this task depends on", "required": False, "default": None, "example": [1, 2]},
            ],
            "returns": "Task object with id, title, state, priority, and timestamps",
            "examples": [
                'execute_forgetful_tool("create_task", {"title": "Add login", "plan_id": 1, "priority": "P1"})',
            ],
            "tags": ["task", "create", "planning"],
        },
        {
            "name": "update_task",
            "mutates": True,
            "description": "Update task metadata using PATCH semantics (only specified fields are updated)",
            "parameters": [
                {"name": "task_id", "type": "int", "description": "ID of the task to update", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "title", "type": "Optional[str]", "description": "New task title", "required": False, "default": None, "example": "Updated task title"},
                {"name": "description", "type": "Optional[str]", "description": "New description", "required": False, "default": None, "example": "Updated description"},
                {"name": "priority", "type": "Optional[str]", "description": "New priority (P0, P1, P2, P3)", "required": False, "default": None, "example": "P0"},
            ],
            "returns": "Updated Task object",
            "examples": [
                'execute_forgetful_tool("update_task", {"task_id": 1, "priority": "P0"})',
            ],
            "tags": ["task", "update", "patch"],
        },
        {
            "name": "get_task",
            "description": "Retrieve complete task details by ID including criteria and dependencies",
            "parameters": [
                {"name": "task_id", "type": "int", "description": "ID of the task to retrieve", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Complete Task object with criteria, dependencies, and state history",
            "examples": [
                'execute_forgetful_tool("get_task", {"task_id": 1})',
            ],
            "tags": ["task", "retrieve", "read"],
        },
        {
            "name": "query_tasks",
            "description": "Query tasks within a plan with optional state, priority, and agent filters",
            "parameters": [
                {"name": "plan_id", "type": "int", "description": "Plan to query tasks from", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "state", "type": "Optional[str]", "description": "Filter by task state (open, in_progress, blocked, done, cancelled)", "required": False, "default": None, "example": "open"},
                {"name": "priority", "type": "Optional[str]", "description": "Filter by priority (P0, P1, P2, P3)", "required": False, "default": None, "example": "P1"},
                {"name": "assigned_agent", "type": "Optional[str]", "description": "Filter by assigned agent", "required": False, "default": None, "example": "agent-123"},
            ],
            "returns": "Dictionary with tasks list and total_count",
            "examples": [
                'execute_forgetful_tool("query_tasks", {"plan_id": 1})',
                'execute_forgetful_tool("query_tasks", {"plan_id": 1, "state": "open", "priority": "P0"})',
            ],
            "tags": ["task", "query", "list"],
        },
        {
            "name": "claim_task",
            "mutates": True,
            "description": "Claim a task for an agent with optimistic concurrency control",
            "parameters": [
                {"name": "task_id", "type": "int", "description": "ID of the task to claim", "required": True, "example": 1},
                {"name": "agent_id", "type": "str", "description": "ID of the agent claiming the task", "required": True, "example": "agent-123"},
                {"name": "version", "type": "int", "description": "Expected task version for optimistic locking", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Updated Task object with agent assignment",
            "examples": [
                'execute_forgetful_tool("claim_task", {"task_id": 1, "agent_id": "agent-123", "version": 1})',
            ],
            "tags": ["task", "claim", "agent", "concurrency"],
        },
        {
            "name": "transition_task",
            "mutates": True,
            "description": "Transition task to a new state with optimistic concurrency control",
            "parameters": [
                {"name": "task_id", "type": "int", "description": "ID of the task to transition", "required": True, "example": 1},
                {"name": "state", "type": "str", "description": "Target state (open, in_progress, blocked, done, cancelled)", "required": True, "example": "done"},
                {"name": "version", "type": "int", "description": "Expected task version for optimistic locking", "required": True, "example": 2},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Updated Task object with new state",
            "examples": [
                'execute_forgetful_tool("transition_task", {"task_id": 1, "state": "done", "version": 2})',
            ],
            "tags": ["task", "state", "transition", "concurrency"],
        },
        {
            "name": "add_criterion",
            "mutates": True,
            "description": "Add an acceptance criterion to a task",
            "parameters": [
                {"name": "task_id", "type": "int", "description": "ID of the task to add criterion to", "required": True, "example": 1},
                {"name": "description", "type": "str", "description": "Criterion description", "required": True, "example": "Returns 200 on valid credentials"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Created Criterion object",
            "examples": [
                'execute_forgetful_tool("add_criterion", {"task_id": 1, "description": "Returns JWT token"})',
            ],
            "tags": ["task", "criterion", "create"],
        },
        {
            "name": "verify_criterion",
            "mutates": True,
            "description": "Mark an acceptance criterion as met or unmet",
            "parameters": [
                {"name": "criterion_id", "type": "int", "description": "ID of the criterion to verify", "required": True, "example": 1},
                {"name": "met", "type": "bool", "description": "Whether the criterion has been met", "required": True, "example": True},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Updated Criterion object",
            "examples": [
                'execute_forgetful_tool("verify_criterion", {"criterion_id": 1, "met": true})',
            ],
            "tags": ["task", "criterion", "verify"],
        },
        {
            "name": "delete_criterion",
            "mutates": True,
            "description": "Delete an acceptance criterion from a task",
            "parameters": [
                {"name": "criterion_id", "type": "int", "description": "ID of the criterion to delete", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with deletion confirmation",
            "examples": [
                'execute_forgetful_tool("delete_criterion", {"criterion_id": 1})',
            ],
            "tags": ["task", "criterion", "delete"],
        },
        {
            "name": "add_dependency",
            "mutates": True,
            "description": "Add a dependency between tasks (task depends on another task)",
            "parameters": [
                {"name": "task_id", "type": "int", "description": "ID of the dependent task", "required": True, "example": 2},
                {"name": "depends_on_task_id", "type": "int", "description": "ID of the task it depends on", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dependency object",
            "examples": [
                'execute_forgetful_tool("add_dependency", {"task_id": 2, "depends_on_task_id": 1})',
            ],
            "tags": ["task", "dependency", "create"],
        },
        {
            "name": "remove_dependency",
            "mutates": True,
            "description": "Remove a dependency between tasks",
            "parameters": [
                {"name": "task_id", "type": "int", "description": "ID of the dependent task", "required": True, "example": 2},
                {"name": "depends_on_task_id", "type": "int", "description": "ID of the task to remove dependency on", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with deletion confirmation",
            "examples": [
                'execute_forgetful_tool("remove_dependency", {"task_id": 2, "depends_on_task_id": 1})',
            ],
            "tags": ["task", "dependency", "delete"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.TASK,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
            mutates=tool_def.get("mutates", False),
        )

    logger.info(f"Registered {len(tools)} task tools")


# ============================================================================
# File Tools Metadata
# ============================================================================

def register_file_tools_metadata(
    registry: ToolRegistry,
    adapters: dict[str, Any],
):
    """Register file tool metadata and implementations"""
    tools = [
        {
            "name": "create_file",
            "mutates": True,
            "description": "Create file for storing binary content (images, PDFs, fonts, etc.) as base64",
            "parameters": [
                {"name": "filename", "type": "str", "description": "Original filename with extension (e.g., 'screenshot.png')", "required": True, "example": "diagram.png"},
                {"name": "description", "type": "str", "description": "What the file contains and when to use it", "required": True, "example": "Architecture diagram for auth service"},
                {"name": "data", "type": "str", "description": "Base64-encoded file content", "required": True, "example": "iVBORw0KGgo..."},
                {"name": "mime_type", "type": "str", "description": "MIME type (e.g., 'image/png', 'application/pdf')", "required": True, "example": "image/png"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Tags for categorization", "required": False, "default": None, "example": ["screenshot", "architecture"]},
                {"name": "project_id", "type": "Optional[int]", "description": "Link to project", "required": False, "default": None, "example": 1},
            ],
            "returns": "File with id, size_bytes, and timestamps",
            "examples": [
                'execute_forgetful_tool("create_file", {"filename": "logo.png", "description": "Project logo", "data": "<base64>", "mime_type": "image/png"})',
            ],
            "tags": ["file", "create", "binary"],
        },
        {
            "name": "get_file",
            "description": "Retrieve file by ID with complete details including base64 data",
            "parameters": [
                {"name": "file_id", "type": "int", "description": "ID of the file to retrieve", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Complete File object with base64 data",
            "examples": [
                'execute_forgetful_tool("get_file", {"file_id": 1})',
            ],
            "tags": ["file", "retrieve", "read"],
        },
        {
            "name": "list_files",
            "description": "List files with optional filtering by project, MIME type, or tags (excludes binary data)",
            "parameters": [
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "project_id", "type": "Optional[int]", "description": "Filter by project", "required": False, "default": None, "example": 1},
                {"name": "mime_type", "type": "Optional[str]", "description": "Filter by MIME type", "required": False, "default": None, "example": "image/png"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Filter by tags", "required": False, "default": None, "example": ["screenshot", "ui"]},
            ],
            "returns": "Dictionary with files list (summaries, no data) and count",
            "examples": [
                'execute_forgetful_tool("list_files", {})',
                'execute_forgetful_tool("list_files", {"mime_type": "image/png"})',
            ],
            "tags": ["file", "list", "query"],
        },
        {
            "name": "update_file",
            "mutates": True,
            "description": "Update file metadata or replace content (PATCH semantics)",
            "parameters": [
                {"name": "file_id", "type": "int", "description": "ID of the file to update", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "filename", "type": "Optional[str]", "description": "New filename", "required": False, "default": None, "example": "updated.png"},
                {"name": "description", "type": "Optional[str]", "description": "New description", "required": False, "default": None, "example": "Updated description"},
                {"name": "data", "type": "Optional[str]", "description": "New base64 content (replaces file)", "required": False, "default": None},
                {"name": "mime_type", "type": "Optional[str]", "description": "New MIME type", "required": False, "default": None, "example": "image/jpeg"},
                {"name": "tags", "type": "Optional[List[str]]", "description": "New tags (replaces existing)", "required": False, "default": None, "example": ["updated"]},
                {"name": "project_id", "type": "Optional[int]", "description": "New project link", "required": False, "default": None, "example": 2},
            ],
            "returns": "Updated File object",
            "examples": [
                'execute_forgetful_tool("update_file", {"file_id": 1, "tags": ["updated"]})',
            ],
            "tags": ["file", "update", "patch"],
        },
        {
            "name": "delete_file",
            "mutates": True,
            "description": "Delete file (cascades memory and entity associations)",
            "parameters": [
                {"name": "file_id", "type": "int", "description": "ID of the file to delete", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with deletion confirmation",
            "examples": [
                'execute_forgetful_tool("delete_file", {"file_id": 1})',
            ],
            "tags": ["file", "delete", "remove"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.FILE,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
            mutates=tool_def.get("mutates", False),
        )

    logger.info(f"Registered {len(tools)} file tools")


# ============================================================================
# Skill Tools Metadata
# ============================================================================

def register_skill_tools_metadata(
    registry: ToolRegistry,
    adapters: dict[str, Any],
):
    """Register skill tool metadata and implementations"""
    tools = [
        {
            "name": "create_skill",
            "mutates": True,
            "description": "Create a skill for procedural memory (Agent Skills format). Skills provide steps and examples for agents to perform tasks.",
            "parameters": [
                {"name": "name", "type": "str", "description": "Kebab-case skill name (e.g., 'pdf-processing', 'code-review'). Must match ^[a-z0-9]+(-[a-z0-9]+)*$", "required": True, "example": "code-review"},
                {"name": "description", "type": "str", "description": "What the skill does and when to use it. Gets embedded for semantic search.", "required": True, "example": "Review code changes for quality, security, and best practices"},
                {"name": "content", "type": "str", "description": "Full SKILL.md body (markdown instructions with steps and examples)", "required": True, "example": "## Steps\n1. Check for security issues\n2. Review naming conventions"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "license", "type": "Optional[str]", "description": "License identifier (e.g., 'MIT', 'Apache-2.0')", "required": False, "default": None, "example": "MIT"},
                {"name": "compatibility", "type": "Optional[str]", "description": "Environment requirements (e.g., 'Requires Python 3.14+ and uv')", "required": False, "default": None, "example": "Requires Python 3.12+"},
                {"name": "allowed_tools", "type": "Optional[List[str]]", "description": "Tool restrictions (e.g., ['Bash(python:*)', 'Read', 'WebFetch'])", "required": False, "default": None, "example": ["Bash", "Read", "Grep"]},
                {"name": "metadata", "type": "Optional[Dict[str, Any]]", "description": "Custom key-value pairs (author, version, mcp-server, etc.)", "required": False, "default": None, "example": {"author": "scottesh", "version": "1.0.0"}},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Categorization tags", "required": False, "default": None, "example": ["code", "review", "quality"]},
                {"name": "importance", "type": "int", "description": "Importance 1-10 (default 7)", "required": False, "default": 7, "example": 8},
                {"name": "project_id", "type": "Optional[int]", "description": "Optional project association", "required": False, "default": None, "example": 1},
            ],
            "returns": "Skill with id, name, and timestamps",
            "examples": [
                'execute_forgetful_tool("create_skill", {"name": "code-review", "description": "Review code for quality", "content": "## Steps\\n1. Check security\\n2. Review naming"})',
            ],
            "tags": ["skill", "create", "procedural-memory"],
        },
        {
            "name": "get_skill",
            "description": "Retrieve skill by ID with complete details including full content",
            "parameters": [
                {"name": "skill_id", "type": "int", "description": "ID of the skill to retrieve", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Complete Skill object with full content",
            "examples": [
                'execute_forgetful_tool("get_skill", {"skill_id": 1})',
            ],
            "tags": ["skill", "retrieve", "read"],
        },
        {
            "name": "list_skills",
            "description": "List skills with optional filtering by project, tags, or importance threshold (returns summaries without full content)",
            "parameters": [
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "project_id", "type": "Optional[int]", "description": "Filter by project", "required": False, "default": None, "example": 1},
                {"name": "tags", "type": "Optional[List[str]]", "description": "Filter by tags (returns skills with ANY of these tags)", "required": False, "default": None, "example": ["code", "review"]},
                {"name": "importance_threshold", "type": "Optional[int]", "description": "Minimum importance level (1-10)", "required": False, "default": None, "example": 7},
            ],
            "returns": "Dictionary with skills list (summaries) and total_count",
            "examples": [
                'execute_forgetful_tool("list_skills", {})',
                'execute_forgetful_tool("list_skills", {"tags": ["code"], "importance_threshold": 8})',
            ],
            "tags": ["skill", "list", "query"],
        },
        {
            "name": "update_skill",
            "mutates": True,
            "description": "Update skill (PATCH semantics - only provided fields changed)",
            "parameters": [
                {"name": "skill_id", "type": "int", "description": "ID of the skill to update", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "name", "type": "Optional[str]", "description": "New kebab-case name", "required": False, "default": None, "example": "updated-skill"},
                {"name": "description", "type": "Optional[str]", "description": "New description", "required": False, "default": None, "example": "Updated description"},
                {"name": "content", "type": "Optional[str]", "description": "New content (markdown body)", "required": False, "default": None, "example": "## Updated Steps\\n1. New step"},
                {"name": "license", "type": "Optional[str]", "description": "New license", "required": False, "default": None, "example": "Apache-2.0"},
                {"name": "compatibility", "type": "Optional[str]", "description": "New compatibility string", "required": False, "default": None, "example": "Requires Node 20+"},
                {"name": "allowed_tools", "type": "Optional[List[str]]", "description": "New tool restrictions (replaces existing)", "required": False, "default": None, "example": ["Read", "Write"]},
                {"name": "metadata", "type": "Optional[Dict[str, Any]]", "description": "New metadata (replaces existing)", "required": False, "default": None, "example": {"version": "2.0.0"}},
                {"name": "tags", "type": "Optional[List[str]]", "description": "New tags (replaces existing)", "required": False, "default": None, "example": ["updated"]},
                {"name": "importance", "type": "Optional[int]", "description": "New importance 1-10", "required": False, "default": None, "example": 9},
                {"name": "project_id", "type": "Optional[int]", "description": "New project association", "required": False, "default": None, "example": 2},
            ],
            "returns": "Updated Skill object",
            "examples": [
                'execute_forgetful_tool("update_skill", {"skill_id": 1, "importance": 9, "tags": ["updated"]})',
            ],
            "tags": ["skill", "update", "patch"],
        },
        {
            "name": "delete_skill",
            "mutates": True,
            "description": "Delete skill (removes skill and its memory associations)",
            "parameters": [
                {"name": "skill_id", "type": "int", "description": "ID of the skill to delete", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with deletion confirmation",
            "examples": [
                'execute_forgetful_tool("delete_skill", {"skill_id": 1})',
            ],
            "tags": ["skill", "delete", "remove"],
        },
        {
            "name": "search_skills",
            "description": "Semantic search across skills to find relevant procedural knowledge",
            "parameters": [
                {"name": "query", "type": "str", "description": "Natural language search query", "required": True, "example": "how to review code"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "k", "type": "int", "description": "Number of results to return (default: 5)", "required": False, "default": 5, "example": 5},
                {"name": "project_id", "type": "Optional[int]", "description": "Filter by project", "required": False, "default": None, "example": 1},
            ],
            "returns": "Dictionary with skills list (summaries), total_count, and search_query",
            "examples": [
                'execute_forgetful_tool("search_skills", {"query": "code review best practices"})',
                'execute_forgetful_tool("search_skills", {"query": "deployment process", "k": 3, "project_id": 1})',
            ],
            "tags": ["skill", "search", "semantic", "query"],
        },
        {
            "name": "import_skill",
            "mutates": True,
            "description": "Import a skill from Agent Skills markdown format (YAML frontmatter between --- delimiters)",
            "parameters": [
                {"name": "skill_md_content", "type": "str", "description": "Raw SKILL.md content with YAML frontmatter between --- delimiters", "required": True, "example": "---\\nname: my-skill\\ndescription: A skill\\n---\\n\\n## Steps\\n1. Do something"},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
                {"name": "project_id", "type": "Optional[int]", "description": "Project association (overrides frontmatter)", "required": False, "default": None, "example": 1},
                {"name": "importance", "type": "int", "description": "Importance level (default: 7)", "required": False, "default": 7, "example": 8},
            ],
            "returns": "Created Skill from parsed markdown",
            "examples": [
                'execute_forgetful_tool("import_skill", {"skill_md_content": "---\\nname: my-skill\\ndescription: Does things\\n---\\n\\nInstructions here"})',
            ],
            "tags": ["skill", "import", "markdown", "agent-skills"],
        },
        {
            "name": "export_skill",
            "description": "Export a skill to Agent Skills markdown format (YAML frontmatter + content body)",
            "parameters": [
                {"name": "skill_id", "type": "int", "description": "ID of the skill to export", "required": True, "example": 1},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Formatted SKILL.md string with YAML frontmatter",
            "examples": [
                'execute_forgetful_tool("export_skill", {"skill_id": 1})',
            ],
            "tags": ["skill", "export", "markdown", "agent-skills"],
        },
        {
            "name": "link_skill_to_memory",
            "mutates": True,
            "description": "Link a skill to a memory (establishes reference relationship)",
            "parameters": [
                {"name": "skill_id", "type": "int", "description": "ID of the skill", "required": True, "example": 1},
                {"name": "memory_id", "type": "int", "description": "ID of the memory", "required": True, "example": 5},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with link confirmation",
            "examples": [
                'execute_forgetful_tool("link_skill_to_memory", {"skill_id": 1, "memory_id": 5})',
            ],
            "tags": ["skill", "memory", "link"],
        },
        {
            "name": "unlink_skill_from_memory",
            "mutates": True,
            "description": "Unlink a skill from a memory (removes reference relationship)",
            "parameters": [
                {"name": "skill_id", "type": "int", "description": "ID of the skill", "required": True, "example": 1},
                {"name": "memory_id", "type": "int", "description": "ID of the memory", "required": True, "example": 5},
                {"name": "ctx", "type": "Context", "description": "FastMCP Context (automatically injected)", "required": True},
            ],
            "returns": "Dictionary with unlink confirmation",
            "examples": [
                'execute_forgetful_tool("unlink_skill_from_memory", {"skill_id": 1, "memory_id": 5})',
            ],
            "tags": ["skill", "memory", "unlink"],
        },
    ]

    for tool_def in tools:
        register_simplified_tool(
            registry=registry,
            name=tool_def["name"],
            category=ToolCategory.SKILL,
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            returns=tool_def["returns"],
            implementation=adapters[tool_def["name"]],
            examples=tool_def.get("examples", []),
            tags=tool_def.get("tags", []),
            mutates=tool_def.get("mutates", False),
        )

    logger.info(f"Registered {len(tools)} skill tools")
