"""
Tool Forge - Dynamic Tool Creation and Lifecycle Management

Creates tools on-demand when no existing tool can handle a request.
Tracks tool performance and manages lifecycle (create, test, refactor, retire).

Key Features:
1. Create tools from natural language descriptions
2. Generate Python code with proper Tool interface
3. Validate generated code before registration
4. Track tool usage and success rates
5. Refactor or retire underperforming tools
"""

import re
import ast
import json
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Callable

from ..core import LLMClient, Config
from ..tools import Tool, ToolDefinition, ToolRegistry

logger = logging.getLogger(__name__)


class ToolStatus(Enum):
    """Lifecycle status of a forged tool."""
    DRAFT = "draft"           # Just created, not tested
    TESTING = "testing"       # Being validated
    ACTIVE = "active"         # In production use
    DEGRADED = "degraded"     # High failure rate
    RETIRED = "retired"       # No longer used


@dataclass
class ToolPerformance:
    """Performance metrics for a tool."""
    tool_name: str
    created_at: datetime = field(default_factory=datetime.now)
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: int = 0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    status: ToolStatus = ToolStatus.DRAFT
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls
    
    @property
    def avg_duration_ms(self) -> float:
        """Average execution duration in milliseconds."""
        if self.successful_calls == 0:
            return 0.0
        return self.total_duration_ms / self.successful_calls
    
    def record_success(self, duration_ms: int):
        """Record a successful execution."""
        self.total_calls += 1
        self.successful_calls += 1
        self.total_duration_ms += duration_ms
        self.last_used = datetime.now()
        
        # Upgrade from testing to active after 3 successes
        if self.status == ToolStatus.TESTING and self.successful_calls >= 3:
            self.status = ToolStatus.ACTIVE
    
    def record_failure(self, error: str):
        """Record a failed execution."""
        self.total_calls += 1
        self.failed_calls += 1
        self.last_used = datetime.now()
        self.last_error = error
        
        # Degrade if failure rate is too high
        if self.total_calls >= 5 and self.success_rate < 0.5:
            self.status = ToolStatus.DEGRADED
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "tool_name": self.tool_name,
            "created_at": self.created_at.isoformat(),
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "total_duration_ms": self.total_duration_ms,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "last_error": self.last_error,
            "status": self.status.value,
            "success_rate": self.success_rate,
            "avg_duration_ms": self.avg_duration_ms,
        }


@dataclass
class ForgedTool:
    """A dynamically created tool."""
    name: str
    description: str
    code: str
    parameters: List[Dict[str, Any]]
    domain: str = "general"
    concepts: List[str] = field(default_factory=list)
    created_by: str = "forge"
    created_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    
    @property
    def code_hash(self) -> str:
        """Hash of the code for version tracking."""
        return hashlib.sha256(self.code.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "name": self.name,
            "description": self.description,
            "code": self.code,
            "parameters": self.parameters,
            "domain": self.domain,
            "concepts": self.concepts,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "code_hash": self.code_hash,
        }


# Prompt for generating tool code
TOOL_FORGE_PROMPT = """Create a Python tool class for this capability.

Capability needed: {capability}
User's original request: {request}

The tool MUST:
1. Inherit from Tool base class
2. Implement get_definition() returning ToolDefinition
3. Implement execute(**kwargs) returning Dict[str, Any]
4. Handle errors gracefully (return {{"error": "message"}} on failure)
5. Use only standard library or common packages (requests, json, etc.)

Template:
```python
from neural_engine.v2.tools import Tool, ToolDefinition

class {class_name}(Tool):
    def __init__(self, config):
        self._config = config
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="{tool_name}",
            description="...",
            parameters=[
                {{"name": "param1", "type": "string", "description": "..."}},
            ],
            required_params=["param1"],
            domain="...",
            concepts=[...],
        )
    
    def execute(self, **kwargs) -> dict:
        try:
            # Implementation here
            return {{"result": ...}}
        except Exception as e:
            return {{"error": str(e)}}
```

Respond with ONLY the Python code, no explanation."""


# Prompt for extracting tool definition from code
TOOL_DEFINITION_PROMPT = """Extract the tool definition from this code.

Code:
```python
{code}
```

Respond with JSON:
{{
    "name": "tool_name",
    "description": "what the tool does",
    "parameters": [
        {{"name": "param1", "type": "string", "description": "..."}}
    ],
    "required_params": ["param1"],
    "domain": "general",
    "concepts": ["concept1", "concept2"]
}}"""


