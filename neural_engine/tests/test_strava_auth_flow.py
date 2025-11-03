"""
Tests for Strava authentication flow and credential handling.
"""
import pytest
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
    
    To run these tests:
    1. Set STRAVA_COOKIES and STRAVA_TOKEN environment variables
    2. Run with: pytest -v -m requires_strava_auth
    
    These tests are skipped in CI and require manual execution.
    """
    
    @pytest.fixture
    def real_credentials(self, kv_store):
        """Load real Strava credentials from environment."""
        import os
        
        cookies = os.getenv('STRAVA_COOKIES')
        token = os.getenv('STRAVA_TOKEN')
        
        if not cookies or not token:
            pytest.skip("Real Strava credentials not provided")
        
        kv_store.set("strava_cookies", cookies)
        kv_store.set("strava_token", token)
        
        yield kv_store
        
        # Don't cleanup - keep creds for other tests
    
    def test_real_auth_success(self, real_credentials):
        """
        Test with real Strava credentials.
        This actually calls the Strava API.
        """
        tool = StravaGetMyActivitiesTool()
        result = tool.execute(per_page=5)
        
        # Should succeed with real data
        assert result['success'] is True
        assert 'data' in result or 'activities' in result
        
        # Verify we got actual activities
        activities = result.get('data') or result.get('activities', [])
        assert isinstance(activities, list)
        
        # If there are activities, verify structure
        if len(activities) > 0:
            activity = activities[0]
            assert 'id' in activity
            assert 'name' in activity
            assert 'distance' in activity or 'moving_time' in activity
    
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
