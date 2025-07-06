import asyncio
import os
import sys

from src.services.chatbot import load_spacy_model, precompute_embeddings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))


async def main():
    """Precompute data into vector embeddings and Annoy index ."""
    nlp_instance = load_spacy_model("en_core_web_lg")
    if nlp_instance is None:
        raise RuntimeError(
            "Failed to load SpaCy model. Cannot precompute embeddings. Please ensure 'en_core_web_lg' is installed by running: python -m spacy download en_core_web_lg"
        )
    await precompute_embeddings(nlp_instance)


if __name__ == "__main__":
    asyncio.run(main())
