from .base_tool import BaseTool
from neural_engine.core.key_value_store import KeyValueStore

class MemoryReadTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.kv_store = KeyValueStore()
    
    def get_tool_definition(self):
        return {
            "name": "memory_read",
            "description": "Reads from the agent's memory. Use this to recall previously stored information.",
            "parameters": [
                {"name": "key", "type": "string", "required": True, "description": "The key to read (e.g., 'user_name')"}
            ]
        }

    def execute(self, **kwargs):
        """Execute memory read - retrieve value by key."""
        key = kwargs.get("key")
        
        if not key:
            return {"status": "error", "message": "Missing required parameter: key"}
        
        # Read from KV store
        value = self.kv_store.get(key)
        
        if value is None:
            return {
                "status": "error",
                "message": f"No value found for key '{key}'"
            }
        
        return {
            "status": "success",
            "message": f"Retrieved value for key '{key}'",
            "key": key,
            "value": value
        }

