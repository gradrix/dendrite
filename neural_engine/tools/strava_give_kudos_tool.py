from neural_engine.tools.base_tool import BaseTool
from neural_engine.clients.strava_client import StravaClient
from neural_engine.core.key_value_store import KeyValueStore
from typing import Dict, Any

class StravaGiveKudosTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "strava_give_kudos",
            "description": "Give kudos (like) to a Strava activity",
            "parameters": [
                {"name": "activity_id", "type": "int", "required": True}
            ]
        }
    
    def get_semantic_metadata(self) -> Dict[str, Any]:
        """Semantic metadata for intelligent discovery."""
        return {
            "domain": "fitness",
            "concepts": ["social", "kudos", "like", "appreciation", "support", "fitness"],
            "actions": ["give", "send", "like", "appreciate"],
            "data_sources": ["strava_api"],
            "synonyms": ["like activity", "give kudos", "thumbs up", "appreciate workout"]
        }

    def execute(self, activity_id: int) -> dict:
        kv_store = KeyValueStore()
        strava_client = StravaClient(kv_store)

        success = strava_client.give_kudos(activity_id)

        if success:
            return {"success": True, "activity_id": activity_id, "message": "Kudos given"}
        else:
            return {"success": True, "activity_id": activity_id, "message": "Already gave kudos (goal already achieved)"}
