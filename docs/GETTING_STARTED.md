# Getting Started with Dendrite

This guide will walk you through setting up and running Dendrite for the first time.

## Prerequisites

Before you begin, ensure you have:

- **Docker Engine 20.10+** - [Install Docker](https://docs.docker.com/get-docker/)
- **Docker Compose 2.0+** - Usually included with Docker Desktop
- **8GB+ RAM** - Required for running LLM models
- **(Optional) NVIDIA GPU** - For GPU acceleration with drivers installed

Verify your installation:
```bash
docker --version
docker compose version
```

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/gradrix/dendrite.git
cd dendrite
```

### 2. Choose Your Profile

Dendrite supports two deployment profiles:

**CPU Profile** (default - works everywhere):
```bash
docker compose --profile cpu up -d
```

**GPU Profile** (requires NVIDIA GPU + drivers):
```bash
docker compose --profile gpu up -d
```

The CPU profile is perfect for:
- CI/CD environments
- Cloud servers without GPU
- Testing and development
- Resource-constrained environments

The GPU profile provides 10-50x faster inference when available.

### 3. Wait for Services to Start

The first startup takes 2-5 minutes to:
- Pull Docker images
- Download the LLM model (mistral, ~4GB)
- Initialize databases
- Index tools for semantic search

Monitor progress:
```bash
docker compose logs -f ollama-cpu  # or ollama for GPU
```

Look for: `"Ollama server ready"` or API becomes responsive.

### 4. Verify Installation

Check all services are running:
```bash
docker compose ps
```

You should see:
- `redis` - Message bus
- `postgres` - Analytics storage
- `ollama-cpu` (or `ollama`) - LLM engine
- Tool discovery indexing complete

Test the LLM:
```bash
docker compose exec ollama-cpu ollama run mistral "Hello!"
```

### 5. Run Your First Goal

```bash
python run_goal.py "Remember that my favorite color is blue"
```

Expected output:
```
Intent: tool_use
Domain: memory
Tool selected: memory_write
✓ Stored: favorite_color = blue
```

Verify it worked:
```bash
python run_goal.py "What is my favorite color?"
```

Expected output:
```
Intent: tool_use
Domain: memory
Tool selected: memory_read
Result: Your favorite color is blue
```

## Understanding the Output

When you run a goal, Dendrite shows its decision-making process:

```
🧠 Intent Classifier: tool_use (requires tool execution)
🎯 Domain Router: memory domain detected
📋 Tool Selection:
   Stage 1: Semantic search (19 tools → 3 candidates)
   Stage 2: Statistical ranking (3 → 2 top performers)
   Stage 3: LLM voting (2 → memory_write selected)
🔧 Parameter Extraction: {key: "favorite_color", value: "blue"}
💻 Code Generation: memory_write.execute(key="favorite_color", value="blue")
✅ Execution: Success
```

## Next Steps

### Explore More Examples

**Memory operations:**
```bash
python run_goal.py "Store my name as Alice"
python run_goal.py "What is my name?"
python run_goal.py "Remember that I like pizza"
```

**Generative queries:**
```bash
python run_goal.py "Explain Docker in simple terms"
python run_goal.py "What is the capital of France?"
```

**Calculations:**
```bash
python run_goal.py "Calculate 123 + 456"
python run_goal.py "What is 15% of 200?"
```

### Configure Strava (Optional)

If you want to use Strava tools:

1. Log into strava.com in your browser
2. Open developer tools (F12) → Network tab
3. Refresh page and find any request to strava.com
4. Copy the `Cookie` header and `X-CSRF-Token` value

Store credentials:
```python
from neural_engine.core.key_value_store import KeyValueStore
kv = KeyValueStore()
kv.set("strava_cookies", "your_cookie_string_here")
kv.set("strava_token", "your_csrf_token_here")
```

Test:
```bash
python run_goal.py "Show me my recent activities"
```

### Run the Test Suite

Verify everything works:
```bash
./scripts/test.sh
```

Expected: ~580/586 tests passing (98%+)

### Development Mode

For live code reloading:
```bash
./scripts/dev.sh
```

Access container shell:
```bash
./scripts/shell.sh
```

## Common Issues

### "Ollama not responding"

**Cause:** Ollama service not fully started

**Solution:**
```bash
# Check status
docker compose ps

# View logs
docker compose logs ollama-cpu

# Restart if needed
docker compose restart ollama-cpu

# Wait for "server ready" message
```

### "Model not available"

**Cause:** Model not yet downloaded

**Solution:**
```bash
# Pull model manually
docker compose exec ollama-cpu ollama pull mistral

# Check available models
docker compose exec ollama-cpu ollama list
```

### "Redis connection refused"

**Cause:** Redis not started or networking issue

**Solution:**
```bash
# Test Redis
docker compose exec redis redis-cli ping
# Should return: PONG

# Restart if needed
docker compose restart redis
```

### "Permission denied" errors

**Cause:** File permissions or Docker socket access

**Solution:**
```bash
# Fix script permissions
chmod +x scripts/*.sh

# Add user to docker group (Linux)
sudo usermod -aG docker $USER
# Log out and back in
```

### GPU not detected (want to use GPU)

**Cause:** NVIDIA drivers or Docker configuration

**Solution:**
```bash
# Verify drivers
nvidia-smi

# Install NVIDIA Container Toolkit
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html

# Use GPU profile
docker compose --profile gpu up -d
```

## Configuration Options

### Change LLM Model

Edit `docker-compose.yml`:
```yaml
environment:
  OLLAMA_MODEL: llama3.1:8b  # or mistral, llama3.2:3b, etc.
```

Pull the new model:
```bash
docker compose exec ollama-cpu ollama pull llama3.1:8b
```

### Adjust Memory Limits

For smaller models or limited RAM:
```yaml
services:
  ollama-cpu:
    deploy:
      resources:
        limits:
          memory: 6G  # Reduce from default
```

### Change Ports

If port 11434 is in use:
```yaml
services:
  ollama-cpu:
    ports:
      - "11435:11434"  # Use different host port
```

Update environment variables accordingly.

## Understanding the Architecture

Dendrite uses a multi-stage process:

1. **Intent Classification** - Determines if goal needs tools or is conversational
2. **Domain Routing** - Detects specialized domains (memory, Strava, calculator)
3. **Tool Discovery** - Semantic search finds relevant tools (if many tools available)
4. **Tool Selection** - LLM voting picks the best tool from candidates
5. **Parameter Extraction** - Extracts required parameters from goal
6. **Code Generation** - Generates Python code to execute the tool
7. **Sandbox Execution** - Runs code in isolated environment
8. **Result Validation** - Checks if goal was achieved

Each stage can use caching to speed up repeated similar goals.

## Learning Resources

- **[Architecture](ARCHITECTURE.md)** - Deep dive into system design
- **[Testing](TESTING.md)** - How tests are organized
- **[Development Plan](DEVELOPMENT_PLAN.md)** - Roadmap and features
- **[Debugging](DEBUGGING.md)** - Troubleshooting guide

## Getting Help

1. Check the [Debugging Guide](DEBUGGING.md)
2. Search existing [GitHub Issues](https://github.com/gradrix/dendrite/issues)
3. Review logs: `docker compose logs`
4. Open a new issue with:
   - Your Docker/OS version
   - Profile used (CPU/GPU)
   - Full error message
   - Steps to reproduce

## Next: Building Your First Tool

See [Development Plan](DEVELOPMENT_PLAN.md) for creating custom tools and extending Dendrite.
