# 🎉 AI Agent Project - Complete!

## What We Built

A fully autonomous AI agent system that runs in Docker containers and uses Ollama LLM to make intelligent decisions about Strava activities.

## 📦 Complete File Structure

```
center/
├── agent/                          # Core agent code
│   ├── __init__.py
│   ├── ollama_client.py           # LLM integration with function calling
│   ├── tool_registry.py           # Dynamic tool discovery & execution
│   ├── instruction_loader.py      # YAML instruction parser
│   ├── state_manager.py           # SQLite state persistence
│   └── action_executor.py         # Safe action execution with permissions
│
├── tools/                          # Extensible tools
│   ├── __init__.py
│   └── strava_tools.py            # 5 Strava API tools (read & write)
│
├── instructions/                   # AI task definitions
│   └── strava_monitor.yaml        # Example: hourly Strava monitoring
│
├── tests/                          # Unit tests
│   └── test_ollama_client.py      # LLM function calling tests
│
├── state/                          # Persistent data (created at runtime)
│   └── agent_state.db             # SQLite database
│
├── logs/                           # Application logs
│   └── agent.log                  # Detailed execution logs
│
├── main.py                         # 🚀 Main entry point
├── config.yaml                     # Main configuration
├── requirements.txt                # Python dependencies
├── .env.example                    # Configuration template
├── .env                            # Active config (gitignored)
│
├── Dockerfile.agent                # Agent container image
├── docker-compose.yml              # Full system orchestration
│
├── start-agent.sh                  # 🎯 Startup script (USE THIS!)
├── test-agent.sh                   # Quick validation script
├── setup-ollama.sh                 # Ollama setup (already exists)
├── stop-ollama.sh                  # Stop Ollama
├── test-ollama.sh                  # Test Ollama
├── list-models.sh                  # List LLM models
│
├── AI_AGENT_README.md              # Complete agent documentation
├── README.md                       # Ollama documentation
└── .gitignore                      # Git ignore rules
```

## 🎯 How to Start the Agent

### Option 1: Quick Test (Recommended First)

```bash
# 1. Ensure Ollama is running
./setup-ollama.sh

# 2. Test the setup
./test-agent.sh

# 3. Run agent once (dry-run mode by default)
./start-agent.sh --once
```

### Option 2: Run in Docker (Production)

```bash
# Start everything (Ollama + Agent)
./start-agent.sh

# This will:
# - Start Ollama if needed
# - Build agent Docker image
# - Start scheduler for continuous operation
```

### Option 3: Manual Control

```bash
# Run specific instruction
./start-agent.sh --instruction "Strava Activity Monitor"

# Run once and exit
./start-agent.sh --once
```

## 🔑 Key Features Implemented

### 1. **LLM Function Calling** ✅
- Ollama client with structured output (JSON)
- Parses tool calls from LLM responses
- Handles markdown code blocks and malformed JSON
- Retry logic and error handling

### 2. **Dynamic Tool System** ✅
- Decorator-based tool registration (`@tool`)
- Auto-discovery from `tools/` directory
- Schema generation for LLM consumption
- Permission system (read/write)
- MCP-compatible design

### 3. **Strava Integration** ✅
- 5 working tools:
  - `getMyLastDayActivities` - Get recent activities
  - `getFriendFeed` - Get friend activities
  - `giveKudos` - Like an activity
  - `postComment` - Comment on activity
  - `getMyProfile` - Get athlete info
- Cookie-based authentication
- Rate limiting
- Error handling

### 4. **Instruction System** ✅
- YAML-based task definitions
- Scheduling (hourly, daily, manual)
- Tool permissions
- Decision rules for AI
- Approval requirements

### 5. **Safety & Permissions** ✅
- Dry-run mode (test without executing)
- Action limits per run
- Cooldown between actions
- Permission checking (read/write)
- Optional approval system
- Comprehensive logging

### 6. **State Management** ✅
- SQLite database
- Execution history
- LLM decision tracking
- Action results logging
- Key-value state store
- Data retention policies

### 7. **Main Agent Loop** ✅
- APScheduler for periodic execution
- Multiple schedule types (hourly, daily)
- Graceful shutdown (Ctrl+C)
- Error recovery
- Context building from history
- Configurable via YAML

