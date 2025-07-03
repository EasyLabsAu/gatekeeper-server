# GateKeeper Server

A production-ready FastAPI project template with best practices for rapid development.

## Features

- FastAPI for high-performance API development
- User authentication and authorization
- SQLAlchemy, SQLModel, and Alembic for database management
- Repository pattern for clean architecture
- PDM for dependency management
- Logging setup with proper error handling
- API versioning
- Testing setup (ready for your tests)

## Project Structure

```
├── migrations/          # Database migrations
├── scripts/             # Utility scripts
├── src/                 # Source code
│   ├── api/             # API routes, endpoints and business logic
│   ├── core/            # Core configurations
│   ├── helpers/         # Helper utilities
│   ├── models/          # Database models
│   ├── middlewares/     # API middlewares
│   ├── repositories/    # Data layer and business logic
│   └── workers/         # Background tasks
└── tests/               # Test files
```

## Getting Started

### Prerequisites

- Python 3.10 or higher
- PDM package manager
- PostgreSQL
- Docker (optional)

### Installation & Usage

1. Clone the repository:

```bash
git clone https://github.com/EasyLabsAu/gatekeeper-server
cd gatekeeper-server
```

2. Setup and install dependencies:

```bash
pdm venv create 3.10
pdm use -f .venv # Optional
pdm install
```

3. Set up environment variables:

```bash
cp example.env .env
# Edit .env with your configuration
```

4. Run database migrations:

```bash
pdm run alembic upgrade head
```

5. Start the development server:

```bash
pdm run dev
```

The API will be available at `http://localhost:8080`

### Containerization & Automation

```bash
./orchestrate.sh --action=start --env=development
./orchestrate.sh --action=start --env=production
```

#### Stop all services

```bash
./orchestrate.sh --action=stop --env=development
```

#### Restart all services

```bash
./orchestrate.sh --action=restart --env=development
```

#### Remove all containers, networks, and volumes

```bash
./orchestrate.sh --action=remove --env=development
```

### API Documentation

Once the server is running, you can access:

- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## Chatbot Functionality

The GateKeeper Server includes an intelligent chatbot designed to assist users with inquiries related to products, services, and general support. It leverages natural language processing (NLP) to understand user intent and manage conversational flows.

### Components

1.  **Intent Recognition (`src/services/chatbot/core.py`, `src/services/chatbot/data/intents.json`, `src/services/chatbot/data/intents_embeddings.pkl`, `src/services/chatbot/data/intents_annoy_index.ann`):**
    *   **Purpose:** Identifies the user's underlying intention from their input (e.g., "greeting", "product_info", "contact_us").
    *   **Mechanism:**
        *   Uses the `en_core_web_lg` SpaCy model to generate vector embeddings for user input and pre-defined patterns.
        *   A pre-computed Annoy index (`intents_annoy_index.ann`) stores embeddings of patterns from `intents.json` for fast similarity search.
        *   Cosine similarity is used to find the closest matching intent pattern, and a confidence score determines the best intent.
    *   **Data:** `intents.json` defines various intents, each with a list of `patterns` (example phrases) and `responses`. `intents_embeddings.pkl` stores the mapping between Annoy index IDs and their corresponding intent labels/patterns.

2.  **Pre-computation (`src/services/chatbot/precompute.py`):**
    *   **Purpose:** Generates and saves the SpaCy embeddings for all patterns in `intents.json` and builds the Annoy index. This is a one-time process that must be run before the chatbot can function.
    *   **Execution:** `python src/services/chatbot/precompute.py`

3.  **Conversation Flow Management (`src/services/chatbot/core.py`, `src/services/chatbot/helpers.py`):**
    *   **Purpose:** Manages multi-turn interactions, such as the "lead capture" flow, where the chatbot asks a series of questions to gather information.
    *   **Mechanism:** The `ConversationFlow` class tracks the state of an active conversation, including the current question, collected answers, and validation rules. The `SessionManager` (from `src/helpers/session_manager.py`, though not explicitly detailed here) is used to persist conversation context across messages for a given session ID.
    *   **Example:** The `lead_capture_start` intent triggers a flow to collect user name and email.

4.  **Response Generation (`src/services/chatbot/core.py`, `src/services/chatbot/data/intents.json`):**
    *   **Purpose:** Selects an appropriate response based on the recognized intent and the current conversation context.
    *   **Mechanism:** Randomly selects a response from the list associated with the identified intent in `intents.json`. For intents like `product_selection`, it can provide specific responses based on a `product_type` extracted from the user's input.

5.  **WebSocket Integration (`src/api/websocket/chat.py`):**
    *   **Purpose:** Provides a real-time communication channel for the chatbot.
    *   **Mechanism:** Uses `socketio` to handle WebSocket connections. User messages are received via the `chat` event, processed by the `Chatbot` instance, and responses are emitted back to the client. Each user session is associated with a unique `Chatbot` instance to maintain individual conversation context.

### Potential Issues/Risks

*   **SpaCy Model Availability:** The `en_core_web_lg` SpaCy model must be downloaded and available. If not, the chatbot will fail to initialize.
*   **Pre-computation Requirement:** The `precompute.py` script *must* be run at least once after any changes to `intents.json` or initial setup. Failure to do so will result in `FileNotFoundError` for the Annoy index or embeddings.
*   **Intent Recognition Accuracy:** The chatbot's understanding is limited by the patterns defined in `intents.json` and the quality of the SpaCy model. Ambiguous or out-of-scope user inputs may lead to incorrect intent recognition or fallback to "invalid" responses.
*   **Contextual Limitations:** While basic conversation flow is managed, complex multi-turn dialogues or nuanced contextual understanding beyond the defined flows might be challenging.
*   **Scalability of Session Management:** The current `SessionManager` implementation (if in-memory) might not scale well for a very large number of concurrent users in a distributed environment.

### Improvements

*   **Enhanced NLP:** Integrate more advanced NLP models (e.g., transformer-based models like BERT, GPT) for improved intent recognition, entity extraction, and more natural language understanding.
*   **Dynamic Response Generation:** Instead of static responses, use generative AI models or integrate with external knowledge bases/APIs to provide more dynamic and personalized answers.
*   **Advanced Dialogue Management:** Implement a more sophisticated dialogue state tracking mechanism to handle complex conversations, disambiguation, and proactive suggestions.
*   **Integration with CRM/External Systems:** Connect the lead capture flow directly to a CRM system or other relevant business applications.
*   **User Feedback Loop:** Implement a mechanism for users to rate responses or provide feedback, which can be used to improve the chatbot's performance over time.
*   **Error Recovery:** More robust error handling and graceful degradation when an intent cannot be recognized or a flow breaks.
*   **Multi-language Support:** Extend `intents.json` and integrate multi-lingual SpaCy models for broader language support.
*   **Testing Framework:** Develop a comprehensive testing framework for chatbot intents and conversation flows to ensure reliability.
*   **Deployment Optimization:** For high-traffic scenarios, consider optimizing the SpaCy model loading and Annoy index access for better performance and resource utilization.

### Development

#### Creating New Migrations

```bash
pdm run alembic revision -m "your migration description"
```

or

```bash
pdm run make-migration -m "your migration description"
```

#### Executing Migrations

```bash
pdm run migrate-up
```

```bash
pdm run migrate-down
```

#### Running Tests

```bash
pdm run test
```
