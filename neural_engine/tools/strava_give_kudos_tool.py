from neural_engine.tools.base_tool import BaseTool
from neural_engine.clients.strava_client import StravaClient
from neural_engine.core.key_value_store import KeyValueStore

class StravaGiveKudosTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "strava_give_kudos",
            "description": "Give kudos (like) to a Strava activity",
            "parameters": [
                {"name": "activity_id", "type": "int", "required": True}
            ]
        }

    def execute(self, activity_id: int) -> dict:
        kv_store = KeyValueStore()
        strava_client = StravaClient(kv_store)

        success = strava_client.give_kudos(activity_id)

        if success:
            return {"success": True, "activity_id": activity_id, "message": "Kudos given"}
        else:
            return {"success": True, "activity_id": activity_id, "message": "Already gave kudos (goal already achieved)"}
