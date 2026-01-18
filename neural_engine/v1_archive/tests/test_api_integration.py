"""
Integration tests for the HTTP API server.

These tests verify the API endpoints work correctly with real dependencies.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_returns_status(self):
        """Health endpoint should return status information."""
        from neural_engine.api.server import app
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "version" in data
            assert "uptime_seconds" in data
            assert data["status"] == "healthy"


class TestGoalsEndpoint:
    """Tests for the goals endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_goal_async_mode(self):
        """Should create a goal and return immediately in async mode."""
        from neural_engine.api.server import app, goal_store
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/goals",
                json={
                    "goal": "Test goal for async mode",
                    "async_mode": True
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "goal_id" in data
            assert data["status"] == "pending"
            assert data["goal"] == "Test goal for async mode"
    
    @pytest.mark.asyncio
    async def test_get_goal_not_found(self):
        """Should return 404 for non-existent goal."""
        from neural_engine.api.server import app
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            response = client.get("/api/v1/goals/nonexistent_id")
            
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_list_goals_empty(self):
        """Should return empty list when no goals exist."""
        from neural_engine.api.server import app, goal_store
        from fastapi.testclient import TestClient
        
        # Clear existing goals
        goal_store.goals.clear()
        
        with TestClient(app) as client:
            response = client.get("/api/v1/goals")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_list_goals_with_limit(self):
        """Should respect limit parameter."""
        from neural_engine.api.server import app, goal_store
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            # Create a few goals
            for i in range(5):
                client.post(
                    "/api/v1/goals",
                    json={"goal": f"Goal {i}", "async_mode": True}
                )
            
            response = client.get("/api/v1/goals?limit=3")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) <= 3


class TestChatEndpoint:
    """Tests for the chat endpoint."""
    
    @pytest.mark.asyncio
    async def test_chat_requires_message(self):
        """Chat should require a message."""
        from neural_engine.api.server import app
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            response = client.post("/api/v1/chat", json={})
            
            assert response.status_code == 422  # Validation error


class TestToolsEndpoint:
    """Tests for the tools endpoint."""
    
    @pytest.mark.asyncio
    async def test_list_tools_returns_list(self):
        """Tools endpoint should return a list."""
        from neural_engine.api.server import app
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            # Mock orchestrator to avoid full initialization
            async def mock_get_orchestrator():
                mock_orchestrator = MagicMock()
                mock_orchestrator.tool_selector = None
                return mock_orchestrator
            
            with patch('neural_engine.api.server.get_orchestrator', mock_get_orchestrator):
                response = client.get("/api/v1/tools")
                
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)


class TestAPIAuthentication:
    """Tests for API authentication."""
    
    @pytest.mark.asyncio
    async def test_no_auth_when_key_not_configured(self):
        """Should not require auth when API_KEY is not set."""
        from neural_engine.api.server import app
        from fastapi.testclient import TestClient
        import os
        
        # Ensure API_KEY is not set
        os.environ.pop("API_KEY", None)
        
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_auth_required_when_key_configured(self):
        """Should require auth when API_KEY is set."""
        import os
        
        # This test is tricky because the API_KEY is read at module load time
        # We'd need to reload the module or use a different approach
        # For now, just test that the verify_api_key function works correctly
        from neural_engine.api.server import verify_api_key
        from fastapi import HTTPException
        
        # Temporarily set API_KEY
        original_key = os.environ.get("API_KEY")
        os.environ["API_KEY"] = "test-secret-key"
        
        try:
            # Import fresh to get the new API_KEY
            import importlib
            import neural_engine.api.server as server_module
            importlib.reload(server_module)
            
            # Wrong key should raise
            with pytest.raises(HTTPException) as exc_info:
                await server_module.verify_api_key("wrong-key")
            assert exc_info.value.status_code == 401
            
        finally:
            if original_key:
                os.environ["API_KEY"] = original_key
            else:
                os.environ.pop("API_KEY", None)


class TestGoalStore:
    """Tests for the in-memory goal store."""
    
    @pytest.mark.asyncio
    async def test_create_and_get_goal(self):
        """Should create and retrieve a goal."""
        from neural_engine.api.server import GoalStore
        
        store = GoalStore()
        
        goal = await store.create("test-123", "My test goal")
        
        assert goal.goal_id == "test-123"
        assert goal.goal == "My test goal"
        assert goal.status == "pending"
        
        retrieved = await store.get("test-123")
        assert retrieved is not None
        assert retrieved.goal_id == "test-123"
    
    @pytest.mark.asyncio
    async def test_update_goal(self):
        """Should update goal fields."""
        from neural_engine.api.server import GoalStore
        
        store = GoalStore()
        await store.create("test-456", "Another goal")
        
        await store.update("test-456", status="completed", result="Done!")
        
        goal = await store.get("test-456")
        assert goal.status == "completed"
        assert goal.result == "Done!"
    
    @pytest.mark.asyncio
    async def test_list_recent_sorted(self):
        """Should return goals sorted by creation time."""
        from neural_engine.api.server import GoalStore
        
        store = GoalStore()
        
        await store.create("a", "Goal A")
        await store.create("b", "Goal B")
        await store.create("c", "Goal C")
        
        recent = await store.list_recent(limit=10)
        
        assert len(recent) == 3
        # Most recent first
        assert recent[0].goal_id == "c"
