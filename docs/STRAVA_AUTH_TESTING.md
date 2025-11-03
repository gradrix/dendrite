# Strava Authentication Testing Guide

## Overview

This guide explains how to test Strava authentication flows, including missing credentials, expired tokens, and successful authentication.

## Test Categories

### 1. Unit Tests (Mocked)

These tests use mocked Strava API responses and run automatically in CI:

```bash
# Run only unit tests
pytest -v -m unit neural_engine/tests/test_strava_auth_flow.py

# Run specific test
pytest -v neural_engine/tests/test_strava_auth_flow.py::TestStravaAuthMocked::test_mocked_successful_auth
```

**Tests included:**
- `test_mocked_successful_auth` - Verify tool works with valid credentials
- `test_mocked_auth_failure` - Test 401 Unauthorized handling
- `test_mocked_network_error` - Test network failure handling

### 2. Integration Tests (No Auth Required)

These tests verify credential handling logic without calling the real API:

```bash
# Run integration tests (no real credentials needed)
pytest -v -m "integration and not requires_strava_auth" neural_engine/tests/test_strava_auth_flow.py
```

**Tests included:**
- `test_missing_credentials_prompts_user` - Verify clear error when credentials missing
- `test_invalid_credentials_handling` - Test invalid credential error messages
- `test_successful_auth_stores_credentials` - Verify credential storage
- `test_credentials_reused_across_requests` - Test credential persistence
- `test_update_expired_credentials` - Test credential refresh
- `test_partial_credential_missing` - Test incomplete credential handling
- `test_credentials_not_in_result` - Security: credentials not exposed
- `test_credentials_not_logged` - Security: credentials not logged

### 3. Real API Tests (Requires Credentials)

These tests make actual Strava API calls and require real credentials:

```bash
# Set your credentials
export STRAVA_COOKIES="your_session_cookie_here"
export STRAVA_TOKEN="your_csrf_token_here"

# Run real API tests
pytest -v -m requires_strava_auth neural_engine/tests/test_strava_auth_flow.py
```

**Tests included:**
- `test_real_auth_success` - Verify real API call succeeds
- `test_real_auth_multiple_tools` - Test credentials work across tools

## Getting Strava Credentials

### Method 1: Extract from Browser (Recommended)

1. Log in to Strava.com in your browser
2. Open Developer Tools (F12)
3. Go to Network tab
4. Navigate to any Strava page
5. Find a request to `strava.com` in the Network tab
6. Copy the `Cookie` header (everything after `Cookie: `)
7. Copy the `X-CSRF-Token` header value

### Method 2: Use the Goal System

1. Start the system: `./scripts/docker/start.sh`
2. Run a Strava-related goal: `./run.sh "Get my recent activities"`
3. When prompted, the system will guide you through authentication
4. Credentials are automatically stored in the key-value store

## CI/CD Integration

### Automated Testing (No Credentials)

The CI pipeline automatically runs:
- All unit tests (mocked)
- All integration tests without `requires_strava_auth` marker

```yaml
# In GitHub Actions
- name: Run Strava auth tests
  run: |
    docker compose --profile cpu run --rm tests pytest -v \
      -m "not requires_strava_auth" \
      neural_engine/tests/test_strava_auth_flow.py
```

### Manual Testing (With Credentials)

To test with real credentials in CI:

1. Add secrets to GitHub repository:
   - `STRAVA_COOKIES`
   - `STRAVA_TOKEN`

2. Create manual workflow or enable via workflow_dispatch:
```yaml
on:
  workflow_dispatch:
    inputs:
      run_real_auth:
        description: 'Run real Strava auth tests'
        required: false
        type: boolean

- name: Run real Strava tests
  if: ${{ inputs.run_real_auth }}
  env:
    STRAVA_COOKIES: ${{ secrets.STRAVA_COOKIES }}
    STRAVA_TOKEN: ${{ secrets.STRAVA_TOKEN }}
  run: |
    docker compose --profile cpu run --rm tests pytest -v \
      -m requires_strava_auth \
      neural_engine/tests/test_strava_auth_flow.py
```

