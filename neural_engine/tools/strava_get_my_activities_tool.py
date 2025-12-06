from neural_engine.tools.base_tool import BaseTool
from neural_engine.clients.strava_client import StravaClient
from neural_engine.core.key_value_store import KeyValueStore
from typing import Optional, Dict, Any, List

class StravaGetMyActivitiesTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "strava_get_my_activities",
            "description": "Get YOUR OWN personal activities (runs, rides, etc. that YOU posted - NOT your friends' activities). Use this when asked for 'my activities', 'my runs', 'my personal activities'. Returns activities with details like name, type, distance, time, kudos count. Supports date filtering with after_unix/before_unix timestamps.",
            "parameters": [
                {"name": "after_unix", "type": "int", "required": False, "description": "Unix timestamp - only activities after this time"},
                {"name": "before_unix", "type": "int", "required": False, "description": "Unix timestamp - only activities before this time"},
                {"name": "page", "type": "int", "required": False, "default": 1, "description": "Page number"},
                {"name": "per_page", "type": "int", "required": False, "default": 30, "description": "Results per page (max 200)"}
            ]
        }
    
    def get_semantic_metadata(self) -> Dict[str, Any]:
        """Semantic metadata for intelligent discovery."""
        return {
            "domain": "fitness",
            "concepts": ["running", "cycling", "exercise", "workout", "sports", "athletics", "training"],
            "actions": ["retrieve", "list", "fetch", "get", "show"],
            "data_sources": ["strava_api", "fitness_tracker"],
            "synonyms": ["runs", "rides", "workouts", "exercises", "activities", "training sessions"]
        }

    def execute(
        self,
        after_unix: Optional[int] = None,
        before_unix: Optional[int] = None,
        page: int = 1,
        per_page: int = 30
    ) -> dict:
        kv_store = KeyValueStore()
        strava_client = StravaClient(kv_store)

        activities = strava_client.get_logged_in_athlete_activities(
            after=after_unix,
            before=before_unix,
            page=page,
            per_page=per_page
        )

        return {
            "success": True,
            "count": len(activities),
            "items": activities,
            "page": page
        }
