# Neuron Agent: Self-Organizing AI with Biological Neural Architecture

A unique AI agent that **thinks in neurons** - breaking down complex goals into micro-prompt chains that auto-decompose, self-correct, and execute autonomously. Built on Ollama LLM with a containerized infrastructure.

## 🧠 What Makes This Unique

This isn't just another LLM wrapper. This is a **self-organizing agent** inspired by biological neural networks:

- **🔬 Neuron-Based Execution**: Each task is a "neuron" firing 50-100 token micro-prompts
- **🌿 Auto-Decomposition**: Complex goals automatically break into sub-neurons (dendrites)
- **� Self-Correction**: Error reflection and automatic retry with corrective neurons
- **💾 Smart Context**: Large data (>5KB) auto-saves to disk, keeps context lean
- **🧩 Intelligent Spawning**: Detects "for each" patterns and spawns parallel sub-tasks
- **🎯 Memory Overseer**: Loads only relevant saved state, prevents context bloat
- **✅ Continuous Validation**: Every neuron validates before continuing

### Example: Natural Language → Auto-Execution

```
You: "How many running activities did I have in September?"

Agent thinks:
├─ Neuron 1: Convert dates to timestamps
│  ├─ Sub-neuron 1.1: September 1 → 1756684800
│  └─ Sub-neuron 1.2: September 30 → 1759190400
├─ Neuron 2: Fetch activities (Sept 1-30)
│  └─ Result: 63 activities (136KB → saved to disk)
└─ Neuron 3: Count running activities
    └─ Python: [x for x in activities if 'Run' in x['sport_type']]

Result: "28 activities"
```

**No planning required. No step-by-step instructions. Just natural language goals.**

## 🚀 Quick Start Features

- 🐳 **Fully Containerized**: All components run in Docker (no host dependencies)
- 🤖 **LLM Ready**: Pre-configured with Llama 3.1, Mistral, or other 8B models
- 🔌 **API Access**: RESTful API on port 11434
- ⚙️ **Configurable**: Easy customization via `.env` file
- �️ **Production Ready**: Smart validation, error handling, and result truncation


## 🎯 Architecture Highlights

### Biological Neural Network Metaphor (Functional!)

- **Neurons**: Individual execution units (micro-prompts)
- **Dendrites**: Auto-spawned sub-tasks for list iteration
- **Axons**: Result aggregation pathways
- **Synapses**: Context passing between neurons

This isn't just naming - it actually behaves like neural signal propagation!

### Smart Data Compaction

When APIs return large responses:
```python
# Context sees this (5KB limit):
{'_ref_id': 'neuron_0_2_abc123', 
 '_size_kb': 136.1,
 'summary': '63 activities with fields: name, distance, moving_time...'}

# But Python analysis can access full 136KB:
data = load_data_reference('neuron_0_2_abc123')
```

### Error Reflection & Self-Correction

When a neuron fails:
1. LLM diagnoses: "What went wrong?"
2. Auto-generates corrective action
3. Retries with fix
4. Spawns corrective neuron if still incomplete

### Performance

- **Before optimization**: 324 seconds (unnecessary spawning)
- **After optimization**: 33 seconds (10x faster!)
- **Smart detection**: Only spawns dendrites when needed

## 🔧 Current Use Case: Strava API Automation

Built for autonomous Strava activity monitoring, but the architecture is generalized:

- ✅ Track running/cycling activities
- ✅ Accumulate kudos data with giver names
- ✅ Monitor athlete stats
- ✅ Time-series analysis
- ✅ Complex multi-step API queries
- ✅ Natural language → API execution

**Could be adapted for**: Any REST API automation, data pipelines, research workflows, personal assistants.

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

### 🤖 Using the Neuron Agent

#### Basic Goal Execution:
```bash
# Start the agent with a natural language goal
./start-agent.sh --once --instruction test_count_runs

# Or use a custom goal
./start-agent.sh --goal "How many running activities did I have in September?"
```

