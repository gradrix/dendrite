#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Parse arguments
MODE="scheduler"
INSTRUCTION=""
USE_V2=false
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --once)
            MODE="once"
            shift
            ;;
        --instruction)
            MODE="instruction"
            INSTRUCTION="$2"
            shift 2
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --v2)
            USE_V2=true
            shift
            ;;
        --goal)
            MODE="goal"
            GOAL="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --once                Run all instructions once and exit"
            echo "  --instruction NAME    Run specific instruction only"
            echo "  --goal \"TEXT\"         Run with natural language goal"
            echo "  --json                Output full JSON structure (default: clean text)"
            echo "  --v2                  Use v2 step-by-step execution (better for small models)"
            echo "  --help, -h           Show this help message"
            echo ""
            echo "Without options, starts the scheduler for continuous operation"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

print_header "AI Agent Startup Script"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker info &> /dev/null; then
    print_error "Docker daemon is not running or you don't have permission"
    exit 1
fi

print_info "Docker is available"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed"
    exit 1
fi

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

print_info "Docker Compose is available"

# Check if .env exists, if not copy from example
if [ ! -f ".env" ]; then
    print_warn ".env file not found, creating from .env.example"
    cp .env.example .env
    print_info "Please edit .env file with your configuration"
fi

# Check if Strava cookies file exists
if [ ! -f ".strava_cookies" ]; then
    print_warn ".strava_cookies file not found"
    print_info "Create this file with your Strava session cookies (JSON format)"
    print_info "Example:"
    cat << 'EOF'
[
  {"name": "_strava4_session", "value": "your_session_value", "domain": ".strava.com"}
]
EOF
    echo ""
fi

# Check if Ollama is running
print_info "Checking Ollama availability..."
if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    print_warn "Ollama is not running. Starting Ollama first..."
    $DOCKER_COMPOSE up -d ollama ollama-setup
    print_info "Waiting for Ollama to be ready..."
    sleep 10
fi

print_info "Ollama is ready"

# Build the agent image
print_info "Building AI Agent Docker image..."
$DOCKER_COMPOSE build agent

# Build v2 flag if needed
V2_FLAG=""
if [ "$USE_V2" = true ]; then
    V2_FLAG="--v2"
    print_info "Using v2 step-by-step execution"
fi

# Build JSON output flag if needed
JSON_FLAG=""
if [ "$JSON_OUTPUT" = true ]; then
    JSON_FLAG="--json"
    print_info "Using JSON output mode (verbose structured data)"
fi

# Determine the command to run
case $MODE in
    once)
        print_header "Running Agent Once"
        print_info "Agent will run all instructions once and exit"
        $DOCKER_COMPOSE run --rm agent python main.py --once $V2_FLAG $JSON_FLAG
        ;;
    instruction)
        print_header "Running Specific Instruction"
        print_info "Instruction: $INSTRUCTION"
        $DOCKER_COMPOSE run --rm agent python main.py --instruction "$INSTRUCTION" $V2_FLAG $JSON_FLAG
        ;;
    goal)
        print_header "Running Goal"
        print_info "Goal: $GOAL"
        $DOCKER_COMPOSE run --rm agent python main.py --goal "$GOAL" $V2_FLAG $JSON_FLAG
        ;;
    scheduler)
        print_header "Starting Agent Scheduler"
        print_info "Agent will run continuously based on instruction schedules"
        print_info "Press Ctrl+C to stop"
        echo ""
        
        # Start agent service
        # Note: Scheduler currently uses v1 execution only
        if [ "$USE_V2" = true ]; then
            print_warn "Note: --v2 flag is ignored in scheduler mode (not yet implemented)"
        fi
        $DOCKER_COMPOSE up agent
        ;;
esac

print_info "Done!"
