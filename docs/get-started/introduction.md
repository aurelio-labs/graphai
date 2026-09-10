GraphAI is a minimal "AI framework" that tries hard not to be one. It gives you a small, flexible graph runtime — nodes, edges, routers, state, streaming — and then gets out of the way. You build the agent, the LLM wrapper, the memory, exactly how you want them.

## What you get

GraphAI is built around a computational graph. It provides:

1. A **graph-based architecture** for wiring components into a workflow.
2. An **async-first design**, so waiting on API calls doesn't waste compute.
3. **Minimal abstractions** — no baked-in notion of "LLM" or "Agent" to fight against.
4. **Callbacks** for streaming and communication between components.

Other libraries ship their own idea of what an LLM, an agent, or a tool should look like. GraphAI doesn't. It hands you the primitives and lets you define those concepts yourself.

## Why

Most AI frameworks impose a shape on your application. That shape becomes a local minimum: fine right up until you need something the framework didn't anticipate. GraphAI takes the opposite stance.

- **Bring your own components.** Any LLM provider, any agent design, any telemetry.
- **Build the workflow you actually need**, not the one the framework assumes.
- **Think in flow, not framework.** Focus on how data moves through your app.

## The core ideas

**Async-first.** AI apps spend most of their time waiting on APIs. GraphAI is async from the ground up, so your code stays busy while responses are in flight.

**A graph of nodes.** Nodes do the work. Edges say where data flows next. Routers are nodes that choose the next path. Complex workflows stay readable because the structure *is* the diagram.

**Only what you need.** A `Graph` to orchestrate, `@node` and `@router` to define steps, a callback for streaming, and a state dict for context. That's the whole surface.

## When to reach for it

GraphAI fits when:

- You want full control over your architecture.
- Existing frameworks feel too opinionated.
- You're mixing components from different ecosystems.
- You prefer explicit code over magic.
- You're building something that doesn't fit the usual patterns.

Ready? The [quickstart](quickstart) builds a working agent in a few minutes.
