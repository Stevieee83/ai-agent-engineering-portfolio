"""
MCP (Model Context Protocol) server exposing the travel provider as tools.

In Example 2 the `book_flight` tool was hard-wired into the agent. Here the
tools live in a separate process behind a standard protocol: any MCP client
(this example's agent, Claude Desktop, an IDE, ...) can discover and call them
without knowing how they are implemented.

Run standalone for debugging:   python mcp_server.py
(The FastAPI app in server.py starts it automatically over stdio.)
"""
import json

from mcp.server.mcpserver import MCPServer

from travel_provider import LOCATIONS, travel_provider

mcp = MCPServer(
    "travel-booking",
    instructions="Search and book flights and hotels in the demo travel network. "
                 "Always search before booking, and use the offer_id / hotel_id returned by the search.",
)


@mcp.tool()
def search_flights(origin: str, destination: str, departure_date: str, passengers: int = 1) -> dict:
    """Search flights between two airports on a date.

    Args:
        origin: IATA code of the departure airport, e.g. "EDI".
        destination: IATA code of the arrival airport, e.g. "AMS".
        departure_date: Date in YYYY-MM-DD format.
        passengers: Number of travellers in the party.
    """
    return travel_provider.search_flights(origin, destination, departure_date, passengers)


@mcp.tool()
def book_flight(offer_id: str, passenger_name: str, cabin: str = "economy", passengers: int = 1) -> dict:
    """Book a flight offer returned by search_flights. Only call after the traveller has explicitly confirmed.

    Args:
        offer_id: The offer_id from a search_flights result.
        passenger_name: Lead passenger's full name, as on their passport.
        cabin: One of "economy", "premium_economy" or "business".
        passengers: Number of travellers in the party.
    """
    return travel_provider.book_flight(offer_id, passenger_name, cabin, passengers)


@mcp.tool()
def search_hotels(city: str, check_in: str, nights: int = 1, guests: int = 1, max_price_per_night: float | None = None) -> dict:
    """Search hotels in a city.

    Args:
        city: City name (e.g. "Amsterdam") or airport code.
        check_in: Check-in date in YYYY-MM-DD format.
        nights: Number of nights.
        guests: Number of guests.
        max_price_per_night: Optional nightly price cap in GBP.
    """
    return travel_provider.search_hotels(city, check_in, nights, guests, max_price_per_night)


@mcp.tool()
def book_hotel(hotel_id: str, guest_name: str, nights: int | None = None) -> dict:
    """Book a hotel returned by search_hotels. Only call after the traveller has explicitly confirmed.

    Args:
        hotel_id: The hotel_id from a search_hotels result.
        guest_name: Lead guest's full name.
        nights: Number of nights (defaults to the nights used in the search).
    """
    return travel_provider.book_hotel(hotel_id, guest_name, nights)


@mcp.tool()
def list_bookings(name: str | None = None) -> list[dict]:
    """List bookings made in this session, optionally filtered by passenger/guest name."""
    return travel_provider.list_bookings(name)


@mcp.resource("travel://locations", mime_type="application/json", description="Airports, airlines and hotel cities supported by this server.")
def supported_locations() -> str:
    return json.dumps(LOCATIONS)


if __name__ == "__main__":
    mcp.run()
