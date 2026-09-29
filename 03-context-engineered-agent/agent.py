"""
The Example 3 travel agent: an LLM whose output is improved by four kinds of
context engineering.

  RAG            - relevant passages from knowledge_base/ are retrieved and put in the prompt
  Context graph  - traveller profile, relationships and derived route insights are put in the prompt
  Skills         - a catalogue of skills is listed; the model loads full instructions on demand
  MCP            - the travel tools live in a separate MCP server and are discovered at runtime

Each of RAG / graph / skills can be switched off per request, so you can compare
the plain "LLM + tools" agent from Example 2 with the context-engineered one.

If OPENAI_API_KEY is not set, a deterministic offline planner stands in for the
LLM. It still uses the same RAG, graph, skills and MCP tools, so the demo works
without network access (but its replies are templated, not generated).
"""
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from context_graph import ContextGraph
from rag import KnowledgeBase
from skills import SkillLibrary

MAX_TOOL_ROUNDS = 10
BOOKING_TOOLS = {"book_flight", "book_hotel"}

BASE_PROMPT = """You are a friendly, precise travel booking agent. Today is {today}.
You search and book flights and hotels with the travel tools. Supported airports: {airports}.

Rules:
- Never invent flights, hotels, prices or confirmation numbers - only use tool results.
- If the origin, destination or date is missing and cannot be inferred from the context below, ask for it.
- Prices are in GBP. Keep answers concise; use markdown tables when comparing options.
"""

RAG_PROMPT = """
## Retrieved knowledge (RAG)
These passages were retrieved from the company knowledge base for this request. Prefer them over
your own memory, cite them inline as [1], [2], ..., and call `search_knowledge_base` if you need more.
Ignore passages that do not apply (e.g. the corporate travel policy only applies to travellers who are SUBJECT_TO it).

{chunks}
"""

GRAPH_PROMPT = """
## Context graph
Facts about the traveller and the travel network, retrieved from the context graph. Use them to
personalise the plan (home airport, nearby airports, preferences, loyalty, past trips, events, policy).
Call `query_context_graph` to look up other entities.

{graph}
"""

SKILLS_PROMPT = """
## Skills
You have these skills. When a skill is relevant, call `load_skill` with its name BEFORE you answer,
then follow its instructions exactly. Load every skill that applies.

{catalog}
{loaded}"""

# Mirrors the "Hotel rate caps" section of knowledge_base/acme_travel_policy.md (offline planner only)
POLICY_HOTEL_CAPS = {"London": 220, "Amsterdam": 190, "Paris": 190, "Dublin": 170, "New York": 300,
                     "Seattle": 250, "Reykjavik": 200}


@dataclass
class TurnOptions:
    use_rag: bool = True
    use_graph: bool = True
    use_skills: bool = True


class Trace:
    """Records each step the agent takes so the UI can show its reasoning."""

    def __init__(self):
        self.steps: list[dict] = []

    def add(self, kind: str, title: str, detail=None, started: float | None = None):
        step = {"kind": kind, "title": title, "detail": detail}
        if started is not None:
            step["ms"] = int((time.perf_counter() - started) * 1000)
        self.steps.append(step)


def _tool_text(result) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


