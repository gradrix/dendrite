# Dendrite

A self-contained AI neural engine with tool execution, scheduled goals, and 100% local LLM inference via llama.cpp.

## Features

- **Local LLM**: Built-in llama.cpp server (Mistral 7B) - no external APIs
- **Tool System**: Semantic tool discovery and execution (Strava, memory, calculator, etc.)
- **Scheduler**: Run goals on cron schedules or intervals
- **PostgreSQL Storage**: Persistent tool data and credentials
- **GPU Acceleration**: Auto-detects NVIDIA GPU for faster inference

## Quick Start

```bash
# Clone
git clone https://github.com/gradrix/dendrite.git
cd dendrite

# Start (auto-detects GPU)
./start.sh

# Run a single goal
./start.sh goal "What is 2+2?"

# Run scheduler daemon
./start.sh scheduler
```

## Commands

```bash
./start.sh              # Start services (auto-detect GPU)
./start.sh goal "..."   # Run single goal and exit
./start.sh scheduler    # Run scheduler daemon (uses goals.yaml)
./start.sh api          # Start HTTP API server
./start.sh stop         # Stop all services
./start.sh status       # Show service status
./start.sh logs         # Follow logs
./start.sh test         # Run tests
./start.sh help         # Show help
```

## Configuration

### Environment (.env)

```bash
# RAM profile for model selection (8gb, 16gb, 32gb)
RAM_PROFILE=32gb

# GPU VRAM (auto-detected if not set)
VRAM_GB=32

# Strava OAuth (optional)
STRAVA_CLIENT_ID=your_id
STRAVA_CLIENT_SECRET=your_secret
```

### Scheduled Goals (goals.yaml)

```yaml
goals:
  - id: collect_kudos
    goal: "Use strava_collect_kudos_givers with hours_back=48"
    schedule: cron
    cron: "0 */4 * * *"  # Every 4 hours
    enabled: true

  - id: reciprocate_kudos
    goal: "Use strava_reciprocate_kudos with count=30 and max_age_hours=24"
    schedule: cron
    cron: "0 */6 * * *"  # Every 6 hours
    enabled: true

settings:
  check_interval: 60
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Orchestrator                        │
│  Routes goals to appropriate neurons based on intent     │
└─────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌───────────┐    ┌───────────┐    ┌───────────┐
   │  Intent   │    │   Tool    │    │ Generative│
   │  Neuron   │    │  Neuron   │    │  Neuron   │
   └───────────┘    └───────────┘    └───────────┘
         │                 │                 │
         ▼                 ▼                 ▼
   ┌───────────┐    ┌───────────┐    ┌───────────┐
   │  LLM      │    │  Tool     │    │  LLM      │
   │  Client   │    │  Registry │    │  Client   │
   └───────────┘    └───────────┘    └───────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │   Tools (Strava, etc)   │
              │   PostgreSQL Storage    │
              └─────────────────────────┘
```

## Tools

### Built-in

- `calculator` - Math expressions
- `memory_write` / `memory_read` - Persistent key-value storage
- `current_datetime` - Current date/time

### Strava Integration

- `strava_get_activities` - Get your activities
- `strava_get_dashboard_feed` - Get friends' activities
- `strava_give_kudos` - Give kudos to an activity
- `strava_collect_kudos_givers` - Track who gives you kudos
- `strava_reciprocate_kudos` - Auto-kudos back to givers
- `strava_list_kudos_givers` - List known kudos givers

## Services

| Service | Port | Description |
|---------|------|-------------|
| llama-gpu | 8080 | llama.cpp server (Mistral 7B) |
| postgres | 5432 | PostgreSQL with pgvector |
| redis | 6379 | Message bus / caching |

## Development

```bash
# Run tests
./start.sh test

# Run specific tests
./start.sh test -k "test_strava"

# Access container shell
./scripts/docker/shell.sh
```

## Project Structure

```
├── main.py                 # Entry point
├── start.sh                # Main startup script
├── goals.yaml              # Scheduled goals config
├── docker-compose.yml      # Services definition
├── neural_engine/
│   └── v2/
│       ├── core/           # Config, LLM, Orchestrator
│       ├── neurons/        # Intent, Tool, Generative, Memory
│       ├── tools/          # Tool implementations
│       ├── scheduler/      # Goal scheduling
│       ├── forge/          # Dynamic tool creation
│       ├── cli.py          # Command-line interface
│       └── api.py          # HTTP API
└── scripts/
    ├── db/                 # Database migrations
    ├── docker/             # Docker helper scripts
    └── testing/            # Test runners
```

## License

MIT
