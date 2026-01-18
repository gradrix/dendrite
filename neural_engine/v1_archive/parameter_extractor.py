"""
Parameter Extractor - Specialized LLM for extracting tool parameters from user goals.

This specialist focuses ONLY on identifying what values should be passed to tool parameters,
preventing the common issue where code generation confuses keys with values.

Example:
  Goal: "Remember that my favorite color is blue"
  Tool: memory_write(key, value)
  Extractor identifies: key="favorite_color", value="blue"
  
Without extractor, LLM might generate: memory_write("user preference", "your favorite color")

ARCHITECTURE PRINCIPLES:
- NO hardcoded regex patterns with natural language
- LLM parses everything dynamically
- If LLM fails, decompose problem and retry
- Cache successful extractions for learning
"""

from typing import Dict, List, Optional
import json
import hashlib


class ParameterExtractor:
    """
    Extracts parameter values from user goals for specific tools.
    
    Uses focused LLM prompts to identify exactly what values should be
    passed to each parameter of a tool.
    """
    
    def __init__(self, ollama_client):
        """
        Initialize parameter extractor.
        
        Args:
            ollama_client: OllamaClient for LLM inference
        """
        self.ollama_client = ollama_client
    
    def extract_parameters(self, goal: str, tool_name: str, tool_description: str, 
                          parameters: List[str]) -> Dict[str, str]:
        """
        Extract parameter values from goal for a specific tool.
        
        Args:
            goal: User goal text
            tool_name: Name of the tool
            tool_description: Description of what the tool does
            parameters: List of parameter names (e.g., ["key", "value"])
        
        Returns:
            Dict mapping parameter names to extracted values
            Example: {"key": "favorite_color", "value": "blue"}
        """
        if not parameters:
            return {}
        
        # Build extraction prompt
        prompt = self._build_extraction_prompt(goal, tool_name, tool_description, parameters)
        
        # Get LLM response using generate()
        response = self.ollama_client.generate(prompt=prompt, check_tokens=False)
        response_text = response['response']
        
        # Parse response
        extracted = self._parse_extraction(response_text, parameters)
        
        return extracted
    
    def _build_extraction_prompt(self, goal: str, tool_name: str, 
                                 tool_description: str, parameters: List[str]) -> str:
        """
        Build prompt for parameter extraction.
        
        Minimal prompt using ONLY the tool description and parameter names.
        No hardcoded examples - let the LLM figure it out from the tool description.
        """
        params_list = ", ".join([f'"{p}"' for p in parameters])
        
        prompt = f"""Extract parameter values from user goal for this tool.

User Goal: "{goal}"

Tool: {tool_name}
Tool Description: {tool_description}
Required Parameters: {params_list}

Read the tool description carefully. It tells you what this tool does and what each parameter means.
Extract the EXACT values from the user's goal that should be passed to each parameter.

Respond in this format (one line per parameter):
parameter_name: extracted_value

Your response:"""
        
        return prompt
    
    def _parse_extraction(self, response: str, parameters: List[str]) -> Dict[str, str]:
        """
        Parse LLM response to extract parameter values.
        
        Args:
            response: LLM response with format "param: value"
            parameters: Expected parameter names
        
        Returns:
            Dict mapping parameters to values
        """
        result = {}
        
        # Parse line by line
        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            # Split on first colon
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            
            param_name = parts[0].strip().lower()
            param_value = parts[1].strip()
            
            # Remove quotes if present
            param_value = param_value.strip('"\'')
            
            # Check if this is one of our expected parameters
            if param_name in [p.lower() for p in parameters]:
                # Find original case parameter name
                for p in parameters:
                    if p.lower() == param_name:
                        result[p] = param_value
                        break
        
        # Fill in missing parameters with fallback values
        for param in parameters:
            if param not in result:
                # Try to extract something reasonable
                result[param] = self._fallback_extraction(param)
        
        return result
    
    def _fallback_extraction(self, parameter: str) -> str:
        """
        Fallback value when extraction fails.
        
        Args:
            parameter: Parameter name
        
        Returns:
            Safe fallback value
        """
        # Common fallbacks
        fallbacks = {
            "key": "data",
            "value": "None",
            "a": "0",
            "b": "0",
            "x": "0",
            "y": "0",
            "n": "1",
            "text": "",
            "message": "",
            "name": "unknown"
        }
        
        return fallbacks.get(parameter.lower(), "None")
    
    def create_parameter_hints(self, extracted: Dict[str, str]) -> str:
        """
        Create hints for code generator about extracted parameters.
        
        Args:
            extracted: Extracted parameter values
        
        Returns:
            Formatted hint string for code generator
        """
        if not extracted:
            return ""
        
        hints = []
        for param, value in extracted.items():
            # Mark extracted values with [] as suggested by user
            hints.append(f'{param}=[{value}]')
        
        hint_str = ", ".join(hints)
        return f"EXTRACTED PARAMETERS: {hint_str}"


