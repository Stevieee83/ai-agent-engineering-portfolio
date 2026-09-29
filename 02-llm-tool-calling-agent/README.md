# Example 2: Utility-Based Decisions and an LLM-Powered Agent

Two standalone scripts that build on Example 1. The first shows how an agent
can rank options using a weighted utility function instead of a single-metric
score. The second replaces the hand-written decision logic entirely with an
LLM that reasons about the request and calls a tool (function) to act.

## Files

- **`agent.py`** — a plain-Python utility function (`travel_utility_function`)
  that scores travel options on a weighted mix of price, comfort, and
  convenience, then picks the best one. No API calls, no LLM — a clean
  illustration of multi-attribute utility scoring before an LLM is involved.
- **`agentic.py`** — an OpenAI-powered travel agent. It defines a `book_flight`
  tool, gives it to the model via OpenAI's function/tool-calling API, and
  runs a simple terminal chat loop so a user can converse with the agent and
  have it call the tool to book a flight.
- **`tools.json`** — the tool/function-calling schema for `book_flight`,
  loaded by `agentic.py` at startup rather than being defined inline.
- **`requirements.txt`** — Python dependencies (`openai`).

## Setup

```bash
pip install -r requirements.txt
```

`agentic.py` reads its OpenAI API key from the `OPENAI_API_KEY` environment
variable:

```bash
export OPENAI_API_KEY="your-key-here"
```

## Running the examples

**`agent.py`** is a plain script:

```bash
python agent.py
```

It prints the utility score for each hard-coded travel option and reports the
winner.

**`agentic.py`** runs directly from the terminal:

```bash
python agentic.py
```

It prints a prompt where you can type a request (e.g. "book me a flight from
London to New York on 15 October for John Smith"). The agent will ask for any
missing details, then confirm the booking. Type `quit` or `exit` to stop.

## How the LLM agent works (`agentic.py`)

1. The `book_flight` tool is described to the model using OpenAI's
   tool-calling schema, loaded from `tools.json` (name, description,
   parameters).
2. `travel_agent()` sends the conversation history plus the tool definition
   to `gpt-4-turbo`.
3. If the model decides it has enough information, it emits a `tool_calls`
   response instead of a plain answer; the arguments are parsed out and
   passed to the local `book_flight` function.
4. `book_flight` fabricates a booking reference — it never contacts a real
   airline or booking provider, so no real flight or payment is ever made.
5. The tool's result is appended back into the conversation as a `role:
   "tool"` message, and a second call to the model produces the final
   natural-language reply shown to the user.
6. The terminal loop wires user input and agent replies into this `messages`
   list turn by turn.
