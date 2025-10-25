# Dendrite Usage Guide

Advanced usage patterns and best practices.

## Running Goals

### Basic Execution

```bash
# One-time execution with natural language
./start-agent.sh --goal "How many running activities this month?"

# Using predefined instruction files
./start-agent.sh --once --instruction test_count_runs

# Continuous monitoring mode
./start-agent.sh --instruction strava_monitor_micro
```

### Creating Instruction Files

Instruction files are YAML files in `instructions/`:

```yaml
# instructions/my_task.yaml
goal: "Get my last 10 activities and count how many had kudos"
description: "Demonstrates multi-step API + Python analysis"
```

Run it:
```bash
./start-agent.sh --once --instruction my_task
```

### Example Instructions

Check `instructions/` for examples:

- `test_count_runs.yaml` - Count running activities in date range
- `test_kudos_accumulation.yaml` - Accumulate kudos data with details
- `test_timeseries_kudos.yaml` - Time-series kudos analysis
- `strava_monitor_micro.yaml` - Continuous activity monitoring

## Monitoring Execution

### View Logs

```bash
# Real-time logs with tree visualization
./scripts/logs.sh

# Or directly
docker logs -f dendrite-agent
```

Example output:
```
🎯 Goal: "How many running activities in September?"

├─ Decompose
├─ Generated 3 neurons
│  1. Convert dates to timestamps
│  2. Fetch activities in range
│  3. Count running activities

├─ Neuron 1
│  ├─ Pre-execution spawning (2 sub-tasks)
│  │  ├─ Dendrite 1: Sept 1 → 1756684800 ✅
│  │  └─ Dendrite 2: Sept 30 → 1759190400 ✅
│  └─ ✅ Complete

├─ Neuron 2
│  ├─ Tool: getMyActivities
│  ├─ Result: 63 activities → Saved to disk (136KB)
│  └─ ✅ Complete

├─ Neuron 3
│  ├─ Tool: executeDataAnalysis
│  ├─ Python: Load data + count runs
│  ├─ Result: 28
│  └─ ✅ Complete

└─ Final: "28 activities"
Duration: 12.09s
Status: ✅ Success
```

### Check Agent State

```bash
# List saved state keys
./scripts/state.sh

# View cached data files
ls -lh state/data_cache/

# Inspect specific cache file
cat state/data_cache/neuron_0_2_abc123.json | jq
```

### Monitor Resources

```bash
# Container resource usage
docker stats ollama dendrite-agent

# Check disk usage
du -sh state/data_cache/
```

## Advanced Patterns

### Multi-Step Goals

The agent automatically breaks down complex goals:

```bash
./start-agent.sh --goal "Get my September activities, count runs, and tell me average distance"
```

Execution:
```
Neuron 1: Convert "September" to timestamps
Neuron 2: Fetch activities
Neuron 3: Filter running activities
Neuron 4: Calculate average distance
Neuron 5: Format result
```

### Accumulating Data Over Time

Goals can reference previously saved state:

```bash
# First run: Get recent kudos
./start-agent.sh --goal "Get kudos from last 24 hours"

# Later run: Agent can reference previous data
./start-agent.sh --goal "Compare today's kudos to yesterday"
```

The Memory Overseer automatically loads relevant saved state.

### Iterative Analysis

Use Python analysis for complex queries:

```bash
./start-agent.sh --goal "Show me which day of the week I get the most kudos"
```

The agent will:
1. Fetch activities with kudos
2. Use `executeDataAnalysis` to process data
3. Group by day of week
4. Return formatted answer

## Working with Strava Data

### Activity Queries

```bash
# Count activities
"How many activities this month?"
"How many runs in September?"

# Filter by type
"Show my cycling activities from last week"
"Count my walks this year"

# Date ranges
"Activities between Sept 1 and Sept 30"
"Last 7 days of activities"
```

### Kudos Analysis

```bash
# Simple counts
"How many kudos did I get today?"
"Total kudos this month"

# Detailed analysis
"Who gave me kudos this week?"
"Which activity got the most kudos?"
"Show kudos over time"
```

### Performance Metrics

```bash
# Distance/pace
"What's my average running distance this month?"
"Fastest run in September"

# Time analysis
"Total hours of activity this week"
"Average moving time per run"
```

## Extending Dendrite

### Adding New Tools

1. **Create the tool function:**

```python
# tools/github_tools.py
def get_repo_issues(owner: str, repo: str, state: str = "open") -> dict:
    """
    Get issues from a GitHub repository.
    
    Args:
        owner: Repository owner
        repo: Repository name
        state: Issue state (open, closed, all)
    
    Returns:
        dict with success flag and issues list
    """
    import requests
    
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {'state': state}
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return {
            'success': True,
            'issues': response.json(),
            'count': len(response.json())
        }
    else:
        return {
            'success': False,
            'error': f"API error: {response.status_code}"
        }
```

2. **Register the tool:**

```python
# agent/tool_registry.py
from tools.github_tools import get_repo_issues

def create_registry():
    registry = ToolRegistry()
    
    # ... existing tools ...
    
    # Add GitHub tool
    registry.register_tool(
        name="getRepoIssues",
        func=get_repo_issues,
        description="Get issues from a GitHub repository"
    )
    
    return registry
```

3. **Use it naturally:**

```bash
./start-agent.sh --goal "How many open issues in owner/repo?"
```

The agent will automatically:
- Discover the `getRepoIssues` tool
- Extract parameters from your goal
- Call the API
- Return formatted results

### Adding Custom Analysis

Create Python analysis functions for domain-specific logic:

```python
# tools/analysis_tools.py

def analyze_workout_trends(activities: list) -> dict:
    """
    Analyze workout trends over time.
    
    Available in executeDataAnalysis as analyze_workout_trends()
    """
    # Your analysis logic
    return {'trend': 'increasing', 'confidence': 0.85}
```

