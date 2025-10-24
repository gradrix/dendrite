"""
Ollama Client for LLM Integration

Handles communication with Ollama API and implements function calling pattern.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

import requests

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API with function calling support."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: int = 60,
        max_retries: int = 3,
        temperature: float = 0.7
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.temperature = temperature
        
    def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        stream: bool = False
    ) -> Union[Dict, requests.Response]:
        """Make HTTP request to Ollama API with retry logic."""
        url = f"{self.base_url}/api/{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    json=data,
                    timeout=self.timeout,
                    stream=stream
                )
                response.raise_for_status()
                
                if stream:
                    return response
                
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
                    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate completion from Ollama.
        
        Args:
            prompt: The user prompt
            system: Optional system prompt
            stream: Whether to stream the response
            **kwargs: Additional parameters (temperature, top_p, etc.)
            
        Returns:
            str: Generated text (if not parsing JSON)
            Dict: Parsed JSON response (if expecting structured output)
        """
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
            }
        }
        
        if system:
            data["system"] = system
            
        # Add any additional options
        for key in ["top_p", "top_k", "num_predict"]:
            if key in kwargs:
                data["options"][key] = kwargs[key]
        
        response = self._make_request("generate", data, stream=stream)
        
        if stream:
            return response
            
        return response.get("response", "")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        Chat completion using Ollama.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters
            
        Returns:
            str: Assistant's response
        """
        data = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
            }
        }
        
        response = self._make_request("chat", data)
        
        return response.get("message", {}).get("content", "")
    
    def function_call(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform function calling with structured output.
        
        Args:
            prompt: The user's request/query
            tools: List of available tools with descriptions
            context: Optional context (previous state, etc.)
            
        Returns:
            Dict with:
                - reasoning: str (why the AI chose these actions)
                - actions: List[Dict] (tool calls to execute)
                - confidence: float (0-1)
                - requires_approval: bool
        """
        # Build tool descriptions
        tool_descriptions = self._format_tools_for_prompt(tools)
        
        # Create system prompt for function calling
        system_prompt = f"""You are an AI agent that helps monitor and interact with Strava activities.

Available tools:
{tool_descriptions}

REQUIRED OUTPUT FORMAT (all fields mandatory):
{{
  "reasoning": "Brief explanation",
  "actions": [{{"tool": "tool_name", "params": {{"key": "value"}}}}],
  "confidence": 0.95,
  "requires_approval": false
}}

ALL 4 FIELDS ARE REQUIRED: reasoning, actions, confidence, requires_approval

PARAM RULES:
- Use ONLY literals: numbers, strings, booleans, null, arrays, objects
- ❌ NO function calls: {{"after_unix": getCurrentDateTime().unix}}
- ✓ YES literals: {{"after_unix": 1729691400}} or {{"hours": 24}}

MULTI-STEP: If you need data from tool A for tool B:
1. Return actions with tool A
2. System executes, calls you again with results
3. Then use those values in tool B

Example: Step 1: [{{"tool": "getCurrentDateTime", "params": {{}}}}] → get timestamp → Step 2: [{{"tool": "getMyActivities", "params": {{"after_unix": 1729691400}}}}]

Rules: Only use listed tools • Set requires_approval=true for writes • Output ONLY JSON
"""
        
        # Add context if provided
        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\nCurrent task:\n{prompt}"
        
        logger.info("Sending function call request to LLM")
        logger.debug(f"Prompt: {full_prompt[:200]}...")
        
        # Get response
        response_text = self.generate(
            prompt=full_prompt,
            system=system_prompt,
            temperature=0.3,  # Lower temperature for more consistent JSON
        )
        
        logger.debug(f"Raw LLM response: {response_text[:500]}...")
        
        # Parse JSON response
        try:
            result = self._parse_json_response(response_text)
            
            # Validate response structure
            if not self._validate_function_call_response(result, tools):
                logger.error(f"Invalid function call response: {result}")
                return self._get_empty_response("Invalid response structure")
                
            logger.info(
                f"Parsed {len(result.get('actions', []))} actions from LLM"
            )
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response was: {response_text}")
            return self._get_empty_response(f"JSON parse error: {e}")
    
    def _format_tools_for_prompt(self, tools: List[Dict[str, Any]]) -> str:
        """Format tool definitions for the LLM prompt."""
        formatted = []
        for tool in tools:
            params_str = ", ".join(
                f"{p['name']}: {p.get('type', 'any')}"
                for p in tool.get("parameters", [])
            )
            formatted.append(
                f"- {tool['name']}({params_str}): {tool['description']}"
            )
        return "\n".join(formatted)
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling markdown code blocks.
        """
        # Remove markdown code blocks if present
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        # Try to find JSON object
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            json_text = text[start_idx:end_idx]
            return json.loads(json_text)
        
        # If no JSON found, try parsing the whole text
        return json.loads(text)
    
    def _validate_function_call_response(
        self,
        response: Dict[str, Any],
        tools: List[Dict[str, Any]]
    ) -> bool:
        """Validate that the response has the correct structure."""
        required_keys = {"reasoning", "actions"}
        missing_keys = required_keys - set(response.keys())
        
        if missing_keys:
            logger.warning(f"Response missing required keys: {missing_keys}")
            return False
        
        # Auto-fill optional fields with defaults if missing
        if "confidence" not in response:
            logger.debug("Auto-filling missing 'confidence' with default 0.8")
            response["confidence"] = 0.8
        
        if "requires_approval" not in response:
            # Check if any write actions - if so, default to requiring approval
            has_write_actions = any(
                any(t["name"] == action.get("tool") and t.get("permissions") == "write" 
                    for t in tools)
                for action in response.get("actions", [])
            )
            response["requires_approval"] = has_write_actions
            logger.debug(f"Auto-filling 'requires_approval' with {has_write_actions} (has_write_actions={has_write_actions})")
        
        # Validate actions
        if not isinstance(response["actions"], list):
            logger.warning(f"Actions is not a list: {type(response['actions'])}")
            return False
        
        # Get valid tool names
        valid_tools = {tool["name"] for tool in tools}
        
        for action in response["actions"]:
            if not isinstance(action, dict):
                return False
            if "tool" not in action:
                return False
            
            # Auto-add empty params if missing (for tools with no parameters)
            if "params" not in action:
                action["params"] = {}
            
            # Check if tool exists
            if action["tool"] not in valid_tools:
                logger.warning(f"Unknown tool requested: {action['tool']}")
                return False
        
        return True
    
    def _get_empty_response(self, reason: str) -> Dict[str, Any]:
        """Return an empty response when parsing fails."""
        return {
            "reasoning": f"Failed to generate valid response: {reason}",
            "actions": [],
            "confidence": 0.0,
            "requires_approval": False
        }
    
    def health_check(self) -> bool:
        """Check if Ollama is accessible and the model is available."""
        try:
            # Check if API is responding
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            
            # Check if our model is available
            models = response.json().get("models", [])
            model_names = [m.get("name") for m in models]
            
            if self.model not in model_names:
                logger.warning(
                    f"Model {self.model} not found. Available: {model_names}"
                )
                return False
            
            logger.info(f"Ollama health check passed. Model: {self.model}")
            return True
            
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
