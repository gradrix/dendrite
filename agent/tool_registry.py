"""
Tool Registry System

Auto-discovers and manages tools for the AI agent.
Provides a decorator-based interface for defining tools that the LLM can call.
"""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Tool:
    """Represents a callable tool for the AI agent."""
    
    def __init__(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: List[Dict[str, Any]],
        returns: str = "any",
        permissions: str = "read"
    ):
        self.name = name
        self.func = func
        self.description = description
        self.parameters = parameters
        self.returns = returns
        self.permissions = permissions  # "read" or "write"
        
    def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        try:
            logger.info(f"Executing tool: {self.name} with params: {kwargs}")
            result = self.func(**kwargs)
            logger.debug(f"Tool {self.name} returned: {result}")
            return result
        except Exception as e:
            logger.error(f"Error executing tool {self.name}: {e}", exc_info=True)
            raise
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary for LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "returns": self.returns,
            "permissions": self.permissions
        }


class ToolRegistry:
    """Registry for managing and discovering tools."""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        
    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
        returns: str = "any",
        permissions: str = "read"
    ) -> Tool:
        """Register a new tool."""
        if parameters is None:
            # Try to infer from function signature
            parameters = self._infer_parameters(func)
        
        tool = Tool(
            name=name,
            func=func,
            description=description,
            parameters=parameters,
            returns=returns,
            permissions=permissions
        )
        
        self.tools[name] = tool
        logger.info(f"Registered tool: {name} ({permissions})")
        return tool
    
    def _infer_parameters(self, func: Callable) -> List[Dict[str, Any]]:
        """Infer parameters from function signature."""
        sig = inspect.signature(func)
        parameters = []
        
        for param_name, param in sig.parameters.items():
            param_info = {
                "name": param_name,
                "type": "any",
                "required": param.default == inspect.Parameter.empty,
            }
            
            # Try to get type from annotation
            if param.annotation != inspect.Parameter.empty:
                param_info["type"] = param.annotation.__name__
            
            # Add default value if present
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
            
            parameters.append(param_info)
        
        return parameters
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self, permissions: Optional[str] = None) -> List[Tool]:
        """List all tools, optionally filtered by permissions."""
        tools = list(self.tools.values())
        
        if permissions:
            tools = [t for t in tools if t.permissions == permissions]
        
        return tools
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get tool schemas for LLM consumption."""
        return [tool.to_dict() for tool in self.tools.values()]
    
    def execute_tool(self, name: str, **kwargs) -> Any:
        """Execute a tool by name with given parameters."""
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        
        return tool.execute(**kwargs)
    
    def discover_tools(self, tools_dir: str = "tools") -> int:
        """
        Auto-discover tools from the tools directory.
        
        Returns:
            int: Number of tools discovered
        """
        tools_path = Path(tools_dir)
        if not tools_path.exists():
            logger.warning(f"Tools directory not found: {tools_dir}")
            return 0
        
        discovered = 0
        
        # Find all Python files in tools directory
        for file_path in tools_path.glob("*.py"):
            if file_path.name.startswith("_"):
                continue  # Skip private modules
            
            module_name = f"{tools_dir}.{file_path.stem}"
            
            try:
                logger.debug(f"Loading module: {module_name}")
                module = importlib.import_module(module_name)
                
                # Look for functions decorated with @tool
                for name, obj in inspect.getmembers(module):
                    if hasattr(obj, "_is_tool"):
                        # This function was decorated with @tool
                        tool_info = obj._tool_info
                        self.register(
                            name=tool_info.get("name", name),
                            func=obj,
                            description=tool_info.get("description", "No description"),
                            parameters=tool_info.get("parameters"),
                            returns=tool_info.get("returns", "any"),
                            permissions=tool_info.get("permissions", "read")
                        )
                        discovered += 1
                        
            except Exception as e:
                logger.error(f"Failed to load tools from {module_name}: {e}")
        
        logger.info(f"Discovered {discovered} tools from {tools_dir}/")
        return discovered


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry


def tool(
    name: Optional[str] = None,
    description: str = "",
    parameters: Optional[List[Dict[str, Any]]] = None,
    returns: str = "any",
    permissions: str = "read"
):
    """
    Decorator to mark a function as a tool.
    
    Example:
        @tool(
            name="get_activities",
            description="Get recent Strava activities",
            returns="List of activities",
            permissions="read"
        )
        def get_my_activities(limit: int = 10):
            # Implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        # Store tool metadata on the function
        func._is_tool = True
        func._tool_info = {
            "name": name or func.__name__,
            "description": description or func.__doc__ or "No description",
            "parameters": parameters,
            "returns": returns,
            "permissions": permissions
        }
        return func
    
    return decorator