Then use in goals:
```bash
./start-agent.sh --goal "Analyze my workout trends"
```

## Authentication Management

### Token Refresh (API Token)

The API token (`.strava_token`) expires after 6 hours.

**Manual refresh:**
```bash
./scripts/refresh_token.sh
```

**Automatic refresh:**
The agent automatically refreshes when:
- API returns 401 Unauthorized
- Token expires_at timestamp is reached
- Before long-running tasks

Token file format (`.strava_token`):
```json
{
  "access_token": "your_access_token",
  "refresh_token": "your_refresh_token",
  "expires_at": 1698765432
}
```

### Cookie Refresh (Session Cookies)

Session cookies (`.strava_cookies`) expire when you log out of Strava.

**Symptoms of expired cookies:**
- `getDashboardFeed` returns empty or errors
- `getActivityKudos` fails with 401/403
- `updateActivity` fails

**Solution:** Re-export cookies from browser (see [SETUP.md](SETUP.md))

### Authentication Troubleshooting

**"No activities found" but you have activities:**
- Check `.strava_token` exists and is valid
- Try: `./scripts/refresh_token.sh`

**"No kudos found" but activity has kudos:**
- Check `.strava_cookies` exists
- Re-export cookies from browser (they may have expired)

**Both files required for most queries!**
- "Get my activities with kudos" needs BOTH token (activities) and cookies (kudos)

## Best Practices

### 1. Be Specific with Goals

❌ **Vague:**
```
"Get my activities"
```

✅ **Specific:**
```
"Get my running activities from September 2025"
```

### 2. Use Natural Language

The agent understands conversational goals:

```bash
"How many times did I run this month?"
"Show me yesterday's activities"
"Count cycling rides in the last week"
```

### 3. Let the Agent Decompose

Don't over-specify steps:

❌ **Over-specified:**
```
"First convert September to timestamps, then fetch activities, then count runs"
```

✅ **Natural:**
```
"How many runs in September?"
```

The agent figures out the steps automatically.

### 4. Check Logs for Understanding

If results seem wrong, check the logs to see:
- How the goal was decomposed
- What parameters were extracted
- What data was processed

```bash
./scripts/logs.sh
```

### 5. Save Important State

For data you'll reference later:

```bash
# The agent can save results
./start-agent.sh --goal "Get September activities and save them"

# Later reference
./start-agent.sh --goal "Compare October to saved September data"
```

## Troubleshooting

### Goal Not Completing

**Symptom:** Agent executes but result seems incomplete

**Solution:**
1. Check logs for validation warnings
2. Look for "⚠️ Goal may not be fully complete"
3. See what corrective neuron was attempted
4. Try rephrasing the goal more specifically

### Wrong Data Returned

**Symptom:** Agent returns data but not what you wanted

**Debugging:**
1. Check parameter extraction in logs
2. Verify date conversions (timestamps)
3. Check which context keys were used
4. Look for "hallucinated" parameter warnings

### Tool Not Found

**Symptom:** "No tool found" or uses AI fallback

**Solution:**
1. Check if tool is registered in `tool_registry.py`
2. Verify tool description matches goal intent
3. Try rephrasing goal to match tool capabilities

### Performance Issues

**Symptom:** Execution takes too long

**Optimization:**
1. Use smaller model for simple queries:
   ```bash
   # Edit .env
   DEFAULT_MODEL=llama3.2:3b
   ```
2. Check if unnecessary dendrites are spawning (logs)
3. Verify data compaction is working (large results → disk)
4. Consider GPU acceleration

## Examples Collection

### Simple Counts

```bash
./start-agent.sh --goal "How many activities this week?"
./start-agent.sh --goal "Count my runs in October"
./start-agent.sh --goal "How many kudos today?"
```

### Date Range Queries

```bash
./start-agent.sh --goal "Activities between Sept 1 and Sept 30"
./start-agent.sh --goal "Last 7 days of running"
./start-agent.sh --goal "This month's cycling activities"
```

### Analysis Queries

```bash
./start-agent.sh --goal "What's my average run distance this month?"
./start-agent.sh --goal "Which activity got the most kudos?"
./start-agent.sh --goal "Show kudos per day this week"
```

### Multi-Step Queries

```bash
./start-agent.sh --goal "Get September runs and calculate average pace"
./start-agent.sh --goal "Find my longest ride and show who gave kudos"
./start-agent.sh --goal "Compare this month's activity count to last month"
```

## Configuration Reference

### Environment Variables (.env)

```bash
# Container Settings
OLLAMA_CONTAINER_NAME=ollama
OLLAMA_PORT=11434

# Model Configuration
DEFAULT_MODEL=llama3.1:8b

# GPU Support
USE_GPU=auto  # auto, true, false

# Agent Settings
MAX_RETRIES=3
MAX_DEPTH=5
```

### Agent Configuration

Edit `config.yaml` for advanced settings:

```yaml
agent:
  max_depth: 5              # Maximum neuron recursion depth
  max_retries: 3            # Retries per neuron
  data_cache_threshold: 5   # KB threshold for disk caching
  
ollama:
  model: llama3.1:8b
  temperature: 0.7
  
logging:
  level: INFO
  show_tree: true          # Show execution tree
```

## API Reference

For direct API access (advanced):

```bash
# Ollama API endpoint
curl http://localhost:11434/api/generate \
  -d '{"model": "llama3.1:8b", "prompt": "Hello"}'
```

Most users won't need this - the agent handles LLM communication automatically.

For more details on the underlying Ollama API:
https://github.com/ollama/ollama/blob/main/docs/api.md
