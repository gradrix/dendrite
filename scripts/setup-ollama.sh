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
    echo -e "${GREEN}✓${NC} Loaded configuration from .env"
else
    echo -e "${YELLOW}⚠${NC} No .env file found, using defaults"
    OLLAMA_CONTAINER_NAME=${OLLAMA_CONTAINER_NAME:-ollama}
    OLLAMA_IMAGE=${OLLAMA_IMAGE:-ollama/ollama:latest}
    OLLAMA_PORT=${OLLAMA_PORT:-11434}
    OLLAMA_HOST=${OLLAMA_HOST:-0.0.0.0}
    DEFAULT_MODEL=${DEFAULT_MODEL:-llama3.1:8b}
    DOCKER_NETWORK=${DOCKER_NETWORK:-ollama-network}
    # GPU mode: true|false|auto (default: auto)
    USE_GPU=${USE_GPU:-auto}
    API_TIMEOUT=${API_TIMEOUT:-300}
    MAX_RETRIES=${MAX_RETRIES:-30}
    RETRY_INTERVAL=${RETRY_INTERVAL:-10}
fi

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running or you don't have permission"
        exit 1
    fi
    
    print_info "Docker is available and running"
}

# Detect if GPU is available and docker can access it
gpu_available() {
    # Basic checks: NVIDIA driver + device files (include WSL's /dev/dxg)
    if [ -x "$(command -v nvidia-smi)" ] || [ -e "/dev/nvidiactl" ] || [ -e "/dev/dri" ] || [ -e "/dev/dxg" ]; then
        # Check Docker supports --gpus flag (NVIDIA Container Toolkit / Docker Desktop)
        if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -qi 'nvidia'; then
            return 0
        fi

        # Fallback heuristic: newer Docker supports --gpus even without explicit runtime listing
        if docker run --help 2>/dev/null | grep -q -- "--gpus"; then
            return 0
        fi
    fi
    return 1
}

# Detect if running inside WSL
is_wsl() {
    if grep -qiE 'microsoft|wsl' /proc/sys/kernel/osrelease 2>/dev/null; then
        return 0
    fi
    if grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null; then
        return 0
    fi
    return 1
}

# Function to create Docker network if it doesn't exist
create_network() {
    if ! docker network inspect "$DOCKER_NETWORK" &> /dev/null; then
        print_info "Creating Docker network: $DOCKER_NETWORK"
        docker network create "$DOCKER_NETWORK"
    else
        print_info "Docker network '$DOCKER_NETWORK' already exists"
    fi
}

# Function to check if container exists
container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^${OLLAMA_CONTAINER_NAME}$"
}

# Function to check if container is running
container_running() {
    docker ps --format '{{.Names}}' | grep -q "^${OLLAMA_CONTAINER_NAME}$"
}

# Function to start Ollama container
start_ollama_container() {
    if container_running; then
        print_info "Ollama container is already running"
        return 0
    fi
    
    if container_exists; then
        print_info "Starting existing Ollama container..."
        docker start "$OLLAMA_CONTAINER_NAME"
    else
        print_info "Creating and starting new Ollama container..."
        
        # Build docker run command
        DOCKER_RUN_CMD="docker run -d --name $OLLAMA_CONTAINER_NAME"
        DOCKER_RUN_CMD="$DOCKER_RUN_CMD --network $DOCKER_NETWORK"
        DOCKER_RUN_CMD="$DOCKER_RUN_CMD -p ${OLLAMA_HOST}:${OLLAMA_PORT}:11434"
        DOCKER_RUN_CMD="$DOCKER_RUN_CMD -v ollama-data:/root/.ollama"
        
        # Decide GPU usage: true|false|auto
        case "$USE_GPU" in
            true)
                print_info "GPU requested via USE_GPU=true"
                DOCKER_RUN_CMD="$DOCKER_RUN_CMD --gpus all"
                ;;
            auto)
                if gpu_available; then
                    print_info "GPU detected and available to Docker (auto): enabling --gpus all"
                    DOCKER_RUN_CMD="$DOCKER_RUN_CMD --gpus all"
                else
                    print_warn "No usable GPU detected or Docker not configured for GPU (auto): running on CPU"
                    if is_wsl; then
                        print_warn "WSL detected. To enable GPU:"
                        echo "  - Ensure Windows NVIDIA drivers are installed"
                        echo "  - In Docker Desktop (Windows): enable WSL integration for your distro and GPU support"
                        echo "  - Or install NVIDIA Container Toolkit in WSL:"
                        echo "      sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit"
                        echo "      sudo nvidia-ctk runtime configure --runtime=docker && sudo service docker restart"
                    fi
                fi
                ;;
            *)
                # explicit false or any other value
                print_info "GPU disabled (USE_GPU=$USE_GPU)"
                ;;
        esac
        
        # Add resource limits if specified
        if [ -n "$OLLAMA_MEMORY_LIMIT" ]; then
            DOCKER_RUN_CMD="$DOCKER_RUN_CMD --memory $OLLAMA_MEMORY_LIMIT"
        fi
        
        if [ -n "$OLLAMA_CPU_LIMIT" ]; then
            DOCKER_RUN_CMD="$DOCKER_RUN_CMD --cpus $OLLAMA_CPU_LIMIT"
        fi
        
        # Complete the command
        DOCKER_RUN_CMD="$DOCKER_RUN_CMD --restart unless-stopped $OLLAMA_IMAGE"
        
        # Execute the command
        eval $DOCKER_RUN_CMD
        
        print_info "Ollama container created successfully"
    fi
}