class MemoryParameterExtractor:
    """
    LLM-based extractor for memory operations.
    
    NO regex patterns - uses LLM to parse dynamically.
    If LLM fails, decomposes problem and retries.
    Caches successful extractions for learning.
    """
    
    # In-memory cache for successful extractions (could be Redis later)
    _extraction_cache: Dict[str, Dict[str, str]] = {}
    
    def __init__(self, ollama_client=None):
        """
        Initialize memory parameter extractor.
        
        Args:
            ollama_client: LLM client for dynamic parsing
        """
        self.ollama_client = ollama_client
    
    def _cache_key(self, goal: str, operation: str) -> str:
        """Generate cache key for goal+operation."""
        return hashlib.md5(f"{operation}:{goal}".encode()).hexdigest()
    
    def _check_cache(self, goal: str, operation: str) -> Optional[Dict[str, str]]:
        """Check if we have a cached extraction for this goal."""
        key = self._cache_key(goal, operation)
        return self._extraction_cache.get(key)
    
    def _save_to_cache(self, goal: str, operation: str, result: Dict[str, str]):
        """Save successful extraction to cache."""
        key = self._cache_key(goal, operation)
        self._extraction_cache[key] = result
    
    def extract_memory_write_params(self, goal: str) -> Dict[str, str]:
        """
        Extract key and value for memory write operations using LLM.
        
        Args:
            goal: User goal like "Remember that my name is Alice"
        
        Returns:
            {"key": "user_name", "value": "Alice"}
        """
        # Check cache first
        cached = self._check_cache(goal, "write")
        if cached:
            return cached
        
        # If no LLM client, return fallback
        if not self.ollama_client:
            return {"key": "data", "value": goal}
        
        # Try LLM extraction with focused prompt
        result = self._extract_with_llm(goal, "write", max_retries=2)
        
        # Cache successful extraction
        if result.get("key") != "data":
            self._save_to_cache(goal, "write", result)
        
        return result
    
    def extract_memory_read_params(self, goal: str) -> Dict[str, str]:
        """
        Extract key for memory read operations using LLM.
        
        Args:
            goal: User goal like "What is my name?"
        
        Returns:
            {"key": "user_name"}
        """
        # Check cache first
        cached = self._check_cache(goal, "read")
        if cached:
            return cached
        
        # If no LLM client, return fallback
        if not self.ollama_client:
            return {"key": "data"}
        
        # Try LLM extraction
        result = self._extract_with_llm(goal, "read", max_retries=2)
        
        # Cache successful extraction
        if result.get("key") != "data":
            self._save_to_cache(goal, "read", result)
        
        return result
    
    def _extract_with_llm(self, goal: str, operation: str, max_retries: int = 2) -> Dict[str, str]:
        """
        Use LLM to extract parameters with retry on failure.
        
        Args:
            goal: User goal text
            operation: "read" or "write"
            max_retries: Number of retries with decomposed prompts
        
        Returns:
            Extracted parameters
        """
        for attempt in range(max_retries + 1):
            prompt = self._build_extraction_prompt(goal, operation, attempt)
            
            try:
                response = self.ollama_client.generate(
                    prompt=prompt, 
                    check_tokens=False,
                    options={"temperature": 0}  # Deterministic for extraction
                )
                response_text = response.get('response', '')
                
                result = self._parse_llm_response(response_text, operation)
                
                # Validate result
                if self._is_valid_extraction(result, operation):
                    return result
                    
            except Exception as e:
                # Log error but continue to retry
                pass
        
        # Fallback after all retries
        if operation == "write":
            return {"key": "data", "value": goal}
        else:
            return {"key": "data"}
    
    def _build_extraction_prompt(self, goal: str, operation: str, attempt: int) -> str:
        """
        Build extraction prompt. More detailed prompts for retries.
        
        Args:
            goal: User goal
            operation: "read" or "write"
            attempt: Retry attempt number (0 = first try)
        """
        if operation == "write":
            if attempt == 0:
                # First attempt - simple prompt
                return f"""Extract key and value from this goal for storing in memory.

Goal: "{goal}"

The KEY should be a short identifier (like "favorite_color" or "user_name").
The VALUE should be the actual data to store (like "blue" or "Alice").

Respond ONLY with:
key: <the key>
value: <the value>"""
            else:
                # Retry - more explicit decomposition
                return f"""I need to extract parameters from this user goal for a memory storage operation.

Goal: "{goal}"

Step 1: What information does the user want to store? (the VALUE)
Step 2: What should we call this information? (the KEY - a short snake_case identifier)

Think step by step, then respond with ONLY:
key: <your answer>
value: <your answer>"""
        else:  # read
            if attempt == 0:
                return f"""Extract the key from this goal for reading from memory.

Goal: "{goal}"

The KEY should be a short identifier for what the user wants to retrieve (like "favorite_color" or "name").

Respond ONLY with:
key: <the key>"""
            else:
                return f"""I need to identify what information the user wants to retrieve from memory.

Goal: "{goal}"

Step 1: What is the user asking about?
Step 2: What would be a good snake_case key for this? (like "favorite_color", "name", "age")

Think step by step, then respond with ONLY:
key: <your answer>"""
    
    def _parse_llm_response(self, response: str, operation: str) -> Dict[str, str]:
        """Parse LLM response to extract key/value."""
        result = {}
        
        for line in response.strip().split('\n'):
            line = line.strip()
            if ':' not in line:
                continue
            
            parts = line.split(':', 1)
            param = parts[0].strip().lower()
            value = parts[1].strip().strip('"\'')
            
            if param == 'key':
                # Clean up key - make it snake_case
                result['key'] = value.replace(' ', '_').replace('-', '_').lower()
            elif param == 'value' and operation == 'write':
                result['value'] = value
        
        return result
    
    def _is_valid_extraction(self, result: Dict[str, str], operation: str) -> bool:
        """Check if extraction result is valid."""
        if not result.get('key') or result['key'] == 'data':
            return False
        
        if operation == 'write' and not result.get('value'):
            return False
        
        return True
