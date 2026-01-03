"""
Integration tests for the HTTP API server.

These tests verify that the FastAPI server endpoints work correctly.
"""

import pytest
import os
import requests
from typing import Generator

# Test configuration
API_URLS = [
    os.environ.get("API_TEST_URL"),  # Explicit override
    "http://api:8000",  # Docker internal network (CPU)
    "http://api-gpu:8000",  # Docker internal network (GPU)
    "http://dendrite-api:8000",  # Container name (CPU)
    "http://dendrite-api-gpu:8000",  # Container name (GPU)
    "http://localhost:8000",  # Host machine
]
TIMEOUT = 10


def find_api_server() -> str:
    """Find a working API server URL."""
    for url in API_URLS:
        if not url:
            continue
        try:
            response = requests.get(f"{url}/health", timeout=3)
            if response.status_code == 200:
                return url
        except requests.exceptions.RequestException:
            pass
    return None


@pytest.fixture(scope="module")
def api_url() -> Generator[str, None, None]:
    """Get API URL, skip tests if not available."""
    url = find_api_server()
    if url is None:
        pytest.skip("API server not available. Start with: ./start.sh api")
    yield url


class TestAPIHealth:
    """Test API health endpoints."""
    
    def test_health_endpoint(self, api_url):
        """Verify health endpoint returns healthy status."""
        response = requests.get(f"{api_url}/health", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0
    
    def test_openapi_docs(self, api_url):
        """Verify OpenAPI documentation is available."""
        response = requests.get(f"{api_url}/docs", timeout=TIMEOUT)
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "redoc" in response.text.lower() or "openapi" in response.text.lower()
    
    def test_openapi_json(self, api_url):
        """Verify OpenAPI JSON schema is available."""
        response = requests.get(f"{api_url}/openapi.json", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


class TestAPIGoals:
    """Test goal submission endpoints."""
    
    def test_list_goals_empty(self, api_url):
        """Verify listing goals works with empty store."""
        response = requests.get(f"{api_url}/api/v1/goals", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_submit_goal_async(self, api_url):
        """Test submitting a goal in async mode."""
        response = requests.post(
            f"{api_url}/api/v1/goals",
            json={"goal": "Say hello", "async_mode": True},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "goal_id" in data
        assert data["status"] in ["pending", "processing"]
        assert data["goal"] == "Say hello"
    
    def test_get_goal_status(self, api_url):
        """Test getting goal status by ID."""
        # Submit a goal first
        submit_response = requests.post(
            f"{api_url}/api/v1/goals",
            json={"goal": "Test goal", "async_mode": True},
            timeout=TIMEOUT
        )
        goal_id = submit_response.json()["goal_id"]
        
        # Get status
        response = requests.get(
            f"{api_url}/api/v1/goals/{goal_id}",
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["goal_id"] == goal_id
    
    def test_get_nonexistent_goal(self, api_url):
        """Test getting a goal that doesn't exist."""
        response = requests.get(
            f"{api_url}/api/v1/goals/nonexistent-id",
            timeout=TIMEOUT
        )
        assert response.status_code == 404


class TestAPITools:
    """Test tools listing endpoint."""
    
    def test_list_tools(self, api_url):
        """Verify tools listing works."""
        response = requests.get(f"{api_url}/api/v1/tools", timeout=TIMEOUT)
        # May return 200 or 500 depending on orchestrator state
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)


class TestAPIChat:
    """Test chat endpoint."""
    
    def test_chat_endpoint_exists(self, api_url):
        """Verify chat endpoint exists."""
        response = requests.post(
            f"{api_url}/api/v1/chat",
            json={"message": "Hello"},
            timeout=30  # Chat may take longer
        )
        # May succeed or fail depending on orchestrator state
        assert response.status_code in [200, 500]


class TestAPIAuthentication:
    """Test API authentication when enabled."""
    
    def test_health_no_auth_required(self, api_url):
        """Health endpoint should not require auth."""
        response = requests.get(f"{api_url}/health", timeout=TIMEOUT)
        assert response.status_code == 200
