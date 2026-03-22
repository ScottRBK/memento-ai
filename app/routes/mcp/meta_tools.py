"""MCP - Meta-Tools
This module implements the meta-tools pattern as an alternative to bloating the context window of an LLM with all the tools available
within the MCP service. Instead of loading all tool definitions upfront, we only expose 3 meta-tools.

The three meta-tools:
1. discover_forgetful_tools: List available tools by category, with enough info to allow most LLMs one-shot usage
2. how_to_use_forgetful_tool: Get detailed documentation for a specific tool
3. execute_forgetful_tool: Dynamically invoke any tool with arguments

Docstrings for discover and execute are built dynamically at registration time based on
which feature flags (SKILLS_ENABLED, FILES_ENABLED, PLANNING_ENABLED) are active, so LLMs
only see tools they can actually use.
"""

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from app.config.logging_config import logging
from app.config.settings import settings
from app.models.tool_registry_models import ToolCategory
from app.routes.mcp.scope_resolver import get_effective_scopes, get_required_scope

logger = logging.getLogger(__name__)


# ============================================================================
# Dynamic Docstring Sections — discover_forgetful_tools
# ============================================================================

_DISCOVER_CORE_SECTIONS = """\

    **User Tools** - User profile and preferences
    - get_current_user: Get authenticated user info
    - update_user_notes: Store user preferences/notes

    **Memory Tools** - Atomic knowledge storage (<400 words per memory)
    - create_memory: Store a single concept with auto-linking to similar memories (supports provenance tracking)
    - query_memory: Semantic search across memories (use query_context for better ranking)
    - get_memory: Retrieve memory by ID
    - update_memory: Modify memory fields (PATCH semantics, supports provenance tracking)
    - link_memories: Manually connect related memories bidirectionally
    - unlink_memories: Remove link between memories
    - mark_memory_obsolete: Soft-delete with audit trail and optional superseded_by
    - get_recent_memories: Get newest memories (timeline view)

    **Provenance Tracking** (optional fields for create_memory/update_memory):
    - source_repo, source_files, source_url: Track where knowledge came from
    - confidence: Reliability score (0.0-1.0) for AI-generated content
    - encoding_agent, encoding_version: Track which agent/version created the memory

    **Project Tools** - Organize memories by context/scope
    - create_project: Create project container (development, personal, work, etc.)
    - get_project: Retrieve project details
    - list_projects: List all projects with optional status/repo filter
    - update_project: Modify project metadata
    - delete_project: Remove project (memories preserved)

    **Code Artifact Tools** - Reusable code snippets and patterns
    - create_code_artifact: Store code with language, tags, project link
    - get_code_artifact: Retrieve code artifact by ID
    - list_code_artifacts: List artifacts with project/language/tags filter
    - update_code_artifact: Modify artifact fields
    - delete_code_artifact: Remove artifact

    **Document Tools** - Long-form content (>300 words)
    - create_document: Store detailed docs, analysis, guides
    - get_document: Retrieve document by ID
    - list_documents: List documents with project/type/tags filter
    - update_document: Modify document fields
    - delete_document: Remove document

    **Entity Tools** - Real-world entities (people, orgs, devices)
    - create_entity: Create entity with type, aka (aliases), notes
    - get_entity: Retrieve entity by ID
    - list_entities: List entities with project/type/tags filter
    - search_entities: Text search by name or aka (aliases)
    - update_entity: Modify entity fields
    - delete_entity: Remove entity (cascades links)
    - link_entity_to_memory: Connect entity to memory
    - unlink_entity_from_memory: Remove entity-memory link
    - link_entity_to_project: Connect entity to project (organizational grouping)
    - unlink_entity_from_project: Remove entity-project link
    - get_entity_memories: Get all memories linked to entity
    - create_entity_relationship: Create typed relationship (works_for, owns, etc.)
    - get_entity_relationships: Get relationships for entity
    - update_entity_relationship: Modify relationship
    - delete_entity_relationship: Remove relationship"""

