#!/bin/bash
set -e

echo "🐛 Running Tests in Debug Mode"
echo "==============================="
echo ""
echo "📍 Debugger will listen on port 5678"
echo "   Attach VS Code debugger after container starts"
echo ""

# Ensure dependencies are running
echo "🐳 Ensuring Redis and Ollama are running..."
docker compose up -d redis ollama

# Wait for Redis
echo "⏳ Waiting for services..."
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
        exit 1
    fi
    sleep 1
done

echo "✅ Services ready"
echo ""

# Build test container with debug support
echo "🏗️  Building test container with debug support..."
docker compose build tests

echo ""
echo "🐛 Starting tests in debug mode..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Debugger listening on 0.0.0.0:5678"
echo "   Waiting for client to attach..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run tests with debugpy
docker compose run --rm \
    -p 5678:5678 \
    tests \
    python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m pytest -v "${@}"
