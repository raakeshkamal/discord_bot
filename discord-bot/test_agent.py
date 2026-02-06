import asyncio
import os
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Mock discord things to allow importing bot
import unittest.mock

with (
    unittest.mock.patch("discord.ext.commands.Bot"),
    unittest.mock.patch("discord.Intents"),
):
    from bot import agent_executor


async def test_agent():
    print("--- Testing Agent ---")

    queries = [
        "What is the weather in London?",
        "I weigh 70 kg",
        "What was my last weight?",
        "Show my progress",
        "Hello there!",
        "What can you help me with?",
        "What's 2+2?",
        "Tell me a joke",
        "How are you today?",
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        try:
            response = await agent_executor.ainvoke({"input": query})
            print(f"Response: {response.get('output')}")
            print(
                f"Tools used: {[step.action.tool for step in response.get('intermediate_steps', [])]}"
            )
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_agent())
