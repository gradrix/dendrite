#!/bin/bash
#
# Dendrite - One-command idempotent startup script
#
# Usage:
#   ./start.sh          # Auto-detect GPU, use if available
#   ./start.sh cpu      # Force CPU mode
#   ./start.sh gpu      # Force GPU mode (fails if no GPU)
#   ./start.sh api      # HTTP API (auto-detect GPU)
#   ./start.sh stop     # Stop all services
#   ./start.sh status   # Show service status
#   ./start.sh logs     # Show logs
#   ./start.sh test     # Run tests (auto-detect GPU)
#
# Requirements:
#   - Docker
#   - Docker Compose (v2)
#
# This script is idempotent - run it as many times as you want.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[dendrite]${NC} $1"; }
warn() { echo -e "${YELLOW}[dendrite]${NC} $1"; }
error() { echo -e "${RED}[dendrite]${NC} $1"; exit 1; }

# =============================================================================
# GPU Detection
# =============================================================================

detect_gpu() {
    # Check if nvidia-smi exists and works
    if ! command -v nvidia-smi &> /dev/null; then
        echo "cpu"
        return
    fi
    
    # Check if NVIDIA driver is working
    if ! nvidia-smi &> /dev/null; then
        echo "cpu"
        return
    fi
    
    # Check if Docker has nvidia runtime
    if docker info 2>/dev/null | grep -q "Runtimes:.*nvidia"; then
        echo "gpu"
        return
    fi
    
    # Fallback: try running a GPU container (slower)
    if timeout 30 docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi &> /dev/null 2>&1; then
        echo "gpu"
        return
    fi
    
    echo "cpu"
}

# Detect mode from argument
MODE="${1:-auto}"

# =============================================================================
# Command handlers
# =============================================================================

cmd_stop() {
    log "Stopping all Dendrite services..."
    docker compose --profile cpu --profile gpu down 2>/dev/null || true
    log "✅ All services stopped"
}

cmd_status() {
    log "Service status:"
    docker compose ps
}

cmd_logs() {
    docker compose logs -f --tail=50
}

cmd_test() {
    # Auto-detect GPU for tests
    local hw_mode=$(detect_gpu)
    log "Running tests (hardware: $hw_mode)..."
    
    # Use tests or tests-gpu based on detected hardware
    local test_service="tests"
    [ "$hw_mode" = "gpu" ] && test_service="tests-gpu"
    
    docker compose --profile "$hw_mode" run --rm "$test_service" pytest "$@"
}

cmd_help() {
    echo "Dendrite - Neural Engine"
    echo ""
    echo "Usage: ./start.sh [command]"
    echo ""
    echo "Commands:"
    echo "  (none), auto  Start with auto-detected hardware (GPU if available)"
    echo "  cpu           Force CPU mode"
    echo "  gpu           Force GPU mode (fails if no GPU)"
    echo "  api           Start HTTP API server (auto-detect hardware)"
    echo "  goal \"...\"    Run a single goal and exit"
    echo "  scheduler     Run the scheduler daemon (uses goals.yaml)"
    echo "  stop          Stop all services"
    echo "  status        Show service status"
    echo "  logs          Follow logs"
    echo "  test          Run tests (auto-detect hardware)"
    echo "  help          Show this help"
    echo ""
    echo "Environment variables:"
    echo "  RAM_PROFILE   Model size: 8gb, 16gb (default), 32gb, 64gb"
    echo "  FORCE_CPU=1   Force CPU mode even if GPU detected"
    echo ""
    echo "Examples:"
    echo "  ./start.sh                    # Auto-detect, use GPU if available"
    echo "  ./start.sh cpu                # Force CPU mode"
    echo "  RAM_PROFILE=8gb ./start.sh    # Start with smaller model"
    echo "  ./start.sh api                # Start HTTP API (auto-detect)"
    echo "  ./start.sh goal \"Get my Strava activities\"  # Run one goal"
    echo "  ./start.sh scheduler          # Run scheduler daemon"
    echo "  ./start.sh test -k 'test_foo' # Run specific tests"
}

# =============================================================================
# Handle commands
# =============================================================================

case "$MODE" in
    stop)
        cmd_stop
        exit 0
        ;;
    status)
        cmd_status
        exit 0
        ;;
    logs)
        cmd_logs
        exit 0
        ;;
    test)
        shift
        cmd_test "$@"
        exit 0
        ;;
    goal)
        shift
        GOAL_TEXT="$*"
        if [ -z "$GOAL_TEXT" ]; then
            error "Usage: ./start.sh goal \"Your goal here\""
        fi
        log "Running single goal: $GOAL_TEXT"
        hw_mode=$(detect_gpu)
        docker compose --profile "$hw_mode" run --rm app-$hw_mode python main.py --goal "$GOAL_TEXT"
        exit 0
        ;;
    scheduler)
        log "Starting scheduler daemon..."
        hw_mode=$(detect_gpu)
        docker compose --profile "$hw_mode" run --rm app-$hw_mode python main.py --scheduler
        exit 0
        ;;
    help|--help|-h)
        cmd_help
        exit 0
        ;;
    auto|cpu|gpu|api)
        # Continue to startup
        ;;
    *)
        error "Unknown command: $MODE. Use './start.sh help' for usage."
        ;;
