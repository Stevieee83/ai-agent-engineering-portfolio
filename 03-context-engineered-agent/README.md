# Example 3: A Context-Engineered Travel Agent (RAG + Context Graph + Skills + MCP)

Example 1 built a rule-based agent. Example 2 handed the decision to an LLM with
a single tool. The LLM in Example 2 only knows what it learned in pre-training and
what the user types, so it doesn't know your company's travel policy, the
traveller's preferences, that Dundee has no flights to Amsterdam, or how your
team likes flights to be ranked.

Example 3 keeps the same LLM + tool-calling loop but improves its output by
engineering the context it works with:

| Technique         | What it adds to the LLM                                               | Where                         |
|-------------------|-----------------------------------------------------------------------|-------------------------------|
| **RAG**           | Relevant passages from *our* documents (airline rules, travel policy, entry requirements, destination guides) | `rag.py`, `knowledge_base/`   |
| **Context graph** | Structured facts and relationships: who is travelling, where they live, nearby airports, loyalty schemes, past trips, events, plus multi-hop *insights* derived from them. Also acts as long-term memory. | `context_graph.py`, `data/context_graph.json` |
| **Skills**        | Reusable expert procedures (how to rank flights, check policy, build an itinerary, plan for families) loaded on demand | `skills.py`, `skills/*/SKILL.md` |
| **MCP**           | The travel tools live in a separate server behind the Model Context Protocol and are discovered at runtime | `mcp_server.py`               |

A React + Tailwind CSS web UI lets you enter trips, chat with the agent, **switch
RAG, the context graph and skills on and off**, and inspect exactly what context
and tool calls went into each answer.

## Architecture

```
 Browser (frontend/: HTML + Tailwind CSS + React)
    │  POST /api/chat {message, traveller, use_rag, use_graph, use_skills}
    ▼
 server.py (FastAPI) ──────────────────────────────────────────────────────────┐
    │                                                                          │
    ▼                                                                          │
 agent.py  TravelAgent                                                         │
    1. Context graph → traveller profile, linked entities, route insights      │
    2. RAG           → top passages for the request (+ a graph-guided query)   │
    3. System prompt = base rules + retrieved knowledge + graph facts          │
                       + skill catalogue (names & descriptions only)           │
    4. LLM tool loop (OpenAI) ── load_skill / search_knowledge_base /          │
                                 query_context_graph  (local tools)            │
                             └── search_flights / book_flight / search_hotels ─┼──► mcp_server.py
                                 / book_hotel / list_bookings  (MCP tools)     │    (stdio subprocess)
    5. Bookings are written back into the context graph (memory)               │    travel_provider.py
                                                                               │
 ◄──────────── reply + trace + retrieved context + bookings ───────────────────┘
```

## Files

- **`server.py`**: FastAPI app. Starts `mcp_server.py` as a subprocess, connects
  to it as an MCP client, reads its `travel://locations` resource, and serves
  the API and the front end.
- **`agent.py`**: the `TravelAgent`. Assembles context, runs the OpenAI
  tool-calling loop, records a step-by-step trace, and includes an offline
  fallback planner (see below).
- **`mcp_server.py`**: an MCP server (built with the official `mcp` Python SDK
  v2 `MCPServer`) exposing five tools and one resource.
- **`travel_provider.py`**: fake flight/hotel data, evolved from Example 1's
  Faker provider. Results are seeded by route and date, so a flight found in a
  search can be booked later in the conversation. Prices, durations and CO₂
  come from great-circle distances.
- **`rag.py`**: splits `knowledge_base/*.md` into chunks at `##` headings and
  retrieves them with TF-IDF cosine similarity (pure Python, no vector DB).
- **`context_graph.py`**: the knowledge graph. It does entity linking,
  breadth-first subgraph retrieval, multi-hop route reasoning
  (City → Airport ← Airline → Airport → City, with loyalty and past-trip
  annotations), and memory write-back.
