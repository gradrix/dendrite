from neural_engine.tools.base_tool import BaseTool
from neural_engine.clients.strava_client import StravaClient
from neural_engine.core.key_value_store import KeyValueStore
from typing import Optional, Dict, Any

class StravaUpdateActivityTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "strava_update_activity",
            "description": "Update activity details (name, description, visibility, map settings)",
            "parameters": [
                {"name": "activity_id", "type": "int", "required": True, "description": "Activity ID to update"},
                {"name": "name", "type": "string", "required": False, "description": "New activity name"},
                {"name": "description", "type": "string", "required": False, "description": "New description"},
                {"name": "visibility", "type": "string", "required": False, "description": "Visibility: 'everyone', 'followers_only', or 'only_me'"},
                {"name": "map_visibility", "type": "string", "required": False, "description": "Map visibility: 'everyone', 'followers_only', or 'only_me'"},
                {"name": "selected_polyline_style", "type": "string", "required": False, "description": "Map style: 'standard', 'satellite', 'fatmap_satellite_3d' (for 3D map)"}
            ]
        }
    
    def get_semantic_metadata(self) -> Dict[str, Any]:
        """Semantic metadata for intelligent discovery."""
        return {
            "domain": "fitness",
            "concepts": ["activity", "update", "edit", "modify", "settings", "fitness"],
            "actions": ["update", "edit", "modify", "change", "rename"],
            "data_sources": ["strava_api"],
            "synonyms": ["rename activity", "change description", "edit workout", "update settings"]
        }

    def execute(
        self,
        activity_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        visibility: Optional[str] = None,
        map_visibility: Optional[str] = None,
        selected_polyline_style: Optional[str] = None
    ) -> dict:
        kv_store = KeyValueStore()
        strava_client = StravaClient(kv_store)

        result = strava_client.update_activity(
            activity_id=activity_id,
            name=name,
            description=description,
            visibility=visibility,
            map_visibility=map_visibility,
            selected_polyline_style=selected_polyline_style
        )

        return result
