# Ollama Container Setup

A complete Docker-based solution for running Ollama LLM (Large Language Model) with automatic setup, model management, and API accessibility.

## Features

- 🐳 **Fully Containerized**: All components run in Docker containers (no host dependencies)
- 🚀 **Automatic Setup**: Idempotent scripts that handle container lifecycle and model downloads
- 🤖 **LLM Ready**: Pre-configured to use small 8B parameter models (Llama 3.1, Mistral, etc.)
- 🔌 **API Access**: RESTful API accessible on port 11434
- 🛠️ **Helper Scripts**: Utilities for testing, stopping, and managing models
- ⚙️ **Configurable**: Easy customization via `.env` file
- 🔄 **Idempotent**: Safe to run multiple times

## Prerequisites

- Docker Engine 20.10+ 
- Docker Compose 2.0+ (optional, for docker-compose usage)
- At least 8GB RAM recommended for 8B models
- (Optional) NVIDIA GPU with nvidia-docker for GPU acceleration

## Quick Start

### Method 1: Using Docker Compose (Recommended)

1. **Clone and configure**:
   ```bash
   # Copy example configuration
   cp .env.example .env
   
   # Edit configuration if needed
   nano .env
   ```

2. **Start everything**:
   ```bash
   docker-compose up -d
   ```

   This will:
   - Start the Ollama container
   - Wait for it to be healthy
   - Run the setup script to pull the default model
   - Make the API available at `http://localhost:11434`

3. **Check status**:
   ```bash
   docker-compose logs -f ollama-setup
   ```

### Method 2: Using Shell Script Directly

1. **Make scripts executable**:
   ```bash
   chmod +x setup-ollama.sh stop-ollama.sh test-ollama.sh list-models.sh
   ```

2. **Run setup**:
   ```bash
   ./setup-ollama.sh
   ```

   This will:
   - Check if Docker is available
   - Create a Docker network
   - Start the Ollama container (if not running)
   - Wait for the API to be ready
   - Pull the default model (llama3.1:8b)
   - Display status and usage information

## Configuration

Edit the `.env` file to customize your setup:

```bash
# Container settings
OLLAMA_CONTAINER_NAME=ollama
OLLAMA_IMAGE=ollama/ollama:latest
OLLAMA_PORT=11434
OLLAMA_HOST=0.0.0.0

# Model configuration
# Options: llama3.1:8b, llama3.2:3b, mistral:7b-instruct-v0.3, gemma2:9b
DEFAULT_MODEL=llama3.1:8b

# Network settings
DOCKER_NETWORK=ollama-network

# GPU support (set to true if you have NVIDIA GPU)
USE_GPU=false

# API settings
API_TIMEOUT=300
MAX_RETRIES=30
RETRY_INTERVAL=10
```

## Available Scripts

### `setup-ollama.sh`
Main setup script that:
- Starts the Ollama container
- Pulls the specified model
- Verifies API accessibility

```bash
./setup-ollama.sh
```

### `test-ollama.sh`
Tests the Ollama API and generates a test response:

```bash
# Test with default model
./test-ollama.sh

# Test with specific model
./test-ollama.sh mistral:7b-instruct-v0.3
```

### `list-models.sh`
Lists all available models in your Ollama instance:

```bash
./list-models.sh
```

### `stop-ollama.sh`
Stops the Ollama container:

```bash
# Stop container
./stop-ollama.sh

# Stop and remove container
./stop-ollama.sh --remove
```

## Usage Examples

### Using the REST API

#### Generate text:
```bash
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "prompt": "Explain Docker in one sentence.",
    "stream": false
  }'
```

#### Chat completion:
```bash
curl -X POST http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [
      {"role": "user", "content": "Hello! How are you?"}
    ],
    "stream": false
  }'
```

#### List models:
```bash
curl http://localhost:11434/api/tags
```

#### Pull a new model:
```bash
curl -X POST http://localhost:11434/api/pull \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mistral:7b-instruct-v0.3"
  }'
```

### Using with Python

```python
import requests

url = "http://localhost:11434/api/generate"
payload = {
    "model": "llama3.1:8b",
    "prompt": "What is the meaning of life?",
    "stream": False
}

response = requests.post(url, json=payload)
print(response.json()["response"])
```

## Recommended Models (8B Parameter Range)

- **llama3.1:8b** - Meta's Llama 3.1 (Recommended, balanced performance)
- **llama3.2:3b** - Smaller, faster variant
- **mistral:7b-instruct-v0.3** - Excellent instruction following
- **gemma2:9b** - Google's Gemma 2

