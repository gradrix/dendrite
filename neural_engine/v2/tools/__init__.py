"""
Tool System - Simple tool registration and execution.

Core concepts:
1. Tool - A function that does something (with metadata)
2. ToolRegistry - Registers and discovers tools
3. ToolLoader - Loads tools from Python files

Simple, no magic.
"""

import os
import importlib
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """
    Definition of a tool.
    
    Contains everything needed to discover, select, and call a tool.
    """
    name: str
    description: str
    
    # Parameters
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    required_params: List[str] = field(default_factory=list)
    
    # Semantic metadata for discovery
    domain: str = "general"
    concepts: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    
    # Source info (for loading)
    module_name: Optional[str] = None
    class_name: Optional[str] = None
    
    def to_prompt_text(self) -> str:
        """Format for LLM prompts."""
        params_text = ", ".join([
            f"{p['name']}: {p.get('type', 'any')}" 
            for p in self.parameters
        ])
        return f"- {self.name}({params_text}): {self.description}"


class Tool(ABC):
    """
    Base class for all tools.
    
    Subclasses implement:
    - get_definition(): Return ToolDefinition
    - execute(**kwargs): Run the tool
    
    Example:
        class MyTool(Tool):
            def get_definition(self):
                return ToolDefinition(
                    name="my_tool",
                    description="Does something cool",
                    parameters=[{"name": "input", "type": "string"}],
                )
            
            def execute(self, input: str):
                return {"result": f"Processed: {input}"}
    """
    
    @abstractmethod
    def get_definition(self) -> ToolDefinition:
        """Return tool definition."""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool."""
        pass


class ToolRegistry:
    """
    Registry for tools.
    
    Register tools manually or load from directory.
    
    Usage:
        registry = ToolRegistry()
        registry.register(MyTool())
        registry.load_from_directory("path/to/tools")
        
        tool = registry.get("my_tool")
        result = tool.execute(input="hello")
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._definitions: Dict[str, ToolDefinition] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a single tool."""
        definition = tool.get_definition()
        self._tools[definition.name] = tool
        self._definitions[definition.name] = definition
        logger.info(f"Registered tool: {definition.name}")
    
    def register_function(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: List[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """
        Register a plain function as a tool.
        
        Convenience method for simple tools.
        """
        wrapper = FunctionTool(name, func, description, parameters or [], **kwargs)
        self.register(wrapper)
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def get_definition(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self._definitions.get(name)
    
    def get_all_definitions(self) -> Dict[str, ToolDefinition]:
        """Get all tool definitions."""
        return self._definitions.copy()
    
    def list_tools(self) -> List[str]:
        """List all tool names."""
        return list(self._tools.keys())
    
    def search(
        self,
        query: str,
        domain: str = None,
        limit: int = 10,
    ) -> List[ToolDefinition]:
        """
        Simple keyword-based tool search.
        
        For semantic search, use the full ToolDiscovery system.
        """
        query_lower = query.lower()
        results = []
        
        for name, definition in self._definitions.items():
            score = 0
            
            # Check name
            if query_lower in name.lower():
                score += 3
            
            # Check description
            if query_lower in definition.description.lower():
                score += 2
            
            # Check domain
            if domain and definition.domain == domain:
                score += 1
            
            # Check concepts
            for concept in definition.concepts:
                if query_lower in concept.lower():
                    score += 1
            
            # Check synonyms
            for syn in definition.synonyms:
                if query_lower in syn.lower():
                    score += 1
            
            if score > 0:
                results.append((score, definition))
        
        # Sort by score, return top N
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]
    
    def load_from_directory(
        self,
        directory: str,
        base_class: type = None,
    ) -> int:
        """
        Load all tools from a directory.
        
        Scans for Python files, imports them, and registers any Tool subclasses.
        
        Args:
            directory: Path to scan for tool files
            base_class: Base class to look for (default: Tool)
        
        Returns:
            Number of tools loaded
        """
        if base_class is None:
            base_class = Tool
        
        count = 0
        
        if not os.path.isdir(directory):
            logger.warning(f"Tool directory not found: {directory}")
            return 0
        
        for root, _, files in os.walk(directory):
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                if filename.startswith("_"):
                    continue
                if filename == "base_tool.py":
                    continue
                
                filepath = os.path.join(root, filename)
                loaded = self._load_from_file(filepath, base_class)
                count += loaded
        
        logger.info(f"Loaded {count} tools from {directory}")
        return count
    
    def _load_from_file(self, filepath: str, base_class: type) -> int:
        """Load tools from a single file."""
        # Convert filepath to module name
        module_name = self._filepath_to_module(filepath)
        
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Failed to import {module_name}: {e}")
            return 0
        
        count = 0
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, base_class):
                continue
            if obj is base_class:
                continue
            
            try:
                tool = obj()
                definition = tool.get_definition()
                definition.module_name = module_name
                definition.class_name = name
                self.register(tool)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to instantiate {name}: {e}")
        
        return count
    
    def _filepath_to_module(self, filepath: str) -> str:
        """Convert filepath to module name."""
        if filepath.endswith(".py"):
            filepath = filepath[:-3]
        return filepath.replace("/", ".").replace("\\", ".")


class FunctionTool(Tool):
    """Wrapper to turn a function into a Tool."""
    
    def __init__(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: List[Dict[str, Any]],
        **kwargs,
    ):
        self._name = name
        self._func = func
        self._description = description
        self._parameters = parameters
        self._kwargs = kwargs
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self._name,
            description=self._description,
            parameters=self._parameters,
            **self._kwargs,
        )
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            result = self._func(**kwargs)
            if isinstance(result, dict):
                return result
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}


# Built-in tools that are always available
def create_builtin_tools(config) -> List[Tool]:
    """Create built-in tools."""
    
    tools = []
    
    # Calculator tool
    class CalculatorTool(Tool):
        def get_definition(self):
            return ToolDefinition(
                name="calculate",
                description="Perform mathematical calculations",
                parameters=[
                    {"name": "expression", "type": "string", "description": "Math expression to evaluate"}
                ],
                required_params=["expression"],
                domain="math",
                concepts=["math", "calculation", "arithmetic", "numbers"],
                synonyms=["compute", "evaluate", "what is", "how much"],
            )
        
        def execute(self, expression: str = "", **kwargs):
            try:
                # Safe eval for math only
                result = eval(expression, {"__builtins__": {}}, {})
                return {"result": result, "expression": expression}
            except Exception as e:
                return {"error": f"Calculation error: {e}"}
    
    tools.append(CalculatorTool())
    
    # Memory read tool (sync wrapper around async Redis)
    class MemoryReadTool(Tool):
        def __init__(self, cfg):
            self._config = cfg
            self._redis = None
        
        def get_definition(self):
            return ToolDefinition(
                name="memory_read",
                description="Read stored information from memory",
                parameters=[
                    {"name": "key", "type": "string", "description": "Key to look up"}
                ],
                required_params=["key"],
                domain="memory",
                concepts=["recall", "remember", "retrieve", "lookup"],
                synonyms=["what is my", "do you remember", "tell me"],
            )
        
        def execute(self, key: str = "", **kwargs):
            import redis as sync_redis
            
            try:
                # Use sync redis directly (simpler for tool execution)
                r = sync_redis.Redis(
                    host=self._config.redis_host, 
                    port=self._config.redis_port,
                    decode_responses=True
                )
                value = r.get(f"memory:{key}")
                r.close()
                
                if value:
                    return {"key": key, "value": value}
                return {"error": f"No value found for key: {key}"}
            except Exception as e:
                return {"error": str(e)}
    
    tools.append(MemoryReadTool(config))
    
    # Memory write tool
    class MemoryWriteTool(Tool):
        def __init__(self, cfg):
            self._config = cfg
        
        def get_definition(self):
            return ToolDefinition(
                name="memory_write",
                description="Store information in memory for later recall",
                parameters=[
                    {"name": "key", "type": "string", "description": "Key to store under"},
                    {"name": "value", "type": "string", "description": "Value to store"},
                ],
                required_params=["key", "value"],
                domain="memory",
                concepts=["store", "save", "remember", "persist"],
                synonyms=["remember that", "my name is", "save this"],
            )
        
        def execute(self, key: str = "", value: str = "", **kwargs):
            import redis as sync_redis
            
            try:
                r = sync_redis.Redis(
                    host=self._config.redis_host,
                    port=self._config.redis_port,
                    decode_responses=True
                )
                r.set(f"memory:{key}", value)
                r.close()
                return {"key": key, "value": value, "status": "stored"}
            except Exception as e:
                return {"error": str(e)}
    
    tools.append(MemoryWriteTool(config))
    
    return tools
