from .base_tool import BaseTool

class StravaTool(BaseTool):
    def get_activities(self, from_date=None):
        return [
            {"activity_type": "Run", "distance": "10km"},
            {"activity_type": "Ride", "distance": "25km"},
        ]

    def get_tool_definition(self):
        return {
            "name": "strava",
            "description": "Tool for interacting with the Strava API.",
            "functions": [
                {
                    "name": "get_activities",
                    "description": "Get a list of recent Strava activities.",
                    "parameters": [{"name": "from_date", "type": "string"}],
                }
            ],
        }
