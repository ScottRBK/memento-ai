# Forgetful MCP Server - Complete Tool Reference

This guide provides comprehensive documentation for all tools available in the Forgetful MCP server.

---

## Table of Contents

- [Meta-Tools Pattern](#meta-tools-pattern)
- [Tool Categories Overview](#tool-categories-overview)
- [User Tools](#user-tools)
- [Memory Tools](#memory-tools)
- [Project Tools](#project-tools)
- [Code Artifact Tools](#code-artifact-tools)
- [Document Tools](#document-tools)
- [Entity Tools](#entity-tools)
- [Cross-Category Workflows](#cross-category-workflows)

---

## Meta-Tools Pattern

Forgetful uses a **meta-tools pattern** to preserve your LLM's context window. Instead of exposing all 42 tools directly, only **3 meta-tools** are visible to MCP clients:

### The Three Meta-Tools

#### 1. `discover_forgetful_tools`
List available tools, optionally filtered by category.

**Parameters:**
- `category` (optional): Filter by category (`user`, `memory`, `project`, `code_artifact`, `document`, `entity`)

**Returns:**
- `tools_by_category`: Tools grouped by category
- `total_count`: Total number of tools
- `categories_available`: List of all categories
- `filtered_by`: Applied filter (if any)

**Example:**
```python
# Discover all memory tools
discover_forgetful_tools(category="memory")

# Discover all available tools
discover_forgetful_tools()
```

#### 2. `how_to_use_forgetful_tool`
Get detailed documentation for a specific tool.

**Parameters:**
- `tool_name`: Name of the tool

**Returns:**
- Complete tool documentation with JSON schema, parameters, and examples

**Example:**
```python
how_to_use_forgetful_tool(tool_name="create_memory")
```

#### 3. `execute_forgetful_tool`
Execute any registered tool dynamically.

**Parameters:**
- `tool_name`: Name of the tool to execute
- `arguments`: Dictionary of arguments for the tool

**Returns:**
- Tool execution result (format depends on specific tool)

**Example:**
```python
execute_forgetful_tool(
    tool_name="create_memory",
    arguments={
        "title": "Database choice: PostgreSQL",
        "content": "Selected PostgreSQL for pgvector support",
        "importance": 9
    }
)
```

---

## Tool Categories Overview

Forgetful organizes **42 tools** across **6 categories**:

| Category | Tool Count | Purpose |
|----------|-----------|---------|
| **User** | 2 | User authentication and profile management |
| **Memory** | 7 | Core memory storage, retrieval, and lifecycle |
| **Project** | 5 | Project organization and scope management |
| **Code Artifact** | 5 | Reusable code snippet storage |
| **Document** | 5 | Long-form content storage (>400 words) |
| **Entity** | 15 | Real-world entity tracking and knowledge graphs |

---

## User Tools

Manage user authentication and profile information.

### `get_current_user`

Returns information about the currently authenticated user.

**Parameters:** None

**Returns:**
- `user_id`: Unique user identifier
- `username`: User's username
- `email`: User's email
- `notes`: User profile notes
- `created_at`: Account creation timestamp

**Example:**
```python
user = execute_forgetful_tool("get_current_user", {})
# Returns: {"user_id": 1, "username": "alex_smith", "email": "alex@example.com", ...}
```

### `update_user_notes`

Update the notes field for the current user's profile.

**Parameters:**
- `notes`: Text content for user notes

**Returns:**
- Updated user object

**Example:**
```python
execute_forgetful_tool(
    "update_user_notes",
    {"notes": "Prefers TypeScript over JavaScript. Works on microservices architecture."}
)
```

---

## Memory Tools

The core of Forgetful - atomic knowledge storage and semantic retrieval.

### `create_memory`

Create an atomic memory with automatic linking to related memories.

**Parameters:**
- `title` (required): Short, searchable title (max 200 chars)
- `content` (required): Memory content - ONE concept (max 2000 chars, ~300-400 words)
- `importance` (required): Importance score 1-10 (9-10 = foundational, 7-8 = patterns, 5-6 = context)
- `context` (optional): Contextual description (max 500 chars)
- `keywords` (optional): List of keywords for semantic clustering (max 10)
- `tags` (optional): List of categorization tags (max 10)
- `project_id` (optional): Link to project
- `linked_document_id` (optional): Link to parent document
- `linked_code_artifact_id` (optional): Link to code artifact

**Returns:**
- `memory_id`: Created memory ID
- `auto_linked_to`: List of automatically linked memory IDs

**Example:**
```python
memory = execute_forgetful_tool(
    "create_memory",
    {
        "title": "API rate limiting: 100 req/min per user",
        "content": "Implemented rate limiting at 100 requests per minute per authenticated user to prevent abuse. Uses Redis for distributed counting across instances.",
        "importance": 8,
        "context": "Performance and security discussion during API redesign",
        "keywords": ["rate-limiting", "api", "redis", "performance"],
        "tags": ["api", "security", "performance"],
        "project_id": 12
    }
)
# Returns: {"memory_id": 156, "auto_linked_to": [142, 148, 151], ...}
```

### `query_memory`

Semantic search across all memories with context-aware ranking.

**Parameters:**
- `query` (required): Natural language search query
- `limit` (optional): Max memories to return (default: 20)
- `project_id` (optional): Scope search to specific project
- `min_importance` (optional): Filter by minimum importance score
- `tags` (optional): Filter by tags

**Returns:**
- List of memories ranked by semantic relevance
- Each memory includes linked artifacts and 1-hop graph connections

**Example:**
```python
results = execute_forgetful_tool(
    "query_memory",
    {
        "query": "how do we handle authentication",
        "project_id": 12,
        "min_importance": 7
    }
)
# Returns: [{"memory_id": 89, "title": "Auth: OAuth2 + JWT", "similarity": 0.92, ...}, ...]
```

### `get_memory`

Retrieve complete memory details by ID.

**Parameters:**
- `memory_id` (required): Memory ID

**Returns:**
- Complete memory object with all fields and relationships

**Example:**
```python
memory = execute_forgetful_tool("get_memory", {"memory_id": 156})
```

### `update_memory`

Update existing memory fields (PATCH semantics - only updates provided fields).

**Parameters:**
- `memory_id` (required): Memory ID
- `title` (optional): Updated title
- `content` (optional): Updated content
- `importance` (optional): Updated importance score
- `context` (optional): Updated context
- `keywords` (optional): Updated keywords
- `tags` (optional): Updated tags

**Returns:**
- Updated memory object

**Example:**
```python
execute_forgetful_tool(
    "update_memory",
    {
        "memory_id": 156,
        "importance": 9,  # Increased importance after realizing how critical this is
        "tags": ["api", "security", "performance", "production"]
    }
)
```

### `link_memories`

Manually create bidirectional links between memories.

**Parameters:**
- `memory_id_1` (required): First memory ID
- `memory_id_2` (required): Second memory ID

**Returns:**
- Confirmation of link creation

**Example:**
```python
# Link related architecture decisions
execute_forgetful_tool(
    "link_memories",
    {
        "memory_id_1": 156,  # Rate limiting decision
        "memory_id_2": 201   # Redis caching strategy
    }
)
```

### `mark_memory_obsolete`

Soft delete a memory with audit trail and supersession tracking.

**Parameters:**
- `memory_id` (required): Memory ID to mark obsolete
- `reason` (optional): Reason for obsolescence
- `superseded_by_memory_id` (optional): ID of replacement memory

**Returns:**
- Updated memory with obsolete flag

**Example:**
```python
execute_forgetful_tool(
    "mark_memory_obsolete",
    {
        "memory_id": 78,  # Old "Docker Swarm deployment" memory
        "reason": "Migrated to Kubernetes",
        "superseded_by_memory_id": 312  # New K8s memory
    }
)
```

### `get_recent_memories`

Retrieve most recent memories sorted by creation timestamp.

**Parameters:**
- `limit` (optional): Max memories to return (default: 20)
- `project_id` (optional): Scope to specific project

**Returns:**
- List of recent memories

**Example:**
```python
recent = execute_forgetful_tool(
    "get_recent_memories",
    {"limit": 10, "project_id": 12}
)
```

---

## Project Tools

Organize memories, code artifacts, and documents by project context.

### Project Types
- `personal`, `work`, `learning`, `development`, `infrastructure`
- `template`, `product`, `marketing`, `finance`, `documentation`
- `development-environment`, `third-party-library`, `open-source`

### Project Statuses
- `active`, `archived`, `completed`

### `create_project`

Create a new project for organizing knowledge.

**Parameters:**
- `name` (required): Project name
- `project_type` (optional): Project type (see list above)
- `description` (optional): Project description
- `status` (optional): Project status (default: `active`)
- `repository_url` (optional): Git repository URL
- `metadata` (optional): Additional JSON metadata

**Returns:**
- Created project with `project_id`

**Example:**
```python
project = execute_forgetful_tool(
    "create_project",
    {
        "name": "E-Commerce Platform Redesign",
        "project_type": "work",
        "description": "Complete redesign of checkout and payment flows",
        "status": "active",
        "repository_url": "https://github.com/company/ecommerce-v2"
    }
)
# Returns: {"project_id": 22, "name": "E-Commerce Platform Redesign", ...}
```

### `list_projects`

List projects with optional filtering.

**Parameters:**
- `project_type` (optional): Filter by project type
- `status` (optional): Filter by status
- `repository_url` (optional): Filter by repository

**Returns:**
- List of matching projects

**Example:**
```python
# Get all active work projects
active_work = execute_forgetful_tool(
    "list_projects",
    {"project_type": "work", "status": "active"}
)
```

### `get_project`

Retrieve complete project details by ID.

**Parameters:**
- `project_id` (required): Project ID

**Returns:**
- Complete project object

**Example:**
```python
project = execute_forgetful_tool("get_project", {"project_id": 22})
```

### `update_project`

Update project metadata (PATCH semantics).

**Parameters:**
- `project_id` (required): Project ID
- `name` (optional): Updated name
- `description` (optional): Updated description
- `status` (optional): Updated status
- `repository_url` (optional): Updated repository URL
- `metadata` (optional): Updated metadata

**Returns:**
- Updated project object

**Example:**
```python
# Mark project as completed
execute_forgetful_tool(
    "update_project",
    {
        "project_id": 22,
        "status": "completed",
        "metadata": {"completion_date": "2025-01-15", "outcome": "shipped to production"}
    }
)
```

### `delete_project`

Delete project while preserving linked memories, artifacts, and documents.

**Parameters:**
- `project_id` (required): Project ID

**Returns:**
- Confirmation of deletion

**Example:**
```python
execute_forgetful_tool("delete_project", {"project_id": 22})
```

---

## Code Artifact Tools

Store and retrieve reusable code snippets and patterns.

### `create_code_artifact`

Store a reusable code snippet.

**Parameters:**
- `title` (required): Artifact title
- `content` (required): Code content
- `language` (required): Programming language
- `description` (optional): Artifact description
- `tags` (optional): Categorization tags
- `project_id` (optional): Link to project
- `framework` (optional): Framework name (e.g., "React", "FastAPI")
- `version` (optional): Version string

**Returns:**
- Created artifact with `code_artifact_id`

**Example:**
```python
artifact = execute_forgetful_tool(
    "create_code_artifact",
    {
        "title": "Async Retry Decorator with Exponential Backoff",
        "content": '''
import asyncio
from functools import wraps

def async_retry(max_attempts=3, base_delay=1.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
        ''',
        "language": "python",
        "description": "Reusable retry logic for async operations - use for API calls",
        "tags": ["async", "retry", "decorator", "resilience"],
        "project_id": 12
    }
)
# Returns: {"code_artifact_id": 45, ...}
```

### `list_code_artifacts`

List code artifacts with optional filtering.

**Parameters:**
- `project_id` (optional): Filter by project
- `language` (optional): Filter by programming language
- `tags` (optional): Filter by tags

**Returns:**
- List of matching code artifacts

**Example:**
```python
# Find all Python utilities
python_utils = execute_forgetful_tool(
    "list_code_artifacts",
    {"language": "python", "tags": ["utility"]}
)
```

### `get_code_artifact`

Retrieve complete code artifact by ID.

**Parameters:**
- `code_artifact_id` (required): Artifact ID

**Returns:**
- Complete artifact object with code content

**Example:**
```python
artifact = execute_forgetful_tool("get_code_artifact", {"code_artifact_id": 45})
```

### `update_code_artifact`

Update code artifact (PATCH semantics).

**Parameters:**
- `code_artifact_id` (required): Artifact ID
- `title`, `content`, `language`, `description`, `tags`, `framework`, `version` (all optional)

**Returns:**
- Updated artifact object

**Example:**
```python
execute_forgetful_tool(
    "update_code_artifact",
    {
        "code_artifact_id": 45,
        "version": "2.0.0",
        "tags": ["async", "retry", "decorator", "resilience", "production"]
    }
)
```

### `delete_code_artifact`

Delete code artifact (cascades memory associations).

**Parameters:**
- `code_artifact_id` (required): Artifact ID

**Returns:**
- Confirmation of deletion

**Example:**
```python
execute_forgetful_tool("delete_code_artifact", {"code_artifact_id": 45})
```

---

## Document Tools

Store long-form content (>400 words) like architecture decision records, research notes, and detailed documentation.

### Document Types
- `text` - Plain text documents
- `markdown` - Markdown-formatted documents
- `code` - Code documentation
- Custom types - Define your own

### `create_document`

Create a document for long-form content.

**Parameters:**
- `title` (required): Document title
- `content` (required): Document content (no character limit)
- `document_type` (optional): Document type (default: `text`)
- `description` (optional): Document description
- `tags` (optional): Categorization tags
- `project_id` (optional): Link to project

**Returns:**
- Created document with `document_id`

**Example:**
```python
doc = execute_forgetful_tool(
    "create_document",
    {
        "title": "ADR-003: Migration to Event-Driven Architecture",
        "content": '''
# Architecture Decision Record: Event-Driven Architecture

## Status
Accepted

## Context
Our monolithic architecture faces scaling challenges:
- Tight coupling between services creates deployment bottlenecks
- Database contention during peak loads
- Difficulty adding new features without affecting existing systems

[... 2000+ words of detailed analysis ...]

## Decision
Adopt event-driven architecture using Apache Kafka as message broker.

## Consequences
### Positive
- Loose coupling enables independent service scaling
- Event sourcing provides audit trail
- Easier to add new consumers

### Negative
- Increased operational complexity
- Eventual consistency requires careful handling
- Team needs training on distributed systems

## Implementation Plan
[... detailed steps ...]
        ''',
        "document_type": "markdown",
        "tags": ["adr", "architecture", "event-driven", "kafka"],
        "project_id": 22
    }
)
# Returns: {"document_id": 89, ...}

# Extract atomic memories from this document
memory1 = execute_forgetful_tool(
    "create_memory",
    {
        "title": "Architecture decision: Event-driven with Kafka",
        "content": "Adopted event-driven architecture using Kafka to resolve monolith scaling issues",
        "importance": 10,
        "linked_document_id": 89,
        "project_id": 22
    }
)
```

### `list_documents`

List documents with optional filtering.

**Parameters:**
- `project_id` (optional): Filter by project
- `document_type` (optional): Filter by type
- `tags` (optional): Filter by tags

**Returns:**
- List of matching documents

**Example:**
```python
# Find all ADRs
adrs = execute_forgetful_tool(
    "list_documents",
    {"tags": ["adr"], "document_type": "markdown"}
)
```

### `get_document`

Retrieve complete document by ID.

**Parameters:**
- `document_id` (required): Document ID

**Returns:**
- Complete document object with full content

**Example:**
```python
doc = execute_forgetful_tool("get_document", {"document_id": 89})
```

### `update_document`

Update document (PATCH semantics).

**Parameters:**
- `document_id` (required): Document ID
- `title`, `content`, `document_type`, `description`, `tags` (all optional)

**Returns:**
- Updated document object

**Example:**
```python
execute_forgetful_tool(
    "update_document",
    {
        "document_id": 89,
        "tags": ["adr", "architecture", "event-driven", "kafka", "implemented"]
    }
)
```

### `delete_document`

Delete document (cascades memory associations).

**Parameters:**
- `document_id` (required): Document ID

**Returns:**
- Confirmation of deletion

**Example:**
```python
execute_forgetful_tool("delete_document", {"document_id": 89})
```

---

## Entity Tools

Track real-world entities (people, organizations, teams, devices) and build knowledge graphs through relationships.

### Entity Types
- `Organization` - Companies, institutions
- `Individual` - People, team members
- `Team` - Groups within organizations
- `Device` - Servers, infrastructure
- `Other` - Custom entity types (requires `custom_type` field)

### Relationship Types
- `works_for` - Employment relationships
- `member_of` - Team membership
- `owns` - Ownership
- `reports_to` - Reporting structure
- `collaborates_with` - Collaboration
- Custom types - Define your own

### Entity CRUD Operations

#### `create_entity`

Create an entity representing a real-world thing.

**Parameters:**
- `name` (required): Entity name
- `entity_type` (required): Type (`Organization`, `Individual`, `Team`, `Device`, `Other`)
- `description` (optional): Entity description
- `tags` (optional): Categorization tags
- `aka` (optional): Alternative names/aliases (max 10). Searchable via `search_entities`.
- `project_id` (optional): Link to project
- `custom_type` (optional): Custom type name (required if entity_type is `Other`)
- `metadata` (optional): Additional JSON metadata

**Returns:**
- Created entity with `entity_id`

**Example:**
```python
# Create a person with aliases
person = execute_forgetful_tool(
    "create_entity",
    {
        "name": "Sarah Chen",
        "entity_type": "Individual",
        "description": "Senior Backend Engineer, specializes in distributed systems",
        "tags": ["engineering", "backend", "distributed-systems"],
        "aka": ["Sarah", "S.C."],  # Alternative names for search
        "metadata": {"start_date": "2024-03-15", "location": "San Francisco"}
    }
)
# Returns: {"entity_id": 42, "name": "Sarah Chen", "aka": ["Sarah", "S.C."], ...}

# Create an organization with stock ticker alias
org = execute_forgetful_tool(
    "create_entity",
    {
        "name": "TechFlow Systems",
        "entity_type": "Organization",
        "description": "SaaS platform for workflow automation",
        "tags": ["company", "saas", "b2b"],
        "aka": ["TechFlow", "TFS"]  # Can search by "TFS" to find this
    }
)
# Returns: {"entity_id": 43, ...}

# Create infrastructure
server = execute_forgetful_tool(
    "create_entity",
    {
        "name": "Cache Server 01",
        "entity_type": "Device",
        "description": "Redis cluster primary node - production",
        "tags": ["infrastructure", "cache", "production", "redis"],
        "aka": ["redis-primary", "cache-01"],
        "metadata": {"ip": "10.0.1.50", "region": "us-west-2"}
    }
)
# Returns: {"entity_id": 44, ...}
```

#### `list_entities`

List entities with optional filtering.

**Parameters:**
- `entity_type` (optional): Filter by type
- `tags` (optional): Filter by tags
- `project_id` (optional): Filter by project

**Returns:**
- List of matching entities

**Example:**
```python
# Find all team members
team = execute_forgetful_tool(
    "list_entities",
    {"entity_type": "Individual", "tags": ["engineering"]}
)
```

#### `search_entities`

Search entities by name or alternative names (aka). Case-insensitive text matching.

**Parameters:**
- `query` (required): Search term (matches name or any aka, partial match supported)
- `entity_type` (optional): Filter by entity type
- `tags` (optional): Filter by tags
- `limit` (optional): Maximum results (1-100, default 20)

**Returns:**
- List of entities matching the search term (via name or aka)

**Example:**
```python
# Find entities with "Chen" in the name
results = execute_forgetful_tool(
    "search_entities",
    {"query": "Chen"}
)
# Returns: [{"entity_id": 42, "name": "Sarah Chen", "aka": ["Sarah", "S.C."], ...}, ...]

# Search by alias - finds "TechFlow Systems" via its "TFS" alias
results = execute_forgetful_tool(
    "search_entities",
    {"query": "TFS"}
)
# Returns: [{"entity_id": 43, "name": "TechFlow Systems", "aka": ["TechFlow", "TFS"], ...}]
```

#### `get_entity`

Retrieve complete entity details by ID.

**Parameters:**
- `entity_id` (required): Entity ID

**Returns:**
- Complete entity object

**Example:**
```python
entity = execute_forgetful_tool("get_entity", {"entity_id": 42})
```

#### `update_entity`

Update entity (PATCH semantics - only provided fields changed).

**Parameters:**
- `entity_id` (required): Entity ID
- `name`, `description`, `tags`, `aka`, `metadata` (all optional)
- `aka`: Replaces existing aliases. Empty list `[]` clears all aliases.

**Returns:**
- Updated entity object

**Example:**
```python
# Update description and add aliases
execute_forgetful_tool(
    "update_entity",
    {
        "entity_id": 42,
        "description": "Principal Backend Engineer, Tech Lead for distributed systems",
        "aka": ["Sarah", "S.C.", "Chen"],  # Replaces existing aka list
        "metadata": {"promotion_date": "2025-01-01", "title": "Principal Engineer"}
    }
)
```

#### `delete_entity`

Delete entity (cascade removes memory links and relationships).

**Parameters:**
- `entity_id` (required): Entity ID

**Returns:**
- Confirmation of deletion

**Example:**
```python
execute_forgetful_tool("delete_entity", {"entity_id": 42})
```

### Entity-Memory Linking

#### `link_entity_to_memory`

Link an entity to a memory (establishes reference relationship).

**Parameters:**
- `entity_id` (required): Entity ID
- `memory_id` (required): Memory ID

**Returns:**
- Confirmation of link

**Example:**
```python
# Link Sarah to a memory about an architecture decision she made
execute_forgetful_tool(
    "link_entity_to_memory",
    {
        "entity_id": 42,  # Sarah Chen
        "memory_id": 156  # "API rate limiting decision"
    }
)
```

#### `unlink_entity_from_memory`

Remove entity-memory link.

**Parameters:**
- `entity_id` (required): Entity ID
- `memory_id` (required): Memory ID

**Returns:**
- Confirmation of unlink

**Example:**
```python
execute_forgetful_tool(
    "unlink_entity_from_memory",
    {"entity_id": 42, "memory_id": 156}
)
```

### Entity Relationships (Knowledge Graph)

Build directional knowledge graphs showing how entities relate to each other.

#### `create_entity_relationship`

Create a typed relationship between two entities.

**Parameters:**
- `from_entity_id` (required): Source entity ID
- `to_entity_id` (required): Target entity ID
- `relationship_type` (required): Relationship type (see list above, or custom)
- `strength` (optional): Relationship strength 0.0-1.0 (default: 1.0)
- `confidence` (optional): Confidence level 0.0-1.0 (default: 1.0)
- `metadata` (optional): Additional JSON metadata

**Returns:**
- Created relationship with `relationship_id`

**Example:**
```python
# Sarah works for TechFlow
relationship = execute_forgetful_tool(
    "create_entity_relationship",
    {
        "from_entity_id": 42,  # Sarah Chen
        "to_entity_id": 43,    # TechFlow Systems
        "relationship_type": "works_for",
        "strength": 1.0,
        "metadata": {
            "role": "Principal Backend Engineer",
            "department": "Platform Engineering",
            "start_date": "2024-03-15"
        }
    }
)
# Returns: {"relationship_id": 12, ...}

# Server owned by TechFlow
execute_forgetful_tool(
    "create_entity_relationship",
    {
        "from_entity_id": 43,  # TechFlow Systems
        "to_entity_id": 44,    # Cache Server 01
        "relationship_type": "owns",
        "metadata": {"purchased": "2024-06-01", "cost_center": "engineering"}
    }
)
```

#### `get_entity_relationships`

Get relationships for an entity with optional filtering.

**Parameters:**
- `entity_id` (required): Entity ID
- `relationship_type` (optional): Filter by relationship type
- `direction` (optional): `outgoing`, `incoming`, or `both` (default: `both`)

**Returns:**
- List of relationships

**Example:**
```python
# Get all of Sarah's relationships
relationships = execute_forgetful_tool(
    "get_entity_relationships",
    {"entity_id": 42}
)

# Get only employment relationships
employment = execute_forgetful_tool(
    "get_entity_relationships",
    {
        "entity_id": 42,
        "relationship_type": "works_for",
        "direction": "outgoing"
    }
)
```

#### `update_entity_relationship`

Update entity relationship (PATCH semantics).

**Parameters:**
- `relationship_id` (required): Relationship ID
- `relationship_type`, `strength`, `confidence`, `metadata` (all optional)

**Returns:**
- Updated relationship object

**Example:**
```python
# Update Sarah's role after promotion
execute_forgetful_tool(
    "update_entity_relationship",
    {
        "relationship_id": 12,
        "metadata": {
            "role": "Engineering Director",
            "department": "Platform Engineering",
            "promotion_date": "2025-01-01"
        }
    }
)
```

#### `delete_entity_relationship`

Delete entity relationship (removes knowledge graph edge).

**Parameters:**
- `relationship_id` (required): Relationship ID

**Returns:**
- Confirmation of deletion

**Example:**
```python
execute_forgetful_tool("delete_entity_relationship", {"relationship_id": 12})
```

---

## Cross-Category Workflows

Real-world scenarios demonstrating how tools work together.

### Scenario 1: Documenting a Complete Feature

**Context:** You've implemented a new authentication system and want to capture all knowledge.

```python
# 1. Create project
project = execute_forgetful_tool(
    "create_project",
    {
        "name": "Authentication System V2",
        "project_type": "development",
        "status": "active"
    }
)
project_id = project["project_id"]

# 2. Store architecture decision document
adr = execute_forgetful_tool(
    "create_document",
    {
        "title": "ADR-001: OAuth2 + JWT Authentication Strategy",
        "content": "[... full 3000-word architecture decision record ...]",
        "document_type": "markdown",
        "tags": ["adr", "authentication", "oauth2", "jwt"],
        "project_id": project_id
    }
)

# 3. Extract key decision as atomic memory
decision_memory = execute_forgetful_tool(
    "create_memory",
    {
        "title": "Auth strategy: OAuth2 for third-party + JWT for sessions",
        "content": "Selected OAuth2 for social login (Google, GitHub) and JWT for internal session management. JWT tokens expire after 24h with refresh token rotation.",
        "importance": 10,
        "tags": ["authentication", "oauth2", "jwt", "decision"],
        "project_id": project_id,
        "linked_document_id": adr["document_id"]
    }
)

# 4. Store reusable JWT middleware
middleware = execute_forgetful_tool(
    "create_code_artifact",
    {
        "title": "JWT Authentication Middleware",
        "content": '''
from fastapi import Request, HTTPException
from jose import jwt, JWTError

async def verify_jwt(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
        ''',
        "language": "python",
        "framework": "FastAPI",
        "tags": ["authentication", "jwt", "middleware"],
        "project_id": project_id
    }
)

# 5. Create entity for the engineer who implemented it
engineer = execute_forgetful_tool(
    "create_entity",
    {
        "name": "Alex Kim",
        "entity_type": "Individual",
        "description": "Senior Full-Stack Engineer",
        "tags": ["engineering", "fullstack"],
        "aka": ["Alex", "A.K."]
    }
)

# 6. Link engineer to the decision memory
execute_forgetful_tool(
    "link_entity_to_memory",
    {
        "entity_id": engineer["entity_id"],
        "memory_id": decision_memory["memory_id"]
    }
)

# 7. Later, query everything about auth
results = execute_forgetful_tool(
    "query_memory",
    {
        "query": "authentication implementation",
        "project_id": project_id
    }
)
# Returns decision_memory + auto-linked memories + linked document + code artifact + entity
```

### Scenario 2: New Team Member Onboarding

**Context:** A new engineer joins, you want to capture their information and link relevant knowledge.

```python
# 1. Create entity for new engineer
new_hire = execute_forgetful_tool(
    "create_entity",
    {
        "name": "Jordan Taylor",
        "entity_type": "Individual",
        "description": "Backend Engineer - Payments Team",
        "tags": ["engineering", "backend", "payments"],
        "aka": ["Jordan", "J.T."],
        "metadata": {"start_date": "2025-01-20", "location": "Remote"}
    }
)

# 2. Get company entity (assuming it exists) - can search by name or alias
company = execute_forgetful_tool(
    "search_entities",
    {"query": "TechFlow"}
)
company_id = company[0]["entity_id"]

# 3. Create employment relationship
execute_forgetful_tool(
    "create_entity_relationship",
    {
        "from_entity_id": new_hire["entity_id"],
        "to_entity_id": company_id,
        "relationship_type": "works_for",
        "metadata": {
            "role": "Backend Engineer II",
            "department": "Payments",
            "team": "Checkout"
        }
    }
)

# 4. Create onboarding memory
onboarding_memory = execute_forgetful_tool(
    "create_memory",
    {
        "title": "Jordan Taylor joined - Payments team focus areas",
        "content": "Jordan will focus on payment gateway integrations (Stripe, PayPal) and PCI compliance. Previous experience with financial systems at FinanceApp Corp.",
        "importance": 7,
        "tags": ["team", "onboarding", "payments"],
        "context": "New hire onboarding - payments team expansion"
    }
)

# 5. Link new hire to onboarding memory
execute_forgetful_tool(
    "link_entity_to_memory",
    {
        "entity_id": new_hire["entity_id"],
        "memory_id": onboarding_memory["memory_id"]
    }
)

# 6. Query existing payment system memories and link relevant ones
payment_memories = execute_forgetful_tool(
    "query_memory",
    {"query": "payment gateway stripe paypal", "limit": 5}
)

for memory in payment_memories:
    execute_forgetful_tool(
        "link_entity_to_memory",
        {
            "entity_id": new_hire["entity_id"],
            "memory_id": memory["memory_id"]
        }
    )
```

### Scenario 3: Infrastructure Incident Documentation

**Context:** Redis server failed, you resolved it and want to document for future reference.

```python
# 1. Get the server entity (can also search by alias like "redis-primary")
server = execute_forgetful_tool(
    "search_entities",
    {"query": "Cache Server 01"}
)
server_id = server[0]["entity_id"]

# 2. Create incident memory
incident = execute_forgetful_tool(
    "create_memory",
    {
        "title": "Redis failover incident - memory exhaustion",
        "content": "Cache Server 01 ran out of memory due to unbounded key growth. Implemented maxmemory-policy=allkeys-lru and set maxmemory=4gb. Also added monitoring alerts at 80% memory usage.",
        "importance": 9,
        "tags": ["incident", "redis", "infrastructure", "production"],
        "context": "Production incident on 2025-01-18, resolved in 45 minutes",
        "keywords": ["redis", "memory", "failover", "monitoring"]
    }
)

# 3. Link incident to server
execute_forgetful_tool(
    "link_entity_to_memory",
    {
        "entity_id": server_id,
        "memory_id": incident["memory_id"]
    }
)

# 4. Update server metadata with fix
execute_forgetful_tool(
    "update_entity",
    {
        "entity_id": server_id,
        "metadata": {
            "maxmemory": "4gb",
            "maxmemory_policy": "allkeys-lru",
            "last_incident": "2025-01-18",
            "monitoring": "enabled"
        }
    }
)

# 5. Create code artifact for monitoring script
monitoring_script = execute_forgetful_tool(
    "create_code_artifact",
    {
        "title": "Redis Memory Monitoring Script",
        "content": '''
import redis
import os

def check_redis_memory(threshold=0.8):
    r = redis.Redis(host='cache-server-01', port=6379)
    info = r.info('memory')
    used = info['used_memory']
    max_mem = info['maxmemory']

    if max_mem > 0 and (used / max_mem) > threshold:
        send_alert(f"Redis memory at {(used/max_mem)*100:.1f}%")
        ''',
        "language": "python",
        "tags": ["monitoring", "redis", "alerting"],
        "description": "Alert when Redis memory usage exceeds threshold"
    }
)

# 6. Link monitoring script to incident memory
execute_forgetful_tool(
    "create_memory",
    {
        "title": "Implemented Redis memory monitoring",
        "content": "Added monitoring script to alert at 80% memory usage to prevent future incidents",
        "importance": 8,
        "tags": ["monitoring", "prevention", "redis"],
        "linked_code_artifact_id": monitoring_script["code_artifact_id"]
    }
)
```

### Scenario 4: Research and Decision Making

**Context:** Researching database options, documenting findings, and making a decision.

```python
# 1. Create research project
research_project = execute_forgetful_tool(
    "create_project",
    {
        "name": "Database Technology Evaluation 2025",
        "project_type": "learning",
        "status": "active"
    }
)
project_id = research_project["project_id"]

# 2. Create comprehensive research document
research_doc = execute_forgetful_tool(
    "create_document",
    {
        "title": "Vector Database Comparison: pgvector vs Qdrant vs Weaviate",
        "content": "[... 5000-word detailed comparison of features, performance, costs ...]",
        "document_type": "markdown",
        "tags": ["research", "database", "vector-db", "embeddings"],
        "project_id": project_id
    }
)

# 3. Extract atomic insights as memories
insight1 = execute_forgetful_tool(
    "create_memory",
    {
        "title": "pgvector: Best for existing PostgreSQL setups",
        "content": "pgvector extension adds vector similarity search to existing PostgreSQL databases. Best choice when you already have PostgreSQL infrastructure and want to avoid managing separate vector DB.",
        "importance": 8,
        "tags": ["database", "pgvector", "postgresql", "vectors"],
        "project_id": project_id,
        "linked_document_id": research_doc["document_id"]
    }
)

insight2 = execute_forgetful_tool(
    "create_memory",
    {
        "title": "Qdrant: Best performance for large-scale vector search",
        "content": "Qdrant provides fastest search performance for >10M vectors with built-in filtering and clustering. Requires separate service deployment.",
        "importance": 8,
        "tags": ["database", "qdrant", "vectors", "performance"],
        "project_id": project_id,
        "linked_document_id": research_doc["document_id"]
    }
)

# 4. Make decision and create decision memory
decision = execute_forgetful_tool(
    "create_memory",
    {
        "title": "Decision: pgvector for Forgetful project",
        "content": "Selected pgvector for Forgetful because we already use PostgreSQL, need strong ACID guarantees, and <1M vector scale fits well within pgvector performance envelope.",
        "importance": 10,
        "tags": ["decision", "database", "pgvector", "forgetful"],
        "project_id": project_id,
        "linked_document_id": research_doc["document_id"]
    }
)

# 5. Manually link related insights to decision
execute_forgetful_tool(
    "link_memories",
    {"memory_id_1": decision["memory_id"], "memory_id_2": insight1["memory_id"]}
)

execute_forgetful_tool(
    "link_memories",
    {"memory_id_1": decision["memory_id"], "memory_id_2": insight2["memory_id"]}
)

# 6. Mark project as completed
execute_forgetful_tool(
    "update_project",
    {
        "project_id": project_id,
        "status": "completed",
        "metadata": {"decision": "pgvector", "completion_date": "2025-01-15"}
    }
)
```

---

## Best Practices

### Memory Creation
- **One concept per memory** - Follow atomic memory principle
- **Title it first** - If you can't easily title it, break it down further
- **High importance for reusable knowledge** - Use 8-10 for architectural decisions and patterns
- **Always provide context** - Future you will thank past you
- **Tag consistently** - Develop a tagging taxonomy for your knowledge domain

### Project Organization
- **Scope queries to projects** - Dramatically improves search relevance
- **Use project types consistently** - Helps with filtering and organization
- **Archive completed projects** - Don't delete - preserve knowledge with context
- **Link related projects** - Create memories that reference multiple projects

### Entity & Knowledge Graph
- **Entities for concrete things, memories for concepts** - "Sarah Chen" is an entity, "Sarah's API design preference" is a memory
- **Build relationships as you learn** - Don't wait to build complete graphs
- **Use metadata liberally** - Capture temporal and contextual information
- **Link entities to relevant memories** - Creates rich context for queries

### Code Artifacts & Documents
- **Code artifacts for reusable snippets (<200 lines)** - Utilities, patterns, configs
- **Documents for detailed content (>400 words)** - ADRs, research, specifications
- **Always extract atomic memories** - Documents are storage, memories are searchable knowledge
- **Link atoms to documents** - Preserve connection to detailed source

### Search & Retrieval
- **Query early and often** - Check existing knowledge before creating duplicates
- **Use natural language** - Semantic search works better than keyword matching
- **Filter by project for focus** - Especially in multi-project environments
- **Check auto-linked memories** - Often find related context you didn't know existed

---

## Token Budget & Performance

Forgetful protects your LLM context window with configurable token budgets:

- **Default: 8,000 tokens** per query result
- **Max 20 memories** returned per query
- **Prioritization**: High importance (9-10) → Medium importance (7-8) → Recency (newest first)
- **Graceful truncation**: If over budget, lower-priority memories excluded

Configure via environment variables:
```bash
MEMORY_TOKEN_BUDGET=8000
MEMORY_MAX_QUERY_RESULTS=20
```

---

## Additional Resources

- [Configuration Guide](configuration.md) - All environment variables
- [Connectivity Guide](connectivity_guide.md) - MCP client setup
- [Search Documentation](search.md) - Embedding pipeline details
- [MCP Protocol](https://modelcontextprotocol.io/) - MCP specification

---

**Last Updated:** 2025-01-22
**Forgetful Version:** 0.1.x
