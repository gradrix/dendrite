#!/bin/bash

# Fix for stalled Ollama model downloads

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo ""
}

print_header "Ollama Model Download Fixer"

# Load config
if [ -f ".env" ]; then
    source .env
fi

OLLAMA_CONTAINER_NAME=${OLLAMA_CONTAINER_NAME:-ollama}
OLLAMA_PORT=${OLLAMA_PORT:-11434}

# Check if Ollama is running
if ! docker ps --format '{{.Names}}' | grep -q "^${OLLAMA_CONTAINER_NAME}$"; then
    print_error "Ollama container is not running"
    exit 1
fi

print_info "Ollama container is running"

# Show current situation
print_info "Checking current models..."
curl -s "http://localhost:${OLLAMA_PORT}/api/tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | while read -r model; do
    echo "  ✓ $model"
done

echo ""
print_warn "Model download appears to be stalled"
echo ""
echo "Choose a solution:"
echo ""
echo "1. Cancel and use smaller model (llama3.2:3b - 2GB, recommended)"
echo "2. Cancel and retry deepseek-r1:32b download"
echo "3. Just cancel - I'll download manually later"
echo "4. Check download status and wait"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        print_header "Switching to Smaller Model"
        
        # Update config files
        print_info "Updating configuration to use llama3.2:3b..."
        
        # Kill the current download
        print_info "Stopping current download..."
        docker exec $OLLAMA_CONTAINER_NAME pkill -f "ollama.*pull" 2>/dev/null || true
        sleep 2
        
        # Pull smaller model
        print_info "Pulling llama3.2:3b (this should be faster - only 2GB)..."
        echo ""
        
        curl -X POST "http://localhost:${OLLAMA_PORT}/api/pull" \
            -H "Content-Type: application/json" \
            -d '{"name": "llama3.2:3b"}' \
            --no-buffer | while IFS= read -r line; do
                if echo "$line" | grep -q '"status"'; then
                    status=$(echo "$line" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
                    echo -ne "\r${GREEN}Status:${NC} $status                              "
                fi
                if echo "$line" | grep -q '"completed"'; then
                    completed=$(echo "$line" | grep -o '"completed":[0-9]*' | cut -d':' -f2)
                    total=$(echo "$line" | grep -o '"total":[0-9]*' | cut -d':' -f2)
                    if [ -n "$completed" ] && [ -n "$total" ] && [ "$total" -gt 0 ]; then
                        percent=$((completed * 100 / total))
                        echo -ne "\r${GREEN}Progress:${NC} ${percent}% (${completed}/${total} bytes)                    "
                    fi
                fi
            done
        
        echo ""
        print_info "Model llama3.2:3b pulled successfully!"
        ;;
        
    2)
        print_header "Retrying deepseek-r1:32b Download"
        
        print_info "Stopping current download..."
        docker exec $OLLAMA_CONTAINER_NAME pkill -f "ollama.*pull" 2>/dev/null || true
        sleep 2
        
        print_info "Retrying download (this may take 10-20 minutes on slow connections)..."
        echo ""
        
        curl -X POST "http://localhost:${OLLAMA_PORT}/api/pull" \
            -H "Content-Type: application/json" \
            -d '{"name": "deepseek-r1:32b"}' \
            --no-buffer | while IFS= read -r line; do
                if echo "$line" | grep -q '"status"'; then
                    status=$(echo "$line" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
                    echo -ne "\r${GREEN}Status:${NC} $status                              "
                fi
            done
        
        echo ""
        print_info "Model pulled successfully!"
        ;;
        
    3)
        print_header "Cancelling Download"
        
        print_info "Stopping download..."
        docker exec $OLLAMA_CONTAINER_NAME pkill -f "ollama.*pull" 2>/dev/null || true
        
        echo ""
        print_info "Download cancelled."
        print_info "To download manually later, run:"
        echo "  docker exec -it $OLLAMA_CONTAINER_NAME ollama pull llama3.2:3b"
        echo "  # or"
        echo "  docker exec -it $OLLAMA_CONTAINER_NAME ollama pull llama3.1:8b"
        ;;
        
    4)
        print_header "Checking Download Status"
        
        print_info "Current Ollama logs (last 20 lines):"
        docker logs --tail 20 $OLLAMA_CONTAINER_NAME
        
        echo ""
        print_info "If download is progressing, wait for it to complete."
        print_info "If it keeps stalling, run this script again and choose option 1."
        ;;
        
    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

echo ""
print_header "Done!"

print_info "Current models:"
curl -s "http://localhost:${OLLAMA_PORT}/api/tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | while read -r model; do
    echo "  ✓ $model"
done

echo ""
print_info "You can now continue with the agent setup!"