_DISCOVER_SKILL_SECTION = """

    **Skill Tools** - Procedural knowledge and agent capabilities (SKILL.md format)
    - create_skill: Create skill with name, description, content, tags
    - get_skill: Retrieve skill by ID with full content
    - list_skills: List skills with project/tags/importance filters
    - update_skill: Modify skill fields (PATCH semantics)
    - delete_skill: Remove skill and associations
    - search_skills: Semantic search for skills by description
    - import_skill: Import from Agent Skills markdown (SKILL.md)
    - export_skill: Export to Agent Skills markdown format
    - link_skill_to_memory: Connect skill to memory
    - unlink_skill_from_memory: Remove skill-memory link
    - link_skill_to_file: Connect skill to file
    - unlink_skill_from_file: Remove skill-file link
    - link_skill_to_code_artifact: Connect skill to code artifact
    - unlink_skill_from_code_artifact: Remove skill-code artifact link
    - link_skill_to_document: Connect skill to document
    - unlink_skill_from_document: Remove skill-document link"""

_DISCOVER_FILE_SECTION = """

    **File Tools** - Binary content storage (images, PDFs, fonts, etc.)
    - create_file: Store file as base64 with metadata and tags
    - get_file: Retrieve file by ID with content
    - list_files: List files with project/mime_type/tags filters
    - update_file: Modify file metadata or content
    - delete_file: Remove file"""

_DISCOVER_PLAN_SECTION = """

    **Plan Tools** - Organize tasks and track goals within projects
    - create_plan: Create plan with title, project_id, goal, context
    - update_plan: Modify plan metadata (PATCH semantics)
    - get_plan: Retrieve plan details by ID
    - list_plans: List plans with project/status filters"""

_DISCOVER_TASK_SECTION = """

    **Task Tools** - Task management with state machine and dependencies
    - create_task: Create task within a plan with criteria and dependencies
    - update_task: Modify task metadata (PATCH semantics)
    - get_task: Retrieve task with criteria and dependencies
    - query_tasks: Query tasks with state/priority/agent filters
    - claim_task: Assign task to agent (optimistic concurrency)
    - transition_task: Change task state (todo/doing/waiting/done/cancelled)
    - add_criterion: Add acceptance criterion to task
    - verify_criterion: Mark criterion as met/unmet
    - delete_criterion: Remove acceptance criterion
    - add_dependency: Add dependency between tasks
    - remove_dependency: Remove task dependency"""


# ============================================================================
# Dynamic Docstring Sections — execute_forgetful_tool
# ============================================================================

_EXECUTE_CORE_EXAMPLES = """\

    ## Quick Start - One-Shot Examples (all required params shown)

    **Memory Operations:**
    - Search: execute_forgetful_tool("query_memory", {"query": "search terms", "query_context": "why searching"})
    - Create: execute_forgetful_tool("create_memory", {"title": "Short title", "content": "Memory content (<2000 chars)", "context": "Why this matters", "keywords": ["kw1", "kw2"], "tags": ["tag1"], "importance": 7, "project_ids": [1]})
    - Create with provenance: execute_forgetful_tool("create_memory", {"title": "...", "content": "...", "context": "...", "keywords": [...], "tags": [...], "importance": 7, "source_repo": "owner/repo", "source_files": ["src/main.py"], "confidence": 0.85, "encoding_agent": "claude-sonnet-4"})
    - Update: execute_forgetful_tool("update_memory", {"memory_id": 1, "content": "new content"})
    - Get: execute_forgetful_tool("get_memory", {"memory_id": 1})
    - Link: execute_forgetful_tool("link_memories", {"memory_id": 1, "related_ids": [2, 3]})
    - Unlink: execute_forgetful_tool("unlink_memories", {"source_id": 1, "target_id": 2})
    - Obsolete: execute_forgetful_tool("mark_memory_obsolete", {"memory_id": 42, "reason": "Outdated approach", "superseded_by": 100})

    **Project Organization:**
    - List: execute_forgetful_tool("list_projects", {})
    - Create: execute_forgetful_tool("create_project", {"name": "Project Name", "description": "What this project is about", "project_type": "development"})
    - Get: execute_forgetful_tool("get_project", {"project_id": 1})
    - Query: execute_forgetful_tool("query_memory", {"query": "search terms", "query_context": "why searching", "project_ids": [1]})

    **Entities (people, orgs, devices):**
    - Create: execute_forgetful_tool("create_entity", {"name": "Sarah Chen", "entity_type": "Individual", "notes": "Backend developer", "aka": ["Sarah", "S.C."]})
    - Search: execute_forgetful_tool("search_entities", {"query": "Sarah"})  # Searches name AND aka
    - Link to memory: execute_forgetful_tool("link_entity_to_memory", {"entity_id": 1, "memory_id": 1})
    - Unlink from memory: execute_forgetful_tool("unlink_entity_from_memory", {"entity_id": 1, "memory_id": 1})
    - Link to project: execute_forgetful_tool("link_entity_to_project", {"entity_id": 1, "project_id": 1})
    - Unlink from project: execute_forgetful_tool("unlink_entity_from_project", {"entity_id": 1, "project_id": 1})

    **Documents (long-form content >300 words):**
    - Create: execute_forgetful_tool("create_document", {"title": "Doc Title", "description": "Brief summary", "content": "Long content...", "document_type": "text", "project_id": 1})

    **Code Artifacts (reusable snippets):**
    - Create: execute_forgetful_tool("create_code_artifact", {"title": "Snippet Title", "description": "What this does", "code": "def example(): pass", "language": "python", "project_id": 1})"""