esac

# =============================================================================
# Startup
# =============================================================================

# Handle FORCE_CPU override
if [ "${FORCE_CPU:-0}" = "1" ]; then
    DETECTED_HW="cpu"
    log "🔧 FORCE_CPU=1 set, using CPU mode"
else
    DETECTED_HW=$(detect_gpu)
fi

# Determine profiles to use based on mode
case "$MODE" in
    auto)
        # Auto-detect hardware
        LLAMA_MODE="$DETECTED_HW"
        PROFILES="--profile $LLAMA_MODE"
        API_ENABLED=false
        ;;
    cpu)
        PROFILES="--profile cpu"
        LLAMA_MODE="cpu"
        API_ENABLED=false
        ;;
    gpu)
        # Verify GPU is available when explicitly requested
        if [ "$DETECTED_HW" != "gpu" ]; then
            error "GPU mode requested but no working GPU detected. Use './start.sh' for auto-detect."
        fi
        PROFILES="--profile gpu"
        LLAMA_MODE="gpu"
        API_ENABLED=false
        ;;
    api)
        # Auto-detect hardware for API mode
        LLAMA_MODE="$DETECTED_HW"
        if [ "$LLAMA_MODE" = "gpu" ]; then
            PROFILES="--profile gpu --profile gpu-api"
        else
            PROFILES="--profile cpu --profile api"
        fi
        API_ENABLED=true
        ;;
esac

log "🧠 Dendrite Neural Engine"
log "   Mode: $MODE (hardware: $LLAMA_MODE)"
log "   RAM Profile: ${RAM_PROFILE:-16gb}"
if [ "$LLAMA_MODE" = "gpu" ]; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    log "   GPU: $GPU_NAME"
fi
if [ "$API_ENABLED" = true ]; then
    log "   HTTP API: Enabled (port 8000)"
fi
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    error "Docker not found. Please install Docker first: https://docs.docker.com/get-docker/"
fi

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    error "Docker Compose v2 not found. Please update Docker."
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    error "Docker daemon not running. Please start Docker."
fi

# Export RAM profile for docker-compose
export RAM_PROFILE="${RAM_PROFILE:-16gb}"
export RAM_PROFILE="${RAM_PROFILE:-16gb}"

# Stop any existing containers (idempotent)
log "Stopping any existing services..."
docker compose --profile cpu --profile gpu --profile api --profile gpu-api down 2>/dev/null || true

# Pull images (idempotent - skips if already present)
log "Pulling images (this may take a while on first run)..."
docker compose $PROFILES pull 2>/dev/null || true

# Start services
log "Starting services..."
docker compose $PROFILES up -d

# Wait for llama.cpp to be ready
log "Waiting for LLM to load model..."
LLAMA_CONTAINER="dendrite-llama-$LLAMA_MODE"
MAX_WAIT=300
WAITED=0

while true; do
    if docker exec "$LLAMA_CONTAINER" curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        break
    fi
    
    if [ $WAITED -ge $MAX_WAIT ]; then
        error "Timeout waiting for LLM. Check logs: docker compose logs llama-$MODE"
    fi
    
    sleep 5
    WAITED=$((WAITED + 5))
    echo -n "."
done
echo ""

log "✅ LLM ready!"

# Wait for API server if enabled
if [ "$API_ENABLED" = true ]; then
    log "Waiting for API server..."
    API_CONTAINER="dendrite-api"
    [ "$LLAMA_MODE" = "gpu" ] && API_CONTAINER="dendrite-api-gpu"
    
    MAX_WAIT=120
    WAITED=0
    
    while true; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            break
        fi
        
        if [ $WAITED -ge $MAX_WAIT ]; then
            warn "⚠️  API server taking longer than expected. Check logs: docker compose logs api"
            break
        fi
        
        sleep 3
        WAITED=$((WAITED + 3))
        echo -n "."
    done
    echo ""
    
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log "✅ API server ready!"
    fi
fi

# Show status
echo ""
log "Service status:"
docker compose $PROFILES ps

# Quick health check
echo ""
log "Testing LLM connection..."
RESPONSE=$(curl -s http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"Say OK"}],"max_tokens":5}' \
    2>/dev/null | grep -o '"content":"[^"]*"' | head -1 || echo "")

if [ -n "$RESPONSE" ]; then
    log "✅ LLM responding: $RESPONSE"
else
    warn "⚠️  Could not verify LLM response. Check logs if issues persist."
fi

echo ""
log "🎉 Dendrite is ready!"
echo ""
echo "  LLM endpoint:  http://localhost:8080/v1/chat/completions"
echo "  LLM health:    http://localhost:8080/health"
if [ "$API_ENABLED" = true ]; then
    echo ""
    echo "  API endpoint:  http://localhost:8000/api/v1/goals"
    echo "  API health:    http://localhost:8000/health"
    echo "  API docs:      http://localhost:8000/docs"
fi
echo ""
echo "  Commands:"
echo "    ./start.sh status   # Check status"
echo "    ./start.sh logs     # View logs"
echo "    ./start.sh stop     # Stop all"
echo "    ./start.sh test     # Run tests"
echo ""
