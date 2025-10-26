from .base_tool import BaseTool

class StravaTool(BaseTool):
    def get_activities(self, from_date=None):
        """
        A mock function to get Strava activities.
        In a real implementation, this would call the Strava API.
        """
        return [
            {"activity_type": "Run", "distance": "10km"},
            {"activity_type": "Ride", "distance": "25km"},
            {"activity_type": "Swim", "distance": "1.5km"},
        ]

    def get_tool_definition(self):
        return {
            "name": "strava",
            "description": "A tool for interacting with the Strava API.",
            "functions": [
                {
                    "name": "get_activities",
                    "description": "Get a list of recent Strava activities.",
                    "parameters": [
                        {
                            "name": "from_date",
                            "type": "string",
                            "description": "The start date from which to fetch activities.",
                        }
                    ],
                }
            ],
        }
