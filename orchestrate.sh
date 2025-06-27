#!/bin/bash

# Function to display error and exit
function error_exit {
    echo "$1" >&2
    exit 1
}

# Determine the correct Docker Compose command (prefer "docker compose" over "docker-compose")
if command -v docker compose &> /dev/null; then
  DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
  DOCKER_COMPOSE_CMD="docker-compose"
else
  error_exit "Error: Docker Compose not found. Please install Docker and Docker Compose."
fi

# Check if the action argument is passed
if [[ -z "$1" ]]; then
  error_exit "Error: You need to specify an action (--action={start/stop/restart/remove})."
fi

# Extract the action from the first argument
ACTION_ARG="${1#--action=}"

# Extract the environment from the second argument (default to 'development' if not provided)
ENV_ARG="development"
if [[ -n "$2" && "$2" == --env=* ]]; then
  ENV_ARG="${2#--env=}"
fi

# Validate the action argument
VALID_ACTIONS=("start" "stop" "restart" "remove")
if [[ ! " ${VALID_ACTIONS[*]} " =~ " ${ACTION_ARG} " ]]; then
  error_exit "Error: Invalid action specified. Use --action=start, stop, restart, or remove."
fi

# Validate the environment argument
if [[ "$ENV_ARG" != "development" && "$ENV_ARG" != "production" ]]; then
  error_exit "Error: Invalid environment specified. Use --env=development or --env=production."
fi

# Check if the .env files exist
for FILE in "./.env"; do
  if [[ ! -f "$FILE" ]]; then
    error_exit "Error: $FILE does not exist. Please create the required .env file."
  fi
done

# Perform the specified action
case "$ACTION_ARG" in
  start)
    echo "Starting Docker services in $ENV_ARG mode..."
    export DOCKER_TARGET=$ENV_ARG
    $DOCKER_COMPOSE_CMD up -d --build
    ;;
  stop)
    echo "Stopping Docker services..."
    export DOCKER_TARGET=$ENV_ARG
    $DOCKER_COMPOSE_CMD down
    ;;
  restart)
    echo "Restarting Docker services..."
    export DOCKER_TARGET=$ENV_ARG
    $DOCKER_COMPOSE_CMD down
    $DOCKER_COMPOSE_CMD up -d --build
    ;;
  remove)
    echo "Removing Docker services, containers, and volumes..."
    export DOCKER_TARGET=$ENV_ARG
    $DOCKER_COMPOSE_CMD down --volumes --remove-orphans
    ;;
  *)
    error_exit "Error: Invalid action specified."
    ;;
esac
