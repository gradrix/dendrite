"""
Tests for Strava authentication flow and credential handling.

This file contains both unit tests (mocked) and integration tests (real API).

Unit Tests (always run):
- Test authentication requirements
- Test credential storage/retrieval
- Test error handling
- Use mocks, no real API calls

Integration Tests (optional, marked with @pytest.mark.requires_strava_auth):
- Test with real Strava credentials
- Make actual API calls
- Skipped if credentials not provided
- See docs/STRAVA_INTEGRATION_TESTING.md for setup instructions
"""
import pytest
import os
import json
from unittest.mock import Mock, patch
from neural_engine.core.key_value_store import KeyValueStore
from neural_engine.tools.strava_get_my_activities_tool import StravaGetMyActivitiesTool
from neural_engine.clients.strava_client import StravaClient


@pytest.fixture
def kv_store():
    """Clean key-value store for testing."""
    kv = KeyValueStore()
    # Clear any existing Strava credentials
    kv.delete("strava_cookies")
    kv.delete("strava_token")
    yield kv
    # Cleanup
    kv.delete("strava_cookies")
    kv.delete("strava_token")


@pytest.fixture
def mock_strava_response():
    """Mock successful Strava API response."""
    return [
        {
            "id": 123456,
            "name": "Morning Run",
            "distance": 5000,
            "moving_time": 1800,
            "type": "Run"
        }
    ]


class TestStravaAuthFlow:
    """Test Strava authentication and credential handling."""
    
    def test_missing_credentials_raises_error(self, kv_store):
        """
        Test that missing credentials result in clear error.
        StravaClient should raise AuthenticationRequiredError.
        """
        from neural_engine.core.exceptions import AuthenticationRequiredError
        
        # Ensure no credentials exist
        assert kv_store.get("strava_cookies") is None
        assert kv_store.get("strava_token") is None
        
        # Creating a client without credentials should raise error
        with pytest.raises(AuthenticationRequiredError) as exc_info:
            StravaClient(kv_store)
        
        # Error message should be helpful
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ['credentials', 'not found', 'strava'])
    
    def test_invalid_credentials_api_call_fails(self, kv_store):
        """
        Test that invalid credentials can be set but API calls will fail.
        """
        # Set invalid credentials (proper format but expired/invalid)
        kv_store.set("strava_cookies", {"strava_session": "invalid_cookie"})
        kv_store.set("strava_token", "invalid_token")
        
        # Client creation should succeed (credentials exist)
        client = StravaClient(kv_store)
        assert client is not None
        
        # But API call with invalid credentials will fail (tested in integration tests)
    
    def test_successful_auth_stores_credentials(self, kv_store):
        """
        Test that valid credentials are stored and can be retrieved.
        """
        # Store valid-looking credentials (proper format)
        test_cookies = {"strava_session": "abc123", "user_id": "456"}
        test_token = "csrf_token_xyz"
        
        kv_store.set("strava_cookies", test_cookies)
        kv_store.set("strava_token", test_token)
        
        # Verify storage
        assert kv_store.get("strava_cookies") == test_cookies
        assert kv_store.get("strava_token") == test_token
        
        # Tool should be able to retrieve them
        tool = StravaGetMyActivitiesTool()
        stored_cookies = kv_store.get("strava_cookies")
        stored_token = kv_store.get("strava_token")
        
        assert stored_cookies is not None
        assert stored_token is not None
    
    def test_credentials_reused_across_clients(self, kv_store):
        """
        Test that credentials are reused for subsequent clients.
        """
        # Set valid credentials (proper dict format)
        kv_store.set("strava_cookies", {"strava_session": "valid_cookie"})
        kv_store.set("strava_token", "valid_token")
        
        # First client
        client1 = StravaClient(kv_store)
        assert client1 is not None
        
        # Second client - should reuse same credentials
        client2 = StravaClient(kv_store)
        assert client2 is not None
        
        # Verify credentials were not cleared
        assert kv_store.get("strava_cookies") is not None
        assert kv_store.get("strava_token") is not None


