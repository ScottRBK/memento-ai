# Forgetful Memory System

You have access to Forgetful, a semantic memory system that provides persistent knowledge storage across conversations and sessions.

## Overview

Forgetful is an MCP (Model Context Protocol) server that gives AI agents persistent memory. It stores knowledge as atomic notes using Zettelkasten principles, automatically builds knowledge graphs through semantic linking, and retrieves relevant context through natural language queries.

**Key capability**: Forgetful exposes only 3 meta-tools that provide access to 42 internal tools. This preserves your context window (~500 tokens vs ~15-20K if all tools were exposed directly).

---

## Core Principles

### Atomic Memory
Each memory contains ONE concept. If you can't easily title something in 5-50 words, break it down further.

| Field | Limit | Purpose |
|-------|-------|---------|
| Title | 200 chars | Short, searchable phrase |
| Content | 2000 chars | Single concept (~300-400 words) |
| Context | 500 chars | Why this matters |
| Keywords | 10 max | Semantic clustering |
| Tags | 10 max | Categorization |

### Importance Scoring
Use the 1-10 scale consistently:
- **9-10**: Foundational decisions, personal facts, architectural patterns
- **8-9**: Critical solutions, major decisions
- **7-8**: Useful patterns, preferences, tool choices
- **6-7**: Project milestones, specific solutions
- **<6**: Minor context (avoid creating these)

### Auto-Linking
When you create a memory, Forgetful automatically:
1. Generates an embedding vector for the content
2. Finds semantically similar memories (≥0.7 cosine similarity)
3. Creates bidirectional links (default: 3 connections)
4. Returns `auto_linked_to` list showing what was connected

### Token Budget
Queries return at most 20 memories, capped at ~8K tokens. Results are prioritized by importance (high first) → recency (newest first within same importance).

---

## The Meta-Tools Pattern

Forgetful uses 3 gateway tools to access all functionality:

### 1. `discover_forgetful_tools(category?)`
List available tools, optionally filtered by category.

```python
# See all tool categories
discover_forgetful_tools()

# See only entity tools
discover_forgetful_tools(category="entity")
```

Categories: `user`, `memory`, `project`, `code_artifact`, `document`, `entity`

### 2. `how_to_use_forgetful_tool(tool_name)`
Get detailed documentation for a specific tool including parameters and examples.

```python
how_to_use_forgetful_tool("create_entity")
```

### 3. `execute_forgetful_tool(tool_name, arguments)`
Execute any registered tool dynamically.

```python
execute_forgetful_tool("create_memory", {
    "title": "API design: REST over GraphQL",
    "content": "Chose REST for this project because...",
    "importance": 8
})
```

**Pattern**: Discover → Learn → Execute. You can skip discovery once you know the tools.

---

## Five Building Blocks

Forgetful organizes knowledge across 5 types:

| Type | What it stores | When to use |
|------|---------------|-------------|
| **Memories** | Atomic concepts, decisions, patterns | ONE concept that's directly queryable |
| **Entities** | Real-world things (people, orgs, devices) | Concrete things with stable identity |
| **Documents** | Long-form content (>300 words) | Detailed analysis, ADRs, research |
| **Code Artifacts** | Reusable code snippets | Utilities, patterns, templates |
| **Projects** | Organizational scope | Group related knowledge |

### Quick Decision Tree

```
Is this a PERSON, COMPANY, or DEVICE?
  → Yes: Create ENTITY
  → No: Continue...

Is this >300 words of detailed content?
  → Yes: Create DOCUMENT, then extract atomic MEMORIES
  → No: Continue...

Is this reusable CODE?
  → Yes: Create CODE ARTIFACT
  → No: Continue...

Is this ONE concept/decision/pattern?
  → Yes: Create MEMORY
  → No: Break it down, then create MEMORIES
```

---

## Deep Dive: Entities & Knowledge Graphs

**This section is critical.** Entities are often misunderstood—they represent CONCRETE REAL-WORLD THINGS, not abstract concepts.

### What Are Entities?

Entities have:
- **Stable identity** over time (a person remains the same person)
- **Physical or organizational existence** (not just ideas)
- **Relationships** to other entities

| Entity Type | Examples |
|-------------|----------|
| `Individual` | Sarah Chen, Alex Kim, your user |
| `Organization` | TechFlow Systems, Anthropic, client companies |
| `Team` | Platform Engineering, Design Team |
| `Device` | Cache Server 01, Production DB, laptop names |
| `Other` | Custom types (use with `custom_type` field) |

