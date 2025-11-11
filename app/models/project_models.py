from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.config.settings import settings


class ProjectType(str, Enum):
    """Project type categories for organization"""
    PERSONAL = "personal"
    WORK = "work"
    LEARNING = "learning"
    DEVELOPMENT = "development"
    INFRASTRUCTURE = "infrastructure"
    TEMPLATE = "template"
    PRODUCT = "product"
    MARKETING = "marketing"
    FINANCE = "finance"
    DOCUMENTATION = "documentation"
    DEVELOPMENT_ENVIRONMENT = "development-environment"
    THIRD_PARTY_LIBRARY = "third-party-library"
    OPEN_SOURCE = "open-source"


class ProjectStatus(str, Enum):
    """Project lifecycle status"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class ProjectCreate(BaseModel):
    """Request model for creating a project

    Projects organize memories by context, enabling scoped queries like
    "show memories for Project X". Each project tracks memories, code artifacts,
    and documents related to a specific initiative, codebase, or area of work.

    Examples:
        Development project: name="forgetful", type="development", description="MIT-licensed memory service with A-MEM principles"
        MCP server: name="speech", type="mcp-server", repo_name="scottrbk/speech-mcp"
        Infrastructure: name="zitadel", type="infrastructure", description="Auth provider for SSO"
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=500,  # DB limit: String(500)
        description="Project name - short identifier (e.g., 'forgetful', 'veridian_memory', 'speech')"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=settings.PROJECT_DESCRIPTION_MAX_LENGTH,
        description="Purpose and scope overview. What is this project about? (e.g., 'MIT-licensed memory service implementing atomic memory principles')"
    )
    project_type: ProjectType = Field(
        ...,
        description="Project category for organization (e.g., 'development', 'mcp-server', 'infrastructure'). See ProjectType enum for all options."
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.ACTIVE,
        description="Project lifecycle status. Default: 'active'. Options: active (in progress), archived (paused), completed (finished)."
    )
    repo_name: str | None = Field(
        default=None,
        max_length=255,  # DB limit: String(255)
        description="GitHub repository in 'owner/repo' format (e.g., 'scottrbk/forgetful'). Optional."
    )
    notes: str | None = Field(
        default=None,
        max_length=settings.PROJECT_NOTES_MAX_LENGTH,
        description="Workflow notes, setup instructions, or additional context. Optional. Max ~4000 chars."
    )

    @field_validator("name", "description", "repo_name", "notes")
    @classmethod
    def strip_whitespace(cls, v, info):
        """Strip whitespace from string fields"""
        if v is None:
            return v

        stripped = v.strip()

        # For required fields, ensure they're not empty after stripping
        if info.field_name in ["name", "description"] and not stripped:
            raise ValueError(f"{info.field_name} cannot be empty or whitespace only")

        return stripped if stripped else None

    @field_validator("repo_name")
    @classmethod
    def validate_repo_format(cls, v):
        """Validate repo_name follows 'owner/repo' format if provided"""
        if v is None or not v:
            return None

        if "/" not in v:
            raise ValueError("repo_name must follow 'owner/repo' format (e.g., 'scottrbk/forgetful')")

        parts = v.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("repo_name must follow 'owner/repo' format with non-empty owner and repo names")

        return v


class ProjectUpdate(BaseModel):
    """Request model for updating a project

    Follows PATCH semantics: only provided fields are updated.
    None values mean "don't change this field".

    Examples:
        Archive project: ProjectUpdate(status=ProjectStatus.ARCHIVED)
        Update description: ProjectUpdate(description="New description after refactor")
        Change repo: ProjectUpdate(repo_name="newowner/newrepo")
    """
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,  # DB limit: String(500)
        description="New project name. Unchanged if null."
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=settings.PROJECT_DESCRIPTION_MAX_LENGTH,
        description="New description. Unchanged if null."
    )
    project_type: ProjectType | None = Field(
        default=None,
        description="New project type. Unchanged if null. See ProjectType enum for options."
    )
    status: ProjectStatus | None = Field(
        default=None,
        description="New lifecycle status. Unchanged if null. Options: active, archived, completed."
    )
    repo_name: str | None = Field(
        default=None,
        max_length=255,  # DB limit: String(255)
        description="New repository name in 'owner/repo' format. Unchanged if null. Set to empty string to clear."
    )
    notes: str | None = Field(
        default=None,
        max_length=settings.PROJECT_NOTES_MAX_LENGTH,
        description="New notes. Unchanged if null. Set to empty string to clear."
    )

    @field_validator("name", "description", "repo_name", "notes")
    @classmethod
    def strip_whitespace(cls, v, info):
        """Strip whitespace from string fields"""
        if v is None:
            return v

        stripped = v.strip()

        # For name and description, don't allow empty after stripping (if provided)
        if info.field_name in ["name", "description"] and not stripped:
            raise ValueError(f"{info.field_name} cannot be empty or whitespace only")

        # For optional fields (repo_name, notes), empty string means "clear field"
        return stripped if stripped else None

    @field_validator("repo_name")
    @classmethod
    def validate_repo_format(cls, v):
        """Validate repo_name follows 'owner/repo' format if provided"""
        if v is None or not v:
            return None

        if "/" not in v:
            raise ValueError("repo_name must follow 'owner/repo' format (e.g., 'scottrbk/forgetful')")

        parts = v.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("repo_name must follow 'owner/repo' format with non-empty owner and repo names")

        return v


class Project(ProjectCreate):
    """Complete project model with generated fields

    Extends ProjectCreate with system-generated fields (id, timestamps, computed properties).
    Used for responses that include full project details.

    Returned by:
    - create_project: After successfully creating a project
    - get_project: When retrieving a specific project by ID
    - update_project: After successfully updating a project
    """
    id: int = Field(
        ...,
        description="Unique project identifier (auto-generated)"
    )
    memory_count: int = Field(
        default=0,
        description="Number of memories linked to this project. Useful for seeing project activity level."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the project was created (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the project was last updated (UTC)"
    )

    model_config = ConfigDict(from_attributes=True)


class ProjectSummary(BaseModel):
    """Lightweight project summary for list operations

    Excludes heavy text fields (description, notes) to minimize token usage
    when listing multiple projects. Contains just enough info to identify
    and filter projects.

    Used by:
    - list_projects: When listing all projects or filtering by status/repo
    - query results: When project context appears in memory queries
    """
    id: int = Field(
        ...,
        description="Unique project identifier"
    )
    name: str = Field(
        ...,
        description="Project name"
    )
    project_type: ProjectType = Field(
        ...,
        description="Project category"
    )
    status: ProjectStatus = Field(
        ...,
        description="Project lifecycle status"
    )
    repo_name: str | None = Field(
        default=None,
        description="GitHub repository ('owner/repo' format)"
    )
    memory_count: int = Field(
        default=0,
        description="Number of memories linked to this project"
    )
    created_at: datetime = Field(
        ...,
        description="When the project was created (UTC)"
    )
    updated_at: datetime = Field(
        ...,
        description="When the project was last updated (UTC)"
    )

    model_config = ConfigDict(from_attributes=True)
