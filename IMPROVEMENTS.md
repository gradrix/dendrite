# Recent Improvements

## ✅ What's New

### 1. **Interactive Query Tool - `./query.py`**
Direct access to Strava tools without LLM overhead. Fast, reliable, perfect for testing.

```bash
# Get your recent activities
./query.py activities --limit 5

# Get kudos for a specific activity  
./query.py kudos 16229059176

# Get dashboard feed
./query.py feed --hours 24 --limit 10

# See who you follow
./query.py following --limit 20

# See your followers
./query.py followers --limit 20
```

**Example:**
```
👍 Fetching kudos for activity 16229059176...

✅ Found 8 kudos:
  1. Gediminas (ID: 118091520)
  2. Maksim (ID: 9364955)
  3. Justinas (ID: 178758614)
  ...
```

### 2. **LLM-Powered Assistant - `./ask.sh`** (Experimental)
Natural language queries using the LLM with access to all tools.

```bash
./ask.sh "What are my last 3 activities?"
./ask.sh "Who gave kudos to my activities today?"
./ask.sh "Show me activities from the feed"
```

**Note:** Currently has JSON parsing issues with llama3.2:3b. Works better with larger models.

### 3. **Auto Token Refresh**
Strava API tokens expire after 6 hours. The system now automatically refreshes them!

**Setup:**
1. Add to `.env`:
   ```bash
   STRAVA_CLIENT_ID=your_client_id
   STRAVA_CLIENT_SECRET=your_client_secret
   ```

2. Get tokens with refresh capability:
   ```bash
   ./get_token_manual.sh auth <CLIENT_ID>
   # Visit the URL, authorize, copy the code
   ./get_token_manual.sh token <CLIENT_ID> <CLIENT_SECRET> <CODE>
   ```

3. Tokens refresh automatically on 401 errors!

**How it works:**
- Detects 401 Unauthorized errors
- Uses `.strava_refresh_token` to get new access token
- Retries the request automatically
- Saves new tokens for future use

### 4. **Model Management Tool - `./manage-models.sh`**
Control Ollama models without entering Docker.

```bash
# See what's running
./manage-models.sh ps

# Load a model into memory
./manage-models.sh load llama3.2:3b

# Unload a specific model
./manage-models.sh unload llama3.2:3b

# Unload everything (free memory)
./manage-models.sh unload-all

# List available models
./manage-models.sh list
```

### 5. **Enhanced Activity Updates**
The `updateActivity` tool now supports:
- **3D Maps**: `selected_polyline_style="fatmap_satellite_3d"`
- **Visibility**: `visibility="everyone"` / `"only_me"` / `"followers_only"`
- **Partial updates**: Only send the fields you want to change!

```python
# Just change map to 3D
update_activity(activity_id=123, selected_polyline_style="fatmap_satellite_3d")

# Just make it public
update_activity(activity_id=123, visibility="everyone")

# Both at once
update_activity(
    activity_id=123,
    visibility="everyone",
    selected_polyline_style="fatmap_satellite_3d"
)
```

### 6. **Kudos Tracking**
New `getActivityKudos` tool retrieves the list of athletes who gave kudos to your activities.

```bash
./query.py kudos 16229059176
```

Returns full athlete details:
- Name
- Athlete ID  
- Username

### 7. **Multi-Step Agent Execution**
The agent now runs in a loop until completion (max 10 iterations):
- Executes workflow steps sequentially
- Passes results between iterations
- Provides detailed logging at each step
- Stops when LLM returns empty actions

### 8. **Better Logging**
Action executor now shows meaningful summaries:
- `getActivityKudos` → Shows count and athlete names
- `getMyActivities` → Shows activity list with kudos counts
- `getDashboardFeed` → Shows kudos statistics
- All tools log their results clearly

Instructions updated to require detailed reasoning from LLM:
- Emoji-based status (✅ ⏭️  📊 📝)
- Activity analysis with visibility decisions
- Summary counts logged

## 🔧 Configuration

### Required Files:
- `.strava_cookies` - Session cookies (for web API)
- `.strava_token` - Access token (for API v3)
- `.strava_refresh_token` - Refresh token (for auto-renewal)

### Environment Variables (Optional):
- `STRAVA_CLIENT_ID` - For token refresh
- `STRAVA_CLIENT_SECRET` - For token refresh

### Docker Volumes Updated:
```yaml
volumes:
  - ./.strava_cookies:/app/.strava_cookies:ro
  - ./.strava_token:/app/.strava_token:ro  # ← NEW
```

## 📝 Workflow Updates

The `strava_monitor.yaml` instruction now includes:
1. Get timestamps
2. Check last feed time  
3. Get recent activities
4. **Analyze with detailed logging** (NEW)
5. **Update visibility + 3D maps** (NEW)
6. **Track kudos givers** (NEW)
7. Save state

## 🎯 Recommended Usage

### For Quick Queries:
Use `./query.py` - it's fast and reliable!

### For Testing Agent Logic:
Use `./start-agent.sh --once` to run the full workflow once.

### For Natural Language:
Use `./ask.sh` (experimental, better with larger models)

### For Model Management:
Use `./manage-models.sh` to control memory usage.

## 🚀 Next Steps

1. **Set up token refresh** (optional but recommended):
   - Add client credentials to `.env`
   - Tokens will refresh automatically

2. **Test the query tool**:
   ```bash
   ./query.py activities --limit 3
   ```

3. **Try the agent**:
   ```bash
   ./start-agent.sh --once
   ```

4. **Check the logs** for detailed activity analysis:
   ```bash
   tail -f logs/agent.log
   ```