_EXECUTE_SKILL_SECTION = """

    **Skills (procedural knowledge):**
    - Create: execute_forgetful_tool("create_skill", {"name": "code-review", "description": "Code review process", "content": "# Steps\\n1. ...", "tags": ["dev"]})
    - Search: execute_forgetful_tool("search_skills", {"query": "deployment workflow"})
    - List: execute_forgetful_tool("list_skills", {})
    - Get: execute_forgetful_tool("get_skill", {"skill_id": 1})"""

_EXECUTE_FILE_SECTION = """

    **Files (binary content):**
    - Create: execute_forgetful_tool("create_file", {"filename": "diagram.png", "description": "Architecture diagram", "data": "<base64>", "mime_type": "image/png"})
    - List: execute_forgetful_tool("list_files", {})
    - Get: execute_forgetful_tool("get_file", {"file_id": 1})"""

_EXECUTE_PLAN_SECTION = """

    **Plans (goal tracking):**
    - Create: execute_forgetful_tool("create_plan", {"title": "Auth implementation", "project_id": 1, "goal": "Add JWT auth"})
    - List: execute_forgetful_tool("list_plans", {"project_id": 1})
    - Update: execute_forgetful_tool("update_plan", {"plan_id": 1, "status": "active"})
    - Get: execute_forgetful_tool("get_plan", {"plan_id": 1})"""

_EXECUTE_TASK_SECTION = """

    **Tasks (work items within plans):**
    - Create: execute_forgetful_tool("create_task", {"title": "Add login endpoint", "plan_id": 1, "priority": "P1"})
    - Query: execute_forgetful_tool("query_tasks", {"plan_id": 1, "state": "todo"})
    - Transition: execute_forgetful_tool("transition_task", {"task_id": 1, "state": "done", "version": 2})
    - Claim: execute_forgetful_tool("claim_task", {"task_id": 1, "agent_id": "agent-123", "version": 1})
    - Add criterion: execute_forgetful_tool("add_criterion", {"task_id": 1, "description": "Returns JWT token"})
    - Add dependency: execute_forgetful_tool("add_dependency", {"task_id": 2, "depends_on_task_id": 1})"""


# ============================================================================
# Docstring Builders
# ============================================================================


def _build_category_list() -> str:
    """Build the valid category filter list based on enabled features."""
    categories = ["user", "memory", "project", "code_artifact", "document", "entity", "linking"]
    if settings.SKILLS_ENABLED:
        categories.append("skill")
    if settings.FILES_ENABLED:
        categories.append("file")
    if settings.PLANNING_ENABLED:
        categories.extend(["plan", "task"])
    return ", ".join(categories)


def _build_tool_categories_line() -> str:
    """Build the tool categories pipe-separated line for execute_forgetful_tool."""
    categories = ["memory", "project", "entity", "document", "code_artifact", "linking", "user"]
    if settings.SKILLS_ENABLED:
        categories.append("skill")
    if settings.FILES_ENABLED:
        categories.append("file")
    if settings.PLANNING_ENABLED:
        categories.extend(["plan", "task"])
    return " | ".join(categories)


