# AI Agent for Strava Monitoring

An autonomous AI agent that periodically monitors Strava activities and takes actions based on instructions. Uses Ollama LLM (Llama 3.1) for intelligent decision-making with function calling.

## 🎯 Features

- **Autonomous Operation**: Runs on a schedule (hourly, daily, etc.)
- **LLM-Powered Decisions**: Uses Ollama with function calling for intelligent actions
- **Extensible Tool System**: Easy to add new tools with decorator-based interface
- **Safe Execution**: Permission system, dry-run mode, action approval
- **State Management**: SQLite database tracks all decisions and actions
- **Strava Integration**: Monitor activities, give kudos, post comments
- **Docker-Ready**: Runs in containers with no host dependencies

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Agent System                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Main Loop (main.py)                                   │ │
│  │  - APScheduler for periodic execution                  │ │
│  │  - Loads instructions & queries LLM                    │ │
│  │  - Executes approved actions                           │ │
│  └────────┬──────────────────────────┬──────────────────┘ │
│           │                           │                     │
│  ┌────────▼─────────┐      ┌─────────▼──────────┐        │
│  │ Ollama Client    │      │ Tool Registry       │        │
│  │ - Function calls │      │ - Auto-discovery    │        │
│  │ - JSON parsing   │      │ - Dynamic execution │        │
│  └──────────────────┘      └─────────┬───────────┘        │
│                                       │                     │
│  ┌────────────────────────────────────▼──────────────────┐ │
│  │  Tools (tools/)                                       │ │
│  │  - strava_tools.py: Strava API integration           │ │
│  │  - (easily add more tools)                           │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Data                                                 │ │
│  │  - instructions/: Task definitions (YAML)            │ │
│  │  - state/: SQLite database (history, decisions)      │ │
│  │  - logs/: Application logs                           │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Ollama running (automatically handled by setup script)
- (Optional) Strava session cookies for API access

### Installation

1. **Clone and setup**:
   ```bash
   cd /path/to/center
   
   # Create .env if needed
   cp .env.example .env
   ```

2. **Start Ollama** (if not already running):
   ```bash
   ./setup-ollama.sh
   ```

3. **Test the setup**:
   ```bash
   ./test-agent.sh
   ```

4. **Run the agent**:
   ```bash
   # Run once (test mode)
   ./start-agent.sh --once
   
   # Run specific instruction
   ./start-agent.sh --instruction "Strava Activity Monitor"
   
   # Start scheduler (continuous operation)
   ./start-agent.sh
   ```

## 📝 Configuration

### Main Config (`config.yaml`)

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: "llama3.1:8b"
  temperature: 0.7

agent:
  check_interval_minutes: 60  # Hourly
  enabled: true
  dry_run: false  # Set true to simulate actions

safety:
  require_approval_for_writes: false
  max_actions_per_run: 10
  action_cooldown_seconds: 5
