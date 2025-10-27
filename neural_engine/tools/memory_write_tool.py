from .base_tool import BaseTool

class MemoryWriteTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "memory_write",
            "description": "Writes to the agent's memory.",
            "parameters": [
                {"name": "key", "type": "string", "required": True},
                {"name": "value", "type": "string", "required": True}
            ]
        }

    def execute(self, **kwargs):
        # Placeholder for future implementation
        key = kwargs.get("key")
        value = kwargs.get("value")
        return {"status": "success", "message": f"Value for key '{key}' would be written."}
