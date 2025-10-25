#!/bin/bash

# Simple AI Assistant - One-shot queries using micro-prompting
# Usage: ./ask.sh "your question here"

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if question provided
if [ -z "$1" ]; then
    echo "Usage: $0 \"your question here\""
    echo ""
    echo "Examples:"
    echo "  $0 \"Get kudos givers for my activities from last 24 hours\""
    echo "  $0 \"List my last 3 activities\""
    echo "  $0 \"Show me activities that need to be made public\""
    echo "  $0 \"What activities got kudos today?\""
    exit 1
fi

GOAL="$1"

print_info "Goal: $GOAL"
echo ""

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

# Execute using micro-prompting agent in Docker
print_info "Executing with micro-prompting agent..."
echo ""

$DOCKER_COMPOSE run --rm agent python3 main.py --goal "$GOAL"

if [ $? -eq 0 ]; then
    print_info "Done!"
else
    print_error "Execution failed"
    exit 1
fi
