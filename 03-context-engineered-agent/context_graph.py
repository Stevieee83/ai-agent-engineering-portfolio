"""
Context graph: a small knowledge graph of travellers, their preferences,
loyalty programmes, past trips and events, linked to cities, airports,
airlines and alliances.

Where RAG retrieves *passages of text*, the context graph supplies *facts and
relationships* ("Alex LIVES_IN Dundee", "Dundee NEAR Edinburgh", "KLM
OPERATES_AT EDI and AMS", "Alex MEMBER_OF Flying Blue", "Flying Blue
EARNABLE_ON KLM"). Following those edges lets the agent work out things no
single document says - e.g. "Alex can take the train to Edinburgh and fly KLM
direct to Amsterdam, earning Flying Blue miles on an airline they rated 5/5".

The graph is also the agent's long-term memory: confirmed bookings are written
back as new Trip nodes (see `record_booking`).
"""
import json
import os
import re
from collections import deque
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(__file__)

# Edges that fan out a lot; only followed when both ends are already relevant
NOISY_RELATIONS = {"OPERATES_AT"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class ContextGraph:
    def __init__(self):
        with open(os.path.join(BASE_DIR, "data", "context_graph.json")) as f:
            seed = json.load(f)
        with open(os.path.join(BASE_DIR, "data", "supported_locations.json")) as f:
            self.locations = json.load(f)

        self.nodes: dict[str, dict] = {n["id"]: {"props": {}, "aliases": [], **n} for n in seed["nodes"]}
        self.edges: list[dict] = [{"props": {}, **e} for e in seed["edges"]]
        self._derive_travel_network()

    # ------------------------------------------------------------------ build
    def _add_node(self, node_id: str, type_: str, label: str, aliases=None, props=None):
        if node_id not in self.nodes:
            self.nodes[node_id] = {"id": node_id, "type": type_, "label": label, "aliases": aliases or [], "props": props or {}}

    def _add_edge(self, source: str, relation: str, target: str, props=None):
        self.edges.append({"source": source, "relation": relation, "target": target, "props": props or {}})

    def _derive_travel_network(self):
        """Create airport, airline and alliance nodes from supported_locations.json."""
        for code, airline in self.locations["airlines"].items():
            self._add_node(f"airline:{code}", "Airline", airline["name"], aliases=[airline["name"].lower()])
            if airline["alliance"]:
                alliance_id = f"alliance:{_slug(airline['alliance'])}"
                self._add_node(alliance_id, "Alliance", airline["alliance"], aliases=[airline["alliance"].lower()])
                self._add_edge(f"airline:{code}", "MEMBER_OF", alliance_id)
            if airline["hub"]:
                self._add_edge(f"airline:{code}", "HUB_AT", f"airport:{airline['hub']}")
        for code, airport in self.locations["airports"].items():
            city_id = f"city:{_slug(airport['city'])}"
            self._add_node(city_id, "City", airport["city"], aliases=[airport["city"].lower()])
            self._add_node(f"airport:{code}", "Airport", f"{airport['name']} ({code})",
                           aliases=[airport["name"].lower()],
                           props={"code": code, "routes_only_to": airport.get("routes_only_to")})
            self._add_edge(f"airport:{code}", "LOCATED_IN", city_id)
            for airline_code in airport["airlines"]:
                self._add_edge(f"airline:{airline_code}", "OPERATES_AT", f"airport:{code}")

    # ------------------------------------------------------------------ helpers
    def label(self, node_id: str) -> str:
        return self.nodes.get(node_id, {}).get("label", node_id)

    def out(self, node_id: str, relation: str | None = None) -> list[dict]:
        return [e for e in self.edges if e["source"] == node_id and (relation is None or e["relation"] == relation)]

    def inc(self, node_id: str, relation: str | None = None) -> list[dict]:
        return [e for e in self.edges if e["target"] == node_id and (relation is None or e["relation"] == relation)]

    def triple(self, edge: dict) -> str:
        props = f" {edge['props']}" if edge["props"] else ""
        return f"{self.label(edge['source'])} -[{edge['relation']}]-> {self.label(edge['target'])}{props}"

    def airports_in(self, city_id: str) -> list[str]:
        return [e["source"] for e in self.inc(city_id, "LOCATED_IN") if e["source"].startswith("airport:")]

    def city_of(self, node_id: str) -> str | None:
        if node_id.startswith("city:"):
            return node_id
        edges = self.out(node_id, "LOCATED_IN")
        return edges[0]["target"] if edges else None

    def airlines_at(self, airport_id: str) -> set[str]:
        return {e["source"] for e in self.inc(airport_id, "OPERATES_AT")}

    def direct_airlines(self, a: str, b: str) -> set[str]:
        """Airlines operating at both airports, honouring `routes_only_to` (e.g. Dundee only flies to LCY)."""
        for x, y in ((a, b), (b, a)):
            only = self.nodes[x]["props"].get("routes_only_to")
            if only and self.nodes[y]["props"]["code"] not in only:
                return set()
        return self.airlines_at(a) & self.airlines_at(b)

    # ------------------------------------------------------------------ entity linking
    def link_entities(self, text: str) -> list[dict]:
        """Find graph nodes mentioned in free text, ordered by where they appear."""
        found: dict[str, int] = {}
        lowered = text.lower()
        for node in self.nodes.values():
            if node["type"] in ("Preference", "Trip"):
                continue
            names = set(node["aliases"]) | {node["label"].lower()}
            for name in names:
                m = re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", lowered)
                if m:
                    found[node["id"]] = min(found.get(node["id"], m.start()), m.start())
            # Airport codes must be written in capitals ("EDI"), to avoid matching ordinary words
            code = node["props"].get("code")
            if code:
                m = re.search(rf"\b{code}\b", text)
                if m:
                    found[node["id"]] = min(found.get(node["id"], m.start()), m.start())
        return [{"id": nid, "label": self.label(nid), "type": self.nodes[nid]["type"], "position": pos}
                for nid, pos in sorted(found.items(), key=lambda kv: kv[1])]

    # ------------------------------------------------------------------ traveller profile
    def traveller_profile(self, traveller_id: str | None) -> dict | None:
        if not traveller_id or traveller_id not in self.nodes:
            return None
        node = self.nodes[traveller_id]
        home = next((e["target"] for e in self.out(traveller_id, "LIVES_IN")), None)
        nearby = [(e["target"], e["props"]) for e in self.out(home, "NEAR")] + \
                 [(e["source"], e["props"]) for e in self.inc(home, "NEAR")] if home else []
        loyalty = [{"programme": self.label(e["target"]), "tier": e["props"].get("tier"),
                    "earn_on": [self.label(x["target"]) for x in self.out(e["target"], "EARNABLE_ON")],
                    "earn_on_codes": [x["target"].split(":")[1] for x in self.out(e["target"], "EARNABLE_ON")]}
                   for e in self.out(traveller_id, "MEMBER_OF")]
        trips = []
        for e in self.out(traveller_id, "TOOK") + self.out(traveller_id, "BOOKED"):
            trip = self.nodes[e["target"]]
            airline = next((self.label(x["target"]) for x in self.out(trip["id"], "FLEW_WITH")), None)
            airline_code = next((x["target"].split(":")[1] for x in self.out(trip["id"], "FLEW_WITH")), None)
            trips.append({"label": trip["label"], "airline": airline, "airline_code": airline_code, **trip["props"]})
        return {
            "id": traveller_id,
            "name": node["label"],
            **node["props"],
            "home_city": self.label(home) if home else None,
            "home_city_id": home,
            "home_airports": [self.nodes[a]["props"]["code"] for a in self.airports_in(home)] if home else [],
            "nearby_airports": [{"code": self.nodes[a]["props"]["code"], "city": self.label(c), **props}
                                for c, props in nearby for a in self.airports_in(c)],
            "preferences": [self.label(e["target"]) for e in self.out(traveller_id, "PREFERS")],
            "preference_ids": [e["target"] for e in self.out(traveller_id, "PREFERS")],
            "loyalty": loyalty,
            "policy": next((self.label(e["target"]) for e in self.out(traveller_id, "SUBJECT_TO")), None),
            "events": [{"name": self.label(e["target"]), "city": self.label(self.city_of(e["target"]) or ""),
                        "city_id": self.city_of(e["target"]), **self.nodes[e["target"]]["props"]}
                       for e in self.out(traveller_id, "ATTENDING")],
            "past_trips": trips,
        }

    # ------------------------------------------------------------------ subgraph + reasoning
    def subgraph(self, seeds: list[str], max_hops: int = 2, max_edges: int = 60) -> list[dict]:
        """Breadth-first expansion from the seed nodes, returning the edges visited."""
        seen_nodes, seen_edges, result = set(seeds), set(), []
        relevant_airports = {a for s in seeds for a in ([s] if s.startswith("airport:") else self.airports_in(s))}
        queue = deque((s, 0) for s in seeds)
        while queue and len(result) < max_edges:
            node_id, depth = queue.popleft()
            if depth >= max_hops:
                continue
            for edge in self.out(node_id) + self.inc(node_id):
                key = (edge["source"], edge["relation"], edge["target"])
                if key in seen_edges:
                    continue
                if edge["relation"] in NOISY_RELATIONS and edge["target"] not in relevant_airports:
                    continue
                seen_edges.add(key)
                result.append(edge)
                other = edge["target"] if edge["source"] == node_id else edge["source"]
                if other not in seen_nodes:
                    seen_nodes.add(other)
                    queue.append((other, depth + 1))
        return result[:max_edges]

    def route_insights(self, origin_city: str, dest_city: str, profile: dict | None) -> list[str]:
        """Derive route facts by walking City -> Airport <- Airline -> Airport -> City."""
        insights = []
        origin_airports = self.airports_in(origin_city)
        # Travellers can also fly from airports in NEAR cities (e.g. Dundee -> Edinburgh)
        near = [(e["target"], e["props"]) for e in self.out(origin_city, "NEAR")] + \
               [(e["source"], e["props"]) for e in self.inc(origin_city, "NEAR")]
        dest_airports = self.airports_in(dest_city)
        loyalty_codes = {c for p in (profile or {}).get("loyalty", []) for c in p["earn_on_codes"]}
        rated = {t["airline_code"]: t.get("rating") for t in (profile or {}).get("past_trips", []) if t.get("airline_code")}

        def describe(origin_ap: str, dest_ap: str, note: str = "") -> str | None:
            common = self.direct_airlines(origin_ap, dest_ap)
            if not common:
                return None
            parts = []
            for a in sorted(common):
                code = a.split(":")[1]
                tags = []
                if code in loyalty_codes:
                    tags.append("earns traveller's loyalty points")
                if code in rated:
                    tags.append(f"traveller rated a past trip {rated[code]}/5")
                parts.append(self.label(a) + (f" ({'; '.join(tags)})" if tags else ""))
            o, d = self.nodes[origin_ap]["props"]["code"], self.nodes[dest_ap]["props"]["code"]
            return f"Direct {o}->{d}{note}: " + ", ".join(parts)

        direct_found = False
        for oa in origin_airports:
            for da in dest_airports:
                line = describe(oa, da)
                if line:
                    insights.append(line)
                    direct_found = True
        if not direct_found and origin_airports:
            codes = ", ".join(self.nodes[a]["props"]["code"] for a in origin_airports)
            insights.append(f"No direct flights from {self.label(origin_city)} ({codes}) to {self.label(dest_city)}.")
        for city, props in near:
            for oa in self.airports_in(city):
                for da in dest_airports:
                    line = describe(oa, da, f" (from nearby {self.label(city)}, rail: {props.get('by_rail', 'n/a')})")
                    if line:
                        insights.append(line)
        return insights

    def context_for(self, message: str, traveller_id: str | None) -> dict:
        """Everything the agent should know from the graph for this message."""
        entities = self.link_entities(message)
        profile = self.traveller_profile(traveller_id)
        seeds = [e["id"] for e in entities]
        if profile:
            seeds.insert(0, traveller_id)
        edges = self.subgraph(seeds)

        insights = []
        cities = []
        for e in entities:
            city = self.city_of(e["id"])
            if city and city not in cities:
                cities.append(city)
        if len(cities) == 1 and profile and profile["home_city_id"] and cities[0] != profile["home_city_id"]:
            cities.insert(0, profile["home_city_id"])   # "fly me to Amsterdam" -> from home
        if len(cities) >= 2:
            insights += self.route_insights(cities[0], cities[1], profile)
        if profile:
            for p in profile["loyalty"]:
                insights.append(f"{profile['name']} holds {p['tier']} tier in {p['programme']} (earns on: {', '.join(p['earn_on'])}).")
            for ev in profile["events"]:
                if ev.get("city_id") in cities or not cities:
                    start = datetime.strptime(ev["start"], "%Y-%m-%d")
                    insights.append(f"{profile['name']} is attending {ev['name']} in {ev['city']} "
                                    f"({ev['start']} to {ev.get('end', ev['start'])}); suggested arrival {(start - timedelta(days=1)).date()}.")
            for t in profile["past_trips"]:
                if t.get("note"):
                    insights.append(f"Past trip - {t['label']}: \"{t['note']}\"")
            if profile.get("policy"):
                insights.append(f"{profile['name']} is subject to the {profile['policy']}.")

        node_ids = {e["source"] for e in edges} | {e["target"] for e in edges} | set(seeds)
        return {
            "entities": entities,
            "cities": [self.label(c) for c in cities],
            "profile": profile,
            "triples": [self.triple(e) for e in edges],
            "insights": insights,
            "nodes": [{"id": n, "label": self.label(n), "type": self.nodes[n]["type"]} for n in node_ids if n in self.nodes],
            "edges": [{"source": e["source"], "target": e["target"], "relation": e["relation"]} for e in edges],
        }

    def query(self, entity: str) -> dict:
        """Tool entry point: return the 1-hop neighbourhood of an entity named in text."""
        linked = self.link_entities(entity)
        if not linked:
            return {"error": f"No entity matching '{entity}' in the context graph."}
        node_id = linked[0]["id"]
        edges = self.out(node_id) + self.inc(node_id)
        return {"entity": self.label(node_id), "type": self.nodes[node_id]["type"],
                "properties": self.nodes[node_id]["props"], "facts": [self.triple(e) for e in edges][:40]}

    @staticmethod
    def format_for_prompt(ctx: dict) -> str:
        lines = []
        if ctx["profile"]:
            p = ctx["profile"]
            lines.append(f"Traveller: {p['name']} - {p.get('role', '')}; party size {p.get('party_size', 1)}; "
                         f"home {p['home_city']} (airports {', '.join(p['home_airports']) or 'none'}); "
                         f"budget ~£{p.get('budget_gbp', '?')}; typical cabin {p.get('typical_cabin', '?')}.")
            lines.append("Preferences: " + ("; ".join(p["preferences"]) or "none recorded"))
        if ctx["insights"]:
            lines.append("Derived insights:\n" + "\n".join(f"- {i}" for i in ctx["insights"]))
        if ctx["triples"]:
            lines.append("Relevant facts (subject -[RELATION]-> object):\n" + "\n".join(f"- {t}" for t in ctx["triples"][:40]))
        return "\n".join(lines)

    # ------------------------------------------------------------------ memory write-back
    def record_booking(self, traveller_id: str | None, booking: dict) -> str | None:
        """Write a confirmed booking back into the graph so future turns can use it."""
        if not traveller_id or traveller_id not in self.nodes or "confirmation" not in booking:
            return None
        trip_id = f"trip:{booking['confirmation'].lower()}"
        name = self.label(traveller_id).split()[0]
        if booking["type"] == "flight":
            f = booking["flight"]
            label = f"{name}: {f['origin']} to {f['destination']}, {f['departure_time'][:10]} (booked {booking['confirmation']})"
            self._add_node(trip_id, "Trip", label, props={"date": f["departure_time"][:10], "cabin": booking["cabin"]})
            self._add_edge(trip_id, "FLEW_WITH", f"airline:{f['airline_code']}")
            dest_city = self.city_of(f"airport:{f['destination']}")
            if dest_city:
                self._add_edge(trip_id, "TO", dest_city)
        else:
            h = booking["hotel"]
            label = f"{name}: {h['name']}, {h['check_in']} x{booking['nights']} nights (booked {booking['confirmation']})"
            self._add_node(trip_id, "Trip", label, props={"date": h["check_in"]})
            self._add_edge(trip_id, "TO", f"city:{_slug(h['city'])}")
        self._add_edge(traveller_id, "BOOKED", trip_id)
        return f"{self.label(traveller_id)} -[BOOKED]-> {label}"


if __name__ == "__main__":
    g = ContextGraph()
    print(f"{len(g.nodes)} nodes, {len(g.edges)} edges")
    ctx = g.context_for("Fly me to Amsterdam for the data summit", "traveller:alex")
    print(ContextGraph.format_for_prompt(ctx))
