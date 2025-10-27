from .base_tool import BaseTool

class PythonScriptTool(BaseTool):
    def execute_script(self, script):
        try:
            # WARNING: This is a security risk. In a real-world application,
            # this should be executed in a sandboxed environment.
            exec(script, globals())
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_tool_definition(self):
        return {
            "name": "python_script",
            "description": "A tool for executing Python scripts.",
            "functions": [
                {
                    "name": "execute_script",
                    "description": "Execute a Python script in the current environment.",
                    "parameters": [{"name": "script", "type": "string"}],
                }
            ],
        }
