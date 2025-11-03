#!/bin/bash
set -e

echo "🧪 Running Tests Locally (faster iteration)"
echo "==========================================="

# Check if running in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Consider running: python -m venv venv && source venv/bin/activate"
    echo ""
fi

# Check if dependencies are installed
if ! python -c "import pytest" 2>/dev/null; then
    echo "📦 Installing test dependencies..."
    pip install -r requirements.txt
fi

# Ensure Redis and Ollama are running
echo "🐳 Ensuring Redis and Ollama are running..."
docker compose up -d redis ollama

# Wait for services
echo "⏳ Waiting for services..."
for i in {1..30}; do
    if docker compose exec -T redis redis-cli ping 2>&1 | grep -q PONG; then
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Redis failed to start"
        exit 1
    fi
    sleep 1
done

# Check Ollama from host (container doesn't have curl)
for i in {1..60}; do
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        break
    fi
    if [ $i -eq 60 ]; then
        echo "❌ Ollama failed to start"
        exit 1
    fi
    sleep 1
done
echo "✅ Services ready"

# Set environment variables for local testing
export REDIS_HOST=localhost
export OLLAMA_HOST=http://localhost:11434

echo "🧪 Running pytest..."
pytest -v neural_engine/tests/ "${@}"
