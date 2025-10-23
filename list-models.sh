#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    OLLAMA_PORT=${OLLAMA_PORT:-11434}
fi

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if API is accessible
if ! curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" > /dev/null; then
    print_error "Ollama API is not accessible. Is the container running?"
    exit 1
fi

print_info "Fetching available models..."
echo ""

# Get and parse model information
models_json=$(curl -s "http://localhost:${OLLAMA_PORT}/api/tags")

if [ -z "$models_json" ] || [ "$models_json" = "{}" ]; then
    print_error "No models found or unable to fetch model list"
    exit 1
fi

# Display models in a formatted way
echo "========================================="
echo "Available Ollama Models"
echo "========================================="

# Parse JSON and display model information
echo "$models_json" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | while read -r model; do
    echo -e "${GREEN}●${NC} $model"
    
    # Try to get size information
    size=$(echo "$models_json" | grep -A5 "\"name\":\"$model\"" | grep -o '"size":[0-9]*' | cut -d':' -f2 | head -1)
    if [ -n "$size" ]; then
        # Convert bytes to GB
        size_gb=$(echo "scale=2; $size / 1024 / 1024 / 1024" | bc 2>/dev/null || echo "N/A")
        if [ "$size_gb" != "N/A" ]; then
            echo "  Size: ${size_gb} GB"
        fi
    fi
done

echo "========================================="
echo ""

# Count total models
total=$(echo "$models_json" | grep -o '"name":"[^"]*"' | wc -l)
print_info "Total models: $total"

echo ""
print_info "To pull a new model, use:"
echo "  curl -X POST http://localhost:${OLLAMA_PORT}/api/pull -d '{\"name\": \"model-name\"}'"
echo ""
print_info "Popular 8B models you can pull:"
echo "  - llama3.1:8b"
echo "  - llama3.2:3b"
echo "  - mistral:7b-instruct-v0.3"
echo "  - gemma2:9b"
