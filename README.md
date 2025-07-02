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
