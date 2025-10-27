from .base_tool import BaseTool
from ..core.message_bus import MessageBus

class MemoryWriteTool(BaseTool):
    def write(self, key: str, data: any):
        memory_key = f"memory:{key}"
        MessageBus().set_data(memory_key, data)
        return {"status": "success"}

    def get_tool_definition(self):
        return {
            "name": "memory_write",
            "description": "Writes data to long-term memory.",
            "functions": [{"name": "write", "parameters": [{"name": "key", "type": "string"}, {"name": "data", "type": "any"}]}],
        }
