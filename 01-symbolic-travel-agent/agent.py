from travel_provider import travel_provider, supported_locations
from typing import List, Dict, Any

AIRPORT_CITY_NAMES = {
    "LAX": "Los Angeles",
    "JFK": "New York",
    "ORD": "Chicago",
    "ATL": "Atlanta",
    "DFW": "Dallas",
    "DEN": "Denver",
    "SEA": "Seattle",
    "SAN": "San Diego",
}

class TravelAgent:
  def __init__(self, name: str):
    self.name = name
    self.goals: List[str] = []
    self.knowledge_base: Dict[str, Any] = {}

  def set_goal(self, goal: str):
    """Agency: Defining objects."""
    self.goals.append(goal)
    print(f"Goal set: {goal}")

  def update_knowledge(self, departure: str, destination: str):
    """Agency: Aquiring information from an API, and scoring."""
    # Simulating API call to get flight options
    response = travel_provider.flight_lookup(departure, destination)
    if response['status_code'] == 200:
      flight_options = response['flight_options']
      # Simple scoring based on price (lower is better)
      scored_options = [
          {**flight, 'score': 1000 / flight['price']}
          for flight in flight_options
      ]
      self.knowledge_base['flight_options'] = scored_options
      print(f"Kowledge update with {len(scored_options)} flight options.")
    else:
      print("Failed to fetch flight information.")

  def print_flight_options(self):
    """Agency: Presenting available options to the user."""
    flight_options = self.knowledge_base.get('flight_options', [])
    if not flight_options:
      print("No flight options to display.")
      return

    print("\n----------- Available Flight Options -----------")
    header = f"{'#':<3} {'Airline':<18} {'Flight #':<10} {'Departure':<20} {'Arrival':<20} {'Price':>8} {'Score':>7}"
    print(header)
    print("-" * len(header))
    for i, flight in enumerate(flight_options, start=1):
      departure_time = flight['departure_time'].strftime('%Y-%m-%d %H:%M')
      arrival_time = flight['arrival_time'].strftime('%Y-%m-%d %H:%M')
      print(
          f"{i:<3} {flight['airline']:<18} {flight['flight_number']:<10} "
          f"{departure_time:<20} {arrival_time:<20} £{flight['price']:>7.2f} {flight['score']:>7.2f}"
      )
    print("-" * len(header))

  def make_decision(self) -> Dict[str, Any]:
    """Autonomy: Independant decision-making"""
    if 'flight_options' not in self.knowledge_base:
      raise ValueError("No flight options available for decision making.")
    best_option = max(self.knowledge_base['flight_options'], key=lambda x: x['score'])
    print(f"Decision made: Slelcted flight {best_option['airline']}")
    return best_option

  def book_travel(self, departure: str, destination: str):
    """Agency: Execute action on behalf of user."""
    print(f"Agent {self.name} is booking travel from {departure} to {destination}")

    self.set_goal(f"Book flight from {departure} to {destination}")
    self.update_knowledge(departure, destination)
    self.print_flight_options()

    try:
      best_flight = self.make_decision()
      # Simulating booking process
      booking_conformation = f"BOOK-{best_flight['airline']}-{self.name.upper()}"
      self.knowledge_base['booking_conformation'] = booking_conformation
    except Exception as e:
      print(f"Booking failed: {str(e)}")

    return self

# Usage example
if __name__ == "__main__":
  print("----------- Supported Airport Codes -----------")
  for code in supported_locations['airports']:
    city = AIRPORT_CITY_NAMES.get(code, "Unknown")
    print(f"{code} - {city}")
  print("-------------------------------------------------\n")

  departure = input("Enter departure airport code: ").strip().upper()
  destination = input("Enter destination airport code: ").strip().upper()

  agent = TravelAgent("TripPlanner")
  agent.book_travel(departure, destination)
  # print("\n----------- Final Agent State: -----------")
  # print(f"Name: {agent.name}")
  # print(f"Goals: {agent.goals}")
  # print(f"Knowledge Base: {agent.knowledge_base}")
  if 'booking_conformation' in agent.knowledge_base:
    print(f"Booking Conformation: {agent.knowledge_base['booking_conformation']}")
