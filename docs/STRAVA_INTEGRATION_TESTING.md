# Strava Integration Testing

## Overview

This project includes both **unit tests** (mocked) and **optional integration tests** (real API calls) for Strava functionality.

## Test Types

### 1. Unit Tests (Always Run)
- Mock the Strava client
- Test authentication logic
- Test error handling
- Test credential storage
- **No real API calls**

### 2. Integration Tests (Optional)
- Use real Strava credentials
- Make actual API calls
- Verify end-to-end functionality
- **Marked with `@pytest.mark.requires_strava_auth`**
- **Skipped in CI** unless credentials provided

## Running Integration Tests

### Option 1: Environment Variables

```bash
# Set credentials as environment variables
export STRAVA_COOKIES='{"strava_session": "your_session_cookie"}'
export STRAVA_TOKEN='your_csrf_token'

# Run integration tests
pytest -v -m requires_strava_auth
```

### Option 2: Hardcoded Test Credentials (Development)

Edit `neural_engine/tests/conftest.py` and add:

```python
# conftest.py
import os

# Optional: Add your real Strava credentials here for local testing
# WARNING: Don't commit real credentials! Add conftest.py to .gitignore
TEST_STRAVA_COOKIES = os.getenv('STRAVA_COOKIES', None)
TEST_STRAVA_TOKEN = os.getenv('STRAVA_TOKEN', None)
```

### Option 3: Store in KeyValueStore (Persistent)

```bash
# Run this once to store credentials
python3 -c "
from neural_engine.core.key_value_store import KeyValueStore
kv = KeyValueStore()
kv.set('strava_cookies', {'strava_session': 'your_session_cookie'})
kv.set('strava_token', 'your_csrf_token')
print('Credentials stored!')
"

# Now integration tests will use these credentials
pytest -v -m requires_strava_auth
```

## Getting Your Strava Credentials

### Method 1: Browser DevTools (Recommended)

1. **Log into Strava** at https://www.strava.com
2. **Open Developer Tools** (F12 or Right-click → Inspect)
3. **Go to Network tab**
4. **Refresh the page** (or navigate to Dashboard)
5. **Click on any request** to strava.com
6. **Look for headers:**
   - **Cookie:** Find `_strava4_session=...` (this is your session cookie)
   - **Form Data:** Look for `csrf_token` in any POST request

### Method 2: Copy from Application Storage

1. **Open Developer Tools** (F12)
2. **Go to Application tab** (Chrome) or **Storage tab** (Firefox)
3. **Navigate to Cookies → https://www.strava.com**
4. **Copy these values:**
   - `_strava4_session` → Your session cookie
   - Find CSRF token in page HTML (look for `<meta name="csrf-token"`)

### Example Credentials Format

```json
{
  "cookies": {
    "strava_session": "ey1234567890abcdef..."
  },
  "token": "csrf_token_value_here"
}
```

## Security Notes

⚠️ **IMPORTANT:**
- **Never commit real credentials** to git
- **Use environment variables** in CI/CD
- **Credentials expire** - sessions typically last 2 weeks
- **Generate new credentials** if tests start failing with auth errors

## Test Organization

```
neural_engine/tests/
├── test_strava_auth_flow.py         # Unit + integration tests
│   ├── TestStravaAuthFlow           # Unit tests (always run)
│   ├── TestStravaRealAuth           # Integration tests (optional)
│   └── TestStravaCredentialUpdate   # Credential management
│
├── test_strava_tools.py             # Tool-specific tests (mocked)
└── test_strava_client.py            # Client tests (mocked)
```

## Running Tests Selectively

```bash
# Run only unit tests (no real API calls)
pytest -v -m "not requires_strava_auth" neural_engine/tests/test_strava*

# Run only integration tests (requires credentials)
pytest -v -m requires_strava_auth neural_engine/tests/test_strava*

# Run all tests (unit + integration if creds available)
pytest -v neural_engine/tests/test_strava*

# Run specific integration test
pytest -v neural_engine/tests/test_strava_auth_flow.py::TestStravaRealAuth::test_real_auth_success
```

## CI/CD Behavior

- **Unit tests:** Always run (use mocks)
- **Integration tests:** Skipped (credentials not provided)
- To enable in CI: Set `STRAVA_COOKIES` and `STRAVA_TOKEN` as secrets

## Troubleshooting

### "Real Strava credentials not provided" - Test Skipped
✅ **Expected behavior** - Integration tests require credentials  
💡 Set environment variables or store in KeyValueStore

### "AuthenticationRequiredError: Strava credentials not found"
✅ **Expected in unit tests** - Tests that auth is required  
❌ **Error in integration tests** - Check your credentials are set correctly

### "401 Unauthorized" or "403 Forbidden"
🔄 **Credentials expired** - Log into Strava and get new session cookie  
⏰ Strava sessions typically expire after ~2 weeks of inactivity

### Integration tests fail but unit tests pass
🔍 **Check credentials format** - Ensure JSON format is correct  
🔍 **Check network** - Ensure you can reach strava.com  
🔍 **Check cookies** - Try getting fresh credentials from browser

## Example: Full Integration Test Run

```bash
# 1. Get credentials from browser
# (Follow "Getting Your Strava Credentials" above)

# 2. Set environment variables
export STRAVA_COOKIES='{"strava_session": "ey1234567890..."}'
export STRAVA_TOKEN='csrf_token_abc123'

# 3. Run integration tests
pytest -v -m requires_strava_auth neural_engine/tests/test_strava_auth_flow.py

# Expected output:
# test_real_auth_success PASSED
# test_real_auth_multiple_tools PASSED
```

## Benefits of This Approach

✅ **Unit tests always run** - No credentials needed for development  
✅ **Integration tests optional** - Run manually to verify real API  
✅ **CI friendly** - Integration tests auto-skip without credentials  
✅ **Developer friendly** - Easy to test with real data when needed  
✅ **Secure** - No hardcoded credentials in repo
