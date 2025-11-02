from .base_tool import BaseTool
from neural_engine.core.key_value_store import KeyValueStore

class MemoryWriteTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.kv_store = KeyValueStore()
    
    def get_tool_definition(self):
        return {
            "name": "memory_write",
            "description": "Writes to the agent's memory. Use this to remember information for later.",
            "parameters": [
                {"name": "key", "type": "string", "required": True, "description": "The key to store (e.g., 'user_name')"},
                {"name": "value", "type": "string", "required": True, "description": "The value to store"}
            ]
        }

    def execute(self, **kwargs):
        """Execute memory write - store key-value pair."""
        key = kwargs.get("key")
        value = kwargs.get("value")
        
        if not key:
            return {"status": "error", "message": "Missing required parameter: key"}
        if not value:
            return {"status": "error", "message": "Missing required parameter: value"}
        
        # Store in KV store
        self.kv_store.set(key, value)
        
        return {
            "status": "success",
            "message": f"Successfully stored '{value}' for key '{key}'",
            "key": key,
            "value": value
        }