def _build_discover_docstring() -> str:
    """Build discover_forgetful_tools docstring based on feature flags."""
    categories = _build_category_list()

    parts = [
        f"""\
Discover available tools, optionally filtered by category

    Returns enough information for LLMs to call tools directly without needing how_to_use.

    Args:
        category: Optional category filter ({categories})
        ctx: FastMCP Context (automatically injected)

    Returns:
        Dictionary with:
        - tools_by_category: Tools grouped by category
        - total_count: Total number of tools
        - categories_available: List of available categories
        - filtered_by: Category filter applied (if any)

    ## All Available Tools
{_DISCOVER_CORE_SECTIONS}""",
    ]

    if settings.SKILLS_ENABLED:
        parts.append(_DISCOVER_SKILL_SECTION)
    if settings.FILES_ENABLED:
        parts.append(_DISCOVER_FILE_SECTION)
    if settings.PLANNING_ENABLED:
        parts.append(_DISCOVER_PLAN_SECTION)
        parts.append(_DISCOVER_TASK_SECTION)

    parts.append("""

    ## Workflow
    1. Call discover_forgetful_tools() to see this catalog
    2. Call execute_forgetful_tool(tool_name, {args}) to run any tool
    3. If needed, call how_to_use_forgetful_tool(tool_name) for full parameter docs
    """)

    return "".join(parts)


def _build_execute_docstring() -> str:
    """Build execute_forgetful_tool docstring based on feature flags."""
    tool_categories = _build_tool_categories_line()

    parts = [
        f"""\
Execute any registered tool dynamically. Forgetful is a semantic memory system for LLMs.
{_EXECUTE_CORE_EXAMPLES}""",
    ]

    if settings.SKILLS_ENABLED:
        parts.append(_EXECUTE_SKILL_SECTION)
    if settings.FILES_ENABLED:
        parts.append(_EXECUTE_FILE_SECTION)
    if settings.PLANNING_ENABLED:
        parts.append(_EXECUTE_PLAN_SECTION)
        parts.append(_EXECUTE_TASK_SECTION)

    parts.append(f"""

    ## Linking Best Practices
    **Always link related items for discoverability:**
    - When creating documents, link atomic memories: `create_memory(..., document_ids=[doc_id])`
    - When creating code artifacts, link to memories: `create_memory(..., code_artifact_ids=[artifact_id])`
    - Link memories to each other: `link_memories(memory_id=1, related_ids=[2, 3])`
    - Link entities to memories: `link_entity_to_memory(entity_id=1, memory_id=1)`
    - Link entities to projects: `link_entity_to_project(entity_id=1, project_id=1)`

    ## Tool Categories
    {tool_categories}

    Use discover_forgetful_tools(category?) for full parameter details and optional params.

    ---

    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments to pass to the tool
        ctx: FastMCP Context (automatically injected)

    Returns:
        Tool execution result (format depends on the specific tool)
    """)

    return "".join(parts)


# ============================================================================
# Tool Registration
# ============================================================================