```

### Instructions (`instructions/*.yaml`)

Instructions define what the agent should do:

```yaml
name: "Strava Activity Monitor"
schedule: "hourly"  # or "daily", "manual"
enabled: true

context: |
  Monitor Strava activities and celebrate achievements.

tools_allowed:
  - getMyLastDayActivities
  - getFriendFeed
  - giveKudos
  - postComment

decision_rules:
  kudos:
    - "Give kudos to activities > 15km"
    - "Give kudos to new PRs"
  comments:
    - "Congratulate on activities > 20km"
    - "Keep comments genuine"

permissions:
  allow_kudos: true
  allow_comments: false  # Requires approval
  max_actions_per_run: 5
```

## 🔧 Adding New Tools

Tools are Python functions decorated with `@tool`:

```python
from agent.tool_registry import tool

@tool(
    name="myCustomTool",
    description="What this tool does",
    parameters=[
        {"name": "param1", "type": "str", "required": True}
    ],
    returns="Description of return value",
    permissions="read"  # or "write"
)
def my_custom_tool(param1: str) -> dict:
    """Implementation here."""
    result = do_something(param1)
    return {"success": True, "data": result}
```

Save to `tools/my_tools.py` and the agent will auto-discover it!

## 🔐 Strava Authentication

### Method 1: Session Cookies (Easier)

1. Login to Strava in your browser
2. Open Developer Tools → Application/Storage → Cookies
3. Copy cookies to `.strava_cookies`:

```json
[
  {
    "name": "_strava4_session",
    "value": "your_session_value_here",
    "domain": ".strava.com"
  }
]
```

### Method 2: OAuth (Future)

Coming soon - proper OAuth flow.

## 🐳 Docker Usage

### Using Docker Compose

```bash
# Start all services (Ollama + Agent)
docker-compose up -d

# View logs
docker-compose logs -f agent

# Stop
docker-compose down
```

### Manual Docker

```bash
# Build agent image
docker build -f Dockerfile.agent -t ai-agent .

# Run once
docker run --rm \
  --network ollama-network \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/logs:/app/logs \
  ai-agent python main.py --once

# Run scheduler
docker run -d \
  --name ai-agent \
  --network ollama-network \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  ai-agent
```

## 📊 Monitoring

### View Logs

```bash
# Real-time logs
tail -f logs/agent.log

# Docker logs
docker logs -f ai-agent
```

### Query State Database

```bash
sqlite3 state/agent_state.db

# Recent executions
SELECT * FROM executions ORDER BY timestamp DESC LIMIT 10;

# Actions taken
SELECT * FROM actions ORDER BY timestamp DESC LIMIT 20;

# LLM decisions
SELECT reasoning, confidence FROM decisions ORDER BY timestamp DESC;
```

## 🧪 Testing

### Run Unit Tests

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=agent --cov=tools
```

### Test Individual Components

```python
# Test Ollama client
python -c "from agent.ollama_client import OllamaClient; \
           c = OllamaClient(); print(c.health_check())"

# Test tool discovery
python -c "from agent.tool_registry import get_registry; \
           r = get_registry(); print(r.discover_tools('tools'))"

# Test instruction loading
python -c "from agent.instruction_loader import InstructionLoader; \
           l = InstructionLoader(); print(len(l.load_all()))"
```

## 🔒 Security Considerations

### Permission System

- **Read tools**: Can query data, no modifications
- **Write tools**: Can take actions (kudos, comments, etc.)
- Instruction files control which tools are allowed
- Optional human-in-the-loop approval for sensitive actions

### Safety Features

1. **Dry Run Mode**: Test without executing actions
   ```yaml
   # config.yaml
   agent:
     dry_run: true
   ```

2. **Action Limits**: Max actions per run
   ```yaml
   safety:
     max_actions_per_run: 10
   ```

3. **Approval System**: Require approval for specific actions
   ```yaml
   requires_approval:
     - "Any comment on activities"
     - "More than 3 kudos in a single run"
   ```

4. **Rate Limiting**: Built-in cooldowns between actions

### Data Privacy

- State database stores decision history locally
- Strava cookies stored in gitignored file
- No data sent externally except to configured services

## 🛠️ Troubleshooting

### Agent won't start

```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Check Docker
docker ps

# View logs
cat logs/agent.log
```

### No actions being taken

1. Check if instruction is enabled
2. Verify tools are allowed in instruction
3. Check permissions settings
4. Review LLM decisions in logs or database

### LLM returning invalid JSON

- Lower temperature in config.yaml (e.g., 0.3)
- Check Ollama model is downloaded
- Review system prompts in ollama_client.py

### Strava API errors

- Verify `.strava_cookies` file exists and is valid
- Check cookie hasn't expired
- Verify rate limits aren't exceeded

## 📚 Examples

### Example 1: Monitor and Encourage

```yaml
name: "Fitness Encouragement"
schedule: "daily"

context: |
  Check if I've exercised today. If not, log a reminder.

decision_rules:
  - "Check getMyLastDayActivities"
  - "If no activities, create a reminder (don't spam)"
```

### Example 2: Social Engagement

```yaml
name: "Friend Engagement"
schedule: "hourly"

context: |
  Monitor friend activities and engage meaningfully.

decision_rules:
  kudos:
    - "Give kudos to impressive efforts (>20km, or PRs)"
    - "Don't duplicate kudos"
```

## 🔮 Future Enhancements

- [ ] Web UI for monitoring and control
- [ ] More tool integrations (GitHub, Email, etc.)
- [ ] MCP (Model Context Protocol) support
- [ ] Self-modification capabilities (AI generates new tools)
- [ ] Multi-LLM support (Claude, GPT-4, etc.)
- [ ] Webhook/notification system
- [ ] OAuth for Strava
- [ ] Metrics and analytics dashboard

## 📄 License

MIT

## 🤝 Contributing

Contributions welcome! Key areas:

- New tool integrations
- Better LLM prompting strategies
- Safety improvements
- Documentation

## 📞 Support

Issues and questions: Open a GitHub issue

---

**Made with ❤️ and AI**
