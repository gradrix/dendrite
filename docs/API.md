# API Reference

Quick reference for Dendrite's main components and their interfaces.

## Table of Contents

- [Orchestrator](#orchestrator)
- [Tool Development](#tool-development)
- [Key-Value Store](#key-value-store)
- [Message Bus](#message-bus)
- [Execution Store](#execution-store)

## Orchestrator

Main entry point for executing goals.

```python
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.system_factory import create_system

# Create orchestrator with all neurons
system = create_system()
orchestrator = system['orchestrator']

# Execute a goal
result = orchestrator.process("Remember my name is Alice")
print(result)
# {'success': True, 'result': 'Stored: name = Alice'}
```

### Methods

**`process(goal: str) -> dict`**

Main entry point. Handles intent classification and routing.

**`execute(goal_id: str, goal: str, depth: int = 0) -> dict`**

Lower-level execution with explicit goal ID and recursion depth.

## Tool Development

Create custom tools by extending `BaseTool`.

### Basic Tool

```python
from neural_engine.tools.base_tool import BaseTool

class WeatherTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "weather",
            "description": "Get current weather for a location",
            "parameters": [
                {
                    "name": "location",
                    "type": "string",
                    "description": "City name or zip code",
                    "required": True
                }
            ]
        }
    
    def execute(self, **kwargs):
        location = kwargs.get('location')
        # Your implementation here
        weather_data = fetch_weather(location)
        return {
            "success": True,
            "temperature": weather_data['temp'],
            "conditions": weather_data['conditions']
        }
```

### Tool with Authentication

```python
from neural_engine.core.key_value_store import KeyValueStore

class APITool(BaseTool):
    def __init__(self):
        super().__init__()
        self.kv = KeyValueStore()
    
    def execute(self, **kwargs):
        # Get stored credentials
        api_key = self.kv.get("api_key")
        if not api_key:
            return {
                "success": False,
                "error": "API key not configured. Please set 'api_key' in key-value store."
            }
        
        # Use credentials
        result = make_api_call(api_key, **kwargs)
        return {"success": True, "data": result}
```

### Tool Discovery

Tools are automatically discovered if placed in `neural_engine/tools/` with filename pattern `*_tool.py` and class name ending in `Tool`.

## Key-Value Store

Simple persistent storage for configuration and user data.

```python
from neural_engine.core.key_value_store import KeyValueStore

kv = KeyValueStore()

# Store values
kv.set("user_name", "Alice")
kv.set("api_key", "secret_key_123")

# Retrieve values
name = kv.get("user_name")  # Returns "Alice"
key = kv.get("api_key")     # Returns "secret_key_123"

# Check existence
if kv.get("optional_setting") is None:
    print("Setting not configured")

# Delete values
kv.delete("old_key")
```

### Storage Location

Data stored in: `var/kv_store.json`

## Message Bus

Communication layer between neurons.

```python
from neural_engine.core.message_bus import MessageBus

bus = MessageBus()

# Get new goal ID
goal_id = bus.get_new_goal_id()  # Returns "goal_1", "goal_2", etc.

# Add messages
bus.add_message(goal_id, "intent_classification", {
    "intent": "tool_use",
    "confidence": 0.95
})

bus.add_message(goal_id, "tool_selection", {
    "selected_tool": "memory_write",
    "confidence": 0.98
})

# Retrieve conversation history
messages = bus.get_messages(goal_id)
for msg in messages:
    print(f"{msg['type']}: {msg['data']}")

# Clear messages (for cleanup)
bus.clear_goal(goal_id)
```

### Message Format

```python
{
    "goal_id": "goal_123",
    "type": "tool_selection",      # Message type
    "data": {...},                  # Arbitrary data
    "depth": 0,                     # Recursion depth
    "timestamp": 1699000000,        # Unix timestamp
    "metadata": {                   # Optional metadata
        "duration_ms": 150,
        "confidence": 0.95
    }
}
```

## Execution Store

PostgreSQL-backed analytics and metrics storage.

```python
from neural_engine.core.execution_store import ExecutionStore

store = ExecutionStore()

# Store execution result
store.store_execution(
    goal="Remember my name is Alice",
    intent="tool_use",
    success=True,
    duration_ms=250,
    result={"stored": True}
)

# Store tool execution
store.store_tool_execution(
    tool_name="memory_write",
    goal="Remember my name is Alice",
    success=True,
    duration_ms=50,
    error_message=None
)

# Query statistics
success_rate = store.get_success_rate(tool_name="memory_write")
print(f"Success rate: {success_rate}%")

# Get recent executions
recent = store.get_recent_executions(
    tool_name="memory_write",
    limit=10
)

# Get top performing tools
top_tools = store.get_top_tools(limit=5)
for tool in top_tools:
    print(f"{tool['name']}: {tool['success_rate']}%")

# Close connection
store.close()
```

### Context Manager Pattern

```python
with ExecutionStore() as store:
    store.store_execution(...)
    stats = store.get_success_rate("memory_write")
# Connection automatically closed
```

## Tool Registry

Access and query available tools.

```python
from neural_engine.core.tool_registry import ToolRegistry

registry = ToolRegistry()

# Get all tools
all_tools = registry.get_all_tools()
for name, tool in all_tools.items():
    print(f"{name}: {tool.get_tool_definition()['description']}")

# Get specific tool
memory_tool = registry.get_tool("memory_write")
if memory_tool:
    result = memory_tool.execute(key="name", value="Alice")

# Get tool definitions (for LLM prompts)
definitions = registry.get_all_tool_definitions()

# Refresh registry (reload tools from disk)
registry.refresh()
```

## Tool Discovery

Semantic search over tools.

```python
from neural_engine.core.tool_discovery import ToolDiscovery
from neural_engine.core.tool_registry import ToolRegistry

registry = ToolRegistry()
discovery = ToolDiscovery(tool_registry=registry)

# Index all tools
discovery.index_all_tools()

# Semantic search
candidates = discovery.discover_tools(
    goal_text="Show me my recent runs",
    semantic_limit=10,
    ranking_limit=5
)

for candidate in candidates:
    print(f"{candidate['tool_name']}: {candidate['relevance']}")
```

## Pattern Cache

Cache LLM decisions for faster repeated queries.

```python
from neural_engine.core.pattern_cache import PatternCache

cache = PatternCache()

# Store pattern
cache.store_pattern(
    pattern="Remember my name is Alice",
    decision={"tool": "memory_write", "params": {"key": "name", "value": "Alice"}},
    confidence=0.95
)

# Lookup similar pattern
result, confidence = cache.lookup("Remember my name is Bob", threshold=0.85)
if result:
    print(f"Cache hit! Confidence: {confidence}")
    print(f"Decision: {result}")

# Update usage after execution
cache.update_usage("Remember my name is Alice", success=True)

# Get statistics
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']}%")

# Clear cache
cache.clear()
```

## Custom Neuron

Create custom processing neurons.

```python
from neural_engine.core.neuron import Neuron

class CustomNeuron(Neuron):
    def __init__(self, message_bus, ollama_client):
        super().__init__(message_bus, ollama_client)
    
    def process(self, goal_id: str, goal: str, depth: int):
        # Your processing logic
        result = self._analyze(goal)
        
        # Store in message bus
        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="custom_analysis",
            data=result,
            depth=depth
        )
        
        return result
    
    def _analyze(self, goal):
        prompt = f"Analyze this goal: {goal}"
        response = self.ollama_client.generate(prompt)
        return {"analysis": response['response']}
```

## Configuration

### Environment Variables

Set in `docker-compose.yml`:

```yaml
environment:
  OLLAMA_HOST: http://ollama:11434
  OLLAMA_MODEL: mistral
  REDIS_HOST: redis
  REDIS_DB: "0"  # Use "1" for tests
  POSTGRES_HOST: postgres
  POSTGRES_DB: dendrite
  POSTGRES_USER: dendrite
  POSTGRES_PASSWORD: dendrite_pass
```

### Programmatic Configuration

```python
import os

# Change model
os.environ['OLLAMA_MODEL'] = 'llama3.1:8b'

# Change Redis database
os.environ['REDIS_DB'] = '1'  # Use test database
```

## Error Handling

All tool executions should return:

```python
{
    "success": bool,     # Required
    "result": any,       # On success
    "error": str,        # On failure
    "error_type": str    # Optional: "transient", "permanent", "auth"
}
```

Example:

```python
def execute(self, **kwargs):
    try:
        result = do_something()
        return {
            "success": True,
            "result": result
        }
    except AuthenticationError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "auth"
        }
    except APIError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "transient"
        }
```

## Testing

### Test Fixtures

```python
import pytest
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.message_bus import MessageBus

@pytest.fixture
def orchestrator():
    from neural_engine.core.system_factory import create_system
    system = create_system()
    return system['orchestrator']

@pytest.fixture
def message_bus():
    return MessageBus()

def test_memory_write(orchestrator):
    result = orchestrator.process("Remember my name is Alice")
    assert result['success'] == True
```

### Mock LLM Responses

```python
from unittest.mock import Mock

def test_with_mock_llm(mocker):
    mock_client = Mock()
    mock_client.generate.return_value = {
        'response': 'YES, confidence: 95'
    }
    
    selector = ToolSelectorNeuron(
        message_bus=MessageBus(),
        ollama_client=mock_client,
        tool_registry=ToolRegistry()
    )
    
    result = selector.process("goal_123", "Test goal", 0)
    assert result is not None
```

## CLI Usage

### Run a Goal

```bash
python run_goal.py "Your goal here"
```

### With Visualization

```bash
python run_goal.py "Your goal" --visualize
```

### Interactive Mode

```python
from neural_engine.core.system_factory import create_system

system = create_system()
orchestrator = system['orchestrator']

while True:
    goal = input("Goal: ")
    if goal == "quit":
        break
    result = orchestrator.process(goal)
    print(result)
```

## Best Practices

1. **Always return dicts from tools** with `success` key
2. **Use KeyValueStore for credentials** don't hardcode
3. **Handle errors gracefully** return error messages, don't raise
4. **Provide clear descriptions** for tool discovery
5. **Test your tools** create unit tests
6. **Use message bus** for debugging and tracing
7. **Close resources** use context managers for stores
8. **Set appropriate confidence** in results (0.0-1.0)
9. **Document parameters** clearly in tool definitions
10. **Follow naming conventions** `*_tool.py` and `*Tool` class

## Common Patterns

### Conditional Tool Execution

```python
def execute(self, **kwargs):
    if not self._validate_params(kwargs):
        return {"success": False, "error": "Invalid parameters"}
    
    if self._should_use_cache(kwargs):
        return self._get_cached_result(kwargs)
    
    result = self._execute_api_call(kwargs)
    self._cache_result(kwargs, result)
    return {"success": True, "result": result}
```

### Retry with Backoff

```python
import time

def execute(self, **kwargs):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return {"success": True, "result": api_call(kwargs)}
        except TransientError:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return {"success": False, "error": "Max retries exceeded"}
```

### Progressive Enhancement

```python
def execute(self, **kwargs):
    # Try best method first
    try:
        return self._method_a(kwargs)
    except:
        pass
    
    # Fallback to good method
    try:
        return self._method_b(kwargs)
    except:
        pass
    
    # Last resort
    return self._method_c(kwargs)
```
