#!/bin/bash
#
# Strava Integration Test Runner
#
# This script runs the Strava integration test in the Docker container
# with proper network access to Ollama.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "============================================================"
echo "  Strava Integration Test"
echo "============================================================"
echo ""

# Check if Ollama is running
echo "Checking Ollama status..."
if ! docker ps | grep -q "ollama"; then
    echo "❌ ERROR: Ollama container is not running"
    echo "   Please start it with: ./setup-ollama.sh"
    exit 1
fi

echo "✅ Ollama container is running"
echo ""

# Check if .strava_cookies exists
if [ ! -f .strava_cookies ]; then
    echo "❌ ERROR: .strava_cookies file not found"
    echo ""
    echo "Please create it with your Strava session cookie:"
    echo ""
    echo "cat > .strava_cookies << 'EOF'"
    echo '['
    echo '  {'
    echo '    "name": "_strava4_session",'
    echo '    "value": "YOUR_SESSION_VALUE_HERE",'
    echo '    "domain": ".strava.com"'
    echo '  }'
    echo ']'
    echo "EOF"
    echo ""
    echo "See instructions in tests/test_strava_integration.py for how to get the cookie"
    exit 1
fi

echo "✅ .strava_cookies file found"
echo ""

# Build the agent image if needed
echo "Building agent Docker image..."
docker compose build agent

echo ""
echo "============================================================"
echo "  Running Integration Test"
echo "============================================================"
echo ""

# Run the test in Docker container with access to Ollama network
docker compose run --rm agent python tests/test_strava_integration.py

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "============================================================"
    echo "  ✅ Integration Test PASSED"
    echo "============================================================"
else
    echo "============================================================"
    echo "  ❌ Integration Test FAILED"
    echo "============================================================"
    echo ""
    echo "Common issues:"
    echo "  1. Invalid/expired Strava cookie - get a fresh one from your browser"
    echo "  2. Ollama not responding - check with: docker logs ollama"
    echo "  3. Network issues - verify with: docker network inspect ollama-network"
fi

exit $EXIT_CODE
