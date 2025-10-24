#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    OLLAMA_PORT=${OLLAMA_PORT:-11434}
fi

OLLAMA_URL="http://localhost:${OLLAMA_PORT}"

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_header() {
    echo -e "${CYAN}=========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}=========================================${NC}"
}

# Check if API is accessible
check_ollama() {
    if ! curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        print_error "Ollama API is not accessible at ${OLLAMA_URL}"
        print_error "Is the container running? Try: docker ps | grep ollama"
        exit 1
    fi
}

# Show running models
show_running() {
    print_header "Running Models"
    
    response=$(curl -s "${OLLAMA_URL}/api/ps" 2>/dev/null)
    
    if [ -z "$response" ] || [ "$response" = "{}" ] || [ "$response" = '{"models":[]}' ]; then
        print_warning "No models currently running"
        echo ""
        return
    fi
    
    # Parse and display running models
    echo "$response" | python3 -c "
import json
import sys
from datetime import datetime

try:
    data = json.load(sys.stdin)
    models = data.get('models', [])
    
    if not models:
        print('No models currently running')
    else:
        for i, model in enumerate(models, 1):
            name = model.get('name', 'unknown')
            size = model.get('size', 0)
            size_gb = size / (1024**3)
            
            # Get timing info if available
            expires_at = model.get('expires_at', '')
            digest = model.get('digest', '')[:12]
            
            print(f'  {i}. {name}')
            print(f'     Size: {size_gb:.2f} GB')
            print(f'     Digest: {digest}...')
            if expires_at:
                print(f'     Expires: {expires_at}')
            print()
            
except Exception as e:
    print(f'Error parsing response: {e}', file=sys.stderr)
" || echo "$response"
    
    echo ""
}

# Unload a specific model
unload_model() {
    local model_name="$1"
    
    if [ -z "$model_name" ]; then
        print_error "Model name required"
        echo "Usage: $0 unload <model-name>"
        exit 1
    fi
    
    print_info "Unloading model: $model_name"
    
    # Generate a request with keep_alive=0 to unload
    response=$(curl -s -X POST "${OLLAMA_URL}/api/generate" \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"${model_name}\", \"keep_alive\": 0}" 2>&1)
    
    if [ $? -eq 0 ]; then
        print_info "Model unloaded successfully"
    else
        print_error "Failed to unload model: $response"
        exit 1
    fi
}

# Load/warm up a model
load_model() {
    local model_name="$1"
    
    if [ -z "$model_name" ]; then
        print_error "Model name required"
        echo "Usage: $0 load <model-name>"
        exit 1
    fi
    
    print_info "Loading model: $model_name"
    print_info "This will keep the model in memory for 5 minutes..."
    
    # Generate a simple request to load the model
    response=$(curl -s -X POST "${OLLAMA_URL}/api/generate" \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"${model_name}\", \"prompt\": \"hi\", \"stream\": false, \"keep_alive\": \"5m\"}" 2>&1)
    
    if [ $? -eq 0 ]; then
        print_info "Model loaded successfully (will stay in memory for 5 minutes)"
    else
        print_error "Failed to load model: $response"
        exit 1
    fi
}

# Unload all running models
unload_all() {
    print_info "Unloading all running models..."
    
    response=$(curl -s "${OLLAMA_URL}/api/ps" 2>/dev/null)
    
    if [ -z "$response" ] || [ "$response" = "{}" ] || [ "$response" = '{"models":[]}' ]; then
        print_warning "No models currently running"
        return
    fi
    
    # Extract model names and unload each
    echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    models = data.get('models', [])
    
    for model in models:
        name = model.get('name', '')
        if name:
            print(name)
            
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
" | while read -r model_name; do
        if [ -n "$model_name" ]; then
            print_info "Unloading: $model_name"
            curl -s -X POST "${OLLAMA_URL}/api/generate" \
                -H "Content-Type: application/json" \
                -d "{\"model\": \"${model_name}\", \"keep_alive\": 0}" > /dev/null 2>&1
        fi
    done
    
    print_info "All models unloaded"
}

# Show help
show_help() {
    echo "Ollama Model Management Tool"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  ps, running          Show currently running models"
    echo "  load <model>         Load a model into memory"
    echo "  unload <model>       Unload a specific model from memory"
    echo "  unload-all           Unload all running models"
    echo "  list                 List all available models"
    echo "  help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 ps                          # Show running models"
    echo "  $0 load llama3.2:3b            # Load a model"
    echo "  $0 unload llama3.2:3b          # Unload a model"
    echo "  $0 unload-all                  # Unload everything"
    echo ""
}

# Main command handler
main() {
    local command="${1:-ps}"
    
    case "$command" in
        ps|running)
            check_ollama
            show_running
            ;;
        load)
            check_ollama
            load_model "$2"
            ;;
        unload)
            check_ollama
            unload_model "$2"
            ;;
        unload-all)
            check_ollama
            unload_all
            ;;
        list)
            check_ollama
            ./list-models.sh
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
