---
description: Save current context as an atomic memory in Forgetful
---
# Save Memory

Create an atomic memory from the current conversation context.

## Your Task

1. Analyze the conversation for the key insight/decision/pattern to capture
2. Check for existing related memories that might be affected
3. Create the memory with proper curation

**User guidance**: $ARGUMENTS

## Pre-Creation: Check for Existing Memories

Before creating, query for related memories:
```
execute_forgetful_tool("query_memory", {
  "query": "<topic of new memory>",
  "query_context": "Checking for existing memories before creating new one",
  "k": 5,
  "include_links": true
})
```

Analyze results to determine if the new memory would:
- **Invalidate** an existing memory (mark it obsolete with `mark_memory_obsolete`)
- **Update** an existing memory (use `update_memory` instead of creating new)
- **Supersede** an existing memory (create new, then mark old as obsolete with `superseded_by`)
- **Complement** existing memories (create new and potentially `link_memories`)

## Atomic Memory Principles (Zettelkasten)

Before creating, verify the memory passes the atomicity test:
- Can you understand the idea at first glance?
- Can you easily title it in 5-50 words?
- Does it represent ONE concept/fact/decision?

## Memory Constraints

- **Title**: Max 200 characters - short, searchable phrase
- **Content**: Max 2000 characters (~300-400 words) - single concept
- **Context**: Max 500 characters - WHY this matters
- **Keywords**: Max 10 - for semantic clustering
- **Tags**: Max 10 - for categorization

## Importance Scoring Guide

- **9-10**: Personal facts, foundational architectural patterns
- **8-9**: Critical technical solutions, major architectural decisions
- **7-8**: Useful patterns, strong preferences, tool choices
- **6-7**: Project milestones, specific solutions
- **5-6**: Minor context (use sparingly)

## Process

1. **Query** existing memories on the topic
2. **Analyze** if this is new knowledge, an update, or supersedes existing
3. **Draft** a memory following atomic principles
4. **Present** the draft with curation plan:
   ```
   Existing memories found:
   - Memory #42: "Previous auth decision" - will be marked obsolete (superseded)

   Ready to save this memory:

   Title: [proposed title]
   Content: [proposed content]
   Context: [why this matters]
   Keywords: [keyword1, keyword2, ...]
   Tags: [tag1, tag2, ...]
   Importance: [score with reasoning]
   Project: [if applicable]

   Curation actions:
   - Mark #42 obsolete (superseded by new memory)
   - Link to #38 (related pattern)

   Confirm? (y/n/edit)
   ```
5. **Execute** the curation plan after user confirms
6. **Report** the result including any auto-linked memories

## If Content is Too Long

If the concept requires >2000 characters:
1. Suggest using `create_document` for the full content
2. Extract 3-5 atomic memories from it
3. Link memories to the document via `document_ids`

## Example with Curation

User: `/memory-save`

You query existing memories, find related content, and propose:
```
Found 2 related memories:
- #89: "Plugin strategy: single plugin" (Importance: 7) - OUTDATED by this decision
- #45: "MCP scope hierarchy" (Importance: 8) - Related context

Ready to save this memory:

Title: "Plugin architecture: Two-plugin strategy (forgetful + context-hub)"
Content: "Decided on two-plugin approach: (1) forgetful - standalone memory tools,
(2) context-hub - orchestrates Forgetful + Context7 + WebSearch. Claude Code handles
duplicate MCP configs gracefully via scope hierarchy."
Context: "Architecture decision for shipping Forgetful as a Claude Code plugin"
Keywords: [claude-code, plugin, forgetful, mcp, architecture]
Tags: [decision, architecture]
Importance: 8 (major architectural decision)
Project: My Project (ID: 1)

Curation actions:
- Mark #89 obsolete (superseded by new memory)
- Link to #45 (MCP scope hierarchy context)

Confirm? (y/n/edit)
```
