#!/bin/bash
#
# Strava Integration Test Runner - Universal
#
# Usage:
#   ./tests/run_strava_integration.sh              # Normal run in Docker
#   ./tests/run_strava_integration.sh --debug      # Debug mode in Docker
#   ./tests/run_strava_integration.sh --local      # Run locally
#   ./tests/run_strava_integration.sh --local --debug  # Debug locally
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse arguments
MODE="docker"
DEBUG=false

for arg in "$@"; do
    case $arg in
        --local|-l)
            MODE="local"
            ;;
        --debug|-d)
            DEBUG=true
            ;;
        --help|-h)
            echo "Strava Integration Test Runner"
            echo ""
            echo "Usage:"
            echo "  $0                     # Normal run in Docker"
            echo "  $0 --debug             # Debug mode in Docker (wait for VS Code)"
            echo "  $0 --local             # Run locally (no Docker)"
            echo "  $0 --local --debug     # Debug locally (wait for VS Code)"
            echo ""
            echo "Options:"
            echo "  --local, -l     Run with local Python (not in Docker)"
            echo "  --debug, -d     Start with debugpy and wait for debugger"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "Debug mode will pause and wait for VS Code to attach."
            echo "In VS Code: F5 → Select appropriate debug configuration"
            exit 0
            ;;
    esac
done

cd "$PROJECT_ROOT"

echo "============================================================"
echo "  Strava Integration Test"
if [ "$DEBUG" = true ]; then
    echo "  MODE: $MODE (DEBUG)"
else
    echo "  MODE: $MODE"
fi
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
    echo "⚠️  WARNING: .strava_cookies file not found"
    echo "   Test will fail at authentication step"
    echo ""
fi

# Run based on mode
if [ "$MODE" = "local" ]; then
    # Local mode
    echo "============================================================"
    echo "  Running Locally"
    echo "============================================================"
    echo ""
    
    # Check Python
    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        echo "❌ ERROR: Python not found"
        exit 1
    fi
    
    PYTHON_CMD=$(command -v python3 || command -v python)
    
    # Check config
    if grep -q "http://ollama:11434" config.yaml; then
        echo "⚠️  NOTE: config.yaml uses 'http://ollama:11434'"
        echo "   For local mode, you may want to use 'http://localhost:11434'"
        echo ""
    fi
    
    if [ "$DEBUG" = true ]; then
        # Check debugpy
        if ! $PYTHON_CMD -c "import debugpy" 2>/dev/null; then
            echo "⚠️  debugpy not found, installing..."
            $PYTHON_CMD -m pip install debugpy
        fi
        
        echo "============================================================"
        echo "  Starting with Debugger (Local)"
        echo "============================================================"
        echo ""
        echo "Debugger will listen on port 5678"
        echo ""
        echo "In VS Code:"
        echo "  1. Set breakpoints in your Python files"
        echo "  2. Press F5"
        echo "  3. Select: 'Python: Strava Integration Test (Local)'"
        echo "     or 'Docker: Attach to Agent Container'"
        echo ""
        echo "Waiting for debugger to attach..."
        echo ""
        
        $PYTHON_CMD -m debugpy --listen 0.0.0.0:5678 --wait-for-client tests/test_strava_integration.py
    else
        # Normal local run
        export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
        $PYTHON_CMD tests/test_strava_integration.py
    fi
    
else
    # Docker mode
    echo "Building agent Docker image..."
    docker compose build agent
    echo ""
    
    echo "============================================================"
    echo "  Running in Docker"
    echo "============================================================"
    echo ""
    
    if [ "$DEBUG" = true ]; then
        echo "Debugger will listen on port 5678"
        echo ""
        echo "In VS Code:"
        echo "  1. Set breakpoints in your Python files"
        echo "  2. Press F5"
        echo "  3. Select: 'Docker: Attach to Agent Container'"
        echo ""
        echo "Waiting for debugger to attach..."
        echo ""
        
        docker compose run --rm \
            -p 5678:5678 \
            agent \
            python -m debugpy --listen 0.0.0.0:5678 --wait-for-client tests/test_strava_integration.py
    else
        # Normal Docker run
        docker compose run --rm agent python tests/test_strava_integration.py
    fi
fi

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
    echo "  1. Invalid/expired Strava cookie - get a fresh one from browser"
    echo "  2. Ollama not responding - check: docker logs ollama"
    if [ "$MODE" = "local" ]; then
        echo "  3. Config mismatch - use http://localhost:11434 for local mode"
    else
        echo "  3. Network issues - verify: docker network inspect ollama-network"
    fi
fi

exit $EXIT_CODE
