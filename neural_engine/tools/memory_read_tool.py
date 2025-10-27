from .base_tool import BaseTool

class MemoryReadTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "memory_read",
            "description": "Reads from the agent's memory.",
            "parameters": [
                {"name": "key", "type": "string", "required": True}
            ]
        }

    def execute(self, **kwargs):
        # Placeholder for future implementation
        key = kwargs.get("key")
        return {"status": "success", "message": f"Value for key '{key}' would be read."}