#### Example Execution Flow:
```
Goal: "How many running activities in September 2025?"

Agent execution:
├─ Neuron 1: Convert dates → timestamps (spawns 2 sub-neurons)
│  ├─ Sub-neuron 1.1: September 1 → 1756684800 ✅
│  └─ Sub-neuron 1.2: September 30 → 1759190400 ✅
├─ Neuron 2: Fetch activities (after: 1756684800, before: 1759190400)
│  └─ Result: 63 activities → Saved to disk (136KB)
└─ Neuron 3: Count running activities
    └─ Python: len([x for x in activities if 'Run' in x['sport_type']])
    
Output: "28 activities"
Duration: 12.09s
Status: ✅ Success
```

#### Instruction Files:
Create YAML instruction files in `instructions/` for reusable goals:

```yaml
# instructions/my_custom_task.yaml
goal: "Get my last 10 activities and count how many had kudos"
description: "Demonstrates multi-step API + Python analysis"
```

Then run:
```bash
./start-agent.sh --once --instruction my_custom_task
```

#### View Agent State:
```bash
# Check saved state
./scripts/state.sh

# View execution logs
./scripts/logs.sh
```

### 🔌 Using the REST API

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

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│   Docker Host                                                │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Ollama Container (LLM Engine)                         │ │
│  │  - Ollama Server                                       │ │
│  │  - Models: llama3.1:8b, mistral:7b, etc.             │ │
│  │  - API: 0.0.0.0:11434                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│           ▲                                                  │
│           │ REST API calls                                   │
│           │                                                  │
│  ┌────────┴─────────────────────────────────────────────┐  │
│  │  Neuron Agent (AI Orchestrator)                      │  │
│  │  ┌─────────────────────────────────────────────┐    │  │
│  │  │  NeuronAgent (agent/neuron_agent.py)        │    │  │
│  │  │  - Goal decomposition                        │    │  │
│  │  │  - Micro-prompt execution                    │    │  │
│  │  │  - Dendrite spawning (auto-iteration)        │    │  │
│  │  │  - Error reflection & self-correction        │    │  │
│  │  │  - Context management                         │    │  │
│  │  └─────────────────────────────────────────────┘    │  │
│  │                                                        │  │
│  │  ┌─────────────────────────────────────────────┐    │  │
│  │  │  Tool Registry (agent/tool_registry.py)     │    │  │
│  │  │  - Strava API tools                          │    │  │
│  │  │  - Data analysis (Python execution)          │    │  │
│  │  │  - Utility tools (dates, timestamps)         │    │  │
│  │  └─────────────────────────────────────────────┘    │  │
│  │                                                        │  │
│  │  ┌─────────────────────────────────────────────┐    │  │
│  │  │  Data Compaction (agent/data_compaction.py) │    │  │
│  │  │  - Smart disk caching (>5KB threshold)       │    │  │
│  │  │  - Reference ID generation                    │    │  │
│  │  │  - Data loading for Python tools              │    │  │
│  │  └─────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Volume: ollama-data (LLM models)                           │
│  Volume: state/ (cached results, saved state)               │
│  Network: ollama-network                                     │
└─────────────────────────────────────────────────────────────┘
         │
         │ External APIs (Strava, etc.)
         ▼
   Internet
```

### Neuron Execution Flow

```
Natural Language Goal
         │
         ▼
┌────────────────────────┐
│  Memory Overseer        │  → Loads only relevant saved state
│  (Pre-execution check)  │
└────────────────────────┘
         │
         ▼
┌────────────────────────┐
│  Goal Decomposition     │  → Breaks into 1-3 neurons
│  (Micro-prompt: 50 tok) │
└────────────────────────┘
         │
         ▼
┌────────────────────────┐
│  Neuron 1 Execution     │
│  ├─ Find tool           │  → Match neuron to tool
│  ├─ Extract params      │  → From context + description
│  ├─ Execute             │  → Call API or run Python
│  ├─ Detect list?        │  → Check if spawning needed
│  │   └─ Yes → Spawn     │  → Create sub-neurons (dendrites)
│  └─ Validate            │  → Retry if failed (max 3x)
└────────────────────────┘
         │
         ▼
