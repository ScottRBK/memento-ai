"""
MCP - Meta-Tools
This module implements the meta-tools pattern as an alternative to bloating the context window of an LLM with all the tools available
within the MCP service. Instead of loading all tool definitions upfront, we only expose 3 meta-tools.

The three meta-tools:
1. discover_forgetful_tools: List available tools by category, with enough info to allow most LLMs one-shot usage
2. how_to_use_forgetful_tool: Get detailed documentation for a specific tool
3. execute_forgetful_tool: Dynamically invoke any tool with arguments
"""

from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

from app.config.logging_config import logging
from app.models.tool_registry_models import ToolCategory

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register meta-tools with the provided FastMCP instance - registry accessed via ctx pattern"""

    @mcp.tool()
    async def discover_forgetful_tools(
        category: Optional[str] = None,
        ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Discover available tools, optionally filtered by category

        Returns enough information for LLMs to call tools directly without needing how_to_use.

        Args:
            category: Optional category filter (user, memory, project, code_artifact, document, entity, linking)
            ctx: FastMCP Context (automatically injected)

        Returns:
            Dictionary with:
            - tools_by_category: Tools grouped by category
            - total_count: Total number of tools
            - categories_available: List of available categories
            - filtered_by: Category filter applied (if any)

        ## All Available Tools

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
        - get_entity_memories: Get all memories linked to entity
        - create_entity_relationship: Create typed relationship (works_for, owns, etc.)
        - get_entity_relationships: Get relationships for entity
        - update_entity_relationship: Modify relationship
        - delete_entity_relationship: Remove relationship

        ## Workflow
        1. Call discover_forgetful_tools() to see this catalog
        2. Call execute_forgetful_tool(tool_name, {args}) to run any tool
        3. If needed, call how_to_use_forgetful_tool(tool_name) for full parameter docs
        """
        try:
            registry = ctx.fastmcp.registry
            logger.info(f"discover_forgetful_tools: category={category}")

            if category:
                try:
                    cat_enum = ToolCategory(category.lower())
                    tools_metadata = registry.list_by_category(cat_enum)
                    filtered_by = category
                except ValueError:
                    valid_categories = [c.value for c in ToolCategory]
                    raise ToolError(
                        f"Invalid category '{category}'. "
                        f"Available categories: {', '.join(valid_categories)}"
                    )
            else:
                tools_metadata = registry.list_all_tools()
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
                "categories_available": list(registry.list_categories().keys()),
                "filtered_by": filtered_by,
            }

            logger.info(f"discover_forgetful_tools: returned {len(tools)} tools")
            return result

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"discover_forgetful_tools failed: {e}", exc_info=True)
            raise ToolError(f"Failed to discover tools: {str(e)}")

    @mcp.tool()
    async def how_to_use_forgetful_tool(
        tool_name: str,
        ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Get detailed documentation for a specific tool

        Returns complete documentation including JSON schema, multiple examples, and full parameter details.

        Args:
            tool_name: Name of the tool to get documentation for
            ctx: FastMCP Context (automatically injected)

        Returns:
            Detailed tool documentation with JSON schema
        """
        try:
            registry = ctx.fastmcp.registry
            logger.info(f"how_to_use_forgetful_tool: tool_name={tool_name}")

            tool = registry.get_tool(tool_name)
            if not tool:
                available_tools = [m.name for m in registry.list_all_tools()[:10]]
                raise ToolError(
                    f"Tool '{tool_name}' not found in registry. "
                    f"Available tools (first 10): {', '.join(available_tools)}"
                )

            detailed_info = tool.metadata.to_detailed_dict()
            logger.info(f"how_to_use_forgetful_tool: returned docs for {tool_name}")
            return detailed_info

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"how_to_use_forgetful_tool failed for {tool_name}: {e}", exc_info=True)
            raise ToolError(f"Failed to get documentation for '{tool_name}': {str(e)}")

    @mcp.tool()
    async def execute_forgetful_tool(
        tool_name: str,
        arguments: Dict[str, Any],
        ctx: Context
    ) -> Any:
        """
        Execute any registered tool dynamically. Forgetful is a semantic memory system for LLMs.

        ## Quick Start - One-Shot Examples (all required params shown)

        **Memory Operations:**
        - Search: execute_forgetful_tool("query_memory", {"query": "search terms", "query_context": "why searching"})
        - Create: execute_forgetful_tool("create_memory", {"title": "Short title", "content": "Memory content (<2000 chars)", "context": "Why this matters", "keywords": ["kw1", "kw2"], "tags": ["tag1"], "importance": 7, "project_ids": [1]})
        - Create with provenance: execute_forgetful_tool("create_memory", {"title": "...", "content": "...", "context": "...", "keywords": [...], "tags": [...], "importance": 7, "source_repo": "owner/repo", "source_files": ["src/main.py"], "confidence": 0.85, "encoding_agent": "claude-sonnet-4"})
        - Update: execute_forgetful_tool("update_memory", {"memory_id": 1, "content": "new content"})
        - Get: execute_forgetful_tool("get_memory", {"memory_id": 1})
        - Link: execute_forgetful_tool("link_memories", {"memory_id": 1, "related_ids": [2, 3]})

        **Project Organization:**
        - List: execute_forgetful_tool("list_projects", {})
        - Create: execute_forgetful_tool("create_project", {"name": "Project Name", "description": "What this project is about", "project_type": "development"})
        - Get: execute_forgetful_tool("get_project", {"project_id": 1})
        - Query: execute_forgetful_tool("query_memory", {"query": "search terms", "query_context": "why searching", "project_ids": [1]})

        **Entities (people, orgs, devices):**
        - Create: execute_forgetful_tool("create_entity", {"name": "Sarah Chen", "entity_type": "Individual", "notes": "Backend developer", "aka": ["Sarah", "S.C."]})
        - Search: execute_forgetful_tool("search_entities", {"query": "Sarah"})  # Searches name AND aka
        - Link to memory: execute_forgetful_tool("link_entity_to_memory", {"entity_id": 1, "memory_id": 1})

        **Documents (long-form content >300 words):**
        - Create: execute_forgetful_tool("create_document", {"title": "Doc Title", "description": "Brief summary", "content": "Long content...", "document_type": "text", "project_id": 1})

        **Code Artifacts (reusable snippets):**
        - Create: execute_forgetful_tool("create_code_artifact", {"title": "Snippet Title", "description": "What this does", "code": "def example(): pass", "language": "python", "project_id": 1})

        ## Linking Best Practices
        **Always link related items for discoverability:**
        - When creating documents, link atomic memories: `create_memory(..., document_ids=[doc_id])`
        - When creating code artifacts, link to memories: `create_memory(..., code_artifact_ids=[artifact_id])`
        - Link memories to each other: `link_memories(memory_id=1, related_ids=[2, 3])`
        - Link entities to memories: `link_entity_to_memory(entity_id=1, memory_id=1)`

        ## Tool Categories
        memory | project | entity | document | code_artifact | linking | user

        Use discover_forgetful_tools(category?) for full parameter details and optional params.

        ---

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments to pass to the tool
            ctx: FastMCP Context (automatically injected)

        Returns:
            Tool execution result (format depends on the specific tool)
        """
        try:
            registry = ctx.fastmcp.registry
            logger.info(f"execute_forgetful_tool: {tool_name}, args={list(arguments.keys())}")

            if not registry.tool_exists(tool_name):
                available_tools = [m.name for m in registry.list_all_tools()[:10]]
                raise ToolError(
                    f"Tool '{tool_name}' not found in registry. "
                    f"Available tools (first 10): {', '.join(available_tools)}"
                )

            # Inject context into arguments for adapters to extract user
            arguments['ctx'] = ctx

            # Execute through registry
            result = await registry.execute(
                name=tool_name,
                arguments=arguments
            )

            logger.info(f"execute_forgetful_tool: {tool_name} executed successfully")
            return result

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"execute_forgetful_tool failed for {tool_name}: {e}", exc_info=True)
            raise ToolError(f"Failed to execute '{tool_name}': {str(e)}")