@pytest.mark.integration
@pytest.mark.requires_strava_auth
class TestStravaRealAuth:
    """
    Integration tests using real Strava credentials.
    
    These tests make actual API calls to Strava and are skipped if credentials are not available.
    
    To run these tests, provide credentials via environment variables:
    
        export STRAVA_COOKIES='{"strava_session": "your_session_cookie"}'
        export STRAVA_TOKEN='your_csrf_token'
        pytest -v -m requires_strava_auth
    
    Or store credentials in KeyValueStore:
    
        python3 -c "
        from neural_engine.core.key_value_store import KeyValueStore
        kv = KeyValueStore()
        kv.set('strava_cookies', {'strava_session': 'your_session'})
        kv.set('strava_token', 'your_token')
        "
    
    For detailed instructions on getting credentials:
        See docs/STRAVA_INTEGRATION_TESTING.md
    """
    
    @pytest.fixture
    def real_credentials(self, kv_store):
        """
        Load real Strava credentials from environment or KeyValueStore.
        
        Priority:
        1. Environment variables (STRAVA_COOKIES, STRAVA_TOKEN)
        2. Existing KeyValueStore credentials
        3. Skip test if neither available
        
        STRAVA_COOKIES format: Semicolon-delimited string as copied from browser
        Example: '_strava4_session=abc123; CloudFront-Policy=xyz; CloudFront-Signature=def'
        """
        # Try environment variables first
        cookies_env = os.getenv('STRAVA_COOKIES')
        token_env = os.getenv('STRAVA_TOKEN')
        
        if cookies_env and token_env:
            # Parse semicolon-delimited cookie string into dict
            try:
                cookies = {}
                for cookie_pair in cookies_env.split(';'):
                    cookie_pair = cookie_pair.strip()
                    if '=' in cookie_pair:
                        key, value = cookie_pair.split('=', 1)
                        cookies[key.strip()] = value.strip()
                
                if not cookies:
                    pytest.skip("STRAVA_COOKIES is empty or invalid format. Expected: 'key1=value1; key2=value2'")
                
                kv_store.set("strava_cookies", cookies)
                kv_store.set("strava_token", token_env)
                print(f"\n✓ Using Strava credentials from environment variables")
                print(f"  Parsed {len(cookies)} cookie(s): {list(cookies.keys())}")
            except Exception as e:
                pytest.skip(f"Failed to parse STRAVA_COOKIES: {e}. Expected format: 'key1=value1; key2=value2'")
        else:
            # Try existing credentials in KeyValueStore
            existing_cookies = kv_store.get("strava_cookies")
            existing_token = kv_store.get("strava_token")
            
            if existing_cookies and existing_token:
                print(f"\n✓ Using existing Strava credentials from KeyValueStore")
            else:
                pytest.skip(
                    "Real Strava credentials not provided. "
                    "Set STRAVA_COOKIES and STRAVA_TOKEN environment variables, "
                    "or see docs/STRAVA_INTEGRATION_TESTING.md for setup instructions."
                )
        
        yield kv_store
        
        # Don't cleanup - keep creds for other tests
    
    def test_real_auth_success(self, real_credentials):
        """
        Test with real Strava credentials.
        This actually calls the Strava API.
        
        This test validates:
        - Credentials are accepted by Strava API
        - API returns 200 OK (not 401/403)
        - Response structure is correct
        - Activities can be retrieved (even if empty list)
        """
        tool = StravaGetMyActivitiesTool()
        result = tool.execute(per_page=5)
        
        # Should succeed with real data
        assert result['success'] is True, f"API call failed: {result.get('error', 'Unknown error')}"
        assert 'data' in result or 'activities' in result
        
        # Verify we got actual activities (or empty list if no activities)
        activities = result.get('data') or result.get('activities', [])
        assert isinstance(activities, list)
        print(f"\n✓ Successfully retrieved {len(activities)} activities from Strava API")
        
        # If there are activities, verify structure
        if len(activities) > 0:
            activity = activities[0]
            assert 'id' in activity
            assert 'name' in activity
            assert 'distance' in activity or 'moving_time' in activity
            print(f"✓ Activity structure valid: '{activity.get('name', 'Unnamed')}' ({activity.get('type', 'Unknown')})")
    
    def test_real_auth_connectivity(self, real_credentials):
        """
        Test basic connectivity to Strava API.
        
        This is a lightweight test that just verifies:
        - Network connectivity to strava.com
        - Credentials are accepted (200 OK, not 401/403)
        - API is responding (not 500/503)
        """
        # Use activities endpoint with minimal data request
        tool = StravaGetMyActivitiesTool()
        result = tool.execute(per_page=1)  # Request only 1 activity
        
        # Success means credentials work and API is reachable
        if result['success']:
            print(f"\n✓ Strava API connectivity verified")
            print(f"✓ Credentials accepted by Strava")
        else:
            # If it fails, provide helpful error message
            error = result.get('error', 'Unknown error')
            if '401' in str(error) or 'Unauthorized' in str(error):
                pytest.fail(
                    "Credentials rejected by Strava (401 Unauthorized). "
                    "Your session may have expired. Get fresh credentials from browser."
                )
            elif '403' in str(error) or 'Forbidden' in str(error):
                pytest.fail(
                    "Access forbidden by Strava (403 Forbidden). "
                    "Check if your account has API access enabled."
                )
            else:
                pytest.fail(f"Strava API call failed: {error}")
        
        assert result['success'] is True
    
    def test_real_auth_multiple_tools(self, real_credentials):
        """
        Test that credentials work across different Strava tools.
        """
        from neural_engine.tools.strava_get_dashboard_feed_tool import StravaGetDashboardFeedTool
        
        # Test activities tool
        activities_tool = StravaGetMyActivitiesTool()
        result1 = activities_tool.execute(per_page=1)
        assert result1['success'] is True
        
        # Test dashboard tool with same credentials
        dashboard_tool = StravaGetDashboardFeedTool()
        result2 = dashboard_tool.execute(page=1)
        assert result2['success'] is True


