from neural_engine.tools.base_tool import BaseTool
from neural_engine.clients.strava_client import StravaClient
from neural_engine.core.key_value_store import KeyValueStore
from typing import Optional, Dict, Any

class StravaGetDashboardFeedTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "strava_get_dashboard_feed",
            "description": "Get recent activities from YOUR FRIENDS' dashboard feed (NOT your own activities - use getMyActivities for that). Returns activities posted by people you follow. Each entry includes: athlete name, activity type, activity name, activity_id, and TOTAL_KUDOS_COUNT (already calculated). Use hours_ago to filter (e.g., hours_ago=24 for last day). NO need to call getActivityKudos separately - kudos count is already included.",
            "parameters": [
                {"name": "hours_ago", "type": "int", "required": False, "description": "Filter activities from last N hours (e.g., 1 for last hour, 24 for last day)"},
                {"name": "num_entries", "type": "int", "required": False, "default": 20, "description": "Number of activities to fetch (default 20)"}
            ]
        }
    
    def get_semantic_metadata(self) -> Dict[str, Any]:
        """Semantic metadata for intelligent discovery."""
        return {
            "domain": "fitness",
            "concepts": ["social", "friends", "feed", "following", "community", "fitness", "activities"],
            "actions": ["retrieve", "list", "fetch", "get", "show"],
            "data_sources": ["strava_api", "social_feed"],
            "synonyms": ["friends activities", "dashboard", "following", "social feed", "what are my friends doing"]
        }

    def execute(self, hours_ago: Optional[int] = None, num_entries: int = 20) -> dict:
        kv_store = KeyValueStore()
        strava_client = StravaClient(kv_store)

        feed = strava_client.get_dashboard_feed(num_entries=num_entries)

        if not isinstance(feed, dict) or "entries" not in feed:
            return {"success": False, "error": "Unexpected feed format", "raw_response": feed}

        entries = feed.get("entries", [])

        summaries = []

        for entry in entries:
            if entry.get("entity") != "Activity":
                continue

            activity = entry.get("activity", {})
            if not activity:
                continue

            start_date_str = activity.get("startDate")
            if not start_date_str:
                continue

            from datetime import datetime, timedelta
            try:
                start_dt = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                start_unix = int(start_dt.timestamp())
            except:
                continue

            if hours_ago is not None:
                now = datetime.utcnow()
                after_time = now - timedelta(hours=hours_ago)
                after_timestamp = int(after_time.timestamp())
                if start_unix < after_timestamp:
                    continue

            athlete_data = activity.get("athlete", {})
            athlete_name = athlete_data.get("athleteName", "Unknown")
            athlete_id = athlete_data.get("athleteId", "")

            activity_name = activity.get("activityName", "Untitled")
            activity_type = activity.get("type", "Unknown")
            activity_id = activity.get("id", "")

            kudos_data = activity.get("kudosAndComments", {})
            you_gave_kudos = kudos_data.get("hasKudoed", False)
            total_kudos = kudos_data.get("kudosCount", 0)
            can_kudo = kudos_data.get("canKudo", False)

            visibility = activity.get("visibility", "unknown")

            summaries.append({
                "athlete_name": athlete_name,
                "athlete_id": athlete_id,
                "activity_type": activity_type,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "start_date": start_date_str,
                "start_unix": start_unix,
                "you_gave_kudos": you_gave_kudos,
                "can_give_kudos": can_kudo,
                "total_kudos": total_kudos,
                "visibility": visibility
            })

        return {
            "success": True,
            "count": len(summaries),
            "hours_filter": hours_ago,
            "items": summaries
        }
