#!/bin/bash
set -e

echo "👀 Test Watch Mode (TDD)"
echo "========================"
echo "Tests will re-run automatically when files change"
echo "Press Ctrl+C to exit"
echo ""

# Check if pytest-watch is installed
if ! python -c "import pytest_watch" 2>/dev/null; then
    echo "📦 Installing pytest-watch..."
    pip install pytest-watch
fi

# Ensure services are running
docker compose up -d redis ollama

# Set environment variables
export REDIS_HOST=localhost
export OLLAMA_HOST=http://localhost:11434

# Run in watch mode
ptw neural_engine/tests/ -- -v "${@}"
