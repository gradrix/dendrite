from neural_engine.tools.base_tool import BaseTool
from neural_engine.clients.strava_client import StravaClient
from neural_engine.core.key_value_store import KeyValueStore
from typing import Dict, Any

class StravaGetActivityKudosTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "strava_get_activity_kudos",
            "description": "Get list of athletes who gave kudos to a specific activity. Returns athlete names and IDs. Useful for tracking who interacted with your activities in the last 24 hours.",
            "parameters": [
                {"name": "activity_id", "type": "int", "required": True, "description": "Activity ID to get kudos for"}
            ]
        }
    
    def get_semantic_metadata(self) -> Dict[str, Any]:
        """Semantic metadata for intelligent discovery."""
        return {
            "domain": "fitness",
            "concepts": ["kudos", "likes", "social", "appreciation", "activity", "fitness"],
            "actions": ["retrieve", "get", "list", "check", "see"],
            "data_sources": ["strava_api"],
            "synonyms": ["who liked", "kudos list", "activity likes", "who appreciated"]
        }

    def execute(self, activity_id: int) -> dict:
        kv_store = KeyValueStore()
        strava_client = StravaClient(kv_store)

        kudos_list = strava_client.get_activity_kudos(activity_id)

        athletes = []
        for athlete in kudos_list:
            athletes.append({
                "id": athlete.get("id"),
                "name": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
                "username": athlete.get("username", ""),
            })

        return {
            "success": True,
            "activity_id": activity_id,
            "kudos_count": len(athletes),
            "athletes": athletes
        }
