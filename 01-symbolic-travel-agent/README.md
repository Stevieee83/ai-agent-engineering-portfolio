# Example 1: A Minimal Travel Agent

A small, dependency-light example that illustrates the core building blocks of an
"agent" — goal-setting, knowledge acquisition, autonomous decision-making, and
taking action — without involving an LLM. It's meant as a first step before
introducing LLM-powered agents in later examples.

## What it demonstrates

`TravelAgent` (in `agent.py`) models four classic agent properties:

| Method              | Property | What it does                                                              |
|----------------------|----------|-----------------------------------------------------------------------------|
| `set_goal`           | Agency   | Records an objective the agent is working towards.                        |
| `update_knowledge`   | Agency   | Calls out to a travel data provider and scores the results it gets back.  |
| `print_flight_options`| Agency  | Prints the scored flight options in a readable table.                     |
| `make_decision`      | Autonomy | Picks the best-scored option from its knowledge base, independently.      |
| `book_travel`        | Agency   | Orchestrates the above and acts on the user's behalf (simulated booking). |

## Files

- **`agent.py`** — the `TravelAgent` class and a runnable, interactive usage example.
- **`travel_provider.py`** — a fake flight/hotel data provider. It uses
  [Faker](https://faker.readthedocs.io/) to generate realistic-looking flight
  and hotel options instead of calling a real travel API.
- **`supported_locations.json`** — the airports and cities the fake provider
  will accept (e.g. `SAN`, `SEA`, `LAX`, `JFK`).
- **`requirements.txt`** — Python dependencies.

## Setup

```bash
pip install -r requirements.txt
```

## Running the example

```bash
python agent.py
```

The script is interactive. It first prints the list of supported airport
codes (with the city each one serves), then prompts for a departure and
destination airport code:

```
----------- Supported Airport Codes -----------
LAX - Los Angeles
JFK - New York
ORD - Chicago
ATL - Atlanta
DFW - Dallas
DEN - Denver
SEA - Seattle
SAN - San Diego
-------------------------------------------------

Enter departure airport code: SAN
Enter destination airport code: SEA
```

It then creates a `TripPlanner` agent and books a flight between the two
codes entered, printing the agent's goals, the available flight options,
the decision made, and the final booking confirmation.

## How it works

1. On startup, the script prints the supported airport codes (from
   `supported_locations.json`, via `travel_provider.py`) alongside their
   city names, then reads the departure and destination codes from the
   terminal with `input()`.
2. `book_travel(departure, destination)` sets a goal describing the trip.
3. `update_knowledge` calls `travel_provider.flight_lookup(...)`, which
   validates the airport codes against `supported_locations.json` and
   returns a handful of randomly generated flight options.
4. Each flight is scored using a simple heuristic (`1000 / price`, so
   cheaper flights score higher).
5. `print_flight_options` prints the scored flight options as an aligned
   table (airline, flight number, departure/arrival times, price, score).
6. `make_decision` selects the highest-scoring flight from the knowledge base.
7. A fake booking confirmation is generated and stored back in the agent's
   knowledge base.

## Notes

- No external APIs or API keys are required — `travel_provider.py` fabricates
  all flight/hotel data locally via Faker.
- Only airports listed in `supported_locations.json` are recognized; anything
  else returns an error from `flight_lookup`. The script prints these codes
  up front so you know what to enter.
- The city names shown next to each airport code (in `agent.py`'s
  `AIRPORT_CITY_NAMES`) are for display only — `supported_locations.json`
  itself only stores the codes.
