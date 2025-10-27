# Dendrite Scripts

This directory contains convenience scripts for managing the Dendrite Neural Engine.

## 🚀 Quick Start

```bash
# First time setup
./scripts/setup.sh

# Start the system
./scripts/start.sh

# Run a goal
./scripts/run.sh "How many running activities did I have in September?"

# Stop everything
./scripts/stop.sh
```

## 📋 Available Scripts

### Startup & Management

- **`start.sh`** - Start all services (Redis, Ollama, App)
  - Waits for services to be healthy
  - Automatically pulls required LLM models if missing
  - Shows status of each component

- **`stop.sh`** - Stop all services gracefully

- **`reset.sh`** - Reset everything (⚠️ deletes all data and volumes)

- **`dev.sh`** - Start in development mode
  - Hot-reload enabled (code changes reflected immediately)
  - Follows application logs

- **`run.sh`** - Execute a goal with the Neural Engine
  ```bash
  ./scripts/run.sh "your goal here"
  ```

### Testing

- **`test.sh`** - Run all tests in Docker (recommended)
  ```bash
  ./scripts/test.sh                    # All tests
  ./scripts/test.sh -k test_specific   # Specific test
  ./scripts/test.sh -v                 # Verbose
  ```

- **`test-debug.sh`** - Run tests with VS Code debugger attached
  ```bash
  ./scripts/test-debug.sh              # Start tests in debug mode
  # Then press F5 in VS Code and select "Python: Attach to Docker"
  # Set breakpoints and debug interactively!
  ```

- **`test-local.sh`** - Run tests locally (faster iteration)
  - Uses local Python environment
  - Still requires Docker for Redis/Ollama

- **`test-unit.sh`** - Run only unit tests (fast)

- **`test-integration.sh`** - Run only integration tests (it_*.py files)

- **`test-watch.sh`** - Watch mode for TDD
  - Automatically re-runs tests on file changes
  - Requires `pytest-watch` (auto-installed)

### Utilities

- **`setup.sh`** - One-time setup for new installations
  - Starts all services
  - Pulls required models
  - Verifies installation

- **`logs.sh`** - View logs from services
  ```bash
  ./scripts/logs.sh          # All services
  ./scripts/logs.sh app      # Just app logs
  ./scripts/logs.sh ollama   # Just Ollama logs
  ```

- **`shell.sh`** - Open shell in container for debugging
  ```bash
  ./scripts/shell.sh         # App container
  ./scripts/shell.sh redis   # Redis container
  ```

- **`health.sh`** - Check status of all services
  - Verifies Docker is running
  - Checks if services are up
  - Tests connectivity

## 🔧 Environment Variables

All scripts respect these environment variables (set in docker-compose.yml):

- `REDIS_HOST` - Redis hostname (default: `redis`)
- `OLLAMA_HOST` - Ollama API endpoint (default: `http://ollama:11434`)

## 📝 Examples

### Complete Workflow

```bash
# 1. Initial setup
./scripts/setup.sh

# 2. Check everything is healthy
./scripts/health.sh

# 3. Run some goals
./scripts/run.sh "List my recent activities"
./scripts/run.sh "How many kudos did I give this month?"

# 4. Make code changes and test
./scripts/test-watch.sh

# 5. Run full test suite
./scripts/test.sh

# 6. View logs if something goes wrong
./scripts/logs.sh app
```

### Development Workflow

```bash
# Start with dev mode (hot reload)
./scripts/dev.sh

# In another terminal, run tests in watch mode
./scripts/test-watch.sh

# Debug in container if needed
./scripts/shell.sh
```

### Testing Workflow

```bash
# Quick unit tests during development
./scripts/test-unit.sh

# Full integration tests before commit
./scripts/test-integration.sh

# All tests before push
./scripts/test.sh
```

## 🐛 Troubleshooting

### "Redis failed to start"
```bash
./scripts/reset.sh  # Nuclear option - deletes everything
./scripts/start.sh
```

### "Ollama failed to start"
Check Docker resources - Ollama needs ~4GB RAM for 8B models:
```bash
docker stats
```

### Tests are slow
Use local testing for faster iteration:
```bash
./scripts/test-local.sh
```

### "Model not found"
The start script auto-pulls `llama3.1:8b`. To use a different model:
```bash
docker compose exec ollama ollama pull mistral:7b
```

## 📦 Requirements

- Docker & Docker Compose
- ~10GB disk space (for models)
- ~4GB RAM minimum
- Bash shell (zsh compatible)

## 🎯 Tips

- Use `./scripts/health.sh` to diagnose issues
- Use `./scripts/logs.sh` to see what's happening
- Use `./scripts/test-watch.sh` for TDD workflow
- Use `./scripts/dev.sh` for development with live logs
