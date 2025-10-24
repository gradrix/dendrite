# Quick Reference: Token & Query Commands

## 🔑 Token Management

### Refresh Token (Manual)
```bash
./refresh_token.sh
```
**Use when:** Token expired, before long tasks, testing

---

### Check Token Status
```bash
# View current token (first 20 chars)
head -c 20 .strava_token && echo "..."

# Check if valid
python3 -c "
from tools.strava_tools import get_my_activities
result = get_my_activities(per_page=1)
print('✅ Valid' if result.get('success') else '❌ Invalid')
"
```

---

### Automatic Refresh
**No action needed!** Happens automatically on API 401 errors.

**Requirements:**
- `.env` file with credentials ✓
- `.strava_refresh_token` file ✓
- Environment variables loaded ✓

---

## 🤖 AI Queries (ask.sh)

### Basic Usage
```bash
./ask.sh "your question here"
```

### Good Queries (Work with small model)
```bash
./ask.sh "List my last 5 activities"
./ask.sh "Show my followers"  
./ask.sh "Get dashboard feed from last 24 hours"
```

### Advanced Queries (Better with larger model)
```bash
# These work but may need llama3.1:8b
./ask.sh "Who gave kudos to my activities in last 24 hours?"
./ask.sh "Show activities that need to be public"
```

---

## 🐍 Direct Python Queries (Recommended for reliability)

### Get Activities
```python
from tools.strava_tools import get_my_activities

# Last 5 activities
result = get_my_activities(per_page=5)
for act in result['activities']:
    print(f"{act['name']} - {act['kudos_count']} kudos")
```

### Get Kudos for Activity
```python
from tools.strava_tools import get_activity_kudos

kudos = get_activity_kudos(activity_id=16229059176)
for athlete in kudos['athletes']:
    print(athlete['name'])
```

### Get Dashboard Feed
```python
from tools.strava_tools import get_dashboard_feed

feed = get_dashboard_feed(hours_ago=24, num_entries=20)
for entry in feed['activities']:
    print(f"{entry['athlete_name']}: {entry['activity_name']}")
```

---

## 🐳 Docker Commands

### Start Agent
```bash
./start-agent.sh          # Run scheduler (hourly)
./start-agent.sh --once   # Run once and exit
```

### View Logs
```bash
docker logs ai-agent -f
```

### Rebuild (after .env changes)
```bash
docker compose down
docker compose up -d --build agent
```

---

## 🔧 Environment Setup

### Check Environment Variables
```bash
source .env
echo "Client ID: $STRAVA_CLIENT_ID"
echo "Secret: ${STRAVA_CLIENT_SECRET:0:10}..."
```

### Load in Python
```python
from dotenv import load_dotenv
import os

load_dotenv()
print(os.environ.get('STRAVA_CLIENT_ID'))
```

---

## 📊 Common Workflows

### Morning Check: Get Recent Activity Kudos
```python
from tools.strava_tools import get_my_activities, get_activity_kudos

# Get yesterday's activities
activities = get_my_activities(per_page=10)

# Check kudos on each
for act in activities['activities'][:5]:
    kudos = get_activity_kudos(act['id'])
    if kudos['kudos_count'] > 0:
        print(f"\n{act['name']}:")
        for athlete in kudos['athletes']:
            print(f"  👍 {athlete['name']}")
```

### Update Activity Visibility
```python
from tools.strava_tools import update_activity

result = update_activity(
    activity_id=16229059176,
    visibility="everyone",
    selected_polyline_style="fatmap_satellite_3d"
)
print(result)
```

### Give Kudos to Friends
```python
from tools.strava_tools import get_dashboard_feed, give_kudos

# Get recent activities
feed = get_dashboard_feed(hours_ago=24)

# Give kudos to activities you haven't liked yet
for activity in feed['activities']:
    if not activity['you_gave_kudos'] and activity['can_give_kudos']:
        result = give_kudos(activity['activity_id'])
        print(f"Gave kudos to {activity['athlete_name']}")
```

---

## 🔍 Troubleshooting

### Token Expired
```bash
./refresh_token.sh
```

### "No module named dotenv"
```bash
pip3 install python-dotenv
# Or in project:
python3 -m pip install -r requirements.txt
```

### "401 Unauthorized" in Docker
Check environment variables are loaded:
```bash
docker exec ai-agent env | grep STRAVA
```

Should show:
```
STRAVA_CLIENT_ID=182379
STRAVA_CLIENT_SECRET=66b6a95f...
```

### ask.sh Not Working
1. Check Ollama is running: `./test-ollama.sh`
2. Try direct Python queries instead
3. Use larger model for complex queries

---

## 📁 Important Files

| File | Purpose | Git |
|------|---------|-----|
| `.env` | OAuth credentials | ❌ Ignored |
| `.strava_token` | Access token (6h) | ❌ Ignored |
| `.strava_refresh_token` | Refresh token | ❌ Ignored |
| `.strava_cookies` | Browser cookies | ❌ Ignored |
| `refresh_token.sh` | Manual refresh | ✅ Committed |
| `ask.sh` | AI queries | ✅ Committed |
| `TOKEN_REFRESH.md` | Full docs | ✅ Committed |

---

## 🎯 Quick Wins

**Want to...** | **Use this**
--- | ---
Refresh expired token | `./refresh_token.sh`
Get last 5 activities | `get_my_activities(per_page=5)`
Check who liked activity | `get_activity_kudos(activity_id)`
Ask AI a question | `./ask.sh "question"`
Run agent once | `./start-agent.sh --once`
Check logs | `docker logs ai-agent -f`
Update visibility | `update_activity(id, visibility="everyone")`

---

## 💡 Pro Tips

1. **Refresh token before long operations** - Get full 6 hours
2. **Use Python for reliability** - Faster and no LLM overhead
3. **Use ask.sh for exploration** - Good for discovering workflows
4. **Monitor logs** - Watch for auto-refresh events
5. **Export env vars** - When running scripts manually:
   ```bash
   export STRAVA_CLIENT_ID=182379
   export STRAVA_CLIENT_SECRET=66b6a95f19b2b2278004822e381004b693c55e69
   ```

---

**Last Updated:** October 24, 2025
**Token Status:** ✅ Valid until 14:42 UTC (6 hours)
**System Status:** ✅ All systems operational
