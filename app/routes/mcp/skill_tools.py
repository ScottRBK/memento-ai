"""MCP Skill tools - FastMCP tool definitions for skill operations

Skills are procedural memory: step-by-step instructions, examples, and
context that allow an agent to perform a particular task.  Implements a
superset of the Agent Skills open standard (agentskills.io).
"""
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from app.config.logging_config import logging
from app.exceptions import NotFoundError
from app.middleware.auth import get_user_from_auth
from app.models.skill_models import (
    Skill,
    SkillCreate,
    SkillUpdate,
)
from app.utils.pydantic_helper import filter_none_values

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register skill tools - services accessed via context at call time"""

    @mcp.tool()
    async def create_skill(
        name: str,
        description: str,
        content: str,
        ctx: Context,
        license: str = None,
        compatibility: str = None,
        allowed_tools: list[str] = None,
        metadata: dict = None,
        tags: list[str] = None,
        importance: int = 7,
        project_id: int = None,
    ) -> Skill:
        """Create a skill for storing procedural knowledge and agent capabilities.

        WHAT: Stores step-by-step instructions, examples, and context that enable
        an agent to perform a specific task. Skills follow the Agent Skills open
        standard (agentskills.io) with YAML frontmatter and markdown body.

        WHEN: When capturing reusable procedures, workflows, or capabilities that
        an agent should be able to execute. Examples:
        - Code review procedures
        - Deployment workflows
        - Data processing pipelines
        - Testing strategies
        - API integration patterns

        BEHAVIOR: Creates skill with provided content and metadata. Name must be
        kebab-case (e.g., 'code-review', 'pdf-processing'). Can be associated with
        a project immediately via project_id. Returns complete skill with generated ID.
        To link to memories, use link_skill_to_memory.

        NOT-USE: For declarative facts or knowledge (use create_memory), long-form
        documentation (use create_document), or code snippets (use create_code_artifact).
        Skills are specifically for procedural "how-to" knowledge.

        Examples:
        create_skill(
            name="code-review",
            description="Systematic code review process for pull requests",
            content="# Code Review\\n\\n## Steps\\n1. Check for...",
            tags=["development", "review", "quality"],
            importance=8
        )

        create_skill(
            name="deploy-staging",
            description="Deploy application to staging environment",
            content="# Staging Deployment\\n\\n## Prerequisites\\n...",
            compatibility="Requires Docker and kubectl",
            allowed_tools=["Bash(docker:*)", "Bash(kubectl:*)"],
            tags=["deployment", "staging"]
        )

        Args:
            name: Kebab-case skill name (e.g., 'pdf-processing'). Must match ^[a-z0-9]+(-[a-z0-9]+)*$
            description: What the skill does and when to use it. Gets embedded for semantic search.
            content: Full SKILL.md body (markdown instructions, steps, examples).
            license: Optional license identifier (e.g., 'MIT', 'Apache-2.0')
            compatibility: Optional environment requirements (e.g., 'Requires Python 3.14+ and uv')
            allowed_tools: Optional tool restrictions (e.g., ['Bash(python:*)', 'Read', 'WebFetch'])
            metadata: Optional custom key-value pairs (author, version, mcp-server, etc.)
            tags: Optional tags for discovery and categorization (max 10)
            importance: Importance 1-10 (default 7)
            project_id: Optional project ID for immediate association
            ctx: Context (automatically injected by FastMCP)

        Returns:
            Complete Skill with ID, timestamps, and metadata
        """
        logger.info("MCP Tool Called -> create_skill", extra={
            "name": name[:50],
            "importance": importance,
        })

        user = await get_user_from_auth(ctx)

        try:
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
        except ValidationError as e:
            raise ToolError(f"Invalid skill data: {e}")

        try:
            skill_service = ctx.fastmcp.skill_service
            skill = await skill_service.create_skill(
                user_id=user.id,
                skill_data=skill_data,
            )

            return skill

        except Exception as e:
            logger.error("Failed to create skill", exc_info=True)
            raise ToolError(f"Failed to create skill: {e!s}")

    @mcp.tool()
    async def get_skill(
        skill_id: int,
        ctx: Context,
    ) -> Skill:
        """Retrieve skill by ID with complete content.

        WHAT: Returns the full skill including markdown content, allowed tools,
        compatibility requirements, metadata, and all other fields.

        WHEN: You need the full skill content and metadata for a specific skill.
        Common after listing or searching skills, or when a memory references
        a skill ID.

        BEHAVIOR: Returns complete skill including full content, description,
        and metadata. Ownership verified automatically.

        NOT-USE: For browsing multiple skills (use list_skills or search_skills).

        Args:
            skill_id: Unique skill ID
            ctx: Context (automatically injected)

        Returns:
            Complete Skill with content, description, metadata

        Raises:
            ToolError if skill not found or access denied
        """
        logger.info("MCP Tool Called -> get_skill", extra={
            "skill_id": skill_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            skill = await skill_service.get_skill(
                user_id=user.id,
                skill_id=skill_id,
            )

            return skill

        except NotFoundError:
            raise ToolError(f"Skill {skill_id} not found")
        except Exception as e:
            logger.error("Failed to get skill", exc_info=True)
            raise ToolError(f"Failed to retrieve skill: {e!s}")

    @mcp.tool()
    async def list_skills(
        ctx: Context,
        project_id: int = None,
        tags: list[str] = None,
        importance_threshold: int = None,
    ) -> dict:
        """List skills with optional filtering.

        WHAT: Returns lightweight skill summaries (excludes full content) sorted
        by creation date (newest first).

        WHEN: Browsing available skills, searching for specific capabilities,
        or discovering skills by category.

        BEHAVIOR: Returns summaries with filters that can be combined:
        - project_id: Only skills in this project
        - tags: Skills with ANY of these tags
        - importance_threshold: Only skills at or above this importance level

        NOT-USE: When you already have a skill ID and need full content (use get_skill).
        For semantic search by description (use search_skills).

        Examples:
        - All deployment skills: list_skills(tags=["deployment"])
        - High-importance skills: list_skills(importance_threshold=8)
        - Project skills: list_skills(project_id=5, tags=["testing"])

        Args:
            project_id: Optional filter by project
            tags: Optional filter by tags (returns skills with ANY of these tags)
            importance_threshold: Optional minimum importance level (1-10)
            ctx: Context (automatically injected)

        Returns:
            {
                "skills": list[SkillSummary],
                "total_count": int,
                "filters": {
                    "project_id": int | None,
                    "tags": list[str] | None,
                    "importance_threshold": int | None
                }
            }
        """
        logger.info("MCP Tool Called -> list_skills", extra={
            "project_id": project_id,
            "tags": tags,
            "importance_threshold": importance_threshold,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            skills = await skill_service.list_skills(
                user_id=user.id,
                project_id=project_id,
                tags=tags,
                importance_threshold=importance_threshold,
            )

            return {
                "skills": skills,
                "total_count": len(skills),
                "filters": {
                    "project_id": project_id,
                    "tags": tags,
                    "importance_threshold": importance_threshold,
                },
            }

        except Exception as e:
            logger.error("Failed to list skills", exc_info=True)
            raise ToolError(f"Failed to list skills: {e!s}")

    @mcp.tool()
    async def update_skill(
        skill_id: int,
        ctx: Context,
        name: str = None,
        description: str = None,
        content: str = None,
        license: str = None,
        compatibility: str = None,
        allowed_tools: list[str] = None,
        metadata: dict = None,
        tags: list[str] = None,
        importance: int = None,
        project_id: int = None,
    ) -> Skill:
        """Update skill (PATCH semantics - only provided fields changed).

        WHAT: Modifies an existing skill's content, metadata, or associations.

        WHEN: Refining instructions, correcting steps, updating metadata,
        changing categorization, or associating with a different project.

        BEHAVIOR: Updates only the fields you provide. Omitted fields remain unchanged.
        - Omit a field = no change
        - Provide new value = replace
        - tags=[] = clear all tags
        - Name must remain kebab-case if updated

        NOT-USE: Creating new skills (use create_skill).

        Examples:
        - Fix instructions: update_skill(skill_id=5, content="corrected steps...")
        - Update metadata: update_skill(skill_id=5, description="New description")
        - Change importance: update_skill(skill_id=5, importance=9)
        - Add tags: update_skill(skill_id=5, tags=["tag1", "tag2", "tag3"])

        Args:
            skill_id: Skill ID to update
            name: New kebab-case name (unchanged if omitted)
            description: New description (unchanged if omitted)
            content: New content (unchanged if omitted)
            license: New license (unchanged if omitted)
            compatibility: New compatibility (unchanged if omitted)
            allowed_tools: New allowed tools list (unchanged if omitted)
            metadata: New metadata dict (unchanged if omitted)
            tags: New tags (unchanged if omitted, empty list [] clears tags)
            importance: New importance 1-10 (unchanged if omitted)
            project_id: New project association (unchanged if omitted)
            ctx: Context (automatically injected)

        Returns:
            Updated Skill

        Raises:
            ToolError if skill not found or update fails
        """
        logger.info("MCP Tool Called -> update_skill", extra={
            "skill_id": skill_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            update_dict = filter_none_values(
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

            update_data = SkillUpdate(**update_dict)
        except ValidationError as e:
            raise ToolError(f"Invalid update data: {e}")

        try:
            skill_service = ctx.fastmcp.skill_service
            skill = await skill_service.update_skill(
                user_id=user.id,
                skill_id=skill_id,
                skill_data=update_data,
            )

            return skill

        except NotFoundError:
            raise ToolError(f"Skill {skill_id} not found")
        except Exception as e:
            logger.error("Failed to update skill", exc_info=True)
            raise ToolError(f"Failed to update skill: {e!s}")

    @mcp.tool()
    async def delete_skill(
        skill_id: int,
        ctx: Context,
    ) -> dict:
        """Delete skill (cascades memory and artifact associations).

        WHAT: Permanently removes a skill and its associations with memories,
        files, code artifacts, and documents.

        WHEN: Removing obsolete, incorrect, or no-longer-relevant skills.

        BEHAVIOR: Permanently deletes skill and removes all associations.
        Linked memories, files, code artifacts, and documents are preserved.
        Cannot be undone.

        NOT-USE: For temporary hiding (no undo available), or updating (use update_skill).

        Args:
            skill_id: Skill ID to delete
            ctx: Context (automatically injected)

        Returns:
            Success confirmation with deleted skill ID

        Raises:
            ToolError if skill not found
        """
        logger.info("MCP Tool Called -> delete_skill", extra={
            "skill_id": skill_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            success = await skill_service.delete_skill(
                user_id=user.id,
                skill_id=skill_id,
            )

            if not success:
                raise ToolError(f"Skill {skill_id} not found")

            return {"success": True, "deleted_id": skill_id}

        except ToolError:
            raise
        except Exception as e:
            logger.error("Failed to delete skill", exc_info=True)
            raise ToolError(f"Failed to delete skill: {e!s}")

    @mcp.tool()
    async def search_skills(
        query: str,
        ctx: Context,
        k: int = 5,
        project_id: int = None,
    ) -> dict:
        """Search skills by semantic similarity.

        WHAT: Finds skills whose descriptions are semantically similar to the
        query string, ranked by relevance.

        WHEN: Looking for skills that match a capability, task, or workflow.
        More flexible than list_skills filtering - understands meaning, not
        just exact tag matches.

        BEHAVIOR: Returns up to k skill summaries ranked by semantic similarity
        to the query. Optionally scoped to a project.

        NOT-USE: For browsing all skills (use list_skills). For exact ID lookup
        (use get_skill).

        Examples:
        - search_skills(query="how to deploy to production")
        - search_skills(query="code review best practices", k=3)
        - search_skills(query="data pipeline", project_id=5)

        Args:
            query: Search query string (semantic, not keyword-only)
            k: Number of results to return (default: 5)
            project_id: Optional filter by project
            ctx: Context (automatically injected)

        Returns:
            {
                "skills": list[SkillSummary],
                "query": str,
                "total_count": int
            }
        """
        logger.info("MCP Tool Called -> search_skills", extra={
            "query": query[:50],
            "k": k,
            "project_id": project_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            skills = await skill_service.search_skills(
                user_id=user.id,
                query=query,
                k=k,
                project_id=project_id,
            )

            return {
                "skills": skills,
                "query": query,
                "total_count": len(skills),
            }

        except Exception as e:
            logger.error("Failed to search skills", exc_info=True)
            raise ToolError(f"Failed to search skills: {e!s}")

    @mcp.tool()
    async def import_skill(
        skill_md: str,
        ctx: Context,
        project_id: int = None,
        importance: int = 7,
    ) -> Skill:
        """Import a skill from Agent Skills markdown format (SKILL.md).

        WHAT: Parses YAML frontmatter between --- delimiters and extracts
        standard fields per the Agent Skills specification, then creates the
        skill in the system.

        WHEN: When importing skills from external sources, shared skill
        repositories, or SKILL.md files. The Agent Skills standard uses
        YAML frontmatter for metadata and markdown body for instructions.

        BEHAVIOR: Parses frontmatter for name, description, license,
        compatibility, allowed-tools, and metadata. The markdown body
        becomes the skill content. project_id and importance are set via
        parameters (not frontmatter).

        NOT-USE: For creating skills from scratch (use create_skill directly).

        Examples:
        import_skill(
            skill_md=\"\"\"---
        name: code-review
        description: Systematic code review process
        license: MIT
        allowed-tools:
          - Read
          - Grep
        ---
        # Code Review
        ## Steps
        1. Check for...
        \"\"\",
            project_id=3,
            importance=8
        )

        Args:
            skill_md: Raw SKILL.md content with YAML frontmatter between --- delimiters
            project_id: Optional project association (overrides any frontmatter project)
            importance: Importance level 1-10 (default: 7)
            ctx: Context (automatically injected)

        Returns:
            Created Skill with generated ID and timestamps

        Raises:
            ToolError if frontmatter is missing, malformed, or required fields absent
        """
        logger.info("MCP Tool Called -> import_skill", extra={
            "content_length": len(skill_md),
            "importance": importance,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            skill = await skill_service.import_skill(
                user_id=user.id,
                skill_md_content=skill_md,
                project_id=project_id,
                importance=importance,
            )

            return skill

        except ValueError as e:
            raise ToolError(f"Invalid skill markdown: {e!s}")
        except ValidationError as e:
            raise ToolError(f"Invalid skill data: {e}")
        except Exception as e:
            logger.error("Failed to import skill", exc_info=True)
            raise ToolError(f"Failed to import skill: {e!s}")

    @mcp.tool()
    async def export_skill(
        skill_id: int,
        ctx: Context,
    ) -> str:
        """Export a skill to Agent Skills markdown format (SKILL.md).

        WHAT: Generates a standards-compliant SKILL.md string with YAML
        frontmatter and markdown body that can be shared or imported elsewhere.

        WHEN: When sharing skills with others, exporting to external repositories,
        or creating portable skill definitions that follow the Agent Skills standard.

        BEHAVIOR: Builds YAML frontmatter from standard fields (name, description,
        license, compatibility, allowed-tools, metadata) and appends the content
        as the markdown body. Only non-None fields are included in frontmatter.

        NOT-USE: For getting full skill details in structured format (use get_skill).

        Args:
            skill_id: Skill ID to export
            ctx: Context (automatically injected)

        Returns:
            Formatted SKILL.md string with YAML frontmatter

        Raises:
            ToolError if skill not found
        """
        logger.info("MCP Tool Called -> export_skill", extra={
            "skill_id": skill_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            skill_md = await skill_service.export_skill(
                user_id=user.id,
                skill_id=skill_id,
            )

            return skill_md

        except NotFoundError:
            raise ToolError(f"Skill {skill_id} not found")
        except Exception as e:
            logger.error("Failed to export skill", exc_info=True)
            raise ToolError(f"Failed to export skill: {e!s}")

    @mcp.tool()
    async def link_skill_to_memory(
        skill_id: int,
        memory_id: int,
        ctx: Context,
    ) -> dict:
        """Link skill to memory (establishes reference relationship).

        WHAT: Creates a bidirectional association between a skill and a memory
        via the memory_skill_association table.

        WHEN: When a memory mentions or relates to a skill, or when procedural
        knowledge (skill) should be discoverable from declarative knowledge
        (memory) and vice versa.

        BEHAVIOR: Creates association between skill and memory. Idempotent -
        safe to call multiple times (won't create duplicates). Both skill and
        memory must exist and be owned by the user.

        Examples:
        # After creating a skill about deployment:
        link_skill_to_memory(skill_id=5, memory_id=123)

        # Connect a testing skill to a testing decision memory:
        link_skill_to_memory(skill_id=8, memory_id=456)

        Args:
            skill_id: Skill ID to link
            memory_id: Memory ID to link
            ctx: Context (automatically injected)

        Returns:
            Confirmation dict with success status

        Raises:
            ToolError: If skill or memory not found or not owned by user
        """
        logger.info("MCP Tool Called -> link_skill_to_memory", extra={
            "skill_id": skill_id,
            "memory_id": memory_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            success = await skill_service.link_skill_to_memory(
                user_id=user.id,
                skill_id=skill_id,
                memory_id=memory_id,
            )

            return {"success": success}

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to link skill to memory", exc_info=True)
            raise ToolError(f"Failed to link skill to memory: {e!s}")

    @mcp.tool()
    async def unlink_skill_from_memory(
        skill_id: int,
        memory_id: int,
        ctx: Context,
    ) -> dict:
        """Unlink skill from memory (removes reference relationship).

        WHAT: Removes the association between a skill and a memory.

        WHEN: When a skill-memory link is no longer relevant or was created
        in error.

        BEHAVIOR: Removes association between skill and memory. Safe to call
        even if link doesn't exist (returns False). Skill and memory remain
        intact.

        Args:
            skill_id: Skill ID to unlink
            memory_id: Memory ID to unlink
            ctx: Context (automatically injected)

        Returns:
            Confirmation dict with success status (True if removed, False if didn't exist)

        Raises:
            ToolError: If unlinking fails
        """
        logger.info("MCP Tool Called -> unlink_skill_from_memory", extra={
            "skill_id": skill_id,
            "memory_id": memory_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            success = await skill_service.unlink_skill_from_memory(
                user_id=user.id,
                skill_id=skill_id,
                memory_id=memory_id,
            )

            return {"success": success}

        except Exception as e:
            logger.error("Failed to unlink skill from memory", exc_info=True)
            raise ToolError(f"Failed to unlink skill from memory: {e!s}")

    @mcp.tool()
    async def link_skill_to_file(
        skill_id: int,
        file_id: int,
        ctx: Context,
    ) -> dict:
        """Link skill to file (establishes reference relationship).

        WHAT: Creates an association between a skill and a file
        via the skill_file_association table.

        WHEN: When a file contains supporting material for a skill
        (e.g. templates, reference documents, images).

        BEHAVIOR: Creates association between skill and file. Both
        skill and file must exist and be owned by the user.

        Args:
            skill_id: Skill ID to link
            file_id: File ID to link
            ctx: Context (automatically injected)

        Returns:
            Confirmation dict with success status

        Raises:
            ToolError: If skill or file not found or not owned by user
        """
        logger.info("MCP Tool Called -> link_skill_to_file", extra={
            "skill_id": skill_id,
            "file_id": file_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            success = await skill_service.link_skill_to_file(
                user_id=user.id,
                skill_id=skill_id,
                file_id=file_id,
            )

            return {"success": success}

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to link skill to file", exc_info=True)
            raise ToolError(f"Failed to link skill to file: {e!s}")

    @mcp.tool()
    async def unlink_skill_from_file(
        skill_id: int,
        file_id: int,
        ctx: Context,
    ) -> dict:
        """Unlink skill from file (removes reference relationship).

        WHAT: Removes the association between a skill and a file.

        WHEN: When a skill-file link is no longer relevant or was
        created in error.

        BEHAVIOR: Removes association between skill and file. Safe
        to call even if link doesn't exist. Skill and file remain
        intact.

        Args:
            skill_id: Skill ID to unlink
            file_id: File ID to unlink
            ctx: Context (automatically injected)

        Returns:
            Confirmation dict with success status

        Raises:
            ToolError: If unlinking fails
        """
        logger.info("MCP Tool Called -> unlink_skill_from_file", extra={
            "skill_id": skill_id,
            "file_id": file_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            success = await skill_service.unlink_skill_from_file(
                user_id=user.id,
                skill_id=skill_id,
                file_id=file_id,
            )

            return {"success": success}

        except Exception as e:
            logger.error("Failed to unlink skill from file", exc_info=True)
            raise ToolError(f"Failed to unlink skill from file: {e!s}")

    @mcp.tool()
    async def link_skill_to_code_artifact(
        skill_id: int,
        code_artifact_id: int,
        ctx: Context,
    ) -> dict:
        """Link skill to code artifact (establishes reference relationship).

        WHAT: Creates an association between a skill and a code artifact
        via the skill_code_artifact_association table.

        WHEN: When a code artifact contains example code, snippets, or
        templates that support a skill's instructions.

        BEHAVIOR: Creates association between skill and code artifact.
        Both skill and code artifact must exist and be owned by the user.

        Args:
            skill_id: Skill ID to link
            code_artifact_id: Code artifact ID to link
            ctx: Context (automatically injected)

        Returns:
            Confirmation dict with success status

        Raises:
            ToolError: If skill or code artifact not found or not owned by user
        """
        logger.info("MCP Tool Called -> link_skill_to_code_artifact", extra={
            "skill_id": skill_id,
            "code_artifact_id": code_artifact_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            success = await skill_service.link_skill_to_code_artifact(
                user_id=user.id,
                skill_id=skill_id,
                code_artifact_id=code_artifact_id,
            )

            return {"success": success}

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to link skill to code artifact", exc_info=True)
            raise ToolError(f"Failed to link skill to code artifact: {e!s}")

    @mcp.tool()
    async def unlink_skill_from_code_artifact(
        skill_id: int,
        code_artifact_id: int,
        ctx: Context,
    ) -> dict:
        """Unlink skill from code artifact (removes reference relationship).

        WHAT: Removes the association between a skill and a code artifact.

        WHEN: When a skill-code artifact link is no longer relevant or
        was created in error.

        BEHAVIOR: Removes association between skill and code artifact.
        Safe to call even if link doesn't exist. Skill and code artifact
        remain intact.

        Args:
            skill_id: Skill ID to unlink
            code_artifact_id: Code artifact ID to unlink
            ctx: Context (automatically injected)

        Returns:
            Confirmation dict with success status

        Raises:
            ToolError: If unlinking fails
        """
        logger.info("MCP Tool Called -> unlink_skill_from_code_artifact", extra={
            "skill_id": skill_id,
            "code_artifact_id": code_artifact_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            success = await skill_service.unlink_skill_from_code_artifact(
                user_id=user.id,
                skill_id=skill_id,
                code_artifact_id=code_artifact_id,
            )

            return {"success": success}

        except Exception as e:
            logger.error("Failed to unlink skill from code artifact", exc_info=True)
            raise ToolError(f"Failed to unlink skill from code artifact: {e!s}")

    @mcp.tool()
    async def link_skill_to_document(
        skill_id: int,
        document_id: int,
        ctx: Context,
    ) -> dict:
        """Link skill to document (establishes reference relationship).

        WHAT: Creates an association between a skill and a document
        via the skill_document_association table.

        WHEN: When a document contains detailed instructions, analysis,
        or reference material that supports a skill.

        BEHAVIOR: Creates association between skill and document. Both
        skill and document must exist and be owned by the user.

        Args:
            skill_id: Skill ID to link
            document_id: Document ID to link
            ctx: Context (automatically injected)

        Returns:
            Confirmation dict with success status

        Raises:
            ToolError: If skill or document not found or not owned by user
        """
        logger.info("MCP Tool Called -> link_skill_to_document", extra={
            "skill_id": skill_id,
            "document_id": document_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            success = await skill_service.link_skill_to_document(
                user_id=user.id,
                skill_id=skill_id,
                document_id=document_id,
            )

            return {"success": success}

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to link skill to document", exc_info=True)
            raise ToolError(f"Failed to link skill to document: {e!s}")

    @mcp.tool()
    async def unlink_skill_from_document(
        skill_id: int,
        document_id: int,
        ctx: Context,
    ) -> dict:
        """Unlink skill from document (removes reference relationship).

        WHAT: Removes the association between a skill and a document.

        WHEN: When a skill-document link is no longer relevant or was
        created in error.

        BEHAVIOR: Removes association between skill and document. Safe
        to call even if link doesn't exist. Skill and document remain
        intact.

        Args:
            skill_id: Skill ID to unlink
            document_id: Document ID to unlink
            ctx: Context (automatically injected)

        Returns:
            Confirmation dict with success status

        Raises:
            ToolError: If unlinking fails
        """
        logger.info("MCP Tool Called -> unlink_skill_from_document", extra={
            "skill_id": skill_id,
            "document_id": document_id,
        })

        user = await get_user_from_auth(ctx)

        try:
            skill_service = ctx.fastmcp.skill_service
            success = await skill_service.unlink_skill_from_document(
                user_id=user.id,
                skill_id=skill_id,
                document_id=document_id,
            )

            return {"success": success}

        except Exception as e:
            logger.error("Failed to unlink skill from document", exc_info=True)
            raise ToolError(f"Failed to unlink skill from document: {e!s}")