### Entity vs Memory: The Key Distinction

| This is... | Type | Why |
|-----------|------|-----|
| "Sarah Chen" | Entity | A person with stable identity |
| "Sarah prefers TypeScript" | Memory | Knowledge ABOUT Sarah |
| "TechFlow Systems" | Entity | An organization |
| "TechFlow uses microservices" | Memory | Knowledge ABOUT TechFlow |
| "Cache Server 01" | Entity | Physical infrastructure |
| "Redis memory limit set to 4GB" | Memory | Configuration knowledge |

**Rule**: If you can point at it (physically or organizationally), it's an entity. If it's a decision, pattern, preference, or insight—it's a memory.

### Entity Aliases (aka field)

Entities support alternative names for flexible lookup:

```python
execute_forgetful_tool("create_entity", {
    "name": "Sarah Chen",
    "entity_type": "Individual",
    "aka": ["Sarah", "S.C.", "Chen"]  # Up to 10 aliases
})
```

`search_entities` searches BOTH the name AND aka fields:

```python
# All of these find "Sarah Chen":
execute_forgetful_tool("search_entities", {"query": "Sarah"})
execute_forgetful_tool("search_entities", {"query": "S.C."})
execute_forgetful_tool("search_entities", {"query": "Chen"})
```

### Entity-Memory Links

Connect entities to related knowledge:

```python
# Create a decision memory
decision = execute_forgetful_tool("create_memory", {
    "title": "API rate limiting: 100 req/min",
    "content": "Implemented rate limiting at 100 requests per minute...",
    "importance": 8
})

# Link the person who made the decision
execute_forgetful_tool("link_entity_to_memory", {
    "entity_id": 42,  # Sarah Chen
    "memory_id": decision["memory_id"]
})
```

When querying memories, linked entities provide context. When viewing entities, you can retrieve all their associated memories.

### Entity Relationships (Knowledge Graphs)

Relationships are DIRECTIONAL connections between entities:

```
Sarah Chen --works_for--> TechFlow Systems --owns--> Cache Server 01
```

Built-in relationship types:
- `works_for` - Employment
- `member_of` - Team membership
- `owns` - Ownership
- `reports_to` - Reporting structure
- `collaborates_with` - Collaboration
- Custom types allowed

```python
# Sarah works for TechFlow
execute_forgetful_tool("create_entity_relationship", {
    "from_entity_id": 42,  # Sarah Chen
    "to_entity_id": 43,    # TechFlow Systems
    "relationship_type": "works_for",
    "metadata": {
        "role": "Principal Engineer",
        "start_date": "2024-03-15"
    }
})
```

### Presenting Entity Information to Users

**CRITICAL**: Never expose entity IDs to users. Always resolve IDs to names.

When you get relationship data, it contains entity IDs. You MUST fetch the actual entity names before presenting:

```python
# BAD - Don't do this:
# "You are a parent to entity ID 6"

# GOOD - Resolve IDs first:
relationships = execute_forgetful_tool("get_entity_relationships", {
    "entity_id": user_entity_id
})

for rel in relationships:
    # Resolve the target entity ID to get the name
    target = execute_forgetful_tool("get_entity", {
        "entity_id": rel["to_entity_id"]
    })
    # Now use the actual name
    # "You are a parent to Emma"
```

**Pattern for exploring relationships:**
1. Get relationships → returns IDs
2. For each related entity ID, call `get_entity` to get the name
3. Present using names: "Sarah works for TechFlow Systems" not "Entity 42 works_for Entity 43"

### Complete Entity Workflow

Here's a full example of building a knowledge graph:

