#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    OLLAMA_PORT=${OLLAMA_PORT:-11434}
    DEFAULT_MODEL=${DEFAULT_MODEL:-llama3.1:8b}
fi

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Test 1: Check if API is accessible
print_info "Testing API connectivity..."
if curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" > /dev/null; then
    print_info "✓ API is accessible"
else
    print_error "✗ API is not accessible"
    exit 1
fi

# Test 2: List available models
print_info "Listing available models..."
models=$(curl -s "http://localhost:${OLLAMA_PORT}/api/tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)

if [ -z "$models" ]; then
    print_warn "No models found"
else
    echo -e "${GREEN}Available models:${NC}"
    echo "$models" | while read -r model; do
        echo "  - $model"
    done
fi

# Test 3: Test generation with default model
MODEL_TO_TEST=${1:-$DEFAULT_MODEL}

if echo "$models" | grep -q "^${MODEL_TO_TEST}$"; then
    print_info "Testing generation with model: $MODEL_TO_TEST"
    
    echo ""
    echo "Sending test prompt: 'Hello, are you ready?'"
    echo ""
    
    response=$(curl -s -X POST "http://localhost:${OLLAMA_PORT}/api/generate" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$MODEL_TO_TEST\",
            \"prompt\": \"Say 'I am ready to assist you!' and nothing else.\",
            \"stream\": false
        }")
    
    if echo "$response" | grep -q "response"; then
        print_info "✓ Generation test successful!"
        echo ""
        echo -e "${GREEN}Model Response:${NC}"
        echo "$response" | grep -o '"response":"[^"]*"' | cut -d'"' -f4
        echo ""
    else
        print_error "✗ Generation test failed"
        echo "$response"
        exit 1
    fi
else
    print_warn "Model $MODEL_TO_TEST not found, skipping generation test"
fi

# Test 4: Show API endpoints
echo ""
print_info "Available API endpoints:"
echo "  - GET  http://localhost:${OLLAMA_PORT}/api/tags         (list models)"
echo "  - POST http://localhost:${OLLAMA_PORT}/api/generate     (generate text)"
echo "  - POST http://localhost:${OLLAMA_PORT}/api/chat         (chat completion)"
echo "  - POST http://localhost:${OLLAMA_PORT}/api/pull         (pull model)"
echo "  - POST http://localhost:${OLLAMA_PORT}/api/push         (push model)"
echo "  - POST http://localhost:${OLLAMA_PORT}/api/embeddings   (generate embeddings)"

echo ""
print_info "All tests passed! Ollama is ready to use."
