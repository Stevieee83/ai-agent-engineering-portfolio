# AI Agent Engineering Portfolio

A set of three progressively more capable example agents, built to demonstrate
how an "agent" evolves from hand-written rules, to an LLM with a single tool,
to an LLM whose context is deliberately engineered (RAG, a knowledge graph,
reusable skills, and MCP). All three examples share the same scenario — a
travel-booking agent — so the differences between them come from the
architecture, not the domain. My intention is to develop the examples in
this repository to use more well established agentic AI and evaluation frameworks
like [LangGraph](https://www.langchain.com/langgraph), [CrewAI](https://www.crewai.com/)
and [MLflow](https://mlflow.org/) wherever possible.

Each example is self-contained, with its own `README.md`, dependencies, and
instructions to run it. This top-level README explains how the examples relate
to each other and how to get started.

## How it works

The three examples form a progression. Each one keeps the ideas from the
previous example and adds a new technique on top:

| # | Example | Adds | LLM involved? |
|---|---------|------|----------------|
| [01](01-symbolic-travel-agent) | **Symbolic travel agent** | Goal-setting, a knowledge base, and autonomous decision-making via a hand-written heuristic (cheapest flight wins). | No |
| [02](02-llm-tool-calling-agent) | **LLM tool-calling agent** | A weighted utility function for ranking options, then an LLM (via OpenAI's function/tool-calling API) that converses with the user and calls a `book_flight` tool to act. | Yes — single tool, no extra context |
| [03](03-context-engineered-agent) | **Context-engineered agent** | The same LLM + tool-calling loop, improved with **RAG** (retrieval over policy/airline documents), a **context graph** (traveller profile, relationships, multi-hop reasoning, long-term memory), **skills** (reusable expert procedures loaded on demand), and **MCP** (tools served over the Model Context Protocol instead of defined inline). Ships with a React + Tailwind web UI that lets you toggle each augmentation on/off and inspect what went into every reply. | Yes — fully context-engineered |

In short:

1. **Example 1** shows what "agency" and "autonomy" mean without an LLM at
   all — a loop that sets a goal, gathers data, scores it, and acts.
2. **Example 2** hands the decision-making to an LLM. The model now reasons in
   natural language and decides when to call a tool, but it only knows what it
   learned in pre-training plus whatever the user types in the conversation.
3. **Example 3** keeps that same LLM + tool-calling loop, but stops relying on
   the model's guesswork. It engineers the context the model sees at each
   turn — grounding it in real documents (RAG), structured facts about the
   traveller (context graph), consistent procedures (skills), and a clean
   separation between "thinking" and "doing" (MCP) — so the same question
   produces a far better answer.

## Repository structure

```
ai-agent-engineering-portfolio/
├── 01-symbolic-travel-agent/     # Rule-based agent, no LLM
├── 02-llm-tool-calling-agent/    # LLM + a single tool
└── 03-context-engineered-agent/  # LLM + RAG + context graph + skills + MCP + web UI
```

## Getting started

Each example has its own `requirements.txt` and is run independently — there
is no shared top-level dependency set. In general:

```bash
cd 0N-<example-name>
pip install -r requirements.txt
python <entry point>   # see that example's README for the exact command
```

Examples 2 and 3 use an LLM (OpenAI) and expect an `OPENAI_API_KEY`. Example 3
also runs without one, falling back to a deterministic offline planner so it
still demonstrates RAG, the context graph, skills and MCP without network
access. See each example's `README.md` for full setup, usage, and a suggested
demo flow.

## Slides

[AI_Agents_What_They_Are_and_Why_They_Matter.pptx.pdf](AI_Agents_What_They_Are_and_Why_They_Matter.pptx.pdf)
is the conference deck accompanying this portfolio.

## Disclaimer

This repository is for educational purposes only. Agentic AI systems can act
autonomously, call external tools, and make decisions with unintended or
unpredictable consequences. Use the code in this portfolio at your own
discretion and risk, and review it carefully before running it against real
data, accounts, or production systems.

All data used in these examples (travellers, bookings, policies, etc.) is
synthetic and fabricated for demonstration purposes. No personal data
belonging to any real individual is included in this repository.

## Further reading

For a deeper treatment of the concepts demonstrated here, see
*Building Agentic AI Systems: Create intelligent, autonomous AI agents that can reason, plan, and adapt* by Anjanava Biswas and Wrick Talukdar (Packt Publishing).

    @book{biswas2025buildingagentic,
    author    = {Biswas, Anjanava and Wrick Talukdar},
    title     = {Building Agentic AI Systems: Create intelligent, autonomous AI agents that can reason, plan, and adapt},
    publisher = {Packt Publishing},
    year      = {2025},
    isbn      = {978-1803238753}
    }

## License

See [LICENSE](LICENSE).
