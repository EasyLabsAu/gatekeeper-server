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

The GateKeeper Server includes an intelligent chatbot designed to assist users with inquiries and guide them through dynamic forms. It uses an intent recognition system powered by natural language processing to understand user input and provide relevant responses.

### Core Components

1.  **Intent Definition (`src/data/intents.json`):**
    -   **Purpose:** This JSON file is the heart of the chatbot's knowledge. It defines the different "intents" the chatbot can understand.
    -   **Structure:** Each intent has a list of `patterns` (example user phrases) and `responses` (what the chatbot will say).

2.  **Intent Recognition (`src/services/chatbot.py`):**
    -   **Purpose:** To determine the user's intent based on their message.
    -   **Mechanism:**
        -   **Embeddings:** On startup, the chatbot pre-computes text embeddings for all patterns in `intents.json` using a `spaCy` model (`en_core_web_lg`).
        -   **Annoy Index:** These embeddings are stored in an `Annoy` index for fast and efficient similarity searches (Approximate Nearest Neighbor).
        -   **Recognition:** When a user sends a message, it's converted into an embedding and compared against the Annoy index to find the most likely intent.

3.  **Conversation and Form Flow (`src/services/chatbot.py`):**
    -   **Purpose:** To manage multi-turn conversations, especially for filling out forms.
    -   **Mechanism:** The `Chatbot` class maintains a `context` dictionary for each session, tracking the conversation state, such as the last intent and progress through a form. This context is persisted using a cache.

4.  **Form Handling:**
    -   **Purpose:** To guide users through a series of questions to complete a form.
    -   **Mechanism:** The chatbot can be initialized with a form structure. It then enters a "flow" state, asking questions one by one, validating user input based on field type (`text`, `number`, `boolean`, etc.), and saving the responses.

5.  **State Management (`src/helpers/cache.py`):**
    -   **Purpose:** To maintain conversation state across multiple interactions.
    -   **Mechanism:** A caching layer (using `PickleSerializer`) stores the session context, allowing the chatbot to remember where the user left off.

6.  **WebSocket Integration (`src/api/websocket/chat.py`):**
    -   **Purpose:** Provides a real-time, interactive communication channel for the chatbot.
    -   **Mechanism:** The chatbot logic is integrated with a WebSocket endpoint, allowing for a responsive chat experience.

### Extending the Chatbot

-   To add new conversational abilities, edit the `src/data/intents.json` file with new intents, patterns, and responses.
-   The embedding and Annoy index files (`intents_embeddings.pkl`, `intents_annoy_index.ann`) are generated automatically if they don't exist. If you modify `intents.json`, it's recommended to delete these files to trigger re-computation on the next startup.

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
