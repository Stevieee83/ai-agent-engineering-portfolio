import random

def travel_utility_function(travel_option):
  """
  A utility function that evaluates travel options based on price,
  comfort, and convenience.
  """
  price_utility = (1000 - travel_option['price']) * 0.05    # Lower price is better
  comfort_utility = travel_option['comfort_rating'] * 10
  convenience_utility = travel_option['convenience_score'] * 15

  total_utility = price_utility + comfort_utility + convenience_utility
  return total_utility

# Define some example travel options
travel_options = [
    {
        'name': 'Budget Airline',
        'price': 300,
        'comfort_rating': 3,
        'convenience_score': 2
    },
    {
        'name': 'Premium Airline',
        'price': 800,
        'comfort_rating': 8,
        'convenience_score': 7
    },
    {
        'name': 'Train',
        'price': 200,
        'comfort_rating': 6,
        'convenience_score': 5
    },
    {
        'name': 'Road Trip',
        'price': 150,
        'comfort_rating': 4,
        'convenience_score': 3
    }
]

# Calculate and print the utility for each travel option
for option in travel_options:
    utility = travel_utility_function(option)
    print(f"Option: {option['name']}")
    print(f"Price: ${option['price']}, Comfort: {option['comfort_rating']}/10, Convenience: {option['convenience_score']}/10")
    print(f"Utility: {utility:.2f}\n")

# Find the best option based on utility
best_option = max(travel_options, key=travel_utility_function)
print(f"The best travel option according to our utility function is: {best_option['name']}")
print(f"Its utility value is: {travel_utility_function(best_option):.2f}")