class ToolForge:
    """
    Dynamic tool creation and lifecycle management.
    
    Features:
    - Generate tools from natural language descriptions
    - Validate generated code before registration
    - Track tool performance and usage
    - Refactor or retire underperforming tools
    
    Usage:
        forge = ToolForge(config, registry)
        
        # Create a new tool
        tool = await forge.create_tool(
            capability="Get weather for a city",
            request="What's the weather in London?"
        )
        
        # Register it
        registry.register(tool)
        
        # Track performance
        forge.record_success("weather_tool", duration_ms=150)
        forge.record_failure("weather_tool", "API timeout")
        
        # Get metrics
        perf = forge.get_performance("weather_tool")
    """
    
    def __init__(self, config: Config, registry: ToolRegistry):
        self.config = config
        self.registry = registry
        self.llm = LLMClient(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
            model=config.llm_model,
        )
        
        # Track performance for all tools
        self._performance: Dict[str, ToolPerformance] = {}
        
        # Store forged tools (for persistence)
        self._forged_tools: Dict[str, ForgedTool] = {}
    
    async def create_tool(
        self,
        capability: str,
        request: str,
        domain: str = "general",
    ) -> Optional[Tool]:
        """
        Create a new tool from a capability description.
        
        Args:
            capability: What the tool should do
            request: Original user request that triggered creation
            domain: Tool domain for categorization
        
        Returns:
            Tool instance if successful, None if generation failed
        """
        # Generate tool name and class name
        tool_name = self._generate_tool_name(capability)
        class_name = self._to_class_name(tool_name)
        
        # Check if tool already exists
        if self.registry.get(tool_name):
            logger.info(f"Tool {tool_name} already exists")
            return self.registry.get(tool_name)
        
        # Generate tool code
        prompt = TOOL_FORGE_PROMPT.format(
            capability=capability,
            request=request,
            class_name=class_name,
            tool_name=tool_name,
        )
        
        try:
            code = await self.llm.generate(prompt)
            code = self._extract_code(code)
            
            if not code:
                logger.error("Failed to generate tool code")
                return None
            
            # Validate the code
            if not self._validate_code(code):
                logger.error("Generated code failed validation")
                return None
            
            # Extract definition from generated code
            definition = await self._extract_definition(code)
            if not definition:
                logger.error("Failed to extract tool definition")
                return None
            
            # Create ForgedTool record
            forged = ForgedTool(
                name=definition["name"],
                description=definition["description"],
                code=code,
                parameters=definition.get("parameters", []),
                domain=domain,
                concepts=definition.get("concepts", []),
            )
            
            # Create actual Tool instance
            tool = self._instantiate_tool(code, class_name)
            if not tool:
                logger.error("Failed to instantiate tool")
                return None
            
            # Store and track
            self._forged_tools[forged.name] = forged
            self._performance[forged.name] = ToolPerformance(
                tool_name=forged.name,
                status=ToolStatus.TESTING,
            )
            
            logger.info(f"Created new tool: {forged.name}")
            return tool
            
        except Exception as e:
            logger.error(f"Tool creation failed: {e}")
            return None
    
    def _generate_tool_name(self, capability: str) -> str:
        """Generate a tool name from capability description."""
        # Extract key words and create snake_case name
        words = re.findall(r'\w+', capability.lower())
        
        # Remove common words
        stop_words = {'a', 'an', 'the', 'for', 'to', 'from', 'in', 'on', 'get', 'do'}
        words = [w for w in words if w not in stop_words][:4]
        
        if not words:
            words = ["custom_tool"]
        
        return "_".join(words)
    
    def _to_class_name(self, tool_name: str) -> str:
        """Convert snake_case to PascalCase."""
        return "".join(word.capitalize() for word in tool_name.split("_")) + "Tool"
    
    def _extract_code(self, response: str) -> Optional[str]:
        """Extract Python code from LLM response."""
        # Try to find code block
        code_match = re.search(r'```python\n(.*?)```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # Try plain code block
        code_match = re.search(r'```\n(.*?)```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # If response looks like code, use it directly
        if "class " in response and "def " in response:
            return response.strip()
        
        return None
    
    def _validate_code(self, code: str) -> bool:
        """Validate that generated code is safe and correct."""
        try:
            # Parse AST to check syntax
            tree = ast.parse(code)
            
            # Check for required elements
            has_class = False
            has_get_definition = False
            has_execute = False
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    has_class = True
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            if item.name == "get_definition":
                                has_get_definition = True
                            elif item.name == "execute":
                                has_execute = True
            
            if not (has_class and has_get_definition and has_execute):
                logger.warning("Code missing required Tool interface elements")
                return False
            
            # Check for dangerous imports/operations
            dangerous = ['os.system', 'subprocess', 'eval(', 'exec(', '__import__']
            for danger in dangerous:
                if danger in code:
                    logger.warning(f"Code contains dangerous pattern: {danger}")
                    return False
            
            return True
            
        except SyntaxError as e:
            logger.warning(f"Code has syntax error: {e}")
            return False
    
    async def _extract_definition(self, code: str) -> Optional[Dict[str, Any]]:
        """Extract tool definition from generated code."""
        prompt = TOOL_DEFINITION_PROMPT.format(code=code)
        
        try:
            definition = await self.llm.generate_json(prompt)
            return definition
        except Exception as e:
            logger.error(f"Failed to extract definition: {e}")
            return None
    
    def _instantiate_tool(self, code: str, class_name: str) -> Optional[Tool]:
        """Instantiate a Tool from generated code."""
        try:
            # Create a module namespace
            namespace = {
                "Tool": Tool,
                "ToolDefinition": ToolDefinition,
            }
            
            # Execute the code to define the class
            exec(code, namespace)
            
            # Get the class and instantiate
            tool_class = namespace.get(class_name)
            if not tool_class:
                # Try to find any Tool subclass
                for name, obj in namespace.items():
                    if isinstance(obj, type) and issubclass(obj, Tool) and obj is not Tool:
                        tool_class = obj
                        break
            
            if tool_class:
                return tool_class(self.config)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to instantiate tool: {e}")
            return None
    
    # Performance tracking
    def record_success(self, tool_name: str, duration_ms: int):
        """Record a successful tool execution."""
        if tool_name not in self._performance:
            self._performance[tool_name] = ToolPerformance(tool_name=tool_name)
        self._performance[tool_name].record_success(duration_ms)
    
    def record_failure(self, tool_name: str, error: str):
        """Record a failed tool execution."""
        if tool_name not in self._performance:
            self._performance[tool_name] = ToolPerformance(tool_name=tool_name)
        self._performance[tool_name].record_failure(error)
    
    def get_performance(self, tool_name: str) -> Optional[ToolPerformance]:
        """Get performance metrics for a tool."""
        return self._performance.get(tool_name)
    
    def get_all_performance(self) -> Dict[str, ToolPerformance]:
        """Get performance metrics for all tracked tools."""
        return self._performance.copy()
    
    def get_degraded_tools(self) -> List[str]:
        """Get list of tools with degraded status."""
        return [
            name for name, perf in self._performance.items()
            if perf.status == ToolStatus.DEGRADED
        ]
    
    def retire_tool(self, tool_name: str) -> bool:
        """Retire a tool (mark as inactive, optionally remove from registry)."""
        if tool_name in self._performance:
            self._performance[tool_name].status = ToolStatus.RETIRED
            logger.info(f"Retired tool: {tool_name}")
            return True
        return False
    
    def get_forged_tool(self, tool_name: str) -> Optional[ForgedTool]:
        """Get a forged tool's definition and code."""
        return self._forged_tools.get(tool_name)
    
    def list_forged_tools(self) -> List[str]:
        """List all forged tool names."""
        return list(self._forged_tools.keys())
    
    # Persistence
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for persistence."""
        return {
            "forged_tools": {
                name: tool.to_dict() 
                for name, tool in self._forged_tools.items()
            },
            "performance": {
                name: perf.to_dict()
                for name, perf in self._performance.items()
            },
        }
    
    def _get_redis(self):
        """Get Redis client."""
        import redis
        return redis.Redis(
            host=self.config.redis_host,
            port=self.config.redis_port,
            decode_responses=True,
        )
    
    def save_to_redis(self) -> bool:
        """Save forge state to Redis for persistence across restarts."""
        try:
            r = self._get_redis()
            data = json.dumps(self.to_dict())
            r.set("forge:state", data)
            r.close()
            logger.info(f"Saved forge state ({len(self._forged_tools)} tools, {len(self._performance)} perf records)")
            return True
        except Exception as e:
            logger.error(f"Failed to save forge state: {e}")
            return False
    
    def load_from_redis(self) -> bool:
        """Load forge state from Redis, reinstantiate saved tools."""
        try:
            r = self._get_redis()
            data_str = r.get("forge:state")
            r.close()
            
            if not data_str:
                logger.info("No saved forge state found")
                return False
            
            data = json.loads(data_str)
            
            # Restore forged tools
            for name, tool_data in data.get("forged_tools", {}).items():
                forged = ForgedTool(
                    name=tool_data["name"],
                    description=tool_data["description"],
                    code=tool_data["code"],
                    parameters=tool_data.get("parameters", []),
                    domain=tool_data.get("domain", "general"),
                    concepts=tool_data.get("concepts", []),
                    created_by=tool_data.get("created_by", "forge"),
                    version=tool_data.get("version", 1),
                )
                self._forged_tools[name] = forged
                
                # Try to reinstantiate and register
                class_name = self._to_class_name(name)
                tool = self._instantiate_tool(forged.code, class_name)
                if tool:
                    self.registry.register(tool)
                    logger.info(f"Restored forged tool: {name}")
            
            # Restore performance data
            for name, perf_data in data.get("performance", {}).items():
                perf = ToolPerformance(
                    tool_name=perf_data["tool_name"],
                    total_calls=perf_data.get("total_calls", 0),
                    successful_calls=perf_data.get("successful_calls", 0),
                    failed_calls=perf_data.get("failed_calls", 0),
                    total_duration_ms=perf_data.get("total_duration_ms", 0),
                    last_error=perf_data.get("last_error"),
                    status=ToolStatus(perf_data.get("status", "active")),
                )
                self._performance[name] = perf
            
            logger.info(f"Loaded forge state ({len(self._forged_tools)} tools)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load forge state: {e}")
            return False