- **`skills.py`**: loads `skills/*/SKILL.md` (YAML front matter plus markdown
  instructions, the same layout as Anthropic's Agent Skills).
- **`skills/`**: `flight-selection`, `travel-policy-compliance`,
  `itinerary-builder`, `family-travel`.
- **`knowledge_base/`**: airline policies, a fictional corporate travel
  policy, entry requirements, destination guides and a booking FAQ.
- **`data/supported_locations.json`**: airports, airlines, alliances and hotel
  cities (includes Dundee (DND), Edinburgh, Glasgow and Aberdeen).
- **`data/context_graph.json`**: seed graph with two fictional travellers,
  their preferences, loyalty memberships, past trips and an event. Airport,
  airline and alliance nodes are derived automatically from the locations file.
- **`frontend/index.html`, `frontend/app.jsx`**: the UI. It uses React 18,
  Tailwind CSS v4 and Babel standalone from a CDN, so there is **no npm/Node
  build step**.

## Setup

```bash
pip install -r requirements.txt
```

Python 3.10+ is required (the `mcp` SDK needs it). Note that `mcp` is pinned to
2.x: v2 renamed `FastMCP` to `MCPServer`, so v1 tutorials won't match this code.

To use a real LLM, set an OpenAI API key (optionally choose the model):

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-5-mini     # optional; any chat-completions model with tool calling
```

**No key? It still runs.** Without `OPENAI_API_KEY` the agent switches to a
deterministic **offline planner** that uses the same RAG, context graph, skills
and MCP tools, but writes templated replies instead of generated ones. This is
handy as a fallback if the venue Wi-Fi fails. The UI header shows which mode
you're in. (The UI still loads its scripts from a CDN, so the browser needs
internet access unless you've already cached the page.)

## Running

```bash
python server.py
```

Then open <http://localhost:8000> (set `PORT` to change it).

You can also run the pieces on their own:

```bash
python rag.py              # index the knowledge base and run a sample query
python context_graph.py    # print the graph context for a sample request
npx @modelcontextprotocol/inspector python mcp_server.py   # poke the MCP server in the MCP Inspector
```

Because the tools use standard MCP, `mcp_server.py` can be plugged into any MCP
client (e.g. Claude Desktop or an IDE) without changes.

## Using the UI

- **Who is travelling?** Pick *Alex Morgan* (a Dundee-based consultant subject to
  a corporate travel policy, attending the Amsterdam Data Summit), *Sam Rivera*
  (a Glasgow family of four on a budget who always need checked bags), or a
  *Guest* with no profile.
- **Context augmentation**: toggle RAG, the context graph and skills. Changes
  apply from the next message, so you can ask the same question twice and
  compare.
- **Trip request**: a structured form that turns into a natural-language
  request. You can also type into the chat or click an example prompt.
- **Inspector** (right-hand panel, for the selected reply):
  - *Trace*: every step (graph lookup, retrieval, LLM round, skill load, MCP
    call, memory write) with timings and expandable payloads, including the
    full system prompt.
  - *RAG*: the retrieved chunks and their similarity scores.
  - *Graph*: the traveller profile, derived insights, an interactive drawing
    of the retrieved subgraph, and the exact facts passed to the LLM.
  - *Skills*: which skills are available or loaded, and their instructions.
  - *Bookings*: confirmed flights and hotels.

## Suggested demo flow

1. Select **Alex**, turn **all augmentations off**, and send *"Get me to
   Amsterdam for the data summit, with a hotel"*. The agent doesn't know who
   Alex is, where they live or when the summit is, so it has to ask.
2. Click **New conversation**, turn **everything on**, and send the same message.
   Now the graph knows Alex lives in Dundee, that DND has no Amsterdam route but
   Edinburgh is 1h30 away by train, that the summit starts 14 October, and which
   airlines earn Alex's loyalty points. RAG brings in the hotel cap and the tip
   about staying near Zuid. Skills rank the flights and run a policy checklist.
   Open the Inspector to show each piece.
3. Reply *"yes"*. The agent books through MCP, and the booking is written back
   into the graph (look for 💾 in the trace). On the next message the new
   `Alex -[BOOKED]-> ...` trip appears in the Graph tab's facts, so the agent
   remembers it.
4. Switch to **Sam** and try *"Family trip to Dublin on 2026-10-17 for 3 nights
   with a hotel"*. The `family-travel` skill and Sam's graph profile change the
   answer: prices for four, checked-bag costs added to fares without a bag,
   penalties for very early or late departures, family rooms, and the child
   passport reminder. The graph also brings in Sam's past trip, where they paid
   extra for bags at the airport.
5. Turn skills **off** and ask the agent to *"... book it"*. Without the
   `travel-policy-compliance` skill, the only guardrail left is the one-line
   tool description. The offline planner books straight away, and an LLM may
   or may not stop to confirm. This is a good talking point about why
   guardrails belong in explicit, testable instructions.

## How the pieces improve the output

- **RAG grounds the answer.** The model cites `[1]`, `[2]` from your documents
  instead of guessing baggage rules or visa requirements. When a traveller is
  selected, a second graph-guided query adds passages about what *they* care
  about (e.g. child passports for Sam).
- **The context graph personalises and reasons.** Retrieved text can't tell the
  model that "Alex LIVES_IN Dundee, Dundee NEAR Edinburgh, KLM OPERATES_AT EDI
  and AMS, Alex MEMBER_OF Flying Blue, Flying Blue EARNABLE_ON KLM, Alex rated
  KLM 5/5". Walking those edges produces insights such as *"take the train to
  EDI and fly KLM direct, earning Flying Blue"*.
- **Skills make behaviour consistent.** Rather than hoping the model ranks
  flights sensibly, the `flight-selection` skill gives it a scoring rubric (the
  Example 2 utility function, written for an LLM). Only the one-line
  descriptions sit in the prompt; the full instructions are loaded with
  `load_skill` when relevant (progressive disclosure).
- **MCP separates thinking from doing.** The agent discovers the tools at
  startup (`list_tools`) and reads data through a resource. You could swap the
  fake provider for a real booking API, or reuse the server from another MCP
  client, without touching the agent.

## Notes and limitations

- All flights, hotels, prices, people and the Acme policy are **fictional demo
  data**. Airline and entry-requirement notes are simplified; don't use them
  for real travel.
- Times are shown in the departure airport's local time, and arrival times
  aren't adjusted for time zones.
- RAG uses TF-IDF to stay dependency-free. For production, swap in an
  embedding model and a vector store; the retrieve-then-generate flow is the
  same.
- The context graph is an in-memory Python structure. Bookings written to it
  are lost when the server restarts (deliberately, so the demo resets cleanly).
  A real system would use a graph database such as Neo4j.
- Conversation state is kept in memory per browser session, and the server
  handles one agent turn at a time.