## GPU Support

This setup can use your GPU when available. By default it runs in auto mode:

- auto (default): if a compatible GPU is detected and Docker is configured, it enables `--gpus all`; otherwise it falls back to CPU.
- true: always request GPU (requires NVIDIA Container Toolkit).
- false: force CPU-only.

Steps to use GPU acceleration:

1. Install NVIDIA drivers and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).
2. Ensure `.env` has the desired mode (default is auto):
  ```bash
  USE_GPU=auto   # or true/false
  ```
3. Run the setup normally:
  ```bash
  ./setup-ollama.sh
  ```

The script will print whether GPU is enabled. If you force `USE_GPU=true` but Docker isn't configured, container startup may fail.

### WSL notes (Windows Subsystem for Linux)

If you are running in WSL and see an error like:

```
docker: Error response from daemon: could not select device driver "" with capabilities: [[gpu]]
```

Follow one of these paths:

- Docker Desktop (recommended):
  1. Install latest NVIDIA Windows driver.
  2. In Docker Desktop (Windows): Settings → Resources → WSL Integration → enable your distro; ensure GPU support is enabled.
  3. Restart Docker Desktop and WSL (`wsl --shutdown`).

- Native dockerd inside WSL:
  ```bash
  # In WSL
  sudo apt-get update
  sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo service docker restart   # or: sudo systemctl restart docker (if systemd enabled)
  ```

Then verify:
```bash
docker info | grep -i runtimes    # should include nvidia
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

## Troubleshooting

### Container won't start
```bash
# Check Docker daemon
docker info

# Check container logs
docker logs ollama

# Remove and recreate
./stop-ollama.sh --remove
./setup-ollama.sh
```

### API not responding
```bash
# Check if container is running
docker ps | grep ollama

# Check API health
curl http://localhost:11434/api/tags

# Restart container
docker restart ollama
```

### Model download stuck
```bash
# Check container logs
docker logs -f ollama

# Free up space if needed
docker system prune -a

# Try smaller model
# Edit .env and set: DEFAULT_MODEL=llama3.2:3b
```

### Port already in use
Edit `.env` and change:
```bash
OLLAMA_PORT=11435  # or any other available port
```

## Architecture

```
┌─────────────────────────────────────┐
│   Docker Host                        │
│                                      │
│  ┌────────────────────────────────┐ │
│  │  Ollama Container              │ │
│  │  - Ollama Server               │ │
│  │  - LLM Models                  │ │
│  │  - API: 0.0.0.0:11434         │ │
│  └────────────────────────────────┘ │
│           ▲                          │
│           │                          │
│  ┌────────┴───────────────────────┐ │
│  │  Setup Container               │ │
│  │  - setup-ollama.sh             │ │
│  │  - Docker CLI                  │ │
│  │  - curl, jq                    │ │
│  └────────────────────────────────┘ │
│                                      │
│  Volume: ollama-data                 │
│  Network: ollama-network             │
└─────────────────────────────────────┘
         │
         │ HTTP API
         ▼
   External Clients
```

## Implementation Details

This section explains the technical implementation and design decisions of the project.

### Project Structure

```
center/
├── .env                    # Active configuration (gitignored)
├── .env.example           # Configuration template
├── .gitignore             # Git ignore rules
├── docker-compose.yml     # Docker Compose orchestration
├── Dockerfile             # Container for setup script
├── README.md              # This file
├── setup-ollama.sh        # Main setup script
├── stop-ollama.sh         # Stop utility
├── test-ollama.sh         # Testing utility
└── list-models.sh         # Model listing utility
```

### Components Explained

#### 1. Configuration Files (`.env` and `.env.example`)

**Purpose**: Centralized configuration management for all scripts and containers.

**What it does**:
- Defines container names, ports, and network settings
- Specifies which LLM model to use by default
- Configures API timeout and retry parameters
- Enables/disables GPU support

**Why it matters**: Allows easy customization without modifying scripts. The `.env.example` serves as documentation and template, while `.env` is gitignored to prevent committing local settings.

**Key settings**:
```bash
DEFAULT_MODEL=llama3.1:8b      # Which model to auto-download
OLLAMA_PORT=11434              # API port binding
USE_GPU=false                  # GPU acceleration toggle
MAX_RETRIES=30                 # How long to wait for API
```

#### 2. Main Setup Script (`setup-ollama.sh`)

**Purpose**: Idempotent, automated Ollama container setup and model initialization.

**What it does**:
1. **Environment Check**: Verifies Docker is installed and running
2. **Network Creation**: Creates isolated Docker network for Ollama
3. **Container Lifecycle**:
   - Checks if container exists and is running
   - Starts existing container OR creates new one
   - Configures volumes, ports, networks, and optional GPU
4. **Health Monitoring**: Waits up to 5 minutes for API to be ready (configurable)
5. **Model Management**: 
   - Checks if specified model exists via API
   - Pulls model automatically if not present
   - Shows progress during download
6. **Status Display**: Shows container info, available models, and usage examples

**Key Features**:
- **Idempotent**: Safe to run multiple times without side effects
- **Error Handling**: Colored output (green/yellow/red) for clear status
- **Retry Logic**: Configurable retries with exponential backoff
- **GPU Support**: Conditionally adds `--gpus all` flag

**Technical highlights**:
```bash
# Dynamic Docker run command building
DOCKER_RUN_CMD="docker run -d --name $OLLAMA_CONTAINER_NAME"
DOCKER_RUN_CMD="$DOCKER_RUN_CMD --network $DOCKER_NETWORK"
# ... conditionally adds GPU, memory limits, etc.

