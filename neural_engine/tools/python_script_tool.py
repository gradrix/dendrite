from .base_tool import BaseTool

class PythonScriptTool(BaseTool):
    def execute_script(self, script):
        """
        Executes a Python script.
        NOTE: This is a dangerous operation and should be used with caution in a sandboxed environment.
        """
        try:
            exec(script)
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
                    "description": "Execute a given Python script.",
                    "parameters": [
                        {
                            "name": "script",
                            "type": "string",
                            "description": "The Python script to execute.",
                        }
                    ],
                }
            ],
        }
