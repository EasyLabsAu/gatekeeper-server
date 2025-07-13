import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.services.chatbot import Chatbot


def print_commands():
    """Prints the available commands."""
    print("\n" + "=" * 20)
    print("Chatbot CLI Commands:")
    print("  --system [PROMPT] : Set a new system prompt.")
    print("  --history         : View the conversation history.")
    print("  --clear           : Clear the conversation history.")
    print("  bye/ exit / quit   : Exit the chatbot.")
    print("=" * 20 + "\n")


async def main():
    """
    Main function to run the chatbot CLI.
    """
    print("Initializing Chatbot...")
    try:
        chatbot = Chatbot(session_id="test")
    except (KeyboardInterrupt, EOFError, Exception) as e:
        print(f"\nError initializing Chatbot: {e}")
        print(
            "Please ensure your LLM provider, model, and API key are configured correctly in your environment."
        )
        return

    print("Chatbot is ready. Start chatting!")
    print_commands()

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["bye", "quit", "exit"]:
                print("Goodbye!")
                break
            elif user_input.lower() == "--clear":
                await chatbot.clear_history()
                print("\n[System: Conversation history cleared.]\n")
            elif user_input.lower() == "--history":
                history = await chatbot.get_history()
                print("\n--- Conversation History ---")
                if not history:
                    print("(empty)")
                for message in history:
                    print(f"[{message.__class__.__name__}]\n{message.content}\n")
                print("--- End of History ---\n")
            elif user_input.lower().startswith("--system"):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1 and parts[1]:
                    system_prompt = parts[1]
                    await chatbot.set_system_prompt(system_prompt)
                    print(f"\n[System: Prompt set to '{system_prompt}']\n")
                else:
                    print("\n[System: --system command requires a prompt.]\n")
            else:
                print("\nBot: ", end="", flush=True)
                async for token in chatbot.chat(user_input, stream=True):
                    print(token, end="", flush=True)
                print("")
                print("")

        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
