# Scripts Directory# Dendrite Scripts



Utility scripts for development, testing, and Docker operations.This directory contains convenience scripts for managing the Dendrite Neural Engine.



## Organization## 🚀 Quick Start



- **docker/** - Docker container management scripts```bash

- **testing/** - Test execution scripts  # First time setup

- **demos/** - Demo and example scripts./scripts/setup.sh

- **db/** - Database initialization files

- **utils/** - General utilities (logs, migration, etc.)# Start the system

- **run.sh** - Main goal execution script (kept at root for convenience)./scripts/start.sh



## Docker Operations (`docker/`)# Run a goal

./scripts/run.sh "How many running activities did I have in September?"

- `start.sh` - Start all services

- `stop.sh` - Stop all services# Stop everything

- `dev.sh` - Development mode with code reloading./scripts/stop.sh

- `shell.sh` - Access container shell```

- `reset.sh` - Clear volumes and restart

- `setup.sh` - Initial setup## 📋 Available Scripts

- `health.sh` - Check service health

### Startup & Management

## Testing (`testing/`)

- **`start.sh`** - Start all services (Redis, Ollama, App)

- `test.sh` - Run complete test suite  - Waits for services to be healthy

- `test-unit.sh` - Unit tests only  - Automatically pulls required LLM models if missing

- `test-integration.sh` - Integration tests  - Shows status of each component

- `test-watch.sh` - Watch mode

- `test-debug.sh` - Debug mode- **`stop.sh`** - Stop all services gracefully

- `test-local.sh` - Run locally (no Docker)

- **`reset.sh`** - Reset everything (⚠️ deletes all data and volumes)

## Demos (`demos/`)

- **`dev.sh`** - Start in development mode

Python scripts demonstrating features:  - Hot-reload enabled (code changes reflected immediately)

- Phase 8b/c/d demos  - Follows application logs

- Phase 9a/b/c demos  

- Stage 3 integration demo- **`run.sh`** - Execute a goal with the Neural Engine

  ```bash

## Database (`db/`)  ./scripts/run.sh "your goal here"

  ```

- `init_db.sql` - Schema initialization

- `init_extensions.sql` - PostgreSQL extensions### Testing



## Utilities (`utils/`)- **`test.sh`** - Run all tests in Docker (recommended)

  ```bash

- `logs.sh` - View service logs  ./scripts/test.sh                    # All tests

- `migrate.sh` - Run migrations  ./scripts/test.sh -k test_specific   # Specific test

- `help.sh` - Show help  ./scripts/test.sh -v                 # Verbose

- `warm_cache.py` - Pre-populate cache  ```



## Quick Start- **`test-debug.sh`** - Run tests with VS Code debugger attached

  ```bash

```bash  ./scripts/test-debug.sh              # Start tests in debug mode

# Setup (first time)  # Then press F5 in VS Code and select "Python: Attach to Docker"

./scripts/docker/setup.sh  # Set breakpoints and debug interactively!

  ```

# Start services

./scripts/docker/start.sh- **`test-local.sh`** - Run tests locally (faster iteration)

  - Uses local Python environment

# Run a goal  - Still requires Docker for Redis/Ollama

./scripts/run.sh "Remember my name is Alice"

- **`test-unit.sh`** - Run only unit tests (fast)

# Run tests

./scripts/testing/test.sh- **`test-integration.sh`** - Run only integration tests (it_*.py files)



# Stop services- **`test-watch.sh`** - Watch mode for TDD

./scripts/docker/stop.sh  - Automatically re-runs tests on file changes

```  - Requires `pytest-watch` (auto-installed)



## Docker Profiles### Utilities



**CPU (no GPU):**- **`setup.sh`** - One-time setup for new installations

```bash  - Starts all services

docker compose --profile cpu up -d  - Pulls required models

```  - Verifies installation



**GPU (NVIDIA):**- **`logs.sh`** - View logs from services

```bash  ```bash

docker compose --profile gpu up -d  ./scripts/logs.sh          # All services

```  ./scripts/logs.sh app      # Just app logs

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
