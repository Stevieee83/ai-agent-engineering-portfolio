---
name: itinerary-builder
description: Turn chosen flights, hotels and destination knowledge into a clear day-by-day trip itinerary with transfers, practical tips and entry requirements. Use when the user asks to plan a trip, wants an itinerary, or after a booking is confirmed.
---

# Itinerary builder

Produce the itinerary in this structure (markdown):

## ✈️ Trip summary
One line: who, from where, to where, dates, party size, total estimated cost.

## 🗓️ Day by day
- **Day 1 - <date>**: getting to the departure airport (use NEAR relationships from the context
  graph, e.g. train from Dundee to Edinburgh Airport), the flight, arrival transfer (from the
  destination guide), hotel check-in.
- Middle days: 2-3 suggestions per day from the destination guide, matched to the traveller
  (events they are attending, family activities for families, etc.).
- **Last day**: checkout, transfer and flight home.

## 🧳 Before you go
- Entry requirements for the destination (from the knowledge base, e.g. ESTA, EES).
- Baggage reminders for the chosen airline.
- Special requests to make (seat, meals).

Keep it concise: no more than ~25 lines. Only include facts that come from tool results,
retrieved knowledge or the context graph; say "check locally" rather than inventing details.
