# Forgetful Prompts

## Overview

AI-agent optimized prompts for understanding codebases and managing project knowledge through Forgetful MCP. Each prompt provides direct, executable instructions with concrete tool calls—ready to paste into an AI agent's system prompt or context.

---

## Prompts

| Prompt | Depth | Use When | Output |
|--------|-------|----------|--------|
| **[Custom Agent Integration](custom_agent_integration.md)** | Comprehensive | Building custom agents, system prompts, deep entity/knowledge graph coverage | Agent with full Forgetful capability |
| **[Example System Prompt](example_system_prompt.md)** | Reference | Adding Forgetful context to CLAUDE.md or system prompts | Ready-to-copy prompt |
| **[Rapid Scan](rapid_project_scan_prompt.md)** | Surface | Bug fixes, quick features, evaluation, initial orientation | Quick orientation map |
| **[Comprehensive Understanding](comprehensive_project_understanding_prompt.md)** | Deep | Major refactoring, architectural changes, deep debugging | Understanding document |
| **[KB Bootstrap](knowledge_base_bootstrap_prompt.md)** | KB Population | Documenting projects, enabling AI agents, institutional knowledge | Populated knowledge base |

---

## Quick Decision Guide

| Your Goal | Use This |
|-----------|----------|
| Build a custom agent with Forgetful | Custom Agent Integration |
| Understand entities & knowledge graphs | Custom Agent Integration |
| Fix a bug | Rapid Scan |
| Add small feature | Rapid Scan |
| Understand architecture | Comprehensive Understanding |
| Major refactoring | Comprehensive Understanding |
| Deep debugging | Comprehensive Understanding |
| Document project | KB Bootstrap |
| Enable AI agents | KB Bootstrap |
| Build institutional knowledge | KB Bootstrap |
| Quick orientation | Rapid Scan |
| Evaluate project fit | Rapid Scan |
| Add Forgetful to CLAUDE.md | Example System Prompt |
| Configure AI agent for Forgetful | Example System Prompt |

---

## Usage

Most agentic coding tools offer hotkeys/commands for reusing prompts, that's why I think it might be better to just list some suggestions and then people can tailor these and wire these up on their individual agents. I do concede that this does add a bit of setup friction, especially if you are setting up multiple agents. the MCP protocol actually supports a /prompt command, however it relies on the agent consuming the tool to have logic baked into to actually call it. 

Here are some documents for setting up commands on some of the various coding agents:

[Claude Code](https://claude.ai/public/artifacts/e2725e41-cca5-48e5-9c15-6eab92012e75)

[Open Code](https://opencode.ai/docs/commands/)

[Codex](https://developers.openai.com/codex/guides/slash-commands/#create-your-own-slash-commands-with-custom-prompts)


Alternatively if your application does not have command based prompts, then you can copy-paste the prompt file contents into your AI agent conversation, then specify:

**Rapid Scan:**
```
Execute Rapid Project Scan on [PROJECT_NAME].
Goal: [add endpoint / fix bug / evaluate fit]
```

**Comprehensive Understanding:**
```
Execute Comprehensive Project Understanding on [PROJECT_NAME].
Goal: [major refactor / architectural change / deep debugging]
```

**KB Bootstrap:**
```
Bootstrap the [PROJECT_NAME] knowledge base using Forgetful MCP.
Project: [owner/repo-name]
Type: [web app / library / CLI / service]
Size: [small / medium / large]
```

**Example System Prompt:**
Copy the contents directly into your CLAUDE.md file or system prompt configuration. No parameters needed—it provides behavioral guidance for AI agents using Forgetful.

---

## Prompt Workflows

These prompts work together:

**Rapid → Comprehensive:**
Start with rapid scan for orientation, escalate to comprehensive for complex areas identified.

**Comprehensive → KB Bootstrap:**
Use understanding document as blueprint for which memories to create.

**KB Bootstrap → Faster Future Understanding:**
Well-populated KB dramatically accelerates future comprehensive understanding (queries return context instead of exploring from scratch).

**Phase 0 Discovery:**
KB Bootstrap includes Phase 0 that checks existing coverage—prevents duplicates, identifies gaps, works for both new and existing projects.

---

## Key Features

**AI-Agent Optimized:**
- Direct, executable instructions
- Concrete tool calls with parameters
- No human time estimates
- Copy-paste ready

**Forgetful MCP Integration:**
- Specific `query_memory`, `create_memory`, `update_memory` calls
- `discover_forgetful_tools` usage
- Auto-linking mechanics (similarity ≥0.7)
- Project/memory/document/artifact/entity patterns

**Phase 0 Discovery (KB Bootstrap):**
Prevents duplicate creation by checking existing project/memories, comparing with current codebase, performing gap analysis, then creating targeted bootstrap plan.

---

## Best Practices

**Start Simple:**
Use Rapid Scan for quick tasks, escalate to Comprehensive only when needed.

**KB Maintenance:**
Bootstrap is not one-time—update memories as code evolves, mark obsolete memories, add new features.

**Strategic Linking:**
Let auto-linking handle semantic connections (≥0.7 similarity), manually link memories to code artifacts and documents.

**Atomic Memories:**
One concept per memory (200-400 words), use documents for >400 word content.

**Honest Importance:**
Most memories should be 7-8, reserve 9-10 for foundational decisions.

---

## Prompt Characteristics

**All Three Prompts:**
- Project-agnostic and reusable
- Direct AI agent instructions
- Concrete tool calls with parameters
- No human time constraints
- Action-oriented phases

**Rapid Scan:**
- 3 phases (Foundation → Architecture → Context)
- Parallel file reads
- Strategic sampling (not exhaustive)
- 80/20 rule application
- Quick escalation path to Comprehensive

**Comprehensive Understanding:**
- 4 phases (KB Mining → Code Exploration → Synthesis → Documentation)
- Deep pattern identification
- Rationale extraction (why, not just what)
- Dependency mapping
- Quality assessment

**KB Bootstrap:**
- Phase 0: Discovery & Assessment (prevents duplicates)
- Phases 1-10: Project → Architecture → Patterns → Features → Decisions → Config → Artifacts → Documents → Entities → Linking
- Atomic memory creation (200-400 words)
- Auto-linking verification (≥0.7 similarity)
- Gap analysis for existing projects
- Coverage goals: 15-25 memories, 5-10 artifacts, 3-5 documents