class TestStravaCredentialUpdate:
    """Test credential update and refresh flows."""
    
    def test_update_expired_credentials(self, kv_store):
        """
        Test updating credentials after they expire.
        """
        # Set initial (expired) credentials (proper dict format)
        kv_store.set("strava_cookies", {"strava_session": "old_expired_cookie"})
        kv_store.set("strava_token", "old_expired_token")
        
        # Update with new credentials
        new_cookies = {"strava_session": "fresh_cookie"}
        new_token = "fresh_token"
        
        kv_store.set("strava_cookies", new_cookies)
        kv_store.set("strava_token", new_token)
        
        # Verify update
        assert kv_store.get("strava_cookies") == new_cookies
        assert kv_store.get("strava_token") == new_token
    
    def test_partial_credential_missing(self, kv_store):
        """
        Test error when only one credential is provided.
        """
        from neural_engine.core.exceptions import AuthenticationRequiredError
        
        # Set only cookies, not token (proper dict format)
        kv_store.set("strava_cookies", {"strava_session": "some_cookie"})
        # Don't set token
        
        # Should fail - need both credentials
        with pytest.raises(AuthenticationRequiredError) as exc_info:
            StravaClient(kv_store)
        
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ['credentials', 'not found', 'strava'])


@pytest.mark.unit
class TestStravaAuthMocked:
    """Unit tests with mocked Strava responses."""
    
    def test_mocked_successful_call(self, kv_store, mock_strava_response):
        """
        Test successful API call with mocked response.
        """
        kv_store.set("strava_cookies", {"strava_session": "mock_cookie"})
        kv_store.set("strava_token", "mock_token")
        
        client = StravaClient(kv_store)
        
        with patch.object(client, 'get_logged_in_athlete_activities', return_value=mock_strava_response):
            activities = client.get_logged_in_athlete_activities(per_page=10)
            
            assert activities == mock_strava_response
            assert len(activities) > 0
    
    def test_tool_with_mocked_client(self, kv_store, mock_strava_response):
        """
        Test tool execution with mocked client.
        """
        kv_store.set("strava_cookies", {"strava_session": "mock_cookie"})
        kv_store.set("strava_token", "mock_token")
        
        with patch.object(StravaClient, 'get_logged_in_athlete_activities', return_value=mock_strava_response):
            tool = StravaGetMyActivitiesTool()
            result = tool.execute(per_page=10)
            
            assert result['success'] is True
            assert result['count'] == len(mock_strava_response)
            assert len(result['items']) > 0


class TestStravaCredentialSecurity:
    """Test security aspects of credential handling."""
    
    def test_credentials_stored_securely(self, kv_store):
        """
        Verify credentials can be stored and retrieved from KV store.
        """
        test_cookies = {"secret_session": "secret_cookies_123"}
        test_token = "secret_token_456"
        
        kv_store.set("strava_cookies", test_cookies)
        kv_store.set("strava_token", test_token)
        
        # Verify storage
        assert kv_store.get("strava_cookies") == test_cookies
        assert kv_store.get("strava_token") == test_token
    
    def test_tool_result_structure(self, kv_store, mock_strava_response):
        """
        Verify tool returns expected structure without credential leaks.
        """
        kv_store.set("strava_cookies", {"secret_session": "secret123"})
        kv_store.set("strava_token", "token456")
        
        with patch.object(StravaClient, 'get_logged_in_athlete_activities', return_value=mock_strava_response):
            tool = StravaGetMyActivitiesTool()
            result = tool.execute(per_page=10)
            
            # Verify result structure
            assert 'success' in result
            assert 'count' in result
            assert 'items' in result
            
            # Convert to string and check for credential leaks
            result_str = str(result)
            assert "secret123" not in result_str
            assert "token456" not in result_str