## Common Test Scenarios

### Test Missing Credentials Flow

This simulates a new user without credentials:

```python
def test_missing_credentials_prompts_user(self, kv_store):
    """Ensure clear error when credentials are missing."""
    # Clear credentials
    kv_store.delete("strava_cookies")
    kv_store.delete("strava_token")
    
    # Try to use tool
    tool = StravaGetMyActivitiesTool()
    result = tool.execute(per_page=10)
    
    # Should fail with helpful message
    assert result['success'] is False
    assert 'credentials' in result['error'].lower()
```

### Test Expired Credentials

This simulates credentials that have expired:

```python
def test_invalid_credentials_handling(self, kv_store):
    """Ensure clear error for expired credentials."""
    # Set expired credentials
    kv_store.set("strava_cookies", "expired_cookies")
    kv_store.set("strava_token", "expired_token")
    
    # Mock 401 response
    with patch.object(StravaClient, 'get_my_activities', 
                     side_effect=Exception("401 Unauthorized")):
        result = tool.execute(per_page=10)
        
        # Should indicate auth failure
        assert '401' in result['error'] or 'unauthorized' in result['error'].lower()
```

### Test Successful Authentication

This verifies the happy path:

```python
def test_successful_auth_stores_credentials(self, kv_store):
    """Verify credentials are properly stored."""
    # Store valid credentials
    kv_store.set("strava_cookies", "valid_cookies")
    kv_store.set("strava_token", "valid_token")
    
    # Verify storage
    assert kv_store.get("strava_cookies") is not None
    assert kv_store.get("strava_token") is not None
```

## Debugging Failed Tests

### Check Credential Format

```python
# Credentials should be strings
cookies = kv_store.get("strava_cookies")
token = kv_store.get("strava_token")

print(f"Cookies type: {type(cookies)}, length: {len(cookies) if cookies else 0}")
print(f"Token type: {type(token)}, length: {len(token) if token else 0}")
```

### Test Credential Validity

```python
# Quick validation script
from neural_engine.clients.strava_client import StravaClient

client = StravaClient()
try:
    activities = client.get_my_activities(per_page=1)
    print(f"✓ Credentials valid, got {len(activities)} activities")
except Exception as e:
    print(f"✗ Credentials invalid: {e}")
```

### Run with Verbose Output

```bash
# See detailed test output
pytest -vv -s neural_engine/tests/test_strava_auth_flow.py::TestStravaAuthFlow::test_missing_credentials_prompts_user

# See fixture setup/teardown
pytest -vv --setup-show neural_engine/tests/test_strava_auth_flow.py
```

## Security Notes

1. **Never commit credentials** - Use environment variables or CI secrets
2. **Credentials are not logged** - Tests verify this with `test_credentials_not_logged`
3. **Credentials are not exposed** - Tests verify with `test_credentials_not_in_result`
4. **Use separate test account** - Don't use your main Strava account for testing

## Running All Auth Tests

```bash
# Run everything except real API tests (CI-safe)
pytest -v -m "not requires_strava_auth" neural_engine/tests/test_strava_auth_flow.py

# Run only real API tests (requires credentials)
export STRAVA_COOKIES="..."
export STRAVA_TOKEN="..."
pytest -v -m requires_strava_auth neural_engine/tests/test_strava_auth_flow.py

# Run all tests (CI + manual)
pytest -v neural_engine/tests/test_strava_auth_flow.py
```

## Test Coverage

These tests cover:
- ✅ Missing credentials error handling
- ✅ Invalid credentials error handling
- ✅ Expired token handling
- ✅ Successful authentication
- ✅ Credential storage and retrieval
- ✅ Credential reuse across requests
- ✅ Credential updates/refresh
- ✅ Partial credential handling
- ✅ Multiple tools sharing credentials
- ✅ Network error handling
- ✅ Security (no credential leaks)
- ✅ Real API integration (manual)

## Next Steps

1. Run unit tests to verify basic auth logic
2. Run integration tests to verify credential handling
3. Optionally: Run real API tests with your credentials
4. Add more tools that use Strava auth
5. Consider implementing automatic token refresh
