"""
Parameter Extractor - Specialized LLM for extracting tool parameters from user goals.

This specialist focuses ONLY on identifying what values should be passed to tool parameters,
preventing the common issue where code generation confuses keys with values.

Example:
  Goal: "Remember that my favorite color is blue"
  Tool: memory_write(key, value)
  Extractor identifies: key="favorite_color", value="blue"
  
Without extractor, LLM might generate: memory_write("user preference", "your favorite color")
"""

from typing import Dict, List, Optional
import json
import re


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
        
        # Get LLM response
        response = self.ollama_client.generate(
            prompt=prompt,
            temperature=0,  # Deterministic
            max_tokens=300
        )
        
        # Parse response
        extracted = self._parse_extraction(response, parameters)
        
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
    Specialized extractor for memory operations (most common failure case).
    
    Uses pattern matching and simple heuristics for fast, accurate extraction
    without needing LLM calls for every memory operation.
    """
    
    def __init__(self):
        """Initialize memory parameter extractor."""
        pass
    
    def extract_memory_write_params(self, goal: str) -> Dict[str, str]:
        """
        Extract key and value for memory write operations.
        
        Args:
            goal: User goal like "Remember that my name is Alice"
        
        Returns:
            {"key": "user_name", "value": "Alice"}
        """
        goal_lower = goal.lower()
        
        # Pattern: "remember that my X is Y"
        pattern1 = r"remember\s+that\s+my\s+(\w+(?:\s+\w+)?)\s+is\s+(.+?)(?:\.|$)"
        match = re.search(pattern1, goal_lower, re.IGNORECASE)
        if match:
            key = match.group(1).strip().replace(' ', '_')
            value = match.group(2).strip()
            # Extract original case value from goal
            value_start = match.start(2)
            original_value = goal[value_start:value_start+len(value)]
            return {"key": key, "value": original_value.strip()}
        
        # Pattern: "store X" or "save X"
        pattern2 = r"(?:store|save|remember)\s+(?:that\s+)?(?:the\s+)?(.+?)(?:\s+(?:as|for|in)\s+(.+?))?(?:\.|$)"
        match = re.search(pattern2, goal_lower, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            key = match.group(2).strip() if match.group(2) else "data"
            # Get original case
            value_start = match.start(1)
            original_value = goal[value_start:value_start+len(value)]
            return {"key": key.replace(' ', '_'), "value": original_value.strip()}
        
        # Pattern: "my X is Y" (without "remember")
        pattern3 = r"my\s+(\w+(?:\s+\w+)?)\s+is\s+(.+?)(?:\.|$)"
        match = re.search(pattern3, goal_lower, re.IGNORECASE)
        if match:
            key = match.group(1).strip().replace(' ', '_')
            value = match.group(2).strip()
            value_start = match.start(2)
            original_value = goal[value_start:value_start+len(value)]
            return {"key": key, "value": original_value.strip()}
        
        # Fallback: couldn't extract clearly
        return {"key": "data", "value": goal}
    
    def extract_memory_read_params(self, goal: str) -> Dict[str, str]:
        """
        Extract key for memory read operations.
        
        Args:
            goal: User goal like "What is my name?"
        
        Returns:
            {"key": "user_name"}
        """
        goal_lower = goal.lower()
        
        # Pattern: "what is my X"
        pattern1 = r"what\s+(?:is|was|'s)\s+my\s+(\w+(?:\s+\w+)?)"
        match = re.search(pattern1, goal_lower, re.IGNORECASE)
        if match:
            key = match.group(1).strip().replace(' ', '_')
            return {"key": key}
        
        # Pattern: "what did I tell you about X"
        pattern2 = r"what\s+did\s+i\s+(?:tell|say)\s+(?:you\s+)?about\s+(?:my\s+)?(\w+(?:\s+\w+)?)"
        match = re.search(pattern2, goal_lower, re.IGNORECASE)
        if match:
            key = match.group(1).strip().replace(' ', '_')
            return {"key": key}
        
        # Pattern: "recall X"
        pattern3 = r"(?:recall|retrieve|get)\s+(?:my\s+)?(\w+(?:\s+\w+)?)"
        match = re.search(pattern3, goal_lower, re.IGNORECASE)
        if match:
            key = match.group(1).strip().replace(' ', '_')
            return {"key": key}
        
        # Fallback
        return {"key": "data"}
