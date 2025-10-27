from .base_tool import BaseTool

class StravaTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "strava",
            "description": "Interacts with the Strava API.",
            "parameters": []
        }

    def execute(self, **kwargs):
        # Placeholder for future implementation
        return {"status": "success", "message": "StravaTool executed."}
