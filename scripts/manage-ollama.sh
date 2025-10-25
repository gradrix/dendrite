#!/bin/bash

# Comprehensive Ollama container management script
# Handles: status, start, stop, restart, logs, stats

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
OLLAMA_CONTAINER_NAME=${OLLAMA_CONTAINER_NAME:-ollama}
OLLAMA_PORT=11434

show_usage() {
    cat << EOF
Ollama Container Management

USAGE:
  $0 <command> [options]

COMMANDS:
  status              Show container status and resource usage
  start               Start the Ollama container
  stop                Stop the container
  restart             Restart the container
  logs [lines]        Show container logs (default: 50 lines)
  stats               Live resource monitoring
  health              Check API health
  remove              Stop and remove container

EXAMPLES:
  $0 status           # Check if running
  $0 logs 100         # Show last 100 log lines
  $0 stats            # Monitor resources (Ctrl+C to exit)
  $0 restart          # Restart container
  $0 remove           # Stop and remove

EOF
    exit 1
}

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${BLUE}━━━ $1 ━━━${NC}"; }

is_running() {
    docker ps --format '{{.Names}}' | grep -q "^${OLLAMA_CONTAINER_NAME}$"
}

cmd_status() {
    print_header "Ollama Container Status"
    
    if is_running; then
        print_info "Container: ${GREEN}RUNNING${NC}"
        
        # Get container details
        echo ""
        docker ps --filter "name=^${OLLAMA_CONTAINER_NAME}$" \
            --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        
        echo ""
        print_header "Resource Usage"
        docker stats --no-stream --format \
            "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}" \
            "$OLLAMA_CONTAINER_NAME"
        
        echo ""
        print_header "Models Loaded"
        curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" 2>/dev/null | \
            python3 -c "import sys, json; models = json.load(sys.stdin).get('models', []); print(f'{len(models)} models available'); [print(f'  - {m[\"name\"]}') for m in models]" || \
            print_warn "Could not fetch model list"
        
    else
        print_error "Container: ${RED}NOT RUNNING${NC}"
        
        # Check if container exists but stopped
        if docker ps -a --format '{{.Names}}' | grep -q "^${OLLAMA_CONTAINER_NAME}$"; then
            print_warn "Container exists but is stopped. Run: $0 start"
        else
            print_warn "Container does not exist. Run: ./setup.sh"
        fi
        return 1
    fi
}

cmd_start() {
    print_header "Starting Ollama Container"
    
    if is_running; then
        print_warn "Container is already running"
        return 0
    fi
    
    # Check if container exists but is stopped
    if docker ps -a --format '{{.Names}}' | grep -q "^${OLLAMA_CONTAINER_NAME}$"; then
        print_info "Starting existing container..."
        docker start "$OLLAMA_CONTAINER_NAME"
        print_info "Container started successfully"
    else
        print_error "Container does not exist. Run: ./setup.sh"
        return 1
    fi
}

cmd_stop() {
    print_header "Stopping Ollama Container"
    
    if ! is_running; then
        print_warn "Container is not running"
        return 0
    fi
    
    print_info "Stopping container..."
    docker stop "$OLLAMA_CONTAINER_NAME"
    print_info "Container stopped successfully"
}

cmd_restart() {
    print_header "Restarting Ollama Container"
    
    if is_running; then
        cmd_stop
    fi
    
    sleep 2
    cmd_start
    
    # Wait for API to be ready
    echo ""
    print_info "Waiting for API to be ready..."
    for i in {1..10}; do
        if curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" > /dev/null 2>&1; then
            print_info "API is ready"
            return 0
        fi
        sleep 1
    done
    
    print_warn "API did not respond within 10 seconds"
}

cmd_logs() {
    local lines=${1:-50}
    
    print_header "Ollama Container Logs (last $lines lines)"
    
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${OLLAMA_CONTAINER_NAME}$"; then
        print_error "Container does not exist"
        return 1
    fi
    
    docker logs --tail "$lines" -f "$OLLAMA_CONTAINER_NAME"
}

cmd_stats() {
    print_header "Ollama Resource Monitoring (Ctrl+C to exit)"
    
    if ! is_running; then
        print_error "Container is not running"
        return 1
    fi
    
    docker stats "$OLLAMA_CONTAINER_NAME"
}

cmd_health() {
    print_header "Ollama API Health Check"
    
    if ! is_running; then
        print_error "Container is not running"
        return 1
    fi
    
    print_info "Testing API endpoint: http://localhost:${OLLAMA_PORT}"
    
    # Test API
    if response=$(curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" 2>&1); then
        model_count=$(echo "$response" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('models', [])))" 2>/dev/null || echo "?")
        print_info "API: ${GREEN}HEALTHY${NC}"
        print_info "Models available: $model_count"
        
        # Test generation (quick)
        print_info "Testing generation..."
        if curl -sf "http://localhost:${OLLAMA_PORT}/api/generate" \
            -d '{"model":"llama2","prompt":"Hi","stream":false,"options":{"num_predict":1}}' > /dev/null 2>&1; then
            print_info "Generation: ${GREEN}WORKING${NC}"
        else
            print_warn "Generation: ${YELLOW}FAILED${NC} (model may not be loaded)"
        fi
    else
        print_error "API: ${RED}UNREACHABLE${NC}"
        return 1
    fi
}

cmd_remove() {
    print_header "Removing Ollama Container"
    
    if is_running; then
        cmd_stop
    fi
    
    if docker ps -a --format '{{.Names}}' | grep -q "^${OLLAMA_CONTAINER_NAME}$"; then
        print_warn "This will remove the container (models will be preserved in volume)"
        read -p "Continue? [y/N] " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker rm "$OLLAMA_CONTAINER_NAME"
            print_info "Container removed"
        else
            print_info "Cancelled"
        fi
    else
        print_warn "Container does not exist"
    fi
}

# Main command dispatcher
case "${1:-}" in
    status)
        cmd_status
        ;;
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    logs)
        cmd_logs "$2"
        ;;
    stats)
        cmd_stats
        ;;
    health)
        cmd_health
        ;;
    remove)
        cmd_remove
        ;;
    -h|--help|help|"")
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_usage
        ;;
esac
