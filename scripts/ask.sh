#!/bin/bash

# Simple AI Assistant - One-shot queries using micro-prompting
# Usage: ./ask.sh [--v2] "your question here"

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

# Parse arguments
USE_V2=false

if [ "$1" = "--v2" ]; then
    USE_V2=true
    shift
fi

# Check if question provided
if [ -z "$1" ]; then
    echo "Usage: $0 [--v2] \"your question here\""
    echo ""
    echo "Options:"
    echo "  --v2    Use v2 step-by-step execution (better for small models)"
    echo ""
    echo "Examples:"
    echo "  $0 \"Get kudos givers for my activities from last 24 hours\""
    echo "  $0 --v2 \"List my last 3 activities\""
    echo "  $0 \"Show me activities that need to be made public\""
    exit 1
fi

GOAL="$1"

print_info "Goal: $GOAL"
if [ "$USE_V2" = true ]; then
    print_info "Using V2 architecture (planning + sequential execution)"
fi
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

# Build v2 flag if needed
V2_FLAG=""
if [ "$USE_V2" = true ]; then
    V2_FLAG="--v2"
fi

$DOCKER_COMPOSE run --rm agent python3 main.py --goal "$GOAL" $V2_FLAG

if [ $? -eq 0 ]; then
    print_info "Done!"
else
    print_error "Execution failed"
    exit 1
fi
