# Strava Integration Test

## Purpose

This test validates the complete AI agent → LLM → Strava API flow with real authentication.

## What It Tests

1. **Ollama Connection**: Verifies LLM is accessible
2. **Cookie Loading**: Validates Strava session cookie format
3. **Tool Discovery**: Registers all Strava tools
4. **LLM Function Calling**: Tests real LLM decision-making
5. **API Execution**: Makes actual Strava API calls
6. **Error Handling**: Detailed debugging for authentication issues

## Files

- `tests/test_strava_integration.py` - Main integration test (Python)
- `tests/run_strava_integration.sh` - Docker runner script (Bash)

## Quick Start

```bash
# Run the integration test
./tests/run_strava_integration.sh
```

Or directly with Docker:

```bash
docker compose run --rm agent python tests/test_strava_integration.py
```

## How to Get Valid Strava Cookies

The tool supports **two cookie formats** - choose whichever is easier for you!

### Format 1: JSON Array (Structured)

```json
[
  {
    "name": "_strava4_session",
    "value": "YOUR_SESSION_VALUE_HERE",
    "domain": ".strava.com"
  }
]
```

### Format 2: Raw Cookie String (Simple - Just Copy/Paste!)

```
_strava4_session=YOUR_SESSION_VALUE; other_cookie=value; yet_another=value
```

**This is the easiest!** Just copy the entire Cookie header from your browser and paste it directly into `.strava_cookies`.

---

### Method 1: Chrome DevTools - Copy Cookie Header (Easiest!)

1. Open Chrome and log into https://www.strava.com
2. Press **F12** to open DevTools
3. Go to the **Network** tab
4. Visit any Strava page (e.g., strava.com/dashboard)
5. Click any request to `strava.com`
6. Find **Request Headers** → **Cookie**
7. **Copy the entire Cookie value** (everything after `Cookie: `)
8. Paste directly into `.strava_cookies`:

```bash
# Just paste the raw cookie string!
echo "_strava4_session=xyz123abc456; CloudFront-Policy=value; CloudFront-Signature=value" > .strava_cookies
```

### Method 2: Chrome DevTools - Application Tab (Structured)

1. Open Chrome and log into https://www.strava.com
2. Press **F12** to open DevTools
3. Click the **Application** tab
4. In the left sidebar: **Storage** → **Cookies** → **https://www.strava.com**
5. Find the `_strava4_session` cookie
6. Copy the **Value** field (long random string)
7. Create `.strava_cookies` with JSON format:

```bash
cat > .strava_cookies << 'EOF'
[
  {
    "name": "_strava4_session",
    "value": "PASTE_YOUR_VALUE_HERE",
    "domain": ".strava.com"
  }
]
EOF
```

### Method 3: Copy as cURL (Advanced)

1. Open DevTools (F12) → **Network** tab
2. Visit any Strava page (e.g., strava.com/dashboard)
3. Click any request to `strava.com`
4. Look at **Request Headers** → **Cookie**
5. Find `_strava4_session=...` in the Cookie header
6. Copy everything after `_strava4_session=` (up to next semicolon or end)

### Method 3: Copy as cURL (Advanced)

1. Open DevTools (F12) → **Network** tab
2. Right-click any Strava request
3. Select **Copy** → **Copy as cURL**
4. Find the `-H 'Cookie: ...'` part in the copied command
5. Extract everything after `Cookie: ` and paste into `.strava_cookies`

Example cURL output:
```bash
curl 'https://www.strava.com/api/v3/athlete' \
  -H 'Cookie: _strava4_session=xyz123; CloudFront-Policy=abc; ...'
```

Just take the cookie string: `_strava4_session=xyz123; CloudFront-Policy=abc; ...`

---

## Cookie Format Examples

### ✅ Valid Format 1 (JSON - Structured)

```json
[
  {
    "name": "_strava4_session",
    "value": "bm51sgja62pr9cei5q5v58fm6869ct37",
    "domain": ".strava.com"
  }
]
```

### ✅ Valid Format 2 (Raw String - Just Copy/Paste!)

```
_strava4_session=bm51sgja62pr9cei5q5v58fm6869ct37; CloudFront-Policy=eyJTdGF0ZW1lbnQiO...; CloudFront-Signature=abc123...
```

### ✅ Minimal (Just the Session Cookie)

```
_strava4_session=bm51sgja62pr9cei5q5v58fm6869ct37
```

### ❌ Invalid Examples

```json
// Missing brackets
{
  "name": "_strava4_session",
  "value": "xyz"
}

// Wrong format
_strava4_session: xyz123

// No equals sign
_strava4_session xyz123
```

## Expected Output

