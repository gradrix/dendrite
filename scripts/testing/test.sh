#!/bin/bash
set -e

echo "🧪 Running Dendrite Test Suite"
echo "=============================="

# Ensure dependencies are running
echo "🐳 Ensuring Redis, Postgres, and Ollama are running..."

# Check if we should use GPU or CPU profile  
USE_GPU=false
if command -v nvidia-smi &> /dev/null && [ -z "$CI" ]; then
    echo "   GPU detected, using GPU profile"
    USE_GPU=true
    PROFILE="--profile gpu"
    OLLAMA_SERVICE="ollama"
else
    echo "   Using CPU profile (no GPU or in CI)"
    PROFILE="--profile cpu"
    OLLAMA_SERVICE="ollama-cpu"
fi

# Stop the other ollama service to avoid port conflict
if [ "$USE_GPU" = true ]; then
    docker compose stop ollama-cpu 2>/dev/null || true
    docker compose rm -f ollama-cpu 2>/dev/null || true
else
    docker compose stop ollama 2>/dev/null || true
    docker compose rm -f ollama 2>/dev/null || true
fi

# Start required services
docker compose $PROFILE up -d redis postgres $OLLAMA_SERVICE

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

# Wait for Postgres
for i in {1..60}; do
    if docker compose exec -T postgres pg_isready -U dendrite -d dendrite >/dev/null 2>&1; then
        if docker compose exec -T postgres psql -U dendrite -d dendrite -c "SELECT 1" >/dev/null 2>&1; then
            echo "✅ Postgres is ready"
            break
        fi
    fi
    if [ $i -eq 60 ]; then
        echo "❌ Postgres failed to start"
        docker compose logs postgres
        exit 1
    fi
    sleep 2
done

# Wait for Ollama (check from host since container doesn't have curl)
for i in {1..60}; do
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "✅ Ollama is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "❌ Ollama failed to start"
        docker compose logs $OLLAMA_SERVICE
        exit 1
    fi
    sleep 1
done

echo "✅ Services ready"

# Run database migrations
echo "🗄️  Running database migrations..."
if ./scripts/utils/migrate.sh; then
    echo "✅ Migrations complete"
else
    echo "⚠️  Migrations had warnings (may already be applied)"
fi

# Build and run tests
echo "🏗️  Building test container..."
if [ "$USE_GPU" = true ]; then
    TEST_SERVICE="tests-gpu"
else
    TEST_SERVICE="tests"
fi
docker compose build $TEST_SERVICE

echo "🧪 Running tests..."
docker compose $PROFILE run --rm $TEST_SERVICE pytest -v "${@}"

TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
else
    echo ""
    echo "❌ Tests failed with exit code $TEST_EXIT_CODE"
fi

exit $TEST_EXIT_CODE
