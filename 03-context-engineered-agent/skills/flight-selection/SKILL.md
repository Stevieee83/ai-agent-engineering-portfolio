---
name: flight-selection
description: Rank and recommend flight options using a weighted utility score over price, duration, stops, baggage, loyalty and traveller preferences. Use whenever flights have been searched and one must be recommended.
---

# Flight selection

Use this procedure after calling `search_flights`. It is the LLM-facing version of the
utility function from Example 2.

## Steps

1. **Filter out hard violations first**
   - Departures before 07:00 or after 22:00 if the traveller prefers no red-eyes.
   - Cabin classes that the travel policy does not allow (see `travel-policy-compliance`).
   - Connecting flights if the traveller strongly prefers direct flights and a direct option exists.
2. **Compute the true price**: for each option use the cabin price multiplied by the party size.
   If the traveller needs checked bags and `checked_bag_included` is false, add about £45
   per person per flight (use the airline baggage policy from the knowledge base if retrieved).
3. **Score each remaining option** (higher is better):
   - Price: `(cheapest_true_price / true_price) * 40`
   - Duration: `(shortest_duration / duration) * 25`
   - Stops: `15` for direct, `0` for one stop
   - Loyalty: `+10` if the airline earns points in one of the traveller's programmes
   - Past experience: `+5` if the traveller rated a previous trip on that airline 4 or 5, `-5` if rated 3 or lower
   - Low price priority: if the traveller's top priority is price, double the price weight
4. **Recommend exactly one option** and give 1-2 runner-ups.

## Output format

- A markdown table: flight, airline, depart, arrive, duration, stops, true price, score.
- Then a short "**Why this one**" paragraph that cites the specific facts that drove the
  choice (e.g. "direct", "earns Avios", "bag included - saves £180 for your family").
- Never invent flights; only use results returned by the `search_flights` tool.
