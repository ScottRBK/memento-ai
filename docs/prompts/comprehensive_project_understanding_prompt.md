# Comprehensive Project Understanding Protocol

## Purpose
A systematic approach for gaining deep understanding of any codebase through knowledge base mining and code exploration. Use this when you need complete project mastery for major refactoring, architectural changes, or comprehensive documentation.

**Use this when:**
- Major refactoring or architectural changes planned
- Need to understand design rationale and trade-offs
- Contributing significant features
- Writing comprehensive documentation
- Deep debugging requiring full system understanding

---

## Phase 1: Knowledge Base Mining (If Available)

**If project has Forgetful MCP or similar knowledge base, start here:**

### Execute Knowledge Base Queries

Use `discover_forgetful_tools` and execute these queries:

```
# Discover available tools
discover_forgetful_tools(category="memory")
discover_forgetful_tools(category="project")
discover_forgetful_tools(category="document")
discover_forgetful_tools(category="entity")

# Query for project information
query_memory({
  "query": "[project-name] architecture overview",
  "include_links": true,
  "project_ids": [project_id]
})

query_memory({
  "query": "[project-name] design decisions",
  "include_links": true,
  "project_ids": [project_id]
})

query_memory({
  "query": "[project-name] implementation patterns",
  "include_links": true,
  "project_ids": [project_id]
})

query_memory({
  "query": "[project-name] features capabilities",
  "include_links": true,
  "project_ids": [project_id]
})

# List all project content
list_memories({"project_id": project_id})
list_documents({"project_id": project_id})
list_code_artifacts({"project_id": project_id})
list_entities({"entity_type": "Individual"})
list_entities({"entity_type": "Device/System"})
```

### Compile KB Summary

Organize findings into:

**A. Project Overview & Purpose**
- What problem does this solve?
- Core value proposition
- Current status and maturity

**B. Architecture & Design**
- System architecture patterns
- Component structure
- Data flow and interactions
- Key design decisions with rationale

**C. Technical Implementation**
- Technology stack
- Critical implementation patterns
- Infrastructure and deployment
- Testing strategy

**D. Features & Capabilities**
- Core feature set
- Advanced capabilities
- Configuration options

**E. Knowledge Artifacts**
- Code patterns stored
- Documentation available
- Entities and relationships
- Historical context and evolution

**F. Design Rationale**
- Why certain approaches were chosen
- Trade-offs and constraints
- Known limitations

**G. Statistics**
- Number of memories/documents/artifacts
- Coverage areas and gaps

---

## Phase 2: Codebase Exploration

### Objective
Systematically explore the actual source code to understand structure, patterns, and implementation details.

### Exploration Workflow

#### Step 1: Foundation Documents (Parallel Read)
```
read_file("README.md")
read_file("pyproject.toml" OR "package.json" OR "pom.xml")
read_file("CONTRIBUTING.md" OR "ARCHITECTURE.md")  # if exists
read_file("settings.py" OR "config.yaml" OR ".env.example")
```

Extract: Purpose, setup steps, tech stack, configuration surface

#### Step 2: Entry Points
```
list_dir("/")  # Identify structure
read_file("main.py" OR "index.js" OR "app.py" OR "server.ts")
```

Identify: Startup logic, DI setup, middleware registration, routing

#### Step 3: Core Architecture (Map Layers)
```
list_dir("/app" OR "/src" OR "/lib")
semantic_search("repository pattern implementation")
semantic_search("service layer business logic")
grep_search("class.*Service|def.*service", isRegexp=true)
grep_search("class.*Repository", isRegexp=true)
```

Map: Models, Protocols/Interfaces, Repositories, Services, Routes, Middleware

#### Step 4: Key Patterns
```
grep_search("@inject|dependency injection", isRegexp=true)
grep_search("try.*except|catch.*error", isRegexp=true)
semantic_search("authentication authorization implementation")
grep_search("test_|describe\(", isRegexp=true)
```

Document: DI approach, error handling, DB patterns, auth, testing

#### Step 5: Critical Flows (Trace One Complete Request)
```
# Pick simplest endpoint and trace:
grep_search("@app.get|@router.get|app.get", isRegexp=true)
read_file("[route_file]")
read_file("[service_file]")
read_file("[repository_file]")
```

Trace: Request → Controller → Service → Repository → Database → Response

---

## Phase 3: Synthesis

**Combine KB insights with code exploration:**

### Reconciliation
- Compare KB design intentions with actual code implementation
- Identify evolution since documentation (what changed and why)
- Note deviations from original plans

### Pattern Identification
- **Architectural**: Layered, hexagonal, microservices, event-driven?
- **Design**: Repository, Factory, Strategy, Observer, etc.
- **Anti-Patterns**: Technical debt areas

