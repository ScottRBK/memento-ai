# Rapid Project Scan Protocol

## Purpose
A streamlined approach to gain functional understanding of a codebase quickly. Use this for quick assessment, targeted changes, or initial orientation.

**Use this when:**
- Quick assessment before deciding on deep dive
- Small to medium projects (<50 files)
- Specific feature implementation (don't need full context)
- Initial triage before deeper exploration
- Bug fix needing minimal context
- Evaluating project for use/contribution

---

## 3-Phase Rapid Scan

### Phase 1: Foundation

**Understand WHAT the project is and HOW to run it**

#### Parallel File Read
```
read_file("README.md")
read_file("pyproject.toml" OR "package.json" OR "pom.xml")
read_file("main.py" OR "index.js" OR "app.py" OR "server.js")
read_file(".env.example" OR "config.yaml")  # optional
```

#### Extract:
- One-sentence project description
- Primary use case
- Tech stack (language, framework, database)
- How to run (commands)
- Key dependencies (top 5)

#### Output Format:
```
[PROJECT] is a [TYPE] that [PURPOSE] using [TECH STACK].
Run: [COMMAND]
Features: [3-5 bullets]
```

---

### Phase 2: Architecture Scan

**Map structure and understand HOW it works**

#### A. Directory Structure
```
list_dir("/")
```
Note: Top-level directories, naming conventions, presence of tests/docs/config

#### B. Layer Identification
```
list_dir("/app" OR "/src" OR "/lib")
grep_search("routes|controllers|api", isRegexp=true, includePattern="**/")
grep_search("services|domain", isRegexp=true, includePattern="**/")
grep_search("repositories|dal", isRegexp=true, includePattern="**/")
grep_search("models|entities", isRegexp=true, includePattern="**/")
```
Locate: Routes, Services, Repositories, Models, Middleware

#### C. Critical Path Trace (Pick ONE simple endpoint)
```
grep_search("@app.get|@router.get|app.get", isRegexp=true)
read_file("[route_file]")
read_file("[service_file]")
read_file("[repository_file]")
```
Trace: Route → Controller → Service → Repository → DB → Response

#### Output Format:
```
Architecture: [Layered / Modular / Monolithic]
Flow: Route → [Layer1] → [Layer2] → DB
Pattern: [MVC / Repository / Service-oriented]
```

#### D. Pattern Recognition
```
grep_search("@inject|DI|dependency", isRegexp=true)
grep_search("try|except|catch|throw", isRegexp=true)
grep_search("ORM|Session|query", isRegexp=true)
grep_search("@auth|authenticate|authorize", isRegexp=true)
```
Identify: DI approach, error handling, DB access, authentication

---

### Phase 3: Context Mining

**Understand WHY and find relevant context**

#### A. Knowledge Base (if available)
```
discover_forgetful_tools(category="memory")
query_memory({"query": "[project-name] architecture", "include_links": true})
query_memory({"query": "[project-name] decisions", "include_links": true})
```
Extract top 3-5 memories by importance score

#### B. Code Pattern Search
```
grep_search("TODO|FIXME|HACK|XXX", isRegexp=true)
grep_search("class.*Service|def.*service", isRegexp=true)
grep_search("async def|await", isRegexp=true)
grep_search("test_|describe\(", isRegexp=true)
```
Identify: Known issues, service patterns, async usage, testing approach

#### C. Dependency Analysis
```
read_file("pyproject.toml" OR "package.json")
```
Count total, identify top 3-5 critical dependencies, note unusual choices

---

## Rapid Scan Output

Generate this condensed summary:

```markdown
# [PROJECT] - Rapid Scan Summary

## What & Why
[One paragraph: what it is, what problem it solves, who uses it]

## Tech Stack
- Language: [version]
- Framework: [name]
- Database: [type]
- Key Libs: [top 3-5]

## Architecture
- Pattern: [architectural pattern]
- Layers: [list present layers]
- Request Flow: [simple trace]

## Quick Orientation Map
| To do this... | Look here... |
|---------------|--------------|
| Add API endpoint | [directory/file] |
| Add business logic | [directory/file] |
| Modify database | [directory/file] |
| Change config | [directory/file] |
| Run tests | [command] |

## Key Patterns
- **Dependency Injection**: [how]
- **Error Handling**: [approach]
- **Database Access**: [pattern]
- **Testing**: [framework & approach]

## Notable Observations
- [3-5 bullets of interesting/important things]

## Next Steps
- [ ] [If going deeper, what to explore next]
- [ ] [Specific files/areas to understand better]
```

---

## Decision Matrix: Rapid vs. Comprehensive

| Situation | Use Rapid Scan | Use Comprehensive |
|-----------|----------------|-------------------|
| Depth needed | Surface | Deep |
| Project size | < 50 files | Any size |
| Goal | Quick change | Major refactor |
| Familiarity | Similar projects | Novel domain |
| Knowledge base | Not available | Available |
| Depth needed | Surface level | Deep understanding |

---

## Rapid Scan for Specific Tasks

### "I need to add a new API endpoint"
1. Find existing endpoint example (grep_search for route decorator)
2. Trace that endpoint through layers
3. Copy pattern for new endpoint
4. Skip: deep architecture, design decisions, historical context

### "I need to fix a bug"
1. Locate error/symptom in logs or issue description
2. grep_search for relevant error messages/function names
3. Read minimal context around that code
4. Skip: overall architecture (unless bug is architectural)

### "I need to add a feature"
1. Find similar existing feature
2. Understand its implementation
3. Identify extension points
4. Copy and adapt pattern

### "I'm evaluating for use/contribution"
1. Read README thoroughly
2. Check license and dependencies
3. Run the project (if possible)
4. Scan issue tracker
5. Check test coverage (if metrics available)

---

## Optimization Tips

**Parallel Execution:**
- Read multiple files simultaneously
- Don't wait for KB queries before code exploration

**Strategic Sampling:**
- Sample 1-2 files per directory, not all
- Trace one simple endpoint, not all
- Focus on immediate needs, not exhaustive understanding

**Smart Search:**
```
# One search vs. multiple
grep_search("TODO|FIXME|HACK|XXX", isRegexp=true, includePattern="**/*.py")

# Overview vs. reading files
grep_search("class.*Service", isRegexp=true, includePattern="app/services/**")
```

**Pattern Recognition Shortcuts:**
- `repositories/` + `services/` + `routes/` = Repository pattern
- `middleware/` + route registration = Web framework
- `__init__.py` with imports = Python package
- `async`/`await` everywhere = Async architecture

Pattern recognition gives 80% understanding without deep reading.

---

## Escalation to Deep Dive

If rapid scan is insufficient:

1. Save rapid scan findings
2. Identify specific gaps (e.g., "unclear: database layer", "why this architecture?")
3. Execute targeted deep dive:
   - Focus on specific layers/components
   - Mine KB for specific topics
   - Read related documentation
4. Update findings

Or escalate to Comprehensive Understanding Protocol for full mastery.

---

## Usage

Invoke this protocol with:

```
Execute Rapid Project Scan on [PROJECT_NAME].

Goal: [add API endpoint / fix bug / evaluate fit / quick orientation]
Focus: [specific area if targeted]

Execute all 3 phases:
- Phase 1: Foundation (parallel file reads)
- Phase 2: Architecture scan (layer ID + trace)
- Phase 3: Context mining (KB + patterns)

Generate rapid scan summary.
```

---

## Critical Reminders

**Avoid:**
- ❌ Trying to understand everything
- ❌ Reading files sequentially
- ❌ Getting stuck on complex code
- ❌ Assuming complete picture
- ❌ Not documenting findings

**Ensure:**
- ✅ Understand enough for immediate task
- ✅ Read in parallel, sample strategically
- ✅ Note complexity, move on
- ✅ Document knowledge gaps
- ✅ Create quick reference notes

**Remember**: Rapid scan is reconnaissance (80/20 rule), not mastery. Escalate to Comprehensive Protocol when needed.
