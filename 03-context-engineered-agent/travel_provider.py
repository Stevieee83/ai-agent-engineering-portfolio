"""
Fake flight and hotel data provider.

An evolution of the Faker-based provider from Example 1. Results are seeded by
route and date, so the same search always returns the same flights - this lets
the agent search, reason about the options, and then book one of them later in
the conversation.
"""
import json
import math
import os
import random
import uuid
from datetime import date, datetime, timedelta

from faker import Faker

BASE_DIR = os.path.dirname(__file__)
with open(os.path.join(BASE_DIR, "data", "supported_locations.json")) as f:
    LOCATIONS = json.load(f)

AIRPORTS = LOCATIONS["airports"]
AIRLINES = LOCATIONS["airlines"]
HOTEL_CITIES = LOCATIONS["hotel_cities"]

FAKER_LOCALES = {"Amsterdam": "nl_NL", "Paris": "fr_FR", "Reykjavik": "is_IS", "Dublin": "en_IE",
                 "New York": "en_US", "Seattle": "en_US", "San Diego": "en_US", "Los Angeles": "en_US"}
HOTEL_AMENITIES = ["free_wifi", "breakfast", "gym", "family_rooms", "step_free_access", "airport_shuttle", "pool", "restaurant"]


def _distance_km(a: str, b: str) -> float:
    """Great-circle distance between two airports."""
    lat1, lon1 = math.radians(AIRPORTS[a]["lat"]), math.radians(AIRPORTS[a]["lon"])
    lat2, lon2 = math.radians(AIRPORTS[b]["lat"]), math.radians(AIRPORTS[b]["lon"])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def serving_airlines(a: str, b: str) -> list[str]:
    """Airlines flying direct between two airports. Small airports may list
    `routes_only_to`, e.g. Dundee only connects to London City."""
    for x, y in ((a, b), (b, a)):
        only = AIRPORTS[x].get("routes_only_to")
        if only and y not in only:
            return []
    return [code for code in AIRPORTS[a]["airlines"] if code in AIRPORTS[b]["airlines"]]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _resolve_city(city: str) -> str | None:
    """Accept a city name or an airport code and return the canonical hotel city."""
    if city.upper() in AIRPORTS:
        return AIRPORTS[city.upper()]["city"]
    for name in HOTEL_CITIES:
        if name.lower() == city.strip().lower():
            return name
    return None