# API polling with retries
while [ $retries -lt $max_retries ]; do
    if curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" > /dev/null 2>&1; then
        return 0  # Success!
    fi
    sleep $retry_interval
done
```

#### 3. Dockerfile (Script Runner Container)

**Purpose**: Containerize the setup script to eliminate host dependencies.

**What it does**:
- Uses `docker:24-cli` as base (lightweight Alpine with Docker CLI)
- Installs runtime dependencies: `bash`, `curl`, `jq`, `grep`
- Copies setup script and configuration
- Makes script executable

**Why containerized**:
- ✅ No host dependencies (works on any system with Docker)
- ✅ Consistent environment across all platforms
- ✅ Can manage Docker containers from within a container (via Docker socket mount)

**How it works**:
```dockerfile
FROM docker:24-cli                    # Lightweight base with Docker CLI
RUN apk add --no-cache bash curl jq   # Install dependencies
COPY setup-ollama.sh /app/            # Copy script
RUN chmod +x /app/setup-ollama.sh     # Make executable
ENTRYPOINT ["/app/setup-ollama.sh"]   # Default command
```

#### 4. Docker Compose Configuration (`docker-compose.yml`)

**Purpose**: Orchestrate both Ollama server and setup script with proper dependencies.

**What it does**:
1. **Ollama Service**:
   - Runs the official Ollama image
   - Exposes API on port 11434
   - Mounts persistent volume for models
   - Includes health check (polls `/api/tags`)
   - Auto-restarts unless stopped manually

2. **Setup Service**:
   - Builds from Dockerfile
   - Mounts Docker socket (`/var/run/docker.sock`) to control host Docker
   - Depends on Ollama being healthy before running
   - Runs setup script to pull models

3. **Networking**: Creates isolated bridge network
4. **Volumes**: Named volume for persistent model storage

**Key feature - Health checks**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
  interval: 30s
  start_period: 40s
```

**Dependency management**:
```yaml
depends_on:
  ollama:
    condition: service_healthy  # Wait for health check to pass
```

#### 5. Helper Utilities

##### `stop-ollama.sh`
- Gracefully stops the Ollama container
- Optional `--remove` flag to delete container
- Preserves volume data unless explicitly removed

##### `test-ollama.sh`
- **API Connectivity**: Verifies `/api/tags` endpoint
- **Model Listing**: Shows all available models
- **Generation Test**: Sends test prompt and validates response
- **Endpoint Documentation**: Lists all available API endpoints

##### `list-models.sh`
- Queries Ollama API for installed models
- Displays model names and sizes (in GB)
- Shows popular models available for download
- Includes example pull commands

#### 6. Git Configuration (`.gitignore`)

**Purpose**: Prevent committing sensitive or generated files.

**What it ignores**:
- `.env` (local configuration may contain secrets)
- Volume data directories
- Editor-specific files
- OS-specific files (`.DS_Store`, `Thumbs.db`)
- Log files

**What it keeps**: `.env.example` for documentation

### Design Decisions

#### 1. Why Containerize Everything?
**Problem**: Different systems have different versions of curl, bash, jq, etc.
**Solution**: Run setup script in container with known dependencies.
**Benefit**: Works identically on any system with Docker.