def register(mcp: FastMCP):
    """Register meta-tools with the provided FastMCP instance - registry accessed via ctx pattern"""

    # Build dynamic docstrings based on enabled feature flags
    discover_doc = _build_discover_docstring()
    execute_doc = _build_execute_docstring()

    # -- discover_forgetful_tools --
    # Defined without @mcp.tool() so we can set docstring before registration

    async def discover_forgetful_tools(
        category: str | None = None,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Placeholder - set dynamically below"""
        try:
            registry = ctx.fastmcp.registry
            permitted, _ = get_effective_scopes(ctx)
            logger.info(f"discover_forgetful_tools: category={category}")

            if category:
                try:
                    cat_enum = ToolCategory(category.lower())
                    tools_metadata = registry.get_permitted_by_category(cat_enum, permitted)
                    filtered_by = category
                except ValueError:
                    valid_categories = [c.value for c in ToolCategory]
                    raise ToolError(
                        f"Invalid category '{category}'. "
                        f"Available categories: {', '.join(valid_categories)}",
                    )
            else:
                tools_metadata = registry.get_permitted_tools(permitted)
                filtered_by = None

            # Convert to discovery format (minimal metadata)
            tools = [meta.to_discovery_dict() for meta in tools_metadata]

            # Group by category
            tools_by_category = {}
            for tool in tools:
                cat = tool["category"]
                if cat not in tools_by_category:
                    tools_by_category[cat] = []
                tools_by_category[cat].append(tool)

            result = {
                "tools_by_category": tools_by_category,
                "total_count": len(tools),
                "categories_available": list(registry.get_permitted_categories(permitted).keys()),
                "filtered_by": filtered_by,
            }

            logger.info(f"discover_forgetful_tools: returned {len(tools)} tools")
            return result

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"discover_forgetful_tools failed: {e}", exc_info=True)
            raise ToolError(f"Failed to discover tools: {e!s}")

    discover_forgetful_tools.__doc__ = discover_doc
    mcp.tool()(discover_forgetful_tools)

    # -- how_to_use_forgetful_tool --
    # Static docstring, no dynamic content needed

    @mcp.tool()
    async def how_to_use_forgetful_tool(
        tool_name: str,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Get detailed documentation for a specific tool

        Returns complete documentation including JSON schema, multiple examples, and full parameter details.

        Args:
            tool_name: Name of the tool to get documentation for
            ctx: FastMCP Context (automatically injected)

        Returns:
            Detailed tool documentation with JSON schema
        """
        try:
            registry = ctx.fastmcp.registry
            permitted, _ = get_effective_scopes(ctx)
            logger.info(f"how_to_use_forgetful_tool: tool_name={tool_name}")

            tool = registry.get_tool(tool_name)
            if not tool:
                available_tools = [m.name for m in registry.get_permitted_tools(permitted)[:10]]
                raise ToolError(
                    f"Tool '{tool_name}' not found in registry. "
                    f"Available tools (first 10): {', '.join(available_tools)}",
                )

            if not registry.is_permitted(tool_name, permitted):
                required_scope = get_required_scope(tool_name, registry)
                raise ToolError(
                    f"Tool '{tool_name}' is not permitted under current scopes. "
                    f"Required scope: '{required_scope}'",
                )

            detailed_info = tool.metadata.to_detailed_dict()
            logger.info(f"how_to_use_forgetful_tool: returned docs for {tool_name}")
            return detailed_info

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"how_to_use_forgetful_tool failed for {tool_name}: {e}", exc_info=True)
            raise ToolError(f"Failed to get documentation for '{tool_name}': {e!s}")

    # -- execute_forgetful_tool --
    # Defined without @mcp.tool() so we can set docstring before registration

    async def execute_forgetful_tool(
        tool_name: str,
        arguments: dict[str, Any],
        ctx: Context,
    ) -> Any:
        """Placeholder - set dynamically below"""
        try:
            registry = ctx.fastmcp.registry
            permitted, _ = get_effective_scopes(ctx)
            logger.info(f"execute_forgetful_tool: {tool_name}, args={list(arguments.keys())}")

            if not registry.tool_exists(tool_name):
                available_tools = [m.name for m in registry.get_permitted_tools(permitted)[:10]]
                raise ToolError(
                    f"Tool '{tool_name}' not found in registry. "
                    f"Available tools (first 10): {', '.join(available_tools)}",
                )

            if tool_name not in permitted:
                required_scope = get_required_scope(tool_name, registry)
                raise ToolError(
                    f"Tool '{tool_name}' is not permitted under current scopes. "
                    f"Required scope: '{required_scope}'",
                )

            # Inject context into arguments for adapters to extract user
            arguments["ctx"] = ctx

            # Execute through registry
            result = await registry.execute(
                name=tool_name,
                arguments=arguments,
            )

            logger.info(f"execute_forgetful_tool: {tool_name} executed successfully")
            return result

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"execute_forgetful_tool failed for {tool_name}: {e}", exc_info=True)
            raise ToolError(f"Failed to execute '{tool_name}': {e!s}")

    execute_forgetful_tool.__doc__ = execute_doc
    mcp.tool()(execute_forgetful_tool)