class TravelProvider:
    def __init__(self):
        self.offers: dict[str, dict] = {}   # flight offers seen in searches, keyed by offer_id
        self.hotels: dict[str, dict] = {}   # hotel offers seen in searches, keyed by hotel_id
        self.bookings: list[dict] = []

    # ------------------------------------------------------------------ flights
    def _routings(self, origin: str, destination: str) -> list[tuple[str, str | None]]:
        """Return (airline, via_airport) pairs that can fly this route."""
        routings = [(code, None) for code in serving_airlines(origin, destination)]
        # One-stop options on a single airline, via its hub (or via the only
        # airport a small airport such as Dundee connects to)
        for code in AIRPORTS[origin]["airlines"]:
            for hub in AIRPORTS[origin].get("routes_only_to") or [AIRLINES[code]["hub"]]:
                if hub and hub not in (origin, destination) and code in serving_airlines(origin, hub) \
                        and code in serving_airlines(hub, destination):
                    routings.append((code, hub))
        return routings

    def search_flights(self, origin: str, destination: str, departure_date: str, passengers: int = 1, num_options: int = 6) -> dict:
        origin, destination = origin.upper(), destination.upper()
        if origin not in AIRPORTS:
            return {"error": f"Unsupported departure airport: {origin}. Supported airports are {sorted(AIRPORTS)}"}
        if destination not in AIRPORTS:
            return {"error": f"Unsupported destination airport: {destination}. Supported airports are {sorted(AIRPORTS)}"}
        if origin == destination:
            return {"error": "Departure and destination airports cannot be the same."}
        try:
            travel_day = _parse_date(departure_date)
        except ValueError:
            return {"error": "departure_date must be in YYYY-MM-DD format."}
        if travel_day < date.today():
            return {"error": f"departure_date {departure_date} is in the past."}

        rng = random.Random(f"{origin}-{destination}-{departure_date}")
        routings = self._routings(origin, destination)
        if not routings:
            return {"origin": origin, "destination": destination, "departure_date": departure_date, "flights": [],
                    "note": "No airline in the demo network serves this route."}
        # Prefer direct options, then a few connections
        direct = [r for r in routings if r[1] is None]
        connecting = [r for r in routings if r[1] is not None]
        rng.shuffle(direct)
        rng.shuffle(connecting)
        chosen = (direct + connecting)[:num_options]

        flights = []
        for airline_code, via in chosen:
            airline = AIRLINES[airline_code]
            if via:
                km = _distance_km(origin, via) + _distance_km(via, destination)
                minutes = int(km / 780 * 60) + 60 + rng.randint(60, 150)
            else:
                km = _distance_km(origin, destination)
                minutes = int(km / 780 * 60) + 35 + rng.randint(-5, 20)
            depart = datetime.combine(travel_day, datetime.min.time()) + timedelta(hours=rng.randint(6, 21), minutes=rng.choice([0, 15, 30, 45]))
            arrive = depart + timedelta(minutes=minutes)  # times are shown in origin time for simplicity
            economy = round((45 + km * 0.09) * airline["price_factor"] * rng.uniform(0.8, 1.25) * (0.9 if via else 1), 2)
            flight_number = f"{airline_code}{rng.randint(100, 9899)}"
            offer = {
                "offer_id": f"{flight_number}-{departure_date}",
                "flight_number": flight_number,
                "airline": airline["name"],
                "airline_code": airline_code,
                "alliance": airline["alliance"],
                "origin": origin,
                "destination": destination,
                "via": via,
                "stops": 1 if via else 0,
                "departure_time": depart.strftime("%Y-%m-%d %H:%M"),
                "arrival_time": arrive.strftime("%Y-%m-%d %H:%M"),
                "duration_minutes": minutes,
                "checked_bag_included": airline["checked_bag_included"],
                "price_gbp_per_person": {
                    "economy": economy,
                    "premium_economy": round(economy * 1.8, 2),
                    **({"business": round(economy * 3.6, 2)} if airline["has_business"] else {}),
                },
                "co2_kg_per_person": round(km * 0.09 * (1.15 if via else 1)),
            }
            self.offers[offer["offer_id"]] = offer
            flights.append(offer)

        return {"origin": origin, "destination": destination, "departure_date": departure_date,
                "passengers": passengers, "flights": flights}

    def book_flight(self, offer_id: str, passenger_name: str, cabin: str = "economy", passengers: int = 1) -> dict:
        offer = self.offers.get(offer_id)
        if not offer:
            return {"error": f"Unknown offer_id {offer_id}. Call search_flights first and use an offer_id from the results."}
        prices = offer["price_gbp_per_person"]
        if cabin not in prices:
            return {"error": f"Cabin '{cabin}' is not available on this flight. Available: {list(prices)}"}
        booking = {
            "type": "flight",
            "confirmation": f"FL-{uuid.uuid4().hex[:6].upper()}",
            "passenger_name": passenger_name,
            "passengers": passengers,
            "cabin": cabin,
            "total_price_gbp": round(prices[cabin] * passengers, 2),
            "flight": offer,
            "booked_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.bookings.append(booking)
        return booking

    # ------------------------------------------------------------------ hotels
    def search_hotels(self, city: str, check_in: str, nights: int = 1, guests: int = 1, max_price_per_night: float | None = None) -> dict:
        canonical = _resolve_city(city)
        if not canonical:
            return {"error": f"Unsupported city: {city}. Supported cities are {HOTEL_CITIES}"}
        try:
            _parse_date(check_in)
        except ValueError:
            return {"error": "check_in must be in YYYY-MM-DD format."}

        rng = random.Random(f"{canonical}-{check_in}")
        fake = Faker(FAKER_LOCALES.get(canonical, "en_GB"))
        fake.seed_instance(f"{canonical}-{check_in}")
        hotels = []
        for i in range(5):
            stars = rng.choice([3, 3, 4, 4, 5])
            price = round(rng.uniform(60, 110) * (1 + (stars - 3) * 0.6) * (1 + 0.15 * (guests - 1)), 2)
            hotel = {
                "hotel_id": f"H-{canonical[:3].upper()}-{check_in.replace('-', '')}-{i}",
                "name": f"{fake.last_name()} {rng.choice(['Hotel', 'House', 'Suites', 'Inn', 'Residence'])} {canonical}",
                "city": canonical,
                "stars": stars,
                "neighbourhood": fake.street_name(),
                "distance_to_centre_km": round(rng.uniform(0.3, 6.0), 1),
                "price_gbp_per_night": price,
                "amenities": sorted(rng.sample(HOTEL_AMENITIES, rng.randint(2, 5))),
                "guest_rating": round(rng.uniform(7.0, 9.6), 1),
                "check_in": check_in,
                "nights": nights,
            }
            self.hotels[hotel["hotel_id"]] = hotel
            hotels.append(hotel)
        if max_price_per_night:
            hotels = [h for h in hotels if h["price_gbp_per_night"] <= max_price_per_night]
        return {"city": canonical, "check_in": check_in, "nights": nights, "guests": guests, "hotels": hotels}

    def book_hotel(self, hotel_id: str, guest_name: str, nights: int | None = None) -> dict:
        hotel = self.hotels.get(hotel_id)
        if not hotel:
            return {"error": f"Unknown hotel_id {hotel_id}. Call search_hotels first."}
        nights = nights or hotel["nights"]
        booking = {
            "type": "hotel",
            "confirmation": f"HT-{uuid.uuid4().hex[:6].upper()}",
            "guest_name": guest_name,
            "nights": nights,
            "total_price_gbp": round(hotel["price_gbp_per_night"] * nights, 2),
            "hotel": hotel,
            "booked_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.bookings.append(booking)
        return booking

    def list_bookings(self, name: str | None = None) -> list[dict]:
        if not name:
            return self.bookings
        name = name.lower()
        return [b for b in self.bookings if name in (b.get("passenger_name") or b.get("guest_name") or "").lower()]


travel_provider = TravelProvider()
