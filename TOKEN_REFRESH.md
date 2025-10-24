# Strava Token Management

## Overview

Strava OAuth tokens expire after 6 hours. This system provides automatic token refresh capabilities to keep the agent running continuously.

## Components

### 1. Credentials Storage (`.env`)

Strava OAuth credentials are stored in `.env` file:

```bash
STRAVA_CLIENT_ID=182379
STRAVA_CLIENT_SECRET=66b6a95f19b2b2278004822e381004b693c55e69
```

**⚠️ Security Notes:**
- `.env` file is git-ignored (never commit credentials!)
- File is loaded by `main.py` using `python-dotenv`
- Docker container receives credentials via `env_file` in docker-compose.yml
- Environment variables are available to `strava_tools.py` for auto-refresh

### 2. Token Files

Three files store authentication tokens:

- **`.strava_token`**: Current access token (expires in 6 hours)
- **`.strava_refresh_token`**: Refresh token (used to get new access tokens)
- **`.strava_cookies`**: Browser session cookies (for web API endpoints)

All three are git-ignored and mounted as volumes in Docker.

### 3. Manual Token Refresh Script (`refresh_token.sh`)

Standalone bash script to manually refresh the access token.

**Usage:**
```bash
./refresh_token.sh
```

**What it does:**
1. Reads credentials from `.env`
2. Reads refresh token from `.strava_refresh_token`
3. Makes POST request to Strava OAuth endpoint
4. Saves new access token to `.strava_token`
5. Updates `.strava_refresh_token` (may change on each refresh)
6. Shows expiration time

**Example output:**
```
🔄 Strava Token Refresh

📡 Requesting new access token...

✅ Access token saved to .strava_token
✅ Refresh token updated
⏰ Token expires at: Fri Oct 24 14:42:04 UTC 2025
⏰ Valid for: 6 hours (21600 seconds)

✅ Token refresh successful!
New access token: 5f93f85e...7aa8

🎉 Ready to use Strava API!
```

### 4. Automatic Token Refresh (in `strava_tools.py`)

The `StravaClient` class automatically refreshes tokens when they expire.

**How it works:**
1. API request returns 401 Unauthorized
2. `_refresh_token()` method is called
3. Reads `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` from environment
4. Uses `.strava_refresh_token` to get new access token
5. Saves new tokens to files
6. Retries the original API request with new token
7. Returns data to caller (transparent to user)

**Code flow:**
```python
# In get_logged_in_athlete_activities()
try:
    response = self.session.request(...)
    response.raise_for_status()
    return response.json()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        logger.warning("⚠️  API token expired (401 Unauthorized)")
        logger.info("🔄 Attempting to refresh token...")
        
        if self._refresh_token():
            logger.info("✅ Token refreshed, retrying request...")
            # Retry with new token
            response = self.session.request(...)
            response.raise_for_status()
            return response.json()
```

**Requirements:**
- `STRAVA_CLIENT_ID` environment variable
- `STRAVA_CLIENT_SECRET` environment variable
- `.strava_refresh_token` file exists

If credentials are missing, logs a warning and returns empty result (no crash).

## Token Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ Initial Setup (One Time)                                     │
├─────────────────────────────────────────────────────────────┤
│ 1. Get OAuth code: ./get_token_manual.sh auth <CLIENT_ID>  │
│ 2. Exchange for tokens: ./get_token_manual.sh token <CODE> │
│ 3. Tokens saved to:                                          │
│    - .strava_token                                           │
│    - .strava_refresh_token                                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Normal Operation (6 hours)                                   │
├─────────────────────────────────────────────────────────────┤
│ • Agent uses .strava_token for API requests                 │
│ • Token is valid for 6 hours                                 │
│ • All API calls succeed                                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ (Token expires)
┌─────────────────────────────────────────────────────────────┐
│ Automatic Refresh (happens transparently)                    │
├─────────────────────────────────────────────────────────────┤
│ 1. API request returns 401 Unauthorized                      │
│ 2. _refresh_token() called automatically                     │
│ 3. POST to https://www.strava.com/api/v3/oauth/token       │
│    with:                                                      │
│    - client_id (from .env)                                   │
│    - client_secret (from .env)                               │
│    - refresh_token (from .strava_refresh_token)              │
│ 4. New tokens saved:                                         │
│    - .strava_token ← new access_token                        │
│    - .strava_refresh_token ← new refresh_token               │
│ 5. Original request retried with new token                   │
│ 6. Success! User never notices                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    (Repeat cycle)
```

## Manual vs Automatic Refresh

### When to Use Manual Refresh (`./refresh_token.sh`)

✅ **Before starting long-running tasks**
   - Pre-emptively refresh to ensure full 6 hours
   
✅ **After long idle periods**
   - Agent was stopped, starting again
   
✅ **Testing/debugging**
   - Verify credentials work
   - Check token expiration time

### When Automatic Refresh Happens

✅ **During agent operation**
   - Token expires while agent is running
   - API request fails with 401
   - Automatically retries with new token
   
✅ **In Docker container**
   - Environment variables loaded from .env
   - Seamless operation 24/7

## Docker Integration

The `docker-compose.yml` is configured to load environment variables:

```yaml
agent:
  environment:
    - PYTHONUNBUFFERED=1
    - STRAVA_CLIENT_ID=${STRAVA_CLIENT_ID}
    - STRAVA_CLIENT_SECRET=${STRAVA_CLIENT_SECRET}
  env_file:
    - .env
  volumes:
    - ./.strava_token:/app/.strava_token:ro
    - ./.strava_refresh_token:/app/.strava_refresh_token:ro
    - ./.strava_cookies:/app/.strava_cookies:ro
