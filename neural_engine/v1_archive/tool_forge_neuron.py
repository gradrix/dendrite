"""
ToolForgeNeuron: AI-Powered Tool Creation

This neuron enables the system to create new tools dynamically based on user requests.
When a user asks for functionality that doesn't exist, ToolForge:
1. Generates Python code for a new tool class
2. Validates the generated code
3. Writes the tool file to disk
4. Refreshes the ToolRegistry to load the new tool

This allows the system to evolve and extend its own capabilities autonomously.
"""

from .neuron import BaseNeuron, fractal_process
import re
import os


class ToolForgeNeuron(BaseNeuron):
    """Neuron that generates new tools based on natural language descriptions."""
    
    def __init__(self, message_bus, ollama_client, tool_registry):
        super().__init__(message_bus, ollama_client)
        self.tool_registry = tool_registry
        self.tools_directory = "neural_engine/tools"
    
    def _load_prompt(self):
        """Load the tool forge prompt template."""
        with open("neural_engine/prompts/tool_forge_prompt.txt", "r") as f:
            return f.read()
    
    def _extract_code_from_response(self, response_text: str) -> str:
        """Extract Python code from LLM response (handles markdown wrappers)."""
        # Remove markdown code blocks if present
        if "```python" in response_text:
            # Extract content between ```python and ```
            match = re.search(r'```python\s*\n(.*?)```', response_text, re.DOTALL)
            if match:
                return match.group(1).strip()
        elif "```" in response_text:
            # Extract content between ``` and ```
            match = re.search(r'```\s*\n(.*?)```', response_text, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # If no markdown wrapper, return as-is
        return response_text.strip()
    
    def _extract_tool_name(self, code: str) -> str:
        """Extract the tool class name from generated code."""
        # Look for class definition
        match = re.search(r'class\s+(\w+Tool)\s*\(', code)
        if match:
            return match.group(1)
        raise ValueError("Could not find tool class name in generated code")
    
    def _validate_tool_code(self, code: str) -> dict:
        """Validate that generated code meets requirements.
        
        Returns:
            dict: {"valid": bool, "errors": list of str}
        """
        errors = []
        
        # Check for BaseTool import
        if "from neural_engine.tools.base_tool import BaseTool" not in code:
            errors.append("Missing BaseTool import")
        
        # Check for class definition ending in Tool
        if not re.search(r'class\s+\w+Tool\s*\(', code):
            errors.append("Class name must end with 'Tool'")
        
        # Check for BaseTool inheritance
        if "BaseTool" not in code or not re.search(r'class\s+\w+Tool\s*\(\s*BaseTool\s*\)', code):
            errors.append("Class must inherit from BaseTool")
        
        # Check for get_tool_definition method
        if "def get_tool_definition(self)" not in code:
            errors.append("Missing get_tool_definition() method")
        
        # Check for execute method
        if "def execute(self" not in code:
            errors.append("Missing execute() method")
        
        # Check for **kwargs in execute
        if "def execute(self, **kwargs)" not in code:
            errors.append("execute() must accept **kwargs")
        
        # Try to compile the code
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _generate_filename(self, tool_class_name: str) -> str:
        """Convert ToolClassName to tool_class_name_tool.py"""
        # Convert CamelCase to snake_case
        snake_case = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', tool_class_name).lower()
        
        # Ensure it ends with _tool.py
        if not snake_case.endswith('_tool'):
            snake_case += '_tool'
        
        return f"{snake_case}.py"
    
    def _write_tool_file(self, code: str, filename: str) -> str:
        """Write tool code to file.
        
        Returns:
            str: Full path to written file
        """
        filepath = os.path.join(self.tools_directory, filename)
        
        with open(filepath, 'w') as f:
            f.write(code)
        
        return filepath
    
    @fractal_process
    def process(self, goal_id: str, data: dict, depth: int = 0):
        """Generate a new tool based on the user's goal.
        
        Args:
            goal_id: Unique identifier for this request
            data: Dict containing "goal" (the tool creation request)
            depth: Recursion depth
            
        Returns:
            dict: {
                "success": bool,
                "tool_name": str (if successful),
                "tool_class": str (if successful),
                "filepath": str (if successful),
                "code": str (generated code),
                "error": str (if failed),
                "validation_errors": list (if validation failed)
            }
        """
        goal = data.get("goal", "")
        
        # Load prompt and generate tool code
        prompt_template = self._load_prompt()
        prompt = prompt_template.format(goal=goal)
        
        # Generate code using LLM
        response = self.ollama_client.generate(prompt=prompt)
        raw_response = response['response']
        
        # Extract clean code
        code = self._extract_code_from_response(raw_response)
        
        # Validate code
        validation = self._validate_tool_code(code)
        
        if not validation["valid"]:
            result = {
                "success": False,
                "code": code,
                "error": "Code validation failed",
                "validation_errors": validation["errors"]
            }
            
            # Store failure in message bus
            self.add_message_with_metadata(
                goal_id=goal_id,
                message_type="tool_forge",
                data=result,
                depth=depth
            )
            
            return result
        
        try:
            # Extract tool name and generate filename
            tool_class_name = self._extract_tool_name(code)
            filename = self._generate_filename(tool_class_name)
            
            # Write tool to file
            filepath = self._write_tool_file(code, filename)
            
            # Refresh tool registry to load new tool
            self.tool_registry.refresh()
            
            # Extract tool name from definition (snake_case without Tool suffix)
            # We'll get it from the registry after refresh
            all_tools = self.tool_registry.get_all_tool_definitions()
            
            # Find the newly added tool by checking which one has our class name
            tool_name = None
            for name, definition in all_tools.items():
                if definition.get("class_name") == tool_class_name:
                    tool_name = name
                    break
            
            if not tool_name:
                # Fallback: convert class name to snake_case and remove _tool suffix
                tool_name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', tool_class_name).lower()
                tool_name = tool_name.replace('_tool', '')
            
            result = {
                "success": True,
                "tool_name": tool_name,
                "tool_class": tool_class_name,
                "filepath": filepath,
                "code": code
            }
            
            # Store success in message bus
            self.add_message_with_metadata(
                goal_id=goal_id,
                message_type="tool_forge",
                data=result,
                depth=depth
            )
            
            return result
            
        except Exception as e:
            result = {
                "success": False,
                "code": code,
                "error": str(e)
            }
            
            # Store failure in message bus
            self.add_message_with_metadata(
                goal_id=goal_id,
                message_type="tool_forge",
                data=result,
                depth=depth
            )
            
            return result
