---
description: Bootstrap a repository into Forgetful's knowledge base
---
# Encode Repository

Bootstrap a repository into Forgetful's knowledge base using a structured 7-phase protocol.

**Project name**: $ARGUMENTS

## Overview

This command walks through a comprehensive process to document a codebase into atomic memories, capturing:
- Project structure and architecture
- Key patterns and conventions
- Important decisions and their rationale
- Technical debt and future considerations

## Phase 1: Discovery

Gather basic project information:

1. Check git remote for repository name:
   ```bash
   !`git remote get-url origin 2>/dev/null || echo "No git remote"`
   ```

2. List project structure:
   ```bash
   !`find . -type f -name "*.md" -o -name "*.json" -o -name "*.toml" | head -20`
   ```

3. Check for existing project in Forgetful:
   ```
   execute_forgetful_tool("list_projects", {"repo_name": "<detected-repo>"})
   ```

4. If no project exists, create one:
   ```
   execute_forgetful_tool("create_project", {
     "name": "$ARGUMENTS",
     "description": "...",
     "project_type": "development",
     "repo_name": "<detected-repo>"
   })
   ```

## Phase 2: Foundation

Capture foundational information:

- Tech stack and dependencies
- Build system and tooling
- Development environment setup
- Testing approach

Create atomic memories for each foundation element.

## Phase 3: Architecture

Document the architecture:

- High-level system design
- Component relationships
- Data flow patterns
- External integrations

For complex architectures, create a document first, then extract atomic memories.

## Phase 4: Patterns

Identify and document patterns:

- Code conventions
- Error handling approach
- Logging patterns
- Configuration management

## Phase 5: Features

Document key features:

- Core functionality
- User-facing capabilities
- API surface (if applicable)
- Extension points

## Phase 6: Decisions

Capture important decisions:

- Why certain technologies were chosen
- Trade-offs that were made
- Rejected alternatives
- Technical debt acknowledged

## Phase 7: Validation

Verify the encoding:

1. Query the new memories:
   ```
   execute_forgetful_tool("query_memory", {
     "query": "$ARGUMENTS architecture patterns",
     "query_context": "Validating encode-repo results",
     "project_ids": [<new-project-id>]
   })
   ```

2. Check for gaps and offer to fill them

3. Report summary:
   ```
   Encoding complete for $ARGUMENTS:
   - Project ID: X
   - Memories created: Y
   - Documents created: Z
   - Key themes: [list]

   Suggested follow-up queries:
   - /memory-search $ARGUMENTS authentication
   - /memory-explore $ARGUMENTS
   ```

## Guidelines

- Create atomic memories (one concept per memory)
- Use importance scoring consistently
- Link related memories together
- Ask clarifying questions when needed
- Don't assume - query the codebase