```

**Note:** Token files are mounted as read-only (`:ro`) in the original setup, but the refresh functionality needs write access. If automatic refresh fails in Docker, update the mounts:

```yaml
    - ./.strava_token:/app/.strava_token  # Remove :ro
    - ./.strava_refresh_token:/app/.strava_refresh_token  # Remove :ro
```

## Strava API Token Endpoint

**Endpoint:** `POST https://www.strava.com/api/v3/oauth/token`

**Request Parameters:**
- `client_id`: Your application client ID
- `client_secret`: Your application client secret
- `grant_type`: `refresh_token`
- `refresh_token`: Current refresh token

**Response:**
```json
{
  "token_type": "Bearer",
  "access_token": "a9b723...",
  "expires_at": 1568775134,
  "expires_in": 20566,
  "refresh_token": "b5c569..."
}
```

**Important Notes:**
- `expires_at`: Unix timestamp when token expires
- `expires_in`: Seconds until expiration (typically 21600 = 6 hours)
- `refresh_token`: **MAY CHANGE** - always save the new one
- Old refresh token becomes invalid after use

## Troubleshooting

### "STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET not set in environment"

**Problem:** Environment variables not loaded

**Solutions:**
1. Check `.env` file exists and contains credentials
2. Verify `main.py` loads dotenv: `load_dotenv()`
3. In Docker: Check `env_file` in docker-compose.yml
4. In local: `source .env` before running Python scripts

### "No refresh token found. Cannot auto-refresh."

**Problem:** `.strava_refresh_token` file missing

**Solutions:**
1. Run `./get_token_manual.sh` to get initial tokens
2. Verify file permissions (readable by agent)
3. Check Docker volume mounts

### "Token refresh failed: 401/400"

**Problem:** Refresh token is invalid or expired

**Solutions:**
1. Refresh tokens can expire if not used for months
2. Get new tokens: `./get_token_manual.sh auth <CLIENT_ID>`
3. Complete OAuth flow again
4. Verify CLIENT_ID and CLIENT_SECRET are correct

### Manual refresh works, but automatic fails in Docker

**Problem:** Token files mounted as read-only

**Solutions:**
1. Remove `:ro` from token volume mounts in docker-compose.yml
2. Rebuild container: `docker compose up -d --build agent`
3. Check file permissions: `ls -la .strava_*`

## Security Best Practices

✅ **DO:**
- Keep `.env` file in `.gitignore`
- Use environment variables for credentials
- Rotate credentials if exposed
- Monitor token refresh logs for anomalies

❌ **DON'T:**
- Commit `.env` to git
- Share CLIENT_SECRET publicly
- Hardcode credentials in source code
- Leave unused tokens active

## Monitoring Token Refresh

Check logs for automatic refresh events:

```bash
# In Docker
docker logs ai-agent | grep -i "token"

# Look for:
⚠️  API token is invalid or expired (401 Unauthorized)
🔄 Attempting to refresh token...
✅ Token refreshed successfully: 5f93f85e...7aa8
```

If you see repeated refresh failures, investigate credentials or refresh token validity.

## Testing Token Refresh

### Test Manual Refresh
```bash
./refresh_token.sh
```

### Test Automatic Refresh
```python
# Invalidate current token
echo "invalid_token_12345" > .strava_token

# Try to fetch activities (should auto-refresh)
python3 -c "
from dotenv import load_dotenv
load_dotenv()
from tools.strava_tools import get_my_activities
result = get_my_activities(per_page=1)
print('Success!' if result.get('success') else 'Failed')
"
```

Expected output:
```
⚠️  API token is invalid or expired (401 Unauthorized)
🔄 Attempting to refresh token...
✅ Token refreshed successfully
Retrieved 1 activities from API v3 (after refresh)
Success!
```

## Summary

With this system in place:

1. ✅ Tokens automatically refresh when expired
2. ✅ Credentials stored securely in `.env`
3. ✅ Manual refresh script available (`./refresh_token.sh`)
4. ✅ Works in Docker and locally
5. ✅ Detailed logging for monitoring
6. ✅ No manual intervention needed for 24/7 operation

The agent can now run indefinitely without token expiration issues!
