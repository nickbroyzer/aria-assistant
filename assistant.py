import anthropic
import json
import os

MEMORY_FILE = "memory.json"

client = anthropic.Anthropic()

memory = {}
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE) as f:
        memory = json.load(f)

ASSISTANT_NAME = "Ash"

SYSTEM_PROMPT = """You are Ash, a friendly and professional AI integration consultant specializing in helping small businesses adopt and get the most out of AI tools.

Your areas of expertise include:
- Recommending the right AI tools for specific business needs (marketing, customer service, operations, finance, etc.)
- Explaining AI concepts in plain, accessible language — no jargon unless asked
- Helping businesses evaluate AI tools based on budget, team size, and technical skill level
- Advising on implementation strategies, change management, and measuring ROI
- Staying current on popular tools like ChatGPT, Claude, Notion AI, Zapier, HubSpot AI, and many others

Your style:
- Warm, encouraging, and approachable — small business owners may feel intimidated by AI
- Practical and actionable — focus on real-world impact, not hype
- Honest about limitations and tradeoffs of different tools
- Always tailor advice to the specific business context

The user's name is {name}."""

if "name" in memory:
    name = memory["name"]
    print(f"\nWelcome back, {name}! Ash here — ready to help with your AI strategy.")
else:
    name = input("What is your name? ")
    memory["name"] = name
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)
    print(f"\nHi {name}, I'm Ash — your AI integration consultant for small businesses!")
    print("I can help you find the right AI tools, plan how to implement them, and get real results.")
    print("Whether you're just getting started or looking to do more with AI, I've got you covered.")

messages = []

while True:
    user_input = input("\nHow can I help you? ")
    if user_input.strip().lower() in ("bye", "exit"):
        print(f"Goodbye, {name}! Best of luck with your business. Don't hesitate to come back!")
        break

    messages.append({"role": "user", "content": user_input})

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT.format(name=name),
        messages=messages,
    ) as stream:
        response_text = ""
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_text += text
        print()

    messages.append({"role": "assistant", "content": response_text})
