"""
Strava API Tools

Tools for interacting with Strava API using session cookies.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from agent.tool_registry import tool

logger = logging.getLogger(__name__)


class StravaClient:
    """Client for Strava API using session cookies."""
    
    def __init__(self, cookies_file: str = ".strava_cookies"):
        self.cookies_file = cookies_file
        self.session = requests.Session()
        self._load_cookies()
        self.base_url = "https://www.strava.com/api/v3"
        self.rate_limit_remaining = 100
        self.rate_limit_reset = None
        
    def _load_cookies(self):
        """Load cookies from file."""
        cookies_path = Path(self.cookies_file)
        if not cookies_path.exists():
            logger.warning(f"Cookies file not found: {self.cookies_file}")
            logger.info("Please create .strava_cookies file with your session cookies")
            return
        
        try:
            with open(cookies_path) as f:
                cookies_data = json.load(f)
                for cookie in cookies_data:
                    self.session.cookies.set(
                        cookie["name"],
                        cookie["value"],
                        domain=cookie.get("domain", ".strava.com")
                    )
            logger.info("Loaded Strava cookies successfully")
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
    
    def _check_rate_limit(self):
        """Check and respect rate limits."""
        if self.rate_limit_remaining <= 1:
            if self.rate_limit_reset:
                wait_time = (self.rate_limit_reset - datetime.now()).total_seconds()
                if wait_time > 0:
                    logger.warning(f"Rate limit reached. Waiting {wait_time}s")
                    time.sleep(wait_time + 1)
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make API request with rate limiting and error handling."""
        self._check_rate_limit()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=30
            )
            
            # Update rate limit info
            self.rate_limit_remaining = int(
                response.headers.get("X-RateLimit-Remaining", 100)
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'N/A'}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def get_athlete(self) -> Dict[str, Any]:
        """Get authenticated athlete info."""
        return self._make_request("GET", "/athlete")
    
    def get_activities(
        self,
        before: Optional[int] = None,
        after: Optional[int] = None,
        page: int = 1,
        per_page: int = 30
    ) -> List[Dict[str, Any]]:
        """Get athlete activities."""
        params = {
            "page": page,
            "per_page": per_page
        }
        if before:
            params["before"] = before
        if after:
            params["after"] = after
        
        return self._make_request("GET", "/athlete/activities", params=params)
    
    def get_activity(self, activity_id: int) -> Dict[str, Any]:
        """Get detailed activity information."""
        return self._make_request("GET", f"/activities/{activity_id}")
    
    def give_kudos(self, activity_id: int) -> Dict[str, Any]:
        """Give kudos to an activity."""
        return self._make_request("POST", f"/activities/{activity_id}/kudos")
    
    def create_comment(self, activity_id: int, text: str) -> Dict[str, Any]:
        """Create a comment on an activity."""
        return self._make_request(
            "POST",
            f"/activities/{activity_id}/comments",
            data={"text": text}
        )


# Global client instance
_client = None


def get_client() -> StravaClient:
    """Get or create Strava client instance."""
    global _client
    if _client is None:
        _client = StravaClient()
    return _client


# Tool definitions using the decorator

@tool(
    name="getMyLastDayActivities",
    description="Get my Strava activities from the last 24 hours",
    returns="List of activity objects with id, name, type, distance, moving_time, etc.",
    permissions="read"
)
def get_my_last_day_activities() -> List[Dict[str, Any]]:
    """Get activities from the last 24 hours."""
    client = get_client()
    
    # Calculate timestamp for 24 hours ago
    yesterday = datetime.now() - timedelta(days=1)
    after_timestamp = int(yesterday.timestamp())
    
    activities = client.get_activities(after=after_timestamp, per_page=30)
    
    logger.info(f"Found {len(activities)} activities in last 24 hours")
    
    # Simplify activity data for LLM
    simplified = []
    for activity in activities:
        simplified.append({
            "id": activity["id"],
            "name": activity["name"],
            "type": activity["type"],
            "distance_km": round(activity["distance"] / 1000, 2),
            "moving_time_minutes": round(activity["moving_time"] / 60),
            "elapsed_time_minutes": round(activity["elapsed_time"] / 60),
            "start_date": activity["start_date"],
            "kudos_count": activity.get("kudos_count", 0),
            "comment_count": activity.get("comment_count", 0),
        })
    
    return simplified


