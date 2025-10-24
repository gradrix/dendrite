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
    """
    Client for Strava using both web frontend API (cookie-based) and official API v3 (token-based).
    
    Supports dual authentication:
    - Cookies (.strava_cookies) for web frontend endpoints
    - Bearer token (.strava_token) for official API v3 endpoints
    """
    
    def __init__(self, cookies_file: str = ".strava_cookies", token_file: str = ".strava_token"):
        self.cookies_file = cookies_file
        self.token_file = token_file
        self.session = requests.Session()
        self.api_token = None
        self._load_cookies()
        self._load_token()
        self.csrf_token = None
        self._extract_csrf_token()
        
    def _extract_csrf_token(self):
        """Extract CSRF token from Strava dashboard."""
        try:
            response = self.session.get("https://www.strava.com/dashboard", timeout=10)
            response.raise_for_status()
            
            # Extract CSRF token from meta tag or script
            import re
            match = re.search(r'"csrf-token"\s*content="([^"]+)"', response.text)
            if not match:
                match = re.search(r'csrf[_-]?token[":\s]+(["\'])([^"\']+)\1', response.text, re.IGNORECASE)
            
            if match:
                self.csrf_token = match.group(2) if len(match.groups()) > 1 else match.group(1)
                logger.info(f"Extracted CSRF token: {self.csrf_token[:10]}...")
            else:
                logger.warning("Could not extract CSRF token from dashboard")
        except Exception as e:
            logger.error(f"Failed to extract CSRF token: {e}")
        
    def _load_cookies(self):
        """
        Load cookies from file.
        
        Supports two formats:
        1. JSON array: [{"name": "...", "value": "...", "domain": "..."}]
        2. Raw cookie string: "key1=value1; key2=value2; ..."
        """
        cookies_path = Path(self.cookies_file)
        if not cookies_path.exists():
            logger.warning(f"Cookies file not found: {self.cookies_file}")
            logger.info("Please create .strava_cookies file with your session cookies")
            return
        
        try:
            with open(cookies_path) as f:
                content = f.read().strip()
                
                # Try to parse as JSON first
                try:
                    cookies_data = json.loads(content)
                    # JSON format: [{"name": "...", "value": "..."}]
                    for cookie in cookies_data:
                        self.session.cookies.set(
                            cookie["name"],
                            cookie["value"],
                            domain=cookie.get("domain", ".strava.com")
                        )
                    logger.info(f"Loaded {len(cookies_data)} cookies from JSON format")
                    
                except (json.JSONDecodeError, TypeError):
                    # Raw cookie string format: "key1=value1; key2=value2"
                    logger.info("Parsing as raw cookie string format")
                    
                    # Split by semicolon and parse key=value pairs
                    cookie_pairs = [pair.strip() for pair in content.split(';')]
                    cookie_count = 0
                    
                    for pair in cookie_pairs:
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            
                            if key:  # Only add non-empty keys
                                self.session.cookies.set(
                                    key,
                                    value,
                                    domain=".strava.com"
                                )
                                cookie_count += 1
                    
                    logger.info(f"Loaded {cookie_count} cookies from raw string format")
                    
            logger.info("Strava cookies loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
    
    def _load_token(self):
        """
        Load API access token from file.
        
        File should contain just the access token string (no quotes needed):
          your_access_token_here_abcdef123456
        
        To get a token:
        1. Go to https://www.strava.com/settings/api
        2. Create an application (or use existing)
        3. Use the access token shown, or do OAuth flow for proper scopes
        """
        token_path = Path(self.token_file)
        if not token_path.exists():
            logger.info(f"API token file not found: {self.token_file}")
            logger.info("API v3 endpoints will not be available without a token")
            return
        
        try:
            with open(token_path) as f:
                token = f.read().strip()
                
                # Remove quotes if present
                if token.startswith('"') and token.endswith('"'):
                    token = token[1:-1]
                elif token.startswith("'") and token.endswith("'"):
                    token = token[1:-1]
                
                if token:
                    self.api_token = token
                    # Mask token for logging
                    masked = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "***"
                    logger.info(f"Loaded API token: {masked}")
                else:
                    logger.warning("API token file is empty")
        
        except Exception as e:
            logger.error(f"Failed to load API token: {e}")
    
    def _get_headers(self, referer: str = "https://www.strava.com/dashboard") -> Dict[str, str]:
        """Get headers for web frontend API requests."""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript",
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest"
        }
        
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        
        return headers
    
    def _get_api_headers(self) -> Dict[str, str]:
        """Get headers for official API v3 requests."""
        headers = {
            "User-Agent": "StravaAgent/1.0",
            "Accept": "application/json"
        }
        
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        
        return headers
    
    def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[str] = None,
        json_data: Optional[Dict] = None
    ) -> Any:
        """Make a request to Strava web frontend API."""
        if headers is None:
            headers = self._get_headers()
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                timeout=30
            )
            
            response.raise_for_status()
            
            # Try to parse as JSON
            try:
                return response.json()
            except:
                return response.text
                
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'N/A'}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def get_logged_in_athlete_activities(
        self, 
        after: Optional[int] = None, 
        before: Optional[int] = None,
        page: int = 1,
        per_page: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get authenticated athlete's activities using official API v3.
        
        Requires API token (.strava_token file).
        
        Args:
            after: Unix timestamp - only activities after this time
            before: Unix timestamp - only activities before this time
            page: Page number (default 1)
            per_page: Results per page (default 30, max 200)
            
        Returns:
            List of activity dictionaries from API v3
        """
        if not self.api_token:
            logger.error("API token not available. Cannot fetch activities from API v3.")
            logger.info("Create .strava_token file with your access token")
            return []
        
        url = "https://www.strava.com/api/v3/athlete/activities"
        
        params = {
            "page": page,
            "per_page": min(per_page, 200)  # API limit
        }
        
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        
        headers = self._get_api_headers()
        
        try:
            response = self.session.request(
                method="GET",
                url=url,
                headers=headers,
                params=params,
                timeout=30
            )
            
            response.raise_for_status()
            activities = response.json()
            
            if isinstance(activities, list):
                logger.info(f"Retrieved {len(activities)} activities from API v3")
                return activities
            else:
                logger.warning(f"Unexpected response format: {type(activities)}")
                return []
            
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 401:
                logger.error("API token is invalid or expired")
                logger.info("Get a new token from https://www.strava.com/settings/api")
            else:
                logger.error(f"HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get athlete activities: {e}")
            return []
    
    def update_activity(
        self,
        activity_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        visibility: Optional[str] = None,
        trainer: Optional[bool] = None,
        commute: Optional[bool] = None,
        hide_from_home: Optional[bool] = None,
        map_visibility: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update activity details.
        
        Args:
            activity_id: Activity ID to update
            name: Activity name
            description: Activity description
            visibility: 'everyone', 'followers_only', or 'only_me'
            trainer: Whether it's a trainer ride
            commute: Whether it's a commute
            hide_from_home: Hide from home feed
            map_visibility: 'everyone', 'followers_only', or 'only_me'
            
        Returns:
            Updated activity data or error
        """
        url = f"https://www.strava.com/activities/{activity_id}"
        headers = self._get_headers(referer=url)
        
        # Build update payload
        data = {}
        
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if visibility is not None:
            # Map visibility to internal values
            visibility_map = {
                "everyone": "everyone",
                "public": "everyone",
                "followers_only": "followers_only",
                "followers": "followers_only",
                "only_me": "only_me",
                "private": "only_me"
            }
            data["visibility"] = visibility_map.get(visibility.lower(), visibility)
        if trainer is not None:
            data["trainer"] = trainer
        if commute is not None:
            data["commute"] = commute
        if hide_from_home is not None:
            data["hide_from_home"] = hide_from_home
        if map_visibility is not None:
            # For 3D map, we might need different field
            data["map_visibility"] = map_visibility
        
        if not data:
            return {"success": False, "error": "No fields to update"}
        
        try:
            response = self._make_request("PUT", url, headers=headers, json_data=data)
            logger.info(f"Updated activity {activity_id}")
            return {"success": True, "activity_id": activity_id, "updated_fields": list(data.keys())}
        except Exception as e:
            logger.error(f"Failed to update activity {activity_id}: {e}")
            return {"success": False, "error": str(e), "activity_id": activity_id}
    
    def get_activity_kudos(self, activity_id: int) -> List[Dict[str, Any]]:
        """
        Get list of athletes who gave kudos to an activity (web frontend API).
        
        Uses cookie-based authentication.
        
        Args:
            activity_id: Activity ID
            
        Returns:
            List of athlete dictionaries with: id, username, firstname, lastname, etc.
        """
        url = f"https://www.strava.com/feed/activity/{activity_id}/kudos"
        headers = self._get_headers(referer=f"https://www.strava.com/activities/{activity_id}")
        
        try:
            response = self._make_request("GET", url, headers=headers)
            
            # Response format can be: {'athletes': [...]}, {'models': [...]}, {'kudosers': [...]}, or direct list
            if isinstance(response, dict):
                logger.info(f"Kudos response keys: {list(response.keys())}")
                
                if 'athletes' in response:
                    kudos_list = response['athletes']
                    logger.info(f"Retrieved {len(kudos_list)} kudos for activity {activity_id}")
                    return kudos_list
                elif 'models' in response:
                    kudos_list = response['models']
                    logger.info(f"Retrieved {len(kudos_list)} kudos for activity {activity_id}")
                    return kudos_list
                elif 'kudosers' in response:
                    kudos_list = response['kudosers']
                    logger.info(f"Retrieved {len(kudos_list)} kudos for activity {activity_id}")
                    return kudos_list
                elif 'entries' in response:
                    kudos_list = response['entries']
                    logger.info(f"Retrieved {len(kudos_list)} kudos for activity {activity_id}")
                    return kudos_list
                elif 'data' in response:
                    kudos_list = response['data']
                    logger.info(f"Retrieved {len(kudos_list)} kudos for activity {activity_id}")
                    return kudos_list
            elif isinstance(response, list):
                logger.info(f"Retrieved {len(response)} kudos for activity {activity_id}")
                return response
                
            logger.warning(f"Unexpected kudos response format: {type(response)}, keys: {list(response.keys()) if isinstance(response, dict) else 'N/A'}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to get activity kudos: {e}")
            return []
    
    def get_following(self) -> List[Dict[str, Any]]:
        """Get list of athletes you are following."""
        url = "https://www.strava.com/athlete/following"
        return self._make_request("GET", url)
    
    def get_followers(self, per_page: int = 1000) -> List[Dict[str, Any]]:
        """Get list of your followers."""
        url = f"https://www.strava.com/athlete/followers?per_page={per_page}"
        response = self._make_request("GET", url)
        
        # Response format: {'results': {'followers': [...]}}
        if isinstance(response, dict) and 'results' in response:
            return response['results'].get('followers', [])
        return response
    
    def get_activity_participants(self, activity_id: int) -> List[Dict[str, Any]]:
        """Get participants (group athletes) for an activity."""
        url = f"https://www.strava.com/feed/activity/{activity_id}/group_athletes"
        headers = self._get_headers(referer=f"https://www.strava.com/activities/{activity_id}")
        response = self._make_request("GET", url, headers=headers)
        
        # Response format: {'athletes': [...]}
        if isinstance(response, dict) and 'athletes' in response:
            return response['athletes']
        return response
    
    def is_activity_kudosable(self, activity_id: int) -> bool:
        """Check if an activity can receive kudos."""
        url = f"https://www.strava.com/feed/activity/{activity_id}/kudos"
        headers = self._get_headers(referer=f"https://www.strava.com/activities/{activity_id}")
        
        try:
            response = self._make_request("GET", url, headers=headers)
            if isinstance(response, dict):
                return response.get('kudosable', False)
            return False
        except Exception as e:
            logger.error(f"Failed to check kudosable status: {e}")
            return False
    
    def give_kudos(self, activity_id: int) -> bool:
        """Give kudos to an activity using web frontend API."""
        url = f"https://www.strava.com/feed/activity/{activity_id}/kudo"
        headers = self._get_headers(referer=f"https://www.strava.com/activities/{activity_id}")
        
        try:
            # Check if already gave kudos
            if not self.is_activity_kudosable(activity_id):
                logger.info(f"Already gave kudos to activity {activity_id} or not possible")
                return False
            
            self._make_request("POST", url, headers=headers, data="")
            logger.info(f"Kudos given to activity {activity_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to give kudos: {e}")
            return False
    
    def get_dashboard_feed(
        self, 
        before: Optional[int] = None,
        cursor: Optional[int] = None,
        num_entries: int = 20
    ) -> Dict[str, Any]:
        """
        Get activity feed from dashboard.
        
        Args:
            before: Unix timestamp - only activities before this time
            cursor: Pagination cursor (use value from previous response)
            num_entries: Number of entries to fetch (default 20)
            
        Returns:
            Feed data with entries and pagination info
        """
        # Build URL with parameters
        params = {
            "feed_type": "following",
            "num_entries": num_entries
        }
        
        if before:
            params["before"] = before
        if cursor:
            params["cursor"] = cursor
            
        url = "https://www.strava.com/dashboard/feed"
        return self._make_request("GET", url, params=params)


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
    name="getDashboardFeed",
    description="Get recent activities from dashboard feed (you and your friends). Returns summary: athlete name, activity type, whether you gave kudos. Use hours_ago to filter recent activities (e.g., hours_ago=1 for last hour)",
    parameters=[
        {"name": "hours_ago", "type": "int", "required": False, "description": "Filter activities from last N hours (e.g., 1 for last hour, 24 for last day)"},
        {"name": "num_entries", "type": "int", "required": False, "default": 20, "description": "Number of activities to fetch (default 20)"}
    ],
    returns="Summary list: each entry has athlete_name, athlete_id, activity_type, activity_name, activity_id, start_date, you_gave_kudos, total_kudos",
    permissions="read"
)
def get_dashboard_feed(hours_ago: Optional[int] = None, num_entries: int = 20) -> Dict[str, Any]:
    """
    Get activity feed from dashboard with optional time filtering.
    
    Returns a clean summary focused on: who posted, what activity, if you gave kudos.
    """
    client = get_client()
    
    try:
        # Calculate time filter if hours_ago provided
        before_timestamp = None
        after_timestamp = None
        
        if hours_ago is not None:
            now = datetime.utcnow()
            after_time = now - timedelta(hours=hours_ago)
            after_timestamp = int(after_time.timestamp())
            logger.info(f"Filtering activities from last {hours_ago} hours (after {after_time.isoformat()})")
        
        # Fetch feed (may need pagination for time filtering)
        feed = client.get_dashboard_feed(num_entries=num_entries)
        
        if not isinstance(feed, dict) or "entries" not in feed:
            logger.warning(f"Unexpected feed format: {type(feed)}")
            return {"success": False, "error": "Unexpected feed format", "raw_response": feed}
        
        entries = feed.get("entries", [])
        logger.info(f"Retrieved {len(entries)} feed entries")
        
        # Parse entries and create summary
        summaries = []
        
        for entry in entries:
            # Only process Activity entries (skip Posts, etc.)
            if entry.get("entity") != "Activity":
                continue
            
            activity = entry.get("activity", {})
            if not activity:
                continue
            
            # Parse start date
            start_date_str = activity.get("startDate")
            if not start_date_str:
                continue
            
            # Parse ISO date: "2025-10-22T06:27:01Z"
            try:
                start_dt = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                start_unix = int(start_dt.timestamp())
            except:
                logger.warning(f"Failed to parse date: {start_date_str}")
                continue
            
            # Apply time filter if specified
            if after_timestamp and start_unix < after_timestamp:
                continue
            
            # Extract athlete info
            athlete_data = activity.get("athlete", {})
            athlete_name = athlete_data.get("athleteName", "Unknown")
            athlete_id = athlete_data.get("athleteId", "")
            
            # Extract activity info
            activity_name = activity.get("activityName", "Untitled")
            activity_type = activity.get("type", "Unknown")
            activity_id = activity.get("id", "")
            
            # Check if you gave kudos
            kudos_data = activity.get("kudosAndComments", {})
            you_gave_kudos = kudos_data.get("hasKudoed", False)
            total_kudos = kudos_data.get("kudosCount", 0)
            can_kudo = kudos_data.get("canKudo", False)
            
            # Check visibility
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
        
        # Log summary
        time_filter_msg = f" (last {hours_ago} hours)" if hours_ago else""
        logger.info(f"Found {len(summaries)} activities{time_filter_msg}")
        
        if summaries:
            kudos_given = sum(1 for s in summaries if s["you_gave_kudos"])
            logger.info(f"You gave kudos to {kudos_given}/{len(summaries)} activities")
        
        return {
            "success": True,
            "count": len(summaries),
            "hours_filter": hours_ago,
            "activities": summaries
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard feed: {e}")
        return {"success": False, "error": str(e)}


@tool(
    name="getFollowing",
    description="Get list of athletes you are following",
    returns="List of athletes with id, name, etc.",
    permissions="read"
)
def get_following() -> Dict[str, Any]:
    """Get athletes you are following."""
    client = get_client()
    
    try:
        following = client.get_following()
        logger.info(f"Found {len(following)} athletes you are following")
        
        # Simplify for LLM
        simplified = []
        for athlete in following:
            simplified.append({
                "id": athlete.get("id"),
                "name": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
                "location": athlete.get("city", ""),
                "profile_url": f"https://www.strava.com/athletes/{athlete.get('id')}"
            })
        
        return {"success": True, "count": len(simplified), "athletes": simplified}
    except Exception as e:
        logger.error(f"Failed to get following: {e}")
        return {"success": False, "error": str(e)}


@tool(
    name="getFollowers",
    description="Get list of your followers",
    returns="List of followers with id, name, etc.",
    permissions="read"
)
def get_followers() -> Dict[str, Any]:
    """Get your followers."""
    client = get_client()
    
    try:
        followers = client.get_followers(per_page=1000)
        logger.info(f"Found {len(followers)} followers")
        
        # Simplify for LLM
        simplified = []
        for follower in followers:
            simplified.append({
                "id": follower.get("athleteId") or follower.get("id"),
                "name": follower.get("name", "Unknown"),
                "location": follower.get("location", ""),
            })
        
        return {"success": True, "count": len(simplified), "followers": simplified}
    except Exception as e:
        logger.error(f"Failed to get followers: {e}")
        return {"success": False, "error": str(e)}


@tool(
    name="getActivityParticipants",
    description="Get participants (group athletes) for a specific activity",
    parameters=[
        {"name": "activity_id", "type": "int", "required": True}
    ],
    returns="List of athletes who participated in the activity",
    permissions="read"
)
def get_activity_participants(activity_id: int) -> Dict[str, Any]:
    """Get participants for an activity."""
    client = get_client()
    
    try:
        participants = client.get_activity_participants(activity_id)
        logger.info(f"Found {len(participants)} participants for activity {activity_id}")
        
        return {
            "success": True,
            "activity_id": activity_id,
            "count": len(participants),
            "participants": participants
        }
    except Exception as e:
        logger.error(f"Failed to get activity participants: {e}")
        return {"success": False, "activity_id": activity_id, "error": str(e)}


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
    """Give kudos to an activity using web frontend API."""
    client = get_client()
    
    try:
        success = client.give_kudos(activity_id)
        if success:
            return {"success": True, "activity_id": activity_id, "message": "Kudos given"}
        else:
            return {"success": False, "activity_id": activity_id, "message": "Already gave kudos or not possible"}
    except Exception as e:
        logger.error(f"Failed to give kudos: {e}")
        return {"success": False, "activity_id": activity_id, "error": str(e)}


@tool(
    name="giveKudosToParticipants",
    description="Give kudos to all participants in an activity (bulk kudos)",
    parameters=[
        {"name": "activity_id", "type": "int", "required": True},
        {"name": "delay_seconds", "type": "float", "required": False, "default": 1.0}
    ],
    returns="Summary of kudos given",
    permissions="write"
)
def give_kudos_to_participants(activity_id: int, delay_seconds: float = 1.0) -> Dict[str, Any]:
    """Give kudos to all participants in an activity."""
    import random
    
    client = get_client()
    
    try:
        # Get participants
        participants = client.get_activity_participants(activity_id)
        logger.info(f"Giving kudos to {len(participants)} participants")
        
        success_count = 0
        failed_count = 0
        results = []
        
        for participant in participants:
            participant_activity_id = participant.get("activity_id")
            if not participant_activity_id:
                continue
            
            try:
                success = client.give_kudos(participant_activity_id)
                if success:
                    success_count += 1
                    results.append({
                        "athlete": participant.get("name"),
                        "activity_id": participant_activity_id,
                        "status": "success"
                    })
                else:
                    results.append({
                        "athlete": participant.get("name"),
                        "activity_id": participant_activity_id,
                        "status": "already_gave_kudos"
                    })
                
                # Random delay to avoid rate limiting
                time.sleep(delay_seconds + random.random())
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to give kudos to {participant.get('name')}: {e}")
                results.append({
                    "athlete": participant.get("name"),
                    "activity_id": participant_activity_id,
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "success": True,
            "activity_id": activity_id,
            "total_participants": len(participants),
            "kudos_given": success_count,
            "failed": failed_count,
            "results": results
        }
    except Exception as e:
        logger.error(f"Failed to give kudos to participants: {e}")
        return {"success": False, "activity_id": activity_id, "error": str(e)}
    
    try:
        result = client.give_kudos(activity_id)
        logger.info(f"Gave kudos to activity {activity_id}")
        return {"success": True, "activity_id": activity_id, "message": "Kudos given"}
    except Exception as e:
        logger.error(f"Failed to give kudos: {e}")
        return {"success": False, "activity_id": activity_id, "error": str(e)}


@tool(
    name="getMyActivities",
    description="Get your own activities with optional date filtering",
    parameters=[
        {"name": "after_unix", "type": "int", "required": False, "description": "Unix timestamp - only activities after this time"},
        {"name": "before_unix", "type": "int", "required": False, "description": "Unix timestamp - only activities before this time"},
        {"name": "page", "type": "int", "required": False, "default": 1, "description": "Page number"},
        {"name": "per_page", "type": "int", "required": False, "default": 30, "description": "Results per page (max 200)"}
    ],
    returns="List of your activities with details (name, type, distance, time, visibility, etc.)",
    permissions="read"
)
def get_my_activities(
    after_unix: Optional[int] = None,
    before_unix: Optional[int] = None, 
    page: int = 1,
    per_page: int = 30
) -> Dict[str, Any]:
    """Get authenticated athlete's activities."""
    client = get_client()
    
    try:
        activities = client.get_logged_in_athlete_activities(
            after=after_unix,
            before=before_unix,
            page=page,
            per_page=per_page
        )
        
        logger.info(f"Retrieved {len(activities)} activities")
        
        return {
            "success": True,
            "count": len(activities),
            "activities": activities,
            "page": page
        }
    except Exception as e:
        logger.error(f"Failed to get activities: {e}")
        return {"success": False, "error": str(e), "activities": []}


@tool(
    name="updateActivity",
    description="Update activity details (name, description, visibility, map settings)",
    parameters=[
        {"name": "activity_id", "type": "int", "required": True, "description": "Activity ID to update"},
        {"name": "name", "type": "string", "required": False, "description": "New activity name"},
        {"name": "description", "type": "string", "required": False, "description": "New description"},
        {"name": "visibility", "type": "string", "required": False, "description": "Visibility: 'everyone', 'followers_only', or 'only_me'"},
        {"name": "map_visibility", "type": "string", "required": False, "description": "Map visibility: 'everyone', 'followers_only', or 'only_me'"}
    ],
    returns="Success status with updated fields",
    permissions="write"
)
def update_activity(
    activity_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    visibility: Optional[str] = None,
    map_visibility: Optional[str] = None
) -> Dict[str, Any]:
    """Update an activity's details."""
    client = get_client()
    
    try:
        result = client.update_activity(
            activity_id=activity_id,
            name=name,
            description=description,
            visibility=visibility,
            map_visibility=map_visibility
        )
        
        if result.get("success"):
            logger.info(f"Updated activity {activity_id}: {result.get('updated_fields', [])}")
        else:
            logger.warning(f"Failed to update activity {activity_id}: {result.get('error')}")
        
        return result
    except Exception as e:
        logger.error(f"Failed to update activity {activity_id}: {e}")
        return {"success": False, "error": str(e), "activity_id": activity_id}


@tool(
    name="getActivityKudos",
    description="Get list of athletes who gave kudos to a specific activity. Returns athlete names and IDs. Useful for tracking who interacted with your activities in the last 24 hours.",
    parameters=[
        {"name": "activity_id", "type": "int", "required": True, "description": "Activity ID to get kudos for"}
    ],
    returns="List of athletes who gave kudos with: id, username, firstname, lastname",
    permissions="read"
)
def get_activity_kudos(activity_id: int) -> Dict[str, Any]:
    """Get list of athletes who gave kudos to an activity."""
    client = get_client()
    
    try:
        kudos_list = client.get_activity_kudos(activity_id)
        
        # Simplify for LLM
        athletes = []
        for athlete in kudos_list:
            athletes.append({
                "id": athlete.get("id"),
                "name": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
                "username": athlete.get("username", ""),
            })
        
        logger.info(f"Found {len(athletes)} kudos on activity {activity_id}")
        
        return {
            "success": True,
            "activity_id": activity_id,
            "kudos_count": len(athletes),
            "athletes": athletes
        }
    except Exception as e:
        logger.error(f"Failed to get kudos for activity {activity_id}: {e}")
        return {"success": False, "error": str(e), "activity_id": activity_id, "athletes": []}