def _as_json(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


class TravelAgent:
    def __init__(self, mcp_client, locations: dict, llm_client=None, model: str = "gpt-5-mini"):
        self.mcp = mcp_client
        self.locations = locations
        self.llm = llm_client
        self.model = model
        self.kb = KnowledgeBase()
        self.graph = ContextGraph()
        self.skills = SkillLibrary()
        self.mcp_tools: list = []
        self.sessions: dict[str, dict] = {}

    async def start(self):
        self.mcp_tools = (await self.mcp.list_tools()).tools

    @property
    def mode(self) -> str:
        return "openai" if self.llm else "offline"

    def session(self, session_id: str) -> dict:
        return self.sessions.setdefault(session_id, {"messages": [], "bookings": [], "skills_loaded": [], "pending": None})

    def reset(self, session_id: str):
        self.sessions.pop(session_id, None)

    # ------------------------------------------------------------------ context assembly
    def _gather_context(self, session: dict, message: str, traveller_id: str | None, opts: TurnOptions, trace: Trace) -> dict:
        recent_user = [m["content"] for m in session["messages"] if m["role"] == "user"][-2:]
        query = " ".join(recent_user + [message])
        ctx = {"rag": [], "graph": None}

        # The graph runs first so it can also sharpen the RAG query (see below)
        if opts.use_graph:
            t = time.perf_counter()
            ctx["graph"] = self.graph.context_for(query, traveller_id)
            trace.add("graph", f"Context graph: {len(ctx['graph']['entities'])} entities linked, "
                               f"{len(ctx['graph']['triples'])} facts, {len(ctx['graph']['insights'])} insights",
                      {"entities": [e["label"] for e in ctx["graph"]["entities"]], "insights": ctx["graph"]["insights"]}, t)

        if opts.use_rag:
            t = time.perf_counter()
            ctx["rag"] = self.kb.search(query, k=3)
            detail = {"query": query}
            profile = ctx["graph"]["profile"] if ctx["graph"] else None
            if profile:
                # Graph-guided retrieval: a second search for what this traveller cares about, so a
                # family's "trip to Dublin" also finds baggage and child-passport guidance
                profile_query = " ".join(profile["preferences"] + ["children passport family"] * bool(profile.get("children"))
                                         + ["corporate travel policy"] * bool(profile.get("policy")))
                seen = {c["id"] for c in ctx["rag"]}
                ctx["rag"] += [c for c in self.kb.search(profile_query, k=3) if c["id"] not in seen][:2]
                detail["profile_query"] = profile_query
            detail["hits"] = [{"title": c["title"], "score": c["score"]} for c in ctx["rag"]]
            trace.add("rag", f"Retrieved {len(ctx['rag'])} knowledge chunks" + (" (+ graph-guided profile query)" if profile else ""), detail, t)
        return ctx

    def _system_prompt(self, session: dict, ctx: dict, opts: TurnOptions) -> str:
        airports = ", ".join(f"{code} ({a['city']})" for code, a in self.locations["airports"].items())
        prompt = BASE_PROMPT.format(today=date.today().isoformat(), airports=airports)
        if opts.use_rag and ctx["rag"]:
            prompt += RAG_PROMPT.format(chunks=KnowledgeBase.format_for_prompt(ctx["rag"]))
        if opts.use_graph and ctx["graph"]:
            prompt += GRAPH_PROMPT.format(graph=ContextGraph.format_for_prompt(ctx["graph"]) or "No relevant facts found.")
        if opts.use_skills:
            loaded = session["skills_loaded"]
            prompt += SKILLS_PROMPT.format(catalog=self.skills.catalog(),
                                           loaded=f"\nAlready loaded earlier in this conversation: {', '.join(loaded)}" if loaded else "")
        return prompt

    def _tool_schemas(self, opts: TurnOptions) -> list[dict]:
        tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                                   "parameters": t.input_schema}} for t in self.mcp_tools]
        if opts.use_rag:
            tools.append({"type": "function", "function": {
                "name": "search_knowledge_base",
                "description": "Search the travel knowledge base (airline policies, corporate travel policy, entry requirements, destination guides, booking FAQ).",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}})
        if opts.use_graph:
            tools.append({"type": "function", "function": {
                "name": "query_context_graph",
                "description": "Look up an entity (traveller, city, airport code, airline, loyalty programme, event) in the context graph and return its relationships.",
                "parameters": {"type": "object", "properties": {"entity": {"type": "string"}}, "required": ["entity"]}}})
        if opts.use_skills:
            tools.append({"type": "function", "function": {
                "name": "load_skill",
                "description": "Load the full instructions for a skill listed in the system prompt.",
                "parameters": {"type": "object", "properties": {"name": {"type": "string", "enum": list(self.skills.skills)}},
                               "required": ["name"]}}})
        return tools

    # ------------------------------------------------------------------ tool execution
    async def _call_tool(self, name: str, args: dict, session: dict, traveller_id: str | None, trace: Trace, new_bookings: list):
        t = time.perf_counter()
        if name == "search_knowledge_base":
            hits = self.kb.search(args.get("query", ""), k=3)
            trace.add("rag", f"search_knowledge_base(\"{args.get('query', '')}\")", [h["title"] for h in hits], t)
            return {"results": [{"title": h["title"], "text": h["text"]} for h in hits]}
        if name == "query_context_graph":
            result = self.graph.query(args.get("entity", ""))
            trace.add("graph", f"query_context_graph(\"{args.get('entity', '')}\")", result, t)
            return result
        if name == "load_skill":
            result = self.skills.load(args.get("name", ""))
            if "error" not in result and result["name"] not in session["skills_loaded"]:
                session["skills_loaded"].append(result["name"])
            trace.add("skill", f"Loaded skill: {args.get('name')}", result.get("instructions", result), t)
            return result

        # Everything else is an MCP tool on the travel server
        result = await self.mcp.call_tool(name, args)
        payload = _as_json(_tool_text(result))
        trace.add("mcp", f"MCP {name}({json.dumps(args)})", payload, t)
        if name in BOOKING_TOOLS and isinstance(payload, dict) and "confirmation" in payload:
            new_bookings.append(payload)
            session["bookings"].append(payload)
            memory = self.graph.record_booking(traveller_id, payload)
            if memory:
                trace.add("memory", "Wrote booking to context graph", memory)
        return payload

    # ------------------------------------------------------------------ main entry point
    async def chat(self, session_id: str, message: str, traveller_id: str | None, opts: TurnOptions) -> dict:
        session = self.session(session_id)
        trace = Trace()
        new_bookings: list[dict] = []
        ctx = self._gather_context(session, message, traveller_id, opts, trace)

        if self.llm:
            reply = await self._llm_turn(session, message, traveller_id, opts, ctx, trace, new_bookings)
        else:
            reply = await self._offline_turn(session, message, traveller_id, opts, ctx, trace, new_bookings)

        return {
            "reply": reply,
            "mode": self.mode,
            "trace": trace.steps,
            "context": {
                "rag": ctx["rag"],
                "graph": ctx["graph"],
                "skills_loaded": list(session["skills_loaded"]) if opts.use_skills else [],
            },
            "new_bookings": new_bookings,
            "bookings": session["bookings"],
        }

    async def _llm_turn(self, session, message, traveller_id, opts, ctx, trace, new_bookings) -> str:
        session["messages"].append({"role": "user", "content": message})
        system = self._system_prompt(session, ctx, opts)
        tools = self._tool_schemas(opts)
        trace.add("llm", f"System prompt assembled ({len(system):,} chars, {len(tools)} tools)", system)

        for _ in range(MAX_TOOL_ROUNDS):
            t = time.perf_counter()
            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}] + session["messages"],
                tools=tools,
            )
            msg = response.choices[0].message
            usage = response.usage
            calls = msg.tool_calls or []
            trace.add("llm", f"{self.model}: " + (f"requested {len(calls)} tool call(s)" if calls else "final answer"),
                      {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens} if usage else None, t)
            if not calls:
                session["messages"].append({"role": "assistant", "content": msg.content or ""})
                return msg.content or ""

            session["messages"].append({
                "role": "assistant", "content": msg.content,
                "tool_calls": [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls],
            })
            for call in calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                    result = await self._call_tool(call.function.name, args, session, traveller_id, trace, new_bookings)
                except Exception as e:  # report tool failures back to the model rather than crashing the turn
                    trace.add("error", f"{call.function.name} failed", str(e))
                    result = {"error": str(e)}
                session["messages"].append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
            # Skills loaded mid-turn should appear in the prompt for the next round
            system = self._system_prompt(session, ctx, opts)

        return "Sorry - I hit the tool-call limit for this turn. Could you rephrase or narrow the request?"

    # ------------------------------------------------------------------ offline planner
    def _parse_places(self, text: str) -> list[str]:
        """Airport codes mentioned in the text (as codes or city names), in order of appearance."""
        found = []
        for code, airport in self.locations["airports"].items():
            for pattern, flags in ((rf"\b{code}\b", 0), (rf"\b{re.escape(airport['city'])}\b", re.IGNORECASE)):
                m = re.search(pattern, text, flags)
                if m:
                    found.append((m.start(), code))
                    break
        ordered, seen_cities = [], set()
        for _, code in sorted(found):
            city = self.locations["airports"][code]["city"]
            if city not in seen_cities:   # "London" -> first London airport only
                seen_cities.add(city)
                ordered.append(code)
        return ordered

    def _pick_origin(self, profile: dict, dest: str) -> tuple[str | None, str | None]:
        """Use the graph: home airport if it has a direct route, else the best nearby airport."""
        dest_node = f"airport:{dest}"
        for code in profile["home_airports"]:
            if self.graph.direct_airlines(f"airport:{code}", dest_node):
                return code, None
        for near in profile["nearby_airports"]:
            if self.graph.direct_airlines(f"airport:{near['code']}", dest_node):
                return near["code"], f"No direct flights from {profile['home_city']}, so I've searched from {near['city']} ({near['code']}) - {near.get('by_rail', '')} by rail."
        return (profile["home_airports"] or [None])[0], None

    def _score_flights(self, flights: list[dict], profile: dict | None, party: int) -> list[dict]:
        """The flight-selection skill, as code."""
        prefs = set((profile or {}).get("preference_ids", []))
        loyalty = {c for p in (profile or {}).get("loyalty", []) for c in p["earn_on_codes"]}
        ratings = {t["airline_code"]: t.get("rating") for t in (profile or {}).get("past_trips", []) if t.get("airline_code")}
        options = []
        for f in flights:
            price = f["price_gbp_per_person"]["economy"] * party
            reasons = []
            if "pref:checked-bags" in prefs and not f["checked_bag_included"]:
                price += 45 * party
                reasons.append(f"⚠️ +£{45 * party} for bags")
            options.append({**f, "true_price": round(price, 2), "reasons": reasons})
        hour_ok = lambda f: 7 <= int(f["departure_time"][11:13]) < 22
        if "pref:no-red-eye" in prefs and any(hour_ok(f) for f in options):
            options = [f for f in options if hour_ok(f)]
        if "pref:direct-flights" in prefs and any(f["stops"] == 0 for f in options):
            options = [f for f in options if f["stops"] == 0]
        cheapest = min(f["true_price"] for f in options)
        shortest = min(f["duration_minutes"] for f in options)
        price_weight = 80 if "pref:low-price" in prefs else 40
        for f in options:
            score = cheapest / f["true_price"] * price_weight + shortest / f["duration_minutes"] * 25
            score += 15 if f["stops"] == 0 else 0
            if f["airline_code"] in loyalty:
                score += 10
                f["reasons"].append("earns your loyalty points")
            rating = ratings.get(f["airline_code"])
            if rating:
                score += 5 if rating >= 4 else -5
                f["reasons"].append(f"{'' if rating >= 4 else '⚠️ '}you rated them {rating}/5 last time")
            if (profile or {}).get("children") and not 8 <= int(f["departure_time"][11:13]) < 18:
                score -= 10   # family-travel skill: sensible departure times for children
                f["reasons"].append("⚠️ early/late departure for children")
            if f["checked_bag_included"]:
                f["reasons"].append("bag included")
            f["score"] = round(score, 1)
        return sorted(options, key=lambda f: f["score"], reverse=True)

    async def _offline_turn(self, session, message, traveller_id, opts, ctx, trace, new_bookings) -> str:
        session["messages"].append({"role": "user", "content": message})
        profile = ctx["graph"]["profile"] if ctx["graph"] else None
        lower = message.lower()
        trace.add("llm", "Offline planner (no OPENAI_API_KEY) - deterministic stand-in for the LLM")

        # Skills: keyword routing stands in for the model choosing which skills to load
        active = []
        if opts.use_skills:
            hints = message + (" family children" if profile and profile.get("children") else "") + \
                    (" business policy booking" if profile and profile.get("policy") else "")
            active = list(dict.fromkeys(["flight-selection"] + self.skills.suggest(hints, limit=3)))
            for name in active:
                if name not in session["skills_loaded"]:
                    session["skills_loaded"].append(name)
                trace.add("skill", f"Loaded skill: {name}", self.skills.load(name)["instructions"])

        # 1. Confirmation of a pending booking
        pending = session.get("pending")
        if pending and re.search(r"\b(yes|confirm|go ahead|book it|please book)\b", lower):
            reply = await self._offline_book(session, pending, traveller_id, trace, new_bookings)
            session["messages"].append({"role": "assistant", "content": reply})
            return reply

        # 2. Understand the request
        conversation = " ".join(m["content"] for m in session["messages"] if m["role"] == "user")
        places = self._parse_places(message) or self._parse_places(conversation)
        notes = []
        if len(places) >= 2:
            origin, dest = places[0], places[1]
        elif len(places) == 1 and profile:
            dest = places[0]
            origin, note = self._pick_origin(profile, dest)
            if note:
                notes.append(note)
        else:
            reply = ("Where would you like to fly from and to? Supported airports: "
                     + ", ".join(f"{c} ({a['city']})" for c, a in self.locations["airports"].items()) + ".")
            if len(places) == 1:
                reply = f"Where are you flying to {self.locations['airports'][places[0]]['city']} from? " + reply.split("? ", 1)[1]
            session["messages"].append({"role": "assistant", "content": reply})
            return reply

        m = re.search(r"\d{4}-\d{2}-\d{2}", message) or re.search(r"\d{4}-\d{2}-\d{2}", conversation)
        dest_city = self.locations["airports"][dest]["city"]
        event = next((e for e in (profile or {}).get("events", []) if e["city"] == dest_city), None)
        if m:
            travel_date = m.group(0)
        elif event:
            travel_date = (datetime.strptime(event["start"], "%Y-%m-%d") - timedelta(days=1)).date().isoformat()
            notes.append(f"You're attending **{event['name']}** ({event['start']}), so I've looked at flights the day before.")
        else:
            travel_date = (date.today() + timedelta(days=14)).isoformat()
            notes.append(f"No date given, so I've assumed {travel_date}.")
        pm = re.search(r"(\d+)\s*(people|passengers|travellers|adults|guests|of us)", lower)
        party = int(pm.group(1)) if pm else (profile or {}).get("party_size", 1)

        # 3. Act through MCP
        t = time.perf_counter()
        args = {"origin": origin, "destination": dest, "departure_date": travel_date, "passengers": party}
        result = _as_json(_tool_text(await self.mcp.call_tool("search_flights", args)))
        trace.add("mcp", f"MCP search_flights({json.dumps(args)})", result, t)
        if "error" in result or not result.get("flights"):
            reply = f"I couldn't find flights from {origin} to {dest}: {result.get('error') or result.get('note')}"
            if not profile and not opts.use_graph:
                reply += " (With the context graph switched on I could suggest nearby airports.)"
            session["messages"].append({"role": "assistant", "content": reply})
            return reply

        if "flight-selection" in active:
            ranked = self._score_flights(result["flights"], profile, party)
        else:  # Example-2-style baseline: cheapest first, no personalisation
            ranked = sorted(({**f, "true_price": round(f["price_gbp_per_person"]["economy"] * party, 2), "reasons": [], "score": None}
                             for f in result["flights"]), key=lambda f: f["true_price"])
        best = ranked[0]

        hotel = None
        nights_m = re.search(r"(\d+)\s*nights?", lower)
        if "hotel" in lower or nights_m:
            nights = int(nights_m.group(1)) if nights_m else 3
            cap = POLICY_HOTEL_CAPS.get(dest_city, 150) if profile and profile.get("policy") else None
            t = time.perf_counter()
            hargs = {"city": dest_city, "check_in": travel_date, "nights": nights, "guests": party}
            hres = _as_json(_tool_text(await self.mcp.call_tool("search_hotels", hargs)))
            trace.add("mcp", f"MCP search_hotels({json.dumps(hargs)})", hres, t)
            hotels = hres.get("hotels", []) if isinstance(hres, dict) else []
            if cap:
                hotels = [h for h in hotels if h["price_gbp_per_night"] <= cap] or hotels
            if profile and "pref:family-hotel" in profile["preference_ids"]:
                hotels.sort(key=lambda h: ("family_rooms" not in h["amenities"], -h["guest_rating"]))
            else:
                hotels.sort(key=lambda h: -h["guest_rating"])
            hotel = hotels[0] if hotels else None

        # 4. Compose the reply
        who = profile["name"].split()[0] if profile else "there"
        lines = [f"Hi {who}! Here are flights **{origin} → {dest}** on **{travel_date}** for {party} traveller{'s' * (party > 1)}:", ""]
        for n in notes:
            lines += [f"> {n}", ""]
        lines.append("| Flight | Airline | Departs | Duration | Stops | Total | " + ("Score |" if best["score"] is not None else ""))
        lines.append("|---|---|---|---|---|---|" + ("---|" if best["score"] is not None else ""))
        for f in ranked[:4]:
            stops = "Direct" if f["stops"] == 0 else f"1 (via {f['via']})"
            lines.append(f"| {f['flight_number']} | {f['airline']} | {f['departure_time'][11:]} | {f['duration_minutes'] // 60}h{f['duration_minutes'] % 60:02d} "
                         f"| {stops} | £{f['true_price']:,.2f} |" + (f" {f['score']} |" if f["score"] is not None else ""))
        lines.append("")
        pros = [r for r in best["reasons"] if not r.startswith("⚠️")]
        cons = [r[2:].strip() for r in best["reasons"] if r.startswith("⚠️")]
        why = ", ".join(pros) or ("cheapest option" if best["score"] is None else "best overall score")
        if cons:
            why += f" (trade-offs: {', '.join(cons)})"
        lines.append(f"**Recommendation: {best['airline']} {best['flight_number']}** - {why}.")
        if hotel:
            lines.append(f"\n🏨 **Hotel:** {hotel['name']} ({hotel['stars']}★, {hotel['guest_rating']}/10) - "
                         f"£{hotel['price_gbp_per_night']:.0f}/night x {hotel['nights']} nights; amenities: {', '.join(hotel['amenities'])}.")

        if "travel-policy-compliance" in active and profile and profile.get("policy"):
            days_ahead = (datetime.strptime(travel_date, "%Y-%m-%d").date() - date.today()).days
            total = best["true_price"] + (hotel["price_gbp_per_night"] * hotel["nights"] if hotel else 0)
            lines.append("\n**Policy check** (" + profile["policy"] + ")")
            lines.append(f"- {'✅' if best['duration_minutes'] < 360 else '⚠️'} Economy cabin for a {best['duration_minutes'] // 60}h{best['duration_minutes'] % 60:02d} flight")
            lines.append(f"- {'✅' if days_ahead >= 14 else '⚠️'} Booked {days_ahead} days ahead (policy: 14+)")
            if hotel:
                cap = POLICY_HOTEL_CAPS.get(dest_city, 150)
                lines.append(f"- {'✅' if hotel['price_gbp_per_night'] <= cap else '❌'} Hotel £{hotel['price_gbp_per_night']:.0f}/night (cap £{cap})")
            lines.append(f"- {'✅' if total <= 1500 else '⚠️'} Trip total £{total:,.2f} (approval needed over £1,500)")

        if "family-travel" in active and party > 2:
            lines.append(f"\n👨‍👩‍👧‍👦 Priced for all {party} travellers. Children under 12 sit with an adult free of charge; every child needs their own passport.")

        # The corporate policy only applies to travellers who are subject to it
        tips = [(i, c) for i, c in enumerate(ctx["rag"], 1) if c["score"] >= 0.15
                and ((profile and profile.get("policy")) or "policy" not in c["source"])][:4]
        if tips:
            lines.append("\n**Good to know**")
            for i, chunk in tips:
                first = " ".join(re.split(r"(?<=\.)\s", chunk["text"])[:2])
                lines.append(f"- {first} [{i}]")

        if re.search(r"\bbook\b", lower) and "travel-policy-compliance" not in active:
            # Without the compliance skill the agent books straight away - the risky Example 2 behaviour
            session["pending"] = {"offer_id": best["offer_id"], "passengers": party, "hotel_id": hotel["hotel_id"] if hotel else None}
            lines.append("\n" + await self._offline_book(session, session["pending"], traveller_id, trace, new_bookings))
        else:
            session["pending"] = {"offer_id": best["offer_id"], "passengers": party, "hotel_id": hotel["hotel_id"] if hotel else None}
            lines.append(f"\nShall I book **{best['flight_number']}**" + (" and the hotel" if hotel else "") + "? Reply **yes** to confirm.")

        reply = "\n".join(lines)
        session["messages"].append({"role": "assistant", "content": reply})
        return reply

    async def _offline_book(self, session, pending, traveller_id, trace, new_bookings) -> str:
        name = self.graph.label(traveller_id) if traveller_id in self.graph.nodes else "Guest Traveller"
        lines = []
        calls = [("book_flight", {"offer_id": pending["offer_id"], "passenger_name": name, "passengers": pending["passengers"]})]
        if pending.get("hotel_id"):
            calls.append(("book_hotel", {"hotel_id": pending["hotel_id"], "guest_name": name}))
        for tool, args in calls:
            booking = await self._call_tool(tool, args, session, traveller_id, trace, new_bookings)
            if isinstance(booking, dict) and "confirmation" in booking:
                lines.append(f"✅ Booked {booking['type']} - confirmation **{booking['confirmation']}** (£{booking['total_price_gbp']:,.2f}).")
            else:
                lines.append(f"⚠️ {tool} failed: {booking}")
        session["pending"] = None
        return "\n\n".join(lines)
