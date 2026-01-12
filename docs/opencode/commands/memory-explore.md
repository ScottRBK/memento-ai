---
description: Deep exploration of the Forgetful knowledge graph
---
# Memory Explore

Perform deep knowledge graph traversal to find related memories, entities, and documents.

**Query**: $ARGUMENTS

## Exploration Strategy

- Explore DEEPLY - follow links aggressively, expand entities, traverse relationships
- Be thorough - comprehensive exploration is valuable
- Track visited IDs to prevent cycles
- Surface only results relevant to the user's query in your final response
- Filter out tangential discoveries

## Phase 1: Semantic Entry

Start with a semantic search:

```
execute_forgetful_tool("query_memory", {
  "query": "$ARGUMENTS",
  "query_context": "Deep exploration via /memory-explore command",
  "k": 5,
  "include_links": true,
  "max_links_per_primary": 5
})
```

Collect all primary_memories and linked_memories.

## Phase 2: Expand Memory Details

For each primary memory found, get full details:

```
execute_forgetful_tool("get_memory", {"memory_id": <id>})
```

Extract: document_ids, code_artifact_ids, project_ids, linked_memory_ids

## Phase 3: Entity Discovery

For discovered project_ids, find related entities:

```
execute_forgetful_tool("list_entities", {"project_ids": [<ids>]})
```

Note: Entities can be explicitly linked to projects for organizational grouping using:
```
execute_forgetful_tool("link_entity_to_project", {"entity_id": <id>, "project_id": <id>})
```

## Phase 4: Entity Relationships

For each relevant entity, get relationships:

```
execute_forgetful_tool("get_entity_relationships", {
  "entity_id": <id>,
  "direction": "both"
})
```

## Phase 5: Entity-Linked Memories

For each entity, get linked memories:

```
execute_forgetful_tool("get_entity_memories", {"entity_id": <id>})
```

Fetch any new memories not already visited.

---

## Response Format

After exploration, provide a structured summary:

### Memories Found

**Primary (N):**
- [Title] (importance: X) - brief content snippet...

**Linked (N):**
- [Title] (importance: X) - connection type...

**Entity-linked (N):**
- [Title] - discovered via [Entity Name]...

### Entities Discovered

- [Name] (type) - X relationships, Y linked memories

### Documents & Artifacts

- [Title] (type/language) - if any found

### Graph Summary

- Total: X memories, Y entities, Z documents/artifacts
- Key themes: [identified clusters]
- Suggested follow-up: /memory-explore "[related query]"

---

## Notes

If the graph is sparse, suggest:
- Broader search terms
- Different project scope
- Creating new memories to build the graph
