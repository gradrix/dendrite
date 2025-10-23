"""
Tests for Ollama Client and Function Calling

Demonstrates how the LLM responds to various scenarios and parses tool calls.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from agent.ollama_client import OllamaClient


class TestOllamaClient:
    """Test Ollama client functionality."""
    
    def test_client_initialization(self):
        """Test client can be initialized with config."""
        client = OllamaClient(
            base_url="http://localhost:11434",
            model="llama3.1:8b",
            timeout=60
        )
        
        assert client.base_url == "http://localhost:11434"
        assert client.model == "llama3.1:8b"
        assert client.timeout == 60
    
    @patch('agent.ollama_client.requests.post')
    def test_simple_generate(self, mock_post):
        """Test simple text generation."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": "Hello! I am an AI assistant."
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = OllamaClient()
        response = client.generate("Say hello")
        
        assert "Hello" in response
        mock_post.assert_called_once()
    
    def test_parse_json_response_clean(self):
        """Test parsing clean JSON response."""
        client = OllamaClient()
        
        json_text = '''
        {
            "reasoning": "User requested greeting",
            "actions": [],
            "confidence": 1.0,
            "requires_approval": false
        }
        '''
        
        result = client._parse_json_response(json_text)
        
        assert result["reasoning"] == "User requested greeting"
        assert result["actions"] == []
        assert result["confidence"] == 1.0
    
    def test_parse_json_response_with_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        client = OllamaClient()
        
        json_text = '''```json
        {
            "reasoning": "Test",
            "actions": [{"tool": "test", "params": {}}],
            "confidence": 0.9,
            "requires_approval": false
        }
        ```'''
        
        result = client._parse_json_response(json_text)
        
        assert result["reasoning"] == "Test"
        assert len(result["actions"]) == 1
    
    def test_parse_json_response_with_extra_text(self):
        """Test parsing JSON with surrounding text."""
        client = OllamaClient()
        
        json_text = '''Here is my response:
        {
            "reasoning": "Parsed correctly",
            "actions": [],
            "confidence": 0.95,
            "requires_approval": false
        }
        That's my answer.'''
        
        result = client._parse_json_response(json_text)
        
        assert result["reasoning"] == "Parsed correctly"
    
    def test_validate_function_call_response_valid(self):
        """Test validation of valid function call response."""
        client = OllamaClient()
        
        tools = [
            {"name": "getTool", "description": "Get data"},
            {"name": "postTool", "description": "Post data"}
        ]
        
        response = {
            "reasoning": "Need to get data",
            "actions": [
                {"tool": "getTool", "params": {"id": 123}}
            ],
            "confidence": 0.9,
            "requires_approval": False
        }
        
        assert client._validate_function_call_response(response, tools) is True
    
    def test_validate_function_call_response_invalid_tool(self):
        """Test validation rejects unknown tools."""
        client = OllamaClient()
        
        tools = [
            {"name": "validTool", "description": "Valid"}
        ]
        
        response = {
            "reasoning": "Using invalid tool",
            "actions": [
                {"tool": "invalidTool", "params": {}}
            ],
            "confidence": 0.9,
            "requires_approval": False
        }
        
        assert client._validate_function_call_response(response, tools) is False
    
    def test_validate_function_call_response_missing_keys(self):
        """Test validation rejects responses with missing keys."""
        client = OllamaClient()
        tools = []
        
        # Missing 'confidence'
        response = {
            "reasoning": "Test",
            "actions": [],
            "requires_approval": False
        }
        
        assert client._validate_function_call_response(response, tools) is False
    
    @patch('agent.ollama_client.requests.post')
    def test_function_call_with_tools(self, mock_post):
        """Test function calling with tool definitions."""
        # Mock LLM response with valid JSON
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": json.dumps({
                "reasoning": "User wants to check activities",
                "actions": [
                    {"tool": "getActivities", "params": {"limit": 10}}
                ],
                "confidence": 0.95,
                "requires_approval": False
            })
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = OllamaClient()
        
        tools = [
            {
                "name": "getActivities",
                "description": "Get recent activities",
                "parameters": [
                    {"name": "limit", "type": "int", "required": False}
                ]
            }
        ]
        
        result = client.function_call(
            prompt="Check my recent activities",
            tools=tools
        )
        
        assert result["reasoning"] == "User wants to check activities"
        assert len(result["actions"]) == 1
        assert result["actions"][0]["tool"] == "getActivities"
        assert result["actions"][0]["params"]["limit"] == 10
    
    def test_empty_response_on_parse_error(self):
        """Test that parse errors return empty response."""
        client = OllamaClient()
        
        result = client._get_empty_response("Test error")
        
        assert result["actions"] == []
        assert result["confidence"] == 0.0
        assert "Test error" in result["reasoning"]


class TestFunctionCallingScenarios:
    """Test realistic function calling scenarios."""
    
    @patch('agent.ollama_client.requests.post')
    def test_scenario_give_kudos(self, mock_post):
        """Test scenario: AI decides to give kudos to friend."""
        # Mock LLM decision
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": '''```json
            {
                "reasoning": "Friend completed a 25km run, which is impressive. Should give kudos.",
                "actions": [
                    {"tool": "giveKudos", "params": {"activity_id": 12345}}
                ],
                "confidence": 0.95,
                "requires_approval": false
            }
            ```'''
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = OllamaClient()
        
        tools = [
            {
                "name": "giveKudos",
                "description": "Give kudos to activity",
                "parameters": [{"name": "activity_id", "type": "int"}]
            }
        ]
        
        context = "Friend John ran 25km this morning"
        result = client.function_call(
            prompt="Check if any friends deserve kudos",
            tools=tools,
            context=context
        )
        
        assert len(result["actions"]) == 1
        assert result["actions"][0]["tool"] == "giveKudos"
        assert result["confidence"] > 0.9
    
    @patch('agent.ollama_client.requests.post')
    def test_scenario_no_action_needed(self, mock_post):
        """Test scenario: AI decides no action is needed."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": json.dumps({
                "reasoning": "No new activities in the last 24 hours. No action needed.",
                "actions": [],
                "confidence": 1.0,
                "requires_approval": False
            })
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = OllamaClient()
        tools = []
        
        result = client.function_call(
            prompt="Check for new activities",
            tools=tools,
            context="No activities found in last 24 hours"
        )
        
        assert result["actions"] == []
        assert "No action needed" in result["reasoning"]
    
    @patch('agent.ollama_client.requests.post')
    def test_scenario_multiple_actions(self, mock_post):
        """Test scenario: AI decides to perform multiple actions."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": json.dumps({
                "reasoning": "Multiple friends had great activities. Give kudos to all.",
                "actions": [
                    {"tool": "giveKudos", "params": {"activity_id": 111}},
                    {"tool": "giveKudos", "params": {"activity_id": 222}},
                    {"tool": "postComment", "params": {"activity_id": 111, "text": "Amazing!"}}
                ],
                "confidence": 0.85,
                "requires_approval": True
            })
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = OllamaClient()
        
        tools = [
            {"name": "giveKudos", "description": "Give kudos"},
            {"name": "postComment", "description": "Post comment"}
        ]
        
        result = client.function_call(
            prompt="Review friend activities",
            tools=tools
        )
        
        assert len(result["actions"]) == 3
        assert result["requires_approval"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