#### 2. Why Separate Setup Script?
**Problem**: docker-compose alone can't conditionally pull models or wait for API readiness.
**Solution**: Setup container runs after Ollama is healthy.
**Benefit**: Fully automated, no manual intervention needed.

#### 3. Why Idempotent Design?
**Problem**: Users may run script multiple times (intentionally or accidentally).
**Solution**: Check state before every action (container exists? model exists?).
**Benefit**: Safe to run repeatedly, self-healing on failures.

#### 4. Why Named Volumes?
**Problem**: Models are large (2-8 GB), re-downloading on every restart is wasteful.
**Solution**: Named volume `ollama-data` persists models across container recreations.
**Benefit**: Fast restarts, persistent data.

#### 5. Why Health Checks?
**Problem**: Ollama takes 10-30 seconds to start and be ready for API calls.
**Solution**: Docker health checks + retry logic in setup script.
**Benefit**: Reliable startup, no race conditions.

### Workflow Diagrams

#### Initial Setup Flow
```
User runs: docker-compose up -d
    ↓
docker-compose creates network
    ↓
Starts ollama container
    ↓
Health check polls /api/tags every 30s
    ↓
Health check passes (API ready)
    ↓
Starts ollama-setup container (depends_on health)
    ↓
setup-ollama.sh runs:
  - Verifies Docker available
  - Waits for API (redundant safety check)
  - Checks if model exists
    ├─ Yes: Skip pull
    └─ No: Pull model via API
    ↓
Displays status and exits
    ↓
System ready! API accessible at :11434
```

#### API Request Flow
```
External Client (curl/Python/etc)
    ↓
HTTP POST → localhost:11434/api/generate
    ↓
Docker port mapping (host:11434 → container:11434)
    ↓
ollama-network (Docker bridge)
    ↓
Ollama container receives request
    ↓
Loads model from /root/.ollama (volume mount)
    ↓
Processes with LLM
    ↓
Returns JSON response
    ↓
Client receives completion
```

### Security Considerations

1. **Docker Socket Mounting**: Setup container has access to Docker daemon
   - ⚠️ This is powerful but necessary for container management
   - ✅ Runs only during setup, not persistent
   - ✅ Can be removed after initial setup

2. **Network Isolation**: Containers use dedicated bridge network
   - ✅ Isolated from other Docker networks
   - ✅ Can restrict external access by changing `OLLAMA_HOST`

3. **Volume Permissions**: Model data stored in named volume
   - ✅ Owned by container user
   - ✅ Not directly accessible from host (security through obscurity)

### Performance Tuning

#### Memory Settings
For 8B models, recommend at least 8GB RAM:
```bash
# In .env
OLLAMA_MEMORY_LIMIT=8g
```

#### CPU Limits
Prevent resource hogging:
```bash
# In .env
OLLAMA_CPU_LIMIT=4
```

#### GPU Acceleration
For NVIDIA GPUs (10-50x faster inference):
```bash
# In .env (auto uses GPU if available)
USE_GPU=auto   # or true/false
```

### Extending the System

#### Adding New Models
```bash
# Option 1: Change default in .env
DEFAULT_MODEL=mistral:7b-instruct-v0.3

# Option 2: Pull manually via API
curl -X POST http://localhost:11434/api/pull \
  -d '{"name": "gemma2:9b"}'
```

#### Adding New Scripts
Template for new utility scripts:
```bash
#!/bin/bash
set -e
source "$(dirname "$0")/.env"  # Load config
# Your logic here
```

#### Integrating with Applications
The API is RESTful and language-agnostic:
- **Python**: `requests` library
- **JavaScript**: `fetch` or `axios`
- **Go**: `net/http` package
- **Java**: `HttpClient`
- **Any language with HTTP support**

### Testing Strategy

1. **Manual Testing**: Run `./test-ollama.sh`
2. **API Testing**: Use included curl examples
3. **Integration Testing**: Test with your application
4. **Load Testing**: Use tools like `wrk` or `ab` for benchmarking

### Monitoring and Logs

#### View Ollama Logs
```bash
docker logs -f ollama
```

#### View Setup Logs
```bash
docker-compose logs ollama-setup
```

#### Check Resource Usage
```bash
docker stats ollama
```

## API Documentation

Full Ollama API documentation: https://github.com/ollama/ollama/blob/main/docs/api.md

## License

MIT

## Contributing

Feel free to submit issues and pull requests!
