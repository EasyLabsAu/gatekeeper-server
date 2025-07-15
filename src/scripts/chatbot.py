import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.services.chatbot import Chatbot


async def main():
    """
    Main function to run the chatbot CLI.
    """
    print("Initializing Chatbot...")
    try:
        chatbot = Chatbot(session_id="test")
        await chatbot.initialize()
    except (KeyboardInterrupt, EOFError, Exception) as e:
        print(f"\nError initializing Chatbot: {e}")
        return

    print("Chatbot is ready. Start chatting! Say 'bye' to exit")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["bye", "quit", "exit"]:
                print("Goodbye!")
                break
            else:
                print("\nBot: ", end="", flush=True)
                async for token in chatbot.chat(user_input):
                    print(token, end="", flush=True)
                print("")

        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
