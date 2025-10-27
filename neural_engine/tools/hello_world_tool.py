from .base_tool import BaseTool

class HelloWorldTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "hello_world",
            "description": "A simple tool that returns a greeting.",
            "parameters": []
        }

    def execute(self, **kwargs):
        return {"message": "Hello, World!"}
