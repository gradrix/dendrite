#!/bin/bash
#
# Dendrite - One-command idempotent startup script
#
# Usage:
#   ./start.sh          # CPU mode (default, for machines without GPU)
#   ./start.sh gpu      # GPU mode (for machines with NVIDIA GPU)
#   ./start.sh stop     # Stop all services
#   ./start.sh status   # Show service status
#   ./start.sh logs     # Show logs
#   ./start.sh test     # Run tests
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

# Detect mode from argument
MODE="${1:-cpu}"

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
    log "Running tests..."
    docker compose --profile cpu run --rm tests pytest "$@"
}

cmd_help() {
    echo "Dendrite - Neural Engine"
    echo ""
    echo "Usage: ./start.sh [command]"
    echo ""
    echo "Commands:"
    echo "  (none), cpu   Start in CPU mode (default)"
    echo "  gpu           Start in GPU mode (NVIDIA)"
    echo "  stop          Stop all services"
    echo "  status        Show service status"
    echo "  logs          Follow logs"
    echo "  test          Run tests"
    echo "  help          Show this help"
    echo ""
    echo "Environment variables:"
    echo "  RAM_PROFILE   Model size: 8gb, 16gb (default), 32gb, 64gb"
    echo ""
    echo "Examples:"
    echo "  ./start.sh                    # Start CPU mode with 16gb model"
    echo "  RAM_PROFILE=8gb ./start.sh    # Start with smaller model"
    echo "  ./start.sh gpu                # Start with GPU acceleration"
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
    help|--help|-h)
        cmd_help
        exit 0
        ;;
    cpu|gpu)
        # Continue to startup
        ;;
    *)
        error "Unknown command: $MODE. Use './start.sh help' for usage."
        ;;
esac

# =============================================================================
# Startup
# =============================================================================

log "🧠 Dendrite Neural Engine"
log "   Mode: $MODE"
log "   RAM Profile: ${RAM_PROFILE:-16gb}"
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

# GPU check for gpu mode
if [ "$MODE" = "gpu" ]; then
    if ! command -v nvidia-smi &> /dev/null; then
        error "GPU mode requested but nvidia-smi not found. Use './start.sh' for CPU mode."
    fi
    
    if ! docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi &> /dev/null; then
        error "NVIDIA Container Toolkit not working. See: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    fi
    
    log "✅ GPU detected: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
fi

# Export RAM profile for docker-compose
export RAM_PROFILE="${RAM_PROFILE:-16gb}"

# Stop any existing containers (idempotent)
log "Stopping any existing services..."
docker compose --profile cpu --profile gpu down 2>/dev/null || true

# Pull images (idempotent - skips if already present)
log "Pulling images (this may take a while on first run)..."
docker compose --profile "$MODE" pull 2>/dev/null || true

# Start services
log "Starting services..."
docker compose --profile "$MODE" up -d

# Wait for llama.cpp to be ready
log "Waiting for LLM to load model..."
LLAMA_CONTAINER="dendrite-llama-$MODE"
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

# Show status
echo ""
log "Service status:"
docker compose --profile "$MODE" ps

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
echo "  API endpoint: http://localhost:8080/v1/chat/completions"
echo "  Health check: http://localhost:8080/health"
echo ""
echo "  Commands:"
echo "    ./start.sh status   # Check status"
echo "    ./start.sh logs     # View logs"
echo "    ./start.sh stop     # Stop all"
echo "    ./start.sh test     # Run tests"
echo ""
