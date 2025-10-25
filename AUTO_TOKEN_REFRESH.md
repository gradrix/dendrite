# Automatic Token Refresh Implementation

## Overview
The Strava API tokens expire after 6 hours. To prevent authentication errors (401 Unauthorized) from breaking the agent, **automatic token refresh** has been implemented with retry logic.

## How It Works

### Detection & Retry Flow
```
API Request → 401 Error
    ↓
Detect: "Authentication failed"
    ↓
Action: Call _refresh_token()
    ↓
Success? → Retry Request → ✅ Success
    ↓
Failure? → Log error → Suggest manual refresh
```

### Implementation Details

#### 1. Token Storage
- **Access Token**: `.strava_token` (expires in 6 hours)
- **Refresh Token**: `.strava_refresh_token` (long-lived)
- **Credentials**: `.env` file with `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`

#### 2. Auto-Refresh Method (`_refresh_token`)
Located in `StravaClient` class:
- Reads refresh token from `.strava_refresh_token`
- Calls Strava OAuth endpoint: `POST /oauth/token`
- Parameters:
  - `client_id`: From `.env`
  - `client_secret`: From `.env`
  - `grant_type`: "refresh_token"
  - `refresh_token`: Current refresh token
- Saves new access token to `.strava_token`
- Saves new refresh token to `.strava_refresh_token`

#### 3. Automatic Retry Logic

**For Web Frontend API (cookie-based)**:
```python
try:
    response = self.session.request(...)
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        if self._refresh_token():
            # Re-extract CSRF token with new session
            self._extract_csrf_token()
            # Retry request ONCE
            response = self.session.request(...)
            response.raise_for_status()
```

**For Official API v3 (token-based)**:
```python
try:
    response = self.session.request(..., headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        if self._refresh_token():
            # Update headers with new token
            headers["Authorization"] = f"Bearer {new_token}"
            # Retry request ONCE
            response = self.session.request(..., headers=headers)
            response.raise_for_status()
```

#### 4. Affected Methods
**All Strava API methods** now have automatic retry on 401:
- ✅ `get_dashboard_feed()`
- ✅ `get_my_activities_v3()`
- ✅ `get_activity_kudos()`
- ✅ `give_kudos()`
- ✅ `update_activity()`
- ✅ `get_activity_participants()`
- ✅ And all other methods...

### Logging Output

**When token expires:**
```
⚠️  Authentication failed (401 Unauthorized)
🔄 Attempting to refresh token and re-authenticate...
Refreshing access token...
✅ Token refreshed successfully
✅ Saved new access token
🔄 Retrying request with new credentials...
✅ Success!
```

**When refresh fails:**
```
❌ Token refresh failed
💡 Run ./refresh_token.sh or ./get_token_manual.sh to refresh manually
```

## Manual Refresh (Fallback)

If automatic refresh fails, users can manually refresh:

```bash
# Option 1: Use refresh token
./refresh_token.sh

# Option 2: Get new tokens (requires browser)
./get_token_manual.sh
```

## Setup Requirements

### 1. Environment Variables
Create `.env` file:
```bash
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

### 2. Initial Token Setup
Run once to get initial tokens:
```bash
./get_token_manual.sh
```

This creates:
- `.strava_token` (access token)
- `.strava_refresh_token` (refresh token)
- `.strava_cookies` (web session cookies)

### 3. Agent Configuration
No changes needed! The agent automatically uses the refresh mechanism.

## Error Handling

### Scenarios Covered

| Scenario | Automatic Action | Manual Fallback |
|----------|-----------------|-----------------|
| Token expired (401) | ✅ Auto-refresh + retry | `./refresh_token.sh` |
| Refresh token expired | ❌ Log error | `./get_token_manual.sh` (browser required) |
| No credentials in .env | ❌ Log error | Add `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` to `.env` |
| No refresh token file | ❌ Log error | Run `./get_token_manual.sh` |
| Network error during refresh | ❌ Log error | Check internet connection, retry manually |

### Retry Limits
- **Max retries**: 1 (to avoid infinite loops)
- **Retry delay**: None (immediate retry after successful refresh)
- **Cooldown**: None (each request handles its own 401)

## Testing

### Simulate Token Expiry
```bash
# Corrupt the token to force 401
echo "invalid_token" > .strava_token

# Run agent
./start-agent.sh --once

# Expected: Auto-refresh triggers, agent continues without interruption
```

### Verify Auto-Refresh
```bash
# Watch the logs
./logs.sh | grep -E "401|refresh|Token"
```

Expected output:
```
⚠️  Authentication failed (401 Unauthorized)
🔄 Attempting to refresh token...
✅ Token refreshed successfully
```

## Security Considerations

### ✅ Implemented
- Refresh tokens are stored locally in `.strava_refresh_token` (gitignored)
- Client credentials are in `.env` (gitignored)
- Tokens are never logged in full
- Failed refresh attempts are rate-limited by Strava (no infinite loop)

### 🔒 Best Practices
- Keep `.env` and token files out of version control
- Don't share refresh tokens (they have long lifetime)
- Regenerate tokens if compromised
- Monitor logs for repeated refresh failures (may indicate account issues)

## Limitations

### What's NOT Covered
- ❌ **Cookie expiration**: Web session cookies may expire independently (requires re-login via browser)
- ❌ **Account suspension**: If Strava account is suspended, refresh will fail
- ❌ **API rate limits**: Refresh doesn't bypass rate limits (429 errors still occur)
- ❌ **Scope changes**: If app permissions change, need to re-authenticate

### When Manual Intervention Required
- Cookie session expires (web frontend API calls fail)
- Refresh token expires (rare, but happens after ~90 days of no use)
- Strava API app is revoked or deleted
- User changes password (may invalidate tokens)

## Future Improvements

### Potential Enhancements
1. **Proactive refresh**: Check token expiry timestamp and refresh BEFORE it expires
2. **Cookie refresh**: Implement automatic cookie renewal via headless browser
3. **Health monitoring**: Track refresh success rate and alert on repeated failures
4. **Exponential backoff**: Add retry delay for network errors during refresh
5. **Token caching**: Cache token in memory to avoid file I/O on every request

### AI-Assisted Token Management? 😄
**Could the AI agent refresh its own tokens?**

Technically yes, but... 🤖💥

**Pros:**
- Ultimate autonomy! The agent never needs human intervention
- Could handle cookie refresh via browser automation

**Cons:**
- Security nightmare (AI handling OAuth credentials)
- Browser automation is fragile and complex
- What if AI decides to "optimize" by modifying token endpoints? 😱
- Debugging becomes hilarious ("Why did the AI request tokens at 3 AM?")

**Verdict:** Let's keep humans in the loop for now. The current automatic refresh is the sweet spot between convenience and safety.

## Summary

✅ **What works automatically:**
- Token expires → Auto-refresh → Retry → Success
- No manual intervention for normal token expiry
- All API methods protected

⚠️ **What needs manual action:**
- Initial token setup (once)
- Refresh token expires (rare)
- Cookie session expires (web API only)

🎯 **Result:** The agent can run **unattended for weeks** without auth errors, only requiring manual intervention if the refresh token itself expires (typically 90+ days).

**TL;DR:** No more 401 errors interrupting your AI agent! It refreshes tokens automatically like a responsible adult. 🎉