```python
# 1. Create a person
person = execute_forgetful_tool("create_entity", {
    "name": "Sarah Chen",
    "entity_type": "Individual",
    "description": "Senior Backend Engineer",
    "aka": ["Sarah", "S.C."],
    "tags": ["engineering", "backend"]
})

# 2. Create a company
company = execute_forgetful_tool("create_entity", {
    "name": "TechFlow Systems",
    "entity_type": "Organization",
    "aka": ["TechFlow", "TFS"]
})

# 3. Create a device
server = execute_forgetful_tool("create_entity", {
    "name": "Cache Server 01",
    "entity_type": "Device",
    "aka": ["redis-primary", "cache-01"],
    "metadata": {"ip": "10.0.1.50"}
})

# 4. Create relationships
execute_forgetful_tool("create_entity_relationship", {
    "from_entity_id": person["entity_id"],
    "to_entity_id": company["entity_id"],
    "relationship_type": "works_for"
})

execute_forgetful_tool("create_entity_relationship", {
    "from_entity_id": company["entity_id"],
    "to_entity_id": server["entity_id"],
    "relationship_type": "owns"
})

# 5. Create a memory about a decision
decision = execute_forgetful_tool("create_memory", {
    "title": "Redis config: maxmemory-policy=allkeys-lru",
    "content": "Set Redis eviction policy after memory incident...",
    "importance": 8
})

# 6. Link the memory to relevant entities
execute_forgetful_tool("link_entity_to_memory", {
    "entity_id": person["entity_id"],
    "memory_id": decision["memory_id"]
})

execute_forgetful_tool("link_entity_to_memory", {
    "entity_id": server["entity_id"],
    "memory_id": decision["memory_id"]
})
```

---

## Essential Tool Reference

### Memory Tools (7 tools)

| Tool | Required Params | Purpose |
|------|-----------------|---------|
| `create_memory` | `title`, `content`, `importance` | Store atomic knowledge |
| `query_memory` | `query`, `query_context` | Semantic search |
| `get_memory` | `memory_id` | Retrieve by ID |
| `update_memory` | `memory_id` | Patch fields |
| `link_memories` | `memory_id`, `related_ids` | Manual linking |
| `mark_memory_obsolete` | `memory_id`, `reason` | Soft delete |
| `get_recent_memories` | (none) | Timeline view |

### Project Tools (5 tools)

| Tool | Required Params | Purpose |
|------|-----------------|---------|
| `create_project` | `name`, `description`, `project_type` | Create scope |
| `list_projects` | (none) | List all |
| `get_project` | `project_id` | Get details |
| `update_project` | `project_id` | Modify |
| `delete_project` | `project_id` | Remove (keeps memories) |

### Entity Tools (15 tools)

**CRUD Operations:**

| Tool | Required Params | Purpose |
|------|-----------------|---------|
| `create_entity` | `name`, `entity_type` | Create person/org/device |
| `list_entities` | (none) | List with filters |
| `search_entities` | `query` | Search name AND aka |
| `get_entity` | `entity_id` | Get by ID |
| `update_entity` | `entity_id` | Modify fields |
| `delete_entity` | `entity_id` | Remove (cascades) |

**Entity-Memory Linking:**

| Tool | Required Params | Purpose |
|------|-----------------|---------|
| `link_entity_to_memory` | `entity_id`, `memory_id` | Connect entity to knowledge |
| `unlink_entity_from_memory` | `entity_id`, `memory_id` | Remove connection |
| `get_entity_memories` | `entity_id` | All memories for entity |

**Relationships (Knowledge Graph):**

| Tool | Required Params | Purpose |
|------|-----------------|---------|
| `create_entity_relationship` | `from_entity_id`, `to_entity_id`, `relationship_type` | Create edge |
| `get_entity_relationships` | `entity_id` | Query edges |
| `update_entity_relationship` | `relationship_id` | Modify edge |
| `delete_entity_relationship` | `relationship_id` | Remove edge |

### Document & Code Artifact Tools (4 key tools)

| Tool | Required Params | Purpose |
|------|-----------------|---------|
| `create_document` | `title`, `description`, `content` | Long-form storage |
| `get_document` | `document_id` | Retrieve full content |
| `create_code_artifact` | `title`, `description`, `code`, `language` | Store snippets |
| `get_code_artifact` | `code_artifact_id` | Retrieve code |

---

## Common Workflows

### 1. Query Before Create (Prevent Duplicates)

Always check if similar knowledge exists:

```python
# Before creating memory about auth
results = execute_forgetful_tool("query_memory", {
    "query": "authentication OAuth JWT",
    "query_context": "Checking for existing auth memories before creating",
    "k": 5
})

if similar_exists(results):
    # Update existing memory instead
    execute_forgetful_tool("update_memory", {...})
else:
    # Create new memory
    execute_forgetful_tool("create_memory", {...})
```

### 2. Project Discovery

Find the correct project before creating memories:

```python
# List projects, optionally filter by repo
projects = execute_forgetful_tool("list_projects", {
    "repo_name": "owner/repo-name"
})

project_id = projects[0]["project_id"] if projects else None
```