# Function to wait for Ollama API to be ready
wait_for_ollama() {
    print_info "Waiting for Ollama API to be ready..."
    
    local retries=0
    local max_retries=$MAX_RETRIES
    local retry_interval=$RETRY_INTERVAL
    
    while [ $retries -lt $max_retries ]; do
        if curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" > /dev/null 2>&1; then
            print_info "Ollama API is ready!"
            return 0
        fi
        
        retries=$((retries + 1))
        if [ $retries -lt $max_retries ]; then
            echo -n "."
            sleep $retry_interval
        fi
    done
    
    print_error "Ollama API did not become ready in time"
    return 1
}

# Function to check if model exists
model_exists() {
    local model_name=$1
    curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" | grep -q "\"name\":\"${model_name}\""
}

# Function to pull model
pull_model() {
    local model_name=$1
    print_info "Pulling model: $model_name (this may take a while...)"
    
    # Use curl to pull the model via API
    curl -X POST "http://localhost:${OLLAMA_PORT}/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$model_name\"}" \
        --no-buffer 2>/dev/null | while IFS= read -r line; do
            # Extract status from JSON response
            if echo "$line" | grep -q '"status"'; then
                status=$(echo "$line" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
                echo -ne "\r${GREEN}Status:${NC} $status"
            fi
        done
    
    echo "" # New line after progress
    print_info "Model $model_name pulled successfully"
}

# Function to setup model
setup_model() {
    local model_name=${1:-$DEFAULT_MODEL}
    
    print_info "Checking for model: $model_name"
    
    if model_exists "$model_name"; then
        print_info "Model $model_name is already available"
    else
        print_info "Model $model_name not found, pulling..."
        pull_model "$model_name"
    fi
}

# Function to test the API
test_api() {
    local model_name=${1:-$DEFAULT_MODEL}
    
    print_info "Testing Ollama API with model: $model_name"
    
    response=$(curl -s -X POST "http://localhost:${OLLAMA_PORT}/api/generate" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$model_name\",
            \"prompt\": \"Say 'Hello, I am ready!' and nothing else.\",
            \"stream\": false
        }")
    
    if echo "$response" | grep -q "response"; then
        print_info "API test successful!"
        echo -e "${GREEN}Response:${NC}"
        echo "$response" | grep -o '"response":"[^"]*"' | cut -d'"' -f4
        return 0
    else
        print_error "API test failed"
        echo "$response"
        return 1
    fi
}

# Function to display status
show_status() {
    echo ""
    echo "========================================="
    echo "Ollama Container Status"
    echo "========================================="
    echo "Container Name: $OLLAMA_CONTAINER_NAME"
    echo "API Endpoint: http://localhost:${OLLAMA_PORT}"
    echo "Default Model: $DEFAULT_MODEL"
    
    if container_running; then
        echo -e "Status: ${GREEN}RUNNING${NC}"
        
        # List available models
        echo ""
        echo "Available Models:"
        curl -s "http://localhost:${OLLAMA_PORT}/api/tags" | \
            grep -o '"name":"[^"]*"' | cut -d'"' -f4 | while read -r model; do
                echo "  - $model"
            done
    else
        echo -e "Status: ${RED}NOT RUNNING${NC}"
    fi
    
    echo "========================================="
    echo ""
}

# Main execution
main() {
    echo ""
    echo "========================================="
    echo "Ollama Container Setup Script"
    echo "========================================="
    echo ""
    
    # Check Docker
    check_docker
    
    # Create network
    create_network
    
    # Start Ollama container
    start_ollama_container
    
    # Wait for API
    if ! wait_for_ollama; then
        print_error "Failed to start Ollama API"
        exit 1
    fi
    
    # Setup model
    setup_model "$DEFAULT_MODEL"
    
    # Show status
    show_status
    
    # Optional: Run a test
    if [ "${RUN_TEST:-false}" = "true" ]; then
        test_api "$DEFAULT_MODEL"
    fi
    
    print_info "Setup complete! Ollama is ready to use."
    print_info "API endpoint: http://localhost:${OLLAMA_PORT}"
    print_info "Example curl command:"
    echo "  curl -X POST http://localhost:${OLLAMA_PORT}/api/generate -H 'Content-Type: application/json' -d '{\"model\": \"$DEFAULT_MODEL\", \"prompt\": \"Hello!\", \"stream\": false}'"
}

# Run main function
main "$@"