### Rationale Extraction
- Why these technologies?
- What problems do patterns solve?
- What constraints drove decisions?

### Dependency Mapping
- Component dependency graph
- Critical paths for core features
- Extension points for new features

### Quality Assessment
- Code organization clarity
- Separation of concerns
- Test coverage and approach
- Error handling consistency

---

## Phase 4: Generate Understanding Document

Compile findings into structured document:

```markdown
# [PROJECT_NAME] - Comprehensive Understanding

## Executive Summary
[2-3 paragraphs capturing essence of the project]

## Architecture Overview
### High-Level Architecture
[Describe the overall architecture pattern and structure]

### Component Map
[List and describe major components/modules]

### Data Flow
[Explain how data moves through the system]

## Technology Stack
- **Language**: [Primary language and version]
- **Framework**: [Main framework]
- **Database**: [Database technology]
- **Key Libraries**: [Critical dependencies]
- **Infrastructure**: [Deployment approach]

## Core Patterns & Practices

### Architectural Patterns
[Document key architectural patterns observed]

### Design Patterns
[List design patterns with examples from codebase]

### Code Organization
[Explain directory structure and organization principles]

## Key Features & Implementation

### Feature 1: [Name]
- **Purpose**: [What it does]
- **Implementation**: [How it's implemented]
- **Key Files**: [Where to find it]

[Repeat for major features]

## Configuration & Extensibility

### Configuration Options
[Document configuration system and key settings]

### Extension Points
[Where and how to extend the system]

## Design Decisions & Rationale

### Decision 1: [Topic]
- **Decision**: [What was decided]
- **Rationale**: [Why this approach]
- **Trade-offs**: [What was sacrificed]
- **Alternatives**: [What was considered]

[Repeat for major decisions]

## Development Workflow

### Setup & Dependencies
[How to get started]

### Testing Strategy
[How testing is approached]

### Build & Deployment
[How to build and deploy]

## Areas for Improvement
[Objective observations about technical debt, missing features, or enhancement opportunities]

## Learning Resources
[Links to relevant documentation, key files to study, etc.]

## Glossary
[Define domain-specific terms and acronyms]
```

---

## Adaptation Guidelines

### For Different Project Types

**Web Applications**
- Focus on: Request/response cycle, middleware, routing, state management
- Key files: Server entry, route definitions, controllers, views

**Libraries/Frameworks**
- Focus on: Public API surface, extension points, documentation
- Key files: Exported modules, plugin systems, examples

**CLI Tools**
- Focus on: Command parsing, execution flow, output formatting
- Key files: CLI entry point, command handlers, configuration

**Data Processing/ML**
- Focus on: Pipeline architecture, data transformations, model management
- Key files: Pipeline definitions, transformers, training scripts

**Mobile Apps**
- Focus on: App lifecycle, navigation, state management, native bridges
- Key files: App entry, screen components, navigation configuration

### For Different Languages

**Python**: Look for `__init__.py`, `setup.py`/`pyproject.toml`, virtual environments

**JavaScript/TypeScript**: Look for `package.json`, `tsconfig.json`, module systems

**Java**: Look for `pom.xml`/`build.gradle`, package structure, Spring configuration

**C#**: Look for `.csproj`, namespace organization, dependency injection

**Go**: Look for `go.mod`, package structure, interface definitions

**Rust**: Look for `Cargo.toml`, module structure, trait definitions

---

## Success Criteria

You've achieved comprehensive understanding when you can:

1. ✅ Explain the project's purpose to someone unfamiliar
2. ✅ Describe the high-level architecture and why it was chosen
3. ✅ Trace a complete request/workflow from entry to exit
4. ✅ Identify where to make common types of changes
5. ✅ Explain key design decisions and trade-offs
6. ✅ Understand the configuration and deployment model
7. ✅ Know where to find critical implementation details
8. ✅ Recognize the patterns and conventions used
9. ✅ Identify dependencies and their roles
10. ✅ Spot areas for improvement or technical debt

---

## Usage

Invoke this protocol with:

```
Execute Comprehensive Project Understanding on [PROJECT_NAME].

Goal: [major refactor / architectural change / deep debugging / etc.]

If knowledge base available:
- Execute Phase 1: KB mining (parallel queries)
- Execute Phase 2: Code exploration (parallel reads)
- Execute Phase 3: Synthesize KB + code
- Execute Phase 4: Generate understanding document

If no knowledge base:
- Skip Phase 1 or adapt to project documentation/wiki
- Execute Phase 2: Thorough code exploration
- Execute Phase 3: Synthesize code insights
- Execute Phase 4: Generate understanding document
```

---