### 3. Memory Creation Template

```python
execute_forgetful_tool("create_memory", {
    "title": "[Concise, searchable, <200 chars]",
    "content": "[ONE concept, ~300-400 words, max 2000 chars]",
    "importance": 8,  # 1-10 scale
    "context": "[Why this matters, max 500 chars]",
    "keywords": ["kw1", "kw2"],  # max 10
    "tags": ["tag1", "tag2"],  # max 10
    "project_ids": [PROJECT_ID]  # scope to project
})
```

### 4. Document Decomposition

For long content, create a document then extract atomic memories:

```python
# 1. Create document with full content
doc = execute_forgetful_tool("create_document", {
    "title": "ADR-003: Event-Driven Architecture",
    "content": "[... 2000+ words ...]",
    "document_type": "markdown",
    "project_id": PROJECT_ID
})

# 2. Extract key decisions as atomic memories
memory1 = execute_forgetful_tool("create_memory", {
    "title": "Architecture: Event-driven with Kafka",
    "content": "Selected event-driven architecture...",
    "importance": 10,
    "document_ids": [doc["document_id"]]
})

memory2 = execute_forgetful_tool("create_memory", {
    "title": "Tradeoff: Eventual consistency accepted",
    "content": "Team accepted eventual consistency...",
    "importance": 8,
    "document_ids": [doc["document_id"]]
})
```

### 5. Knowledge Graph Building

Build graphs incrementally as you learn:

```python
# Find or create entities as you encounter them
entity = execute_forgetful_tool("search_entities", {"query": "TechFlow"})

if not entity:
    entity = execute_forgetful_tool("create_entity", {
        "name": "TechFlow Systems",
        "entity_type": "Organization"
    })

# Link to memories when creating them
execute_forgetful_tool("link_entity_to_memory", {
    "entity_id": entity["entity_id"],
    "memory_id": memory["memory_id"]
})
```

---

## Best Practices & Anti-Patterns

### DO

- **Query before create** - Check for existing memories to prevent duplicates
- **Use project scoping** - Filter queries with `project_ids` for relevance
- **Link liberally** - Connect entities to memories, entities to entities
- **Mark obsolete, don't delete** - Preserve knowledge with audit trail
- **Use aka for aliases** - Enable flexible entity lookup
- **Build relationships incrementally** - Add graph edges as you learn
- **Search entities first** - Check if entity exists before creating

### DON'T

- **Expose entity IDs to users** - Always resolve IDs to names first
- **Create memories for transient info** - Current file paths, temporary errors
- **Assume project_id** - Always discover the correct project first
- **Store common knowledge** - Things readily available elsewhere
- **Exceed character limits** - Split into atomic pieces instead
- **Confuse entities with memories** - "Sarah" is entity, "Sarah's preference" is memory
- **Create duplicate entities** - Search before creating
- **Create low-importance memories (<6)** - Focus on reusable knowledge
- **Store entire documents as memories** - Use Documents, extract atoms

---

## Quick Reference

```python
# Essential patterns

# 1. Query memory
execute_forgetful_tool("query_memory", {
    "query": "search terms",
    "query_context": "why searching"
})

# 2. Create memory
execute_forgetful_tool("create_memory", {
    "title": "Short title",
    "content": "One concept",
    "importance": 8
})

# 3. Create entity
execute_forgetful_tool("create_entity", {
    "name": "Full Name",
    "entity_type": "Individual",
    "aka": ["Alias1", "Alias2"]
})

# 4. Search entities
execute_forgetful_tool("search_entities", {
    "query": "name or alias"
})

# 5. Link entity to memory
execute_forgetful_tool("link_entity_to_memory", {
    "entity_id": 42,
    "memory_id": 156
})

# 6. Create relationship
execute_forgetful_tool("create_entity_relationship", {
    "from_entity_id": 42,
    "to_entity_id": 43,
    "relationship_type": "works_for"
})

# 7. Explore relationships (resolve IDs to names!)
relationships = execute_forgetful_tool("get_entity_relationships", {
    "entity_id": 42
})
for rel in relationships:
    target = execute_forgetful_tool("get_entity", {"entity_id": rel["to_entity_id"]})
    # Now say: "You work for TechFlow Systems" - NOT "Entity 43"
```

---

*Last updated: 2026-01*