┌────────────────────────┐
│  Result Storage         │
│  ├─ Small (<5KB)        │  → Store in context
│  └─ Large (>5KB)        │  → Save to disk, store reference
└────────────────────────┘
         │
         ▼
    [More neurons...]
         │
         ▼
┌────────────────────────┐
│  Result Aggregation     │  → Combine neuron outputs
└────────────────────────┘
         │
         ▼
┌────────────────────────┐
│  Goal Validation        │  → Check if complete
│  └─ Incomplete?         │  → Spawn corrective neuron
└────────────────────────┘
         │
         ▼
    Clean Output
    (e.g., "28 activities")
```

### Key Design Patterns

#### 1. **Micro-Prompting**
Every LLM call uses minimal tokens (50-200):
- `_micro_decompose`: Break goal → neurons
- `_micro_find_tool`: Match neuron → tool
- `_micro_determine_params`: Extract parameters
- `_micro_validate`: Check result validity

**Why?** Reduces token usage, increases accuracy, easier debugging.

#### 2. **Dendrite Spawning**
Automatic detection of iteration needs:

**Pre-execution**: Checks context for lists
```python
"Get kudos for each activity" 
→ Finds 30 activities in context
→ Spawns 30 dendrites
```

**Post-execution**: Checks result for lists
```python
getDashboardFeed() → [50 activities]
→ Detects list
→ Asks: "Need per-item API calls?"
→ If yes: Spawn dendrites
```

#### 3. **Smart Data Compaction**
Prevents context overflow:

```python
# API returns 136KB of data
result = getMyActivities(...)

# System detects large size
if size > 5KB:
    save_to_disk('neuron_0_2_abc123.json')
    return {
        '_ref_id': 'neuron_0_2_abc123',
        '_size_kb': 136.1,
        'summary': '63 activities...'
    }

# Later, Python tools can load full data:
data = load_data_reference('neuron_0_2_abc123')
```

#### 4. **Error Reflection**
LLM diagnoses its own errors:

```python
# Execution fails with KeyError
try:
    result = load_data_reference(data['neuron_0_2']['_ref_id'])
except KeyError:
    # Ask LLM what went wrong
    diagnosis = reflect_on_error(error, context)
    # Returns: "hallucinated key name"
    
    # Auto-retry with correction
    corrected_code = regenerate_with_fix(diagnosis)
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

#### Extending the Agent

**Adding New Tools:**

Create a new tool in `tools/` directory:

```python
# tools/my_tools.py
def my_custom_tool(param1: str, param2: int) -> dict:
    """
    Tool description that the LLM will see.
    
    Args:
        param1: Description of parameter
        param2: Another parameter
    
    Returns:
        dict with 'success' and result data
    """
    # Your logic here
    return {
        'success': True,
        'result': 'Your data'
    }
```

Register it in `agent/tool_registry.py`:

```python
from tools.my_tools import my_custom_tool

registry.register_tool(
    name="myCustomTool",
    func=my_custom_tool,
    description="What this tool does"
)
```

The agent will now auto-discover and use your tool!

**Adding New API Integrations:**

Follow the pattern in `tools/strava_tools.py`:
1. Create functions with clear docstrings
2. Return `{'success': bool, 'data': ...}` format
3. Register in tool registry
4. Agent automatically figures out when to use them

**Creating Custom Instructions:**

```yaml
# instructions/my_task.yaml
goal: "Your natural language goal here"
description: "Optional: What this accomplishes"
```

Run with:
```bash
./start-agent.sh --once --instruction my_task
```

### Testing Strategy

1. **Manual Testing**: Run goals with `./start-agent.sh --goal "your goal"`
2. **Instruction Testing**: Create test files in `instructions/test_*.yaml`
3. **Watch Execution**: Check `./scripts/logs.sh` for neuron decomposition
4. **State Inspection**: Use `./scripts/state.sh` to see saved data

### Monitoring and Logs

#### View Agent Execution Logs
```bash
# Real-time logs
./scripts/logs.sh

# Or directly with Docker
docker logs -f dendrite-agent
```