### 8. **Docker Integration** ✅
- Dedicated agent Dockerfile
- Docker Compose orchestration
- Volume mounts for persistence
- Network integration with Ollama
- Health checks
- Auto-restart policies

### 9. **Startup Scripts** ✅
- `start-agent.sh` - Main entry point
- `test-agent.sh` - Validation script
- Multiple modes (once, scheduler, specific instruction)
- Error checking and user-friendly output
- Automatic Ollama startup

### 10. **Testing** ✅
- Unit tests for Ollama client
- Mock LLM responses
- Function calling scenarios
- JSON parsing edge cases
- pytest-based test suite

## 📖 Usage Examples

### Run Agent Once (Test Mode)

```bash
./start-agent.sh --once
```

This will:
1. Load all enabled instructions
2. Query LLM for each instruction
3. Execute approved actions (or dry-run)
4. Exit

### Start Scheduler (Production)

```bash
./start-agent.sh
```

This will:
1. Start agent container
2. Run instructions on their schedules (hourly/daily)
3. Keep running until stopped (Ctrl+C)
4. Auto-restart on failures

### Run Specific Instruction

```bash
./start-agent.sh --instruction "Strava Activity Monitor"
```

### View Logs

```bash
# Real-time logs
docker logs -f ai-agent

# Or from file
tail -f logs/agent.log
```

### Query State

```bash
sqlite3 state/agent_state.db "SELECT * FROM executions ORDER BY timestamp DESC LIMIT 10;"
```

## 🔧 Configuration

### Enable/Disable Dry Run

Edit `config.yaml`:

```yaml
agent:
  dry_run: false  # Set to true to simulate actions
```

### Change Schedule

Edit `instructions/strava_monitor.yaml`:

```yaml
schedule: "hourly"  # or "daily", "manual"
```

### Allow Write Actions

Edit instruction permissions:

```yaml
permissions:
  allow_kudos: true
  allow_comments: true  # Enable comments
```

## 🔐 Strava Setup (Required for Real Use)

Create `.strava_cookies` file:

```json
[
  {
    "name": "_strava4_session",
    "value": "YOUR_SESSION_VALUE",
    "domain": ".strava.com"
  }
]
```

Get this from your browser's Developer Tools → Application → Cookies after logging into Strava.

## 🧪 Testing Without Strava

You can test the agent without Strava cookies:

1. Set `dry_run: true` in `config.yaml`
2. Run `./start-agent.sh --once`
3. Agent will simulate all actions

## 🎓 How It Works

1. **Scheduler** wakes up (e.g., every hour)
2. **Instruction Loader** loads task definition
3. **Tool Registry** provides available tools to LLM
4. **Ollama Client** queries LLM with context + tools
5. **LLM** responds with JSON containing actions to take
6. **Action Executor** validates and executes actions
7. **State Manager** logs everything to database

## 🚀 Next Steps

### Immediate:
1. Run `./test-agent.sh` to validate setup
2. Configure Strava cookies if you want real API access
3. Run `./start-agent.sh --once` to test
4. Adjust instruction rules based on results
5. Enable production mode (`dry_run: false`)

### Future Enhancements:
- Add more tools (GitHub, email, weather, etc.)
- Create web UI for monitoring
- Implement MCP server
- Add self-modification capabilities
- Support multiple LLM backends

## 📚 Documentation

- **AI_AGENT_README.md** - Complete agent documentation
- **README.md** - Ollama setup documentation
- **config.yaml** - Inline comments
- **instructions/*.yaml** - Example instruction files

## 🎉 Success Criteria

- ✅ Agent starts without errors
- ✅ LLM makes intelligent decisions
- ✅ Tools are discovered and executable
- ✅ Actions are logged to database
- ✅ Runs on schedule automatically
- ✅ Safe with dry-run mode
- ✅ Dockerized for easy deployment

---

## 🏁 You're Ready!

Run this to get started:

```bash
# 1. Setup Ollama (if needed)
./setup-ollama.sh

# 2. Test everything
./test-agent.sh

# 3. Run agent once
./start-agent.sh --once

# 4. Start scheduler
./start-agent.sh
```

**Enjoy your autonomous AI agent! 🤖✨**
