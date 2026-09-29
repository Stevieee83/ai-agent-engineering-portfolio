---
name: travel-policy-compliance
description: Check a business trip against the traveller's corporate travel policy (cabin class, rail-first, hotel caps, approval thresholds) and enforce explicit confirmation before booking. Use for any business traveller or before calling a booking tool.
---

# Travel policy compliance

## When the traveller is SUBJECT_TO a corporate policy

1. Retrieve the policy text with `search_knowledge_base` (query e.g. "cabin class rules hotel caps")
   if it is not already in the retrieved knowledge.
2. Check each rule and report a compliance checklist using ✅ / ⚠️ / ❌:
   - Cabin class allowed for the flight duration
   - Rail-first rule for short UK journeys
   - Hotel nightly rate under the city cap
   - Booking window (14+ days ahead)
   - Total trip cost vs the manager-approval threshold
   - Preferred (loyalty) airline within 10% of the cheapest compliant option
3. If something is ❌, propose a compliant alternative instead of booking it.

## Before calling any booking tool (everyone, not just business travellers)

- Summarise exactly what will be booked (flight number, date, passenger name, cabin, hotel, nights, total price).
- Ask the traveller to confirm with an explicit "yes". Do **not** call `book_flight` or
  `book_hotel` until the traveller has confirmed in their latest message.
- After booking, repeat the confirmation reference(s) back to the traveller.