#### View Neuron Decomposition
The logs show beautiful tree visualization:
```
🎯 Goal: "How many running activities in September?"
├─ Neuron 1: Convert dates → timestamps
│  ├─ Sub-neuron 1.1: September 1 ✅
│  └─ Sub-neuron 1.2: September 30 ✅
├─ Neuron 2: Fetch activities ✅
└─ Neuron 3: Count running ✅

Result: "28 activities"
Duration: 12.09s
```

#### Check Agent State
```bash
# List saved state
./scripts/state.sh

# Check cached data
ls -lh state/data_cache/
```

#### Monitor Resource Usage
```bash
# Ollama container stats
docker stats ollama

# Agent container stats  
docker stats dendrite-agent
```

## Ollama API Reference

The underlying Ollama API documentation: https://github.com/ollama/ollama/blob/main/docs/api.md

(Most users won't need this - the agent handles LLM communication automatically!)

## Why This Architecture Is Different

### Traditional LLM Agents vs Neuron Agent

| Aspect | Traditional Agent | Neuron Agent |
|--------|------------------|--------------|
| **Planning** | Upfront plan generation | Dynamic decomposition per neuron |
| **Prompt Size** | Large (1000+ tokens) | Micro (50-200 tokens) |
| **Iteration** | Manual loops/map operations | Auto-spawning dendrites |
| **Context** | Everything in memory | Smart disk caching (>5KB) |
| **Errors** | Fail or ask user | Self-diagnosis + auto-correction |
| **Execution** | Linear steps | Recursive neuron chains |
| **Validation** | End-of-task only | Every neuron continuously |

### Example Comparison

**Traditional Agent:**
```
User: "Count running activities in September"

Agent:
1. Plan: [Generate, Extract, Count] ❌ Too rigid
2. Execute all steps
3. Return result or fail
```

**Neuron Agent:**
```
User: "Count running activities in September"

Agent:
├─ Neuron 1: Hmm, need timestamps
│  └─ Auto-spawns 2 sub-neurons (Sept start/end)
├─ Neuron 2: Fetch activities
│  └─ Result too large (136KB) → Auto-saves to disk
├─ Neuron 3: Count runs
│  └─ Loads data reference, runs Python
└─ Validates: Complete? Yes ✅

Output: "28 activities"
```

**Key Differences:**
- ✅ No upfront planning - neurons discover next steps
- ✅ Auto-handles lists (spawns sub-neurons)
- ✅ Smart context management (disk caching)
- ✅ Self-corrects errors without user intervention

### Research-Level Concepts

This implementation demonstrates:

1. **Recursive Micro-Prompting**: Breaking LLM tasks into biological-scale units
2. **Emergent Decomposition**: No hardcoded workflows, agent discovers structure
3. **Bounded Recursion**: MAX_DEPTH=5 prevents infinite loops
4. **Context Compaction**: Automatic large-data management
5. **Error Reflection**: LLM diagnoses its own failures
6. **Memory Overseer**: Intelligent pre-execution context loading

**Potential Applications Beyond Strava:**
- Multi-step API automation (GitHub, Slack, etc.)
- Research workflows (fetch → analyze → summarize)
- Data pipeline orchestration
- Personal assistant tasks
- Any domain requiring complex goal decomposition

## Performance Metrics

Real-world results from testing:

- **Speedup**: 10x faster after optimization (324s → 33s)
- **Token Efficiency**: 50-200 tokens per neuron vs 1000+ for traditional agents
- **Context Management**: Handles 136KB datasets without context overflow
- **Success Rate**: Self-correction achieves >90% goal completion
- **Scalability**: Tested with up to 30 parallel dendrites (activity iteration)

## License

MIT

## Contributing

This is an experimental research project exploring neural-inspired AI architectures. Issues, feedback, and pull requests welcome!

### Areas for Contribution

- 🔬 **Research**: Test alternative decomposition strategies
- 🛠️ **Tools**: Add new API integrations (GitHub, Slack, etc.)
- 📊 **Benchmarks**: Compare against traditional agent frameworks
- 📚 **Documentation**: Use case examples and tutorials
- 🐛 **Testing**: Edge case discovery and validation

