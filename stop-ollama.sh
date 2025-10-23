#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    OLLAMA_CONTAINER_NAME=${OLLAMA_CONTAINER_NAME:-ollama}
fi

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${OLLAMA_CONTAINER_NAME}$"; then
    print_error "Ollama container is not running"
    exit 1
fi

print_info "Stopping Ollama container: $OLLAMA_CONTAINER_NAME"
docker stop "$OLLAMA_CONTAINER_NAME"

# Ask if user wants to remove the container
if [ "${1}" = "--remove" ] || [ "${1}" = "-r" ]; then
    print_info "Removing container..."
    docker rm "$OLLAMA_CONTAINER_NAME"
    print_info "Container removed"
fi

print_info "Ollama container stopped successfully"
