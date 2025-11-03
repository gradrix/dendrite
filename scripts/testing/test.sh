#!/bin/bash
set -e

echo "🧪 Running Dendrite Test Suite"
echo "=============================="

# Ensure dependencies are running
echo "🐳 Ensuring Redis and Ollama are running..."
docker compose up -d redis ollama

# Wait for services
echo "⏳ Waiting for services..."

# Wait for Redis
for i in {1..30}; do
    if docker compose exec -T redis redis-cli ping 2>&1 | grep -q PONG; then
        echo "✅ Redis is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Redis failed to start"
        exit 1
    fi
    sleep 1
done

# Wait for Ollama (check from host since container doesn't have curl)
for i in {1..60}; do
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "✅ Ollama is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "❌ Ollama failed to start"
        docker compose logs ollama
        exit 1
    fi
    sleep 1
done

echo "✅ Services ready"

# Build and run tests
echo "🏗️  Building test container..."
docker compose build tests

echo "🧪 Running tests..."
docker compose run --rm tests pytest -v "${@}"

TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
else
    echo ""
    echo "❌ Tests failed with exit code $TEST_EXIT_CODE"
fi

exit $TEST_EXIT_CODE
