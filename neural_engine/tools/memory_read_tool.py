from .base_tool import BaseTool
from ..core.message_bus import MessageBus

class MemoryReadTool(BaseTool):
    def read(self, key: str):
        memory_key = f"memory:{key}"
        return MessageBus().get_data(memory_key)

    def get_tool_definition(self):
        return {
            "name": "memory_read",
            "description": "Reads data from long-term memory.",
            "functions": [{"name": "read", "parameters": [{"name": "key", "type": "string"}]}],
        }
