import json
import pickle
from pathlib import Path

from annoy import AnnoyIndex
from spacy.language import Language

from src.services.chatbot.helpers import load_spacy_model

INTENTS_FILE = Path(__file__).parent.parent / "data" / "intents.json"
EMBEDDINGS_FILE = Path(__file__).parent / "data" / "intents_embeddings.pkl"
ANNOY_INDEX_FILE = Path(__file__).parent / "data" / "intents_annoy_index.ann"


def precompute_embeddings(nlp_model: Language):
    print(f"Loading intents from {INTENTS_FILE}...")
    with open(INTENTS_FILE, encoding="utf-8") as f:
        intents_data = json.load(f)

    # Prepare data for Annoy
    patterns = []
    intent_labels = []
    for intent_name, data in intents_data.items():
        for pattern in data["patterns"]:
            patterns.append(pattern)
            intent_labels.append(intent_name)

    if not patterns:
        print("No patterns found in intents.json. Skipping embedding pre-computation.")
        return

    print(f"Generating embeddings for {len(patterns)} patterns...")
    # Get embeddings for all patterns
    # Using nlp.pipe for efficiency
    pattern_embeddings = [nlp_model(text).vector for text in patterns]

    if not pattern_embeddings:
        print("No valid embeddings generated. Skipping Annoy index build.")
        return

    embedding_dim = len(pattern_embeddings[0])

    # Build Annoy index
    annoy_index = AnnoyIndex(
        embedding_dim, "angular"
    )  # angular distance is cosine similarity
    for i, vec in enumerate(pattern_embeddings):
        annoy_index.add_item(i, vec)

    print("Building Annoy index...")
    annoy_index.build(10)  # 10 trees for good balance between speed and accuracy

    # Save Annoy index
    annoy_index.save(str(ANNOY_INDEX_FILE))
    print(f"Annoy index saved to {ANNOY_INDEX_FILE}")

    # Save mapping from index to intent label and original pattern
    # This is needed to retrieve the actual intent and pattern after Annoy search
    intent_mapping = {i: (intent_labels[i], patterns[i]) for i in range(len(patterns))}
    with open(EMBEDDINGS_FILE, "wb") as f:
        pickle.dump(intent_mapping, f)
    print(f"Intent mapping saved to {EMBEDDINGS_FILE}")

    print("Pre-computation complete.")


if __name__ == "__main__":
    nlp_instance = load_spacy_model("en_core_web_lg")
    if nlp_instance is None:
        raise RuntimeError(
            "Failed to load SpaCy model. Cannot precompute embeddings. Please ensure 'en_core_web_lg' is installed by running: python -m spacy download en_core_web_lg"
        )
    precompute_embeddings(nlp_instance)
