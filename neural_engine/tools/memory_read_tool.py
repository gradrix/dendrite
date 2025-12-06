from .base_tool import BaseTool
from neural_engine.core.key_value_store import KeyValueStore
from typing import Dict, Any

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
    
    def get_semantic_metadata(self) -> Dict[str, Any]:
        """Semantic metadata for intelligent discovery."""
        return {
            "domain": "memory",
            "concepts": ["recall", "remember", "personal info", "user data", "preferences", "stored information", "retrieval"],
            "actions": ["retrieve", "recall", "get", "read", "fetch", "lookup"],
            "data_sources": ["local_memory", "key_value_store"],
            "synonyms": ["what is my name", "do you remember", "tell me my", "stored", "told you"]
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

