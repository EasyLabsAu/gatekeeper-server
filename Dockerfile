# Stage 1: Development Environment
FROM python:3.10 AS development

ENV PYTHONUNBUFFERED=1
ENV BLIS_ARCH=generic
ENV CFLAGS="-O2"
ENV CPPFLAGS="-O2"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    libblas-dev \
    liblapack-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python build tools first
RUN pip install --upgrade pip setuptools wheel

# Install Cython and numpy first (required for many packages)
RUN pip install Cython numpy

WORKDIR /app

COPY pyproject.toml .

# Install dependencies from pyproject.toml (including dev and test)
RUN pip install toml
RUN python -c "import toml, subprocess, sys; data = toml.load('pyproject.toml'); deps = data['project']['dependencies'] + data['dependency-groups']['dev'] + data['dependency-groups']['test']; [subprocess.check_call([sys.executable, '-m', 'pip', 'install', d]) for d in deps]"
RUN python -m spacy download en_core_web_lg

COPY . .

EXPOSE 8080

ENV PYTHONPATH=/app

CMD ["sh", "-c", "alembic upgrade head && python src/scripts/seed.py && python src/scripts/precompute.py && uvicorn src.server:app --reload --lifespan on --host 0.0.0.0 --port 8080"]

# Stage 2: Builder Environment
FROM python:3.10 AS builder

ENV PYTHONUNBUFFERED=1
ENV BLIS_ARCH=generic
ENV CFLAGS="-O2"
ENV CPPFLAGS="-O2"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    libblas-dev \
    liblapack-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python build tools
RUN pip install --upgrade pip setuptools wheel

# Install Cython and numpy first
RUN pip install Cython numpy

WORKDIR /app

COPY pyproject.toml .

# Install production dependencies from pyproject.toml
RUN pip install toml
RUN python -c "import toml, subprocess, sys; data = toml.load('pyproject.toml'); deps = data['project']['dependencies']; [subprocess.check_call([sys.executable, '-m', 'pip', 'install', d]) for d in deps]"
RUN python -m spacy download en_core_web_lg
COPY src /app/src

# Stage 3: Production Environment
FROM python:3.10-slim-buster AS production

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
# Copy executables if they are installed globally
COPY --from=builder /usr/local/bin/alembic /usr/local/bin/alembic
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

COPY --from=builder /app/src /app/src

EXPOSE 8080

ENV PYTHONPATH=/app
CMD ["sh", "-c", "alembic upgrade head && python src/scripts/seed.py && python src/scripts/precompute.py && uvicorn src.server:app --host 0.0.0.0 --port 8080"]
