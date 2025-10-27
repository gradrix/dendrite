#!/bin/bash
set -e

echo "🧠 Starting Dendrite Neural Engine..."
echo "=================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Start all services
echo "🐳 Starting Docker services..."
docker compose up -d redis ollama

# Wait for Redis to be ready
echo "⏳ Waiting for Redis..."
for i in {1..30}; do
    if docker compose exec -T redis redis-cli ping 2>&1 | grep -q PONG; then
        echo "✅ Redis is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Redis failed to start"
        docker compose logs redis
        exit 1
    fi
    sleep 1
done

# Wait for Ollama to be ready (check from host since container doesn't have curl)
echo "⏳ Waiting for Ollama..."
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

# Check if required models are available
echo "🤖 Checking for required LLM models..."
REQUIRED_MODEL="llama3.1:8b"
if ! docker compose exec -T ollama ollama list | grep -q "$REQUIRED_MODEL"; then
    echo "📥 Pulling $REQUIRED_MODEL (this may take a few minutes)..."
    docker compose exec -T ollama ollama pull "$REQUIRED_MODEL"
fi
echo "✅ Model $REQUIRED_MODEL is available"

# Start the main app
echo "🚀 Starting Neural Engine application..."
docker compose up -d app

echo ""
echo "✅ Dendrite is running!"
echo "=================================="
echo "📊 Redis:  localhost:6379"
echo "🤖 Ollama: localhost:11434"
echo ""
echo "📝 View logs: ./scripts/logs.sh"
echo "🛑 Stop:      ./scripts/stop.sh"
echo "🐚 Shell:     ./scripts/shell.sh"
echo ""