```
============================================================
  Strava Integration Test - Full LLM Flow
============================================================

Loading configuration...
✅ Config loaded
✅ Found Strava session cookie: bm51sgja...t37
   Cookie length: 32 characters

============================================================
  Step 1: Testing Ollama Connection
============================================================

Ollama URL: http://ollama:11434
Model: llama3.2:3b
✅ Ollama is healthy and model 'llama3.2:3b' is available

============================================================
  Step 2: Discovering Strava Tools
============================================================

✅ Found 5 tools:
   - getFriendFeed (read): Get recent activities from friends
   - getMyLastDayActivities (read): Get my activities from last 24 hours
   - getMyProfile (read): Get my Strava profile
   - giveKudos (write): Give kudos to an activity
   - postComment (write): Post a comment on an activity

============================================================
  Step 3: LLM Function Calling Test
============================================================

Sending request to LLM...
✅ LLM Response received!

Reasoning: I'll fetch your recent activities and friend feed
Confidence: 0.95
Actions to execute: 2

============================================================
  Step 4: Executing Tool Calls
============================================================

Action 1/2: getMyLastDayActivities
Parameters: {}

Executing getMyLastDayActivities...
✅ SUCCESS! Got response from getMyLastDayActivities

Result preview:
  - Found 3 activities
    1. Morning Run (Run)
    2. Lunch Ride (Ride)
    3. Evening Workout (Workout)

Action 2/2: getFriendFeed
Parameters: {"page": 1, "per_page": 10}

Executing getFriendFeed...
✅ SUCCESS! Got response from getFriendFeed

Result preview:
  - Found 10 activities
    1. John's Epic Ride (Ride)
    2. Sarah's Trail Run (Run)
    3. Mike's Swim Session (Swim)
    ... and 7 more

============================================================
  Test Summary
============================================================

✅ Successfully executed: 2/2 actions

🎉 All tool calls succeeded! Integration test PASSED!

============================================================
  ✅ INTEGRATION TEST PASSED
============================================================
```

## Troubleshooting

### 401 Unauthorized Error

```
❌ ERROR: 401 Client Error: Unauthorized
   🔑 AUTHENTICATION ISSUE DETECTED!
```

**Solution**: Your Strava session cookie is invalid or expired.

1. Get a fresh cookie from your browser (see methods above)
2. Session cookies typically expire after a few hours or days
3. You need to be actively logged into Strava in your browser

### Ollama Connection Refused

```
❌ ERROR: Connection refused to localhost:11434
```

**Solution**: 
- Check if Ollama is running: `docker ps | grep ollama`
- Start Ollama: `./setup-ollama.sh`
- Verify network: `docker network inspect ollama-network`

### Cookie Format Error

```
❌ ERROR: Invalid cookie format - must be a JSON array
```

**Solution**: Ensure `.strava_cookies` is valid JSON:
- Must be an array `[ ... ]`
- Must have proper quotes (double quotes, not single)
- Use an online JSON validator if needed

## What the Test Does Internally

1. **Loads config.yaml** - Gets Ollama URL and model settings
2. **Validates cookies** - Checks `.strava_cookies` format and masks for display
3. **Connects to Ollama** - Health check on LLM server
4. **Discovers tools** - Loads all `@tool` decorated functions
5. **Prompts LLM** - Asks AI to fetch Strava activities
6. **Parses LLM response** - Extracts function calls from AI response
7. **Executes tools** - Runs the actual Strava API calls
8. **Reports results** - Shows success/failure with detailed errors

## Key Features

- ✅ **Real LLM integration** - Uses actual Ollama, not mocks
- ✅ **Real API calls** - Tests against live Strava API
- ✅ **Cookie masking** - Safely displays cookie info in logs
- ✅ **Detailed errors** - Shows exactly what failed and why
- ✅ **Step-by-step output** - Clear progress through test phases
- ✅ **Exit codes** - Returns 0 on success, 1 on failure

## Use Cases

- **Debug authentication** - Verify your Strava cookies work
- **Test LLM function calling** - Ensure AI can correctly invoke tools
- **Validate API integration** - Confirm Strava API responses
- **Development workflow** - Run before committing changes
- **CI/CD integration** - Can be automated (with valid cookies)

## Running Without Docker

```bash
# Set environment for local Python
export PYTHONPATH=/home/gradrix/repos/center:$PYTHONPATH

# Update config.yaml to use localhost
# Change: base_url: "http://ollama:11434"
# To:     base_url: "http://localhost:11434"

# Run directly
python tests/test_strava_integration.py
```

## Next Steps After Success

Once this test passes:

1. **Enable scheduler mode**: `./start-agent.sh` (runs hourly)
2. **Test with instructions**: `./start-agent.sh --instruction strava_monitor`
3. **Create custom instructions**: Add YAML files to `instructions/`
4. **Monitor logs**: Check `logs/agent.log` and `state/agent_state.db`
5. **Disable dry-run**: Set `dry_run: false` in `config.yaml` for real actions

## Security Notes

- ⚠️ **Never commit `.strava_cookies`** - It's in `.gitignore`
- ⚠️ **Cookies are sensitive** - They grant full account access
- ⚠️ **Rotate regularly** - Get fresh cookies periodically
- ⚠️ **Log out when done** - Invalidates the session cookie