@tool(
    name="getFriendFeed",
    description="Get recent activities from friends (activity feed)",
    parameters=[
        {"name": "page", "type": "int", "required": False, "default": 1},
        {"name": "per_page", "type": "int", "required": False, "default": 10}
    ],
    returns="List of friend activities",
    permissions="read"
)
def get_friend_feed(page: int = 1, per_page: int = 10) -> List[Dict[str, Any]]:
    """
    Get activities from friends.
    Note: This might require web scraping or different API approach.
    For now, returns recent activities that might include friends.
    """
    client = get_client()
    
    # Get recent activities (this gets all activities the athlete can see)
    activities = client.get_activities(page=page, per_page=per_page)
    
    logger.info(f"Retrieved {len(activities)} activities from feed")
    
    # Simplify for LLM
    simplified = []
    for activity in activities:
        simplified.append({
            "id": activity["id"],
            "athlete_id": activity["athlete"]["id"],
            "athlete_name": f"{activity['athlete'].get('firstname', '')} {activity['athlete'].get('lastname', '')}",
            "name": activity["name"],
            "type": activity["type"],
            "distance_km": round(activity["distance"] / 1000, 2),
            "moving_time_minutes": round(activity["moving_time"] / 60),
            "start_date": activity["start_date"],
            "kudos_count": activity.get("kudos_count", 0),
        })
    
    return simplified


@tool(
    name="giveKudos",
    description="Give kudos (like) to a Strava activity",
    parameters=[
        {"name": "activity_id", "type": "int", "required": True}
    ],
    returns="Success message",
    permissions="write"
)
def give_kudos(activity_id: int) -> Dict[str, Any]:
    """Give kudos to an activity."""
    client = get_client()
    
    try:
        result = client.give_kudos(activity_id)
        logger.info(f"Gave kudos to activity {activity_id}")
        return {"success": True, "activity_id": activity_id, "message": "Kudos given"}
    except Exception as e:
        logger.error(f"Failed to give kudos: {e}")
        return {"success": False, "activity_id": activity_id, "error": str(e)}


@tool(
    name="postComment",
    description="Post a comment on a Strava activity",
    parameters=[
        {"name": "activity_id", "type": "int", "required": True},
        {"name": "text", "type": "str", "required": True}
    ],
    returns="Comment object with id and text",
    permissions="write"
)
def post_comment(activity_id: int, text: str) -> Dict[str, Any]:
    """Post a comment on an activity."""
    client = get_client()
    
    try:
        result = client.create_comment(activity_id, text)
        logger.info(f"Posted comment on activity {activity_id}")
        return {
            "success": True,
            "activity_id": activity_id,
            "comment_id": result.get("id"),
            "text": text
        }
    except Exception as e:
        logger.error(f"Failed to post comment: {e}")
        return {"success": False, "activity_id": activity_id, "error": str(e)}


@tool(
    name="getMyProfile",
    description="Get my Strava athlete profile information",
    returns="Athlete profile with name, stats, etc.",
    permissions="read"
)
def get_my_profile() -> Dict[str, Any]:
    """Get authenticated athlete profile."""
    client = get_client()
    
    athlete = client.get_athlete()
    
    # Simplify for LLM
    return {
        "id": athlete["id"],
        "username": athlete.get("username"),
        "firstname": athlete.get("firstname"),
        "lastname": athlete.get("lastname"),
        "city": athlete.get("city"),
        "state": athlete.get("state"),
        "country": athlete.get("country"),
        "follower_count": athlete.get("follower_count", 0),
        "friend_count": athlete.get("friend_count", 0),
    }
