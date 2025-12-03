# Core Concepts

Forgetful organizes knowledge into five building blocks. Understanding when to use each one makes the difference between a cluttered knowledge dump and a useful, searchable knowledge graph.

---

## The Building Blocks

### Memories

**Atomic knowledge units** - one concept per note.

Memories are the core of Forgetful. Each memory captures a single fact, decision, preference, or insight. Think of them as the nodes in your knowledge graph.

Good memories are:
- **Easily titled** - if you can't summarize it in ~10 words, it's probably not atomic
- **Self-contained** - understandable without needing to read other memories
- **Linkable** - small enough to connect precisely to related concepts

**Examples:**
- "Chose Stripe over PayPal for lower fees and better webhook support"
- "Use temperature 0.7 for creative tasks, 0.2 for factual queries"
- "Scott prefers explicit error handling over silent fallbacks"

**Limits:** 200 char title, ~300-400 words content

### Entities

**Real-world things** - people, organizations, devices, products.

Entities represent concrete nouns that exist in the world. They can have relationships with each other and link to memories. Use entities when you want to track WHO or WHAT is involved, not just the knowledge itself.

**Types:** Organization, Individual, Team, Device, Product, Service (or custom)

**Examples:**
- Sarah Chen (Individual) - "Backend lead, payments team"
- TechFlow Systems (Organization) - "SaaS platform company"
- Production Server 01 (Device) - "Primary API server, us-east-1"
- GPT-4 (Product) - "OpenAI's flagship model"

**Relationships:** Entities connect to each other (e.g., "Sarah works_at TechFlow") and to memories (e.g., "Sarah" linked to "Hired Sarah for Stripe integration").

### Documents

**Long-form reference material** - guides, analysis, specifications.

When content exceeds ~300 words or covers multiple related concepts, use a document. Documents are meant to be referenced, not retrieved in full during every query.

**Best practice:** Create the document, then extract 3-7 atomic memories that link back to it. This gives you both the detailed reference AND searchable knowledge atoms.

**Examples:**
- "Payment Integration Architecture Guide" - 2000 word technical spec
- "Q4 Planning Meeting Notes" - detailed discussion summary
- "TTS Engine Evaluation Report" - comparison of 5 different engines

### Code Artifacts

**Reusable code snippets** - patterns, templates, examples.

Attach working code to memories so agents can retrieve not just the concept but a concrete implementation.

**Examples:**
- Stripe webhook handler boilerplate
- FastAPI dependency injection pattern
- React form validation hook

### Projects

**Organizational scope** - groups memories by context.

Projects help you filter queries to relevant knowledge. When working on the e-commerce platform, you don't need memories from the trading bot project cluttering your results.

**Examples:**
- "E-Commerce Platform Redesign" (status: active)
- "Q4 Hiring Initiative" (status: completed)
- "AI Agent Framework" (status: active)

---

## Decision Flow: What Goes Where?

| Question | Answer |
|----------|--------|
| Is it a person, org, device, or product? | **Entity** |
| Is it detailed analysis or a guide (>300 words)? | **Document** |
| Is it a single fact, decision, or preference? | **Memory** |
| Is it reusable code? | **Code Artifact** |
| Does it help scope/filter other knowledge? | **Project** |

---

## The Litmus Test

### Memory vs Entity

**Entity** = a thing that EXISTS (noun you could point at)
**Memory** = knowledge ABOUT things (facts, decisions, preferences)

Ask: "Can I point at it?" If yes, probably an entity. If it's abstract knowledge, it's a memory.

- "Sarah Chen" - Entity (she exists)
- "Sarah is great at debugging async issues" - Memory (knowledge about Sarah)

### Memory vs Document

**Memory** = single concept, scannable, <400 words
**Document** = multiple concepts, reference material, >300 words

Ask: "Is this ONE idea or MANY?" One idea = memory. Many related ideas = document (then extract atomic memories from it).

- "Chose XTTS-v2 for voice cloning" - Memory
- "TTS Engine Evaluation comparing 5 engines with benchmarks" - Document

### When to Use Projects

Create a project when you have:
- Multiple related memories that should be queried together
- Work context that you'll return to repeatedly
- A need to exclude unrelated knowledge from searches

---

## Worked Example 1: E-Commerce Project

You're building a payment system. Here's how to decompose the knowledge:

**Entities:**
- Stripe (Product) - "Payment processor API"
- PayPal (Product) - "Alternative payment processor"
- Jordan Taylor (Individual) - "Backend engineer, payments team"
- TechFlow Systems (Organization) - "The company"

**Project:**
- "E-Commerce Platform v2" (active)

**Document:**
- "Payment Gateway Evaluation" - 1500 word comparison of Stripe vs PayPal vs Square

**Memories (extracted from document + decisions):**
- "Chose Stripe over PayPal: better webhooks, lower fees, superior fraud detection"
- "PCI compliance: use Stripe Elements to avoid handling raw card data"
- "Subscription billing requires Stripe Billing API, not one-time charges endpoint"
- "Jordan Taylor owns payment integration - hired specifically for Stripe experience"

**Code Artifact:**
- Stripe webhook signature verification snippet

**Links:**
- Memories link to → Stripe entity, PayPal entity, Jordan entity
- Memories link to → Payment Gateway Evaluation document
- Everything scoped to → E-Commerce Platform v2 project

---

## Worked Example 2: AI Agent Project

You're developing a coding assistant agent. Here's the breakdown:

**Entities:**
- Claude Sonnet (Product) - "Anthropic's fast model"
- Claude Opus (Product) - "Anthropic's reasoning model"
- OpenAI (Organization) - "GPT provider"
- Production Agent Server (Device) - "Hosts the deployed agent"

**Project:**
- "AI Coding Assistant" (active)

**Document:**
- "Prompt Engineering Guidelines" - 2000 word guide on system prompts, temperature, context management

**Memories (extracted + decisions):**
- "Use Claude Sonnet for quick edits, Opus for complex refactoring"
- "Temperature 0.3 for code generation, 0.7 for explanations"
- "System prompt must include repo structure for accurate file references"
- "Context window overflow: summarize conversation history after 50k tokens"
- "Tool calls: prefer specific tools over generic bash when available"

**Code Artifact:**
- Conversation summarization prompt template
- Tool result truncation logic

**Links:**
- Model-related memories link to → Claude Sonnet, Claude Opus entities
- Infrastructure memories link to → Production Agent Server entity
- Everything scoped to → AI Coding Assistant project

---

## Quick Reference

| Type | Size | Contains | Links To |
|------|------|----------|----------|
| Memory | <400 words | One concept | Memories, Entities, Documents, Code Artifacts |
| Entity | N/A | Real-world thing | Other Entities, Memories |
| Document | >300 words | Multiple concepts | Memories |
| Code Artifact | Variable | Working code | Memories |
| Project | N/A | Scope/context | Memories |

The knowledge graph emerges from these connections. Memories are the atoms; entities, documents, and projects provide structure and context.
