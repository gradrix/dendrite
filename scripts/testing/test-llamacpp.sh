#!/bin/bash
# scripts/testing/test-llamacpp.sh
# Quick script to run llama.cpp integration tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "🦙 llama.cpp Integration Tests"
echo "================================"
echo ""

# Check if already running
if curl -s http://localhost:18080/health > /dev/null 2>&1; then
    echo "✅ llama.cpp test server already running"
else
    echo "🚀 Starting llama.cpp test server..."
    echo "   (First run will download ~1GB model)"
    echo ""
    
    docker compose -f docker-compose.llamacpp-test.yml up -d
    
    echo ""
    echo "⏳ Waiting for server to be ready..."
    
    # Wait for health check (up to 5 minutes for first-time model download)
    MAX_WAIT=300
    WAITED=0
    while ! curl -s http://localhost:18080/health > /dev/null 2>&1; do
        sleep 5
        WAITED=$((WAITED + 5))
        
        if [ $WAITED -ge $MAX_WAIT ]; then
            echo "❌ Timeout waiting for llama.cpp server"
            echo "   Check logs: docker compose -f docker-compose.llamacpp-test.yml logs"
            exit 1
        fi
        
        echo "   Waited ${WAITED}s..."
    done
    
    echo "✅ Server ready!"
fi

echo ""
echo "🧪 Running integration tests..."
echo ""

# Run tests
pytest neural_engine/tests/integration/test_llamacpp.py -v --tb=short

echo ""
echo "✅ All tests passed!"
echo ""
echo "💡 To stop the test server:"
echo "   docker compose -f docker-compose.llamacpp-test.yml down"
