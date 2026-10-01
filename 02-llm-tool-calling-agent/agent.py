from openai import OpenAI
import json
import os
import random

# Helper function that fabricates a fake booking confirmation for demo purposes.
# This never contacts a real airline or booking provider and no real flight is booked.
def book_flight(passenger_name: str,
                from_city: str,
                to_city: str,
                travel_date: str) -> str:

    # Generate a clearly fake, random booking reference
    booking_reference = f"DEMO-{random.randint(100000, 999999)}"

    return {
        "response": (
            f"A {travel_date} flight has been booked from {from_city} to {to_city} "
            f"for {passenger_name}. Booking reference: {booking_reference}."
        )
    }


# Main function that calls the LLM
def travel_agent(user_message: str, messages: list) -> str:
    messages.append({"role": "user", "content": user_message})
    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            tools=tools
        )
        if response.choices[0].message.content:
            return response.choices[0].message.content
        elif response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            arguments = json.loads(tool_call.function.arguments)
            from_city = arguments.get('from_city')
            to_city = arguments.get('to_city')
            travel_date = arguments.get('travel_date')
            passenger_name = arguments.get('passenger_name')

            # Call our travel booking function that we defined earlier
            booking_confirmation = book_flight(passenger_name=passenger_name, from_city=from_city, to_city=to_city, travel_date=travel_date)

            function_call_result_message = {
                "role": "tool",
                "content": json.dumps({
                    "confirmation_message": booking_confirmation,
                }),
                "tool_call_id": response.choices[0].message.tool_calls[0].id
            }
            messages.append(response.choices[0].message)
            messages.append(function_call_result_message)
            response = openai.chat.completions.create(
                            model="gpt-4-turbo",
                            messages=messages,
                        )
            return response.choices[0].message.content
        else:
            return "Sorry, I didn't get a response. Could you try rephrasing that?"
    except Exception as e:
        return f"An error occurred: {str(e)}"


if __name__ == "__main__":

    # Read the OpenAI API key from the environment rather than hardcoding it in the script
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set the OPENAI_API_KEY environment variable before running this script.")
    openai = OpenAI(api_key=api_key)

    # Load the tool definitions the LLM can call from an external JSON file
    with open("tools.json", "r") as tools_file:
        tools = json.load(tools_file)

    # Initialize the conversation history with a system prompt defining the agent's role
    messages = [
        {"role": "system", "content": """You are a helpful travel agent assistant.
         Use the supplied tools to assist the customer.
         If you don't have enough information to book, just ask.
         When you have the travel cities, dates and name, you can use the tool to book the ticket."""},
    ]

    # Run a simple terminal chat loop so the agent can be used without a notebook
    print("YOUR AI TRAVEL AGENT")
    print("Type 'quit' or 'exit' to stop")
    while True:
        message = input("What service would you like to request today: ").strip()
        if message.lower() in ("quit", "exit"):
            break
        if not message:
            continue

        response = travel_agent(user_message=message, messages=messages)
        messages.append({"role": "assistant", "content": response})
        print(f"Travel agent: {response}")
