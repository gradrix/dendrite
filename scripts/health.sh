#!/bin/bash

echo "🏥 Dendrite Health Check"
echo "========================"
echo ""

# Check Docker
if docker info > /dev/null 2>&1; then
    echo "✅ Docker is running"
else
    echo "❌ Docker is not running"
    exit 1
fi

# Check services
echo ""
echo "Services:"
echo "---------"

if docker compose ps redis | grep -q "Up"; then
    echo "✅ Redis is running"
    if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "   └─ Redis responds to PING"
    else
        echo "   └─ ⚠️  Redis not responding"
    fi
else
    echo "❌ Redis is not running"
fi

if docker compose ps ollama | grep -q "Up"; then
    echo "✅ Ollama is running"
    if docker compose exec -T ollama curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "   └─ Ollama API is responding"
        MODEL_COUNT=$(docker compose exec -T ollama ollama list | tail -n +2 | wc -l)
        echo "   └─ $MODEL_COUNT model(s) available"
    else
        echo "   └─ ⚠️  Ollama API not responding"
    fi
else
    echo "❌ Ollama is not running"
fi

if docker compose ps app | grep -q "Up"; then
    echo "✅ App container is running"
else
    echo "⚠️  App container is not running"
fi

echo ""
