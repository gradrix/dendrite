"""
Strava Tools for Neural Engine v2

Provides tools for interacting with Strava:
- Get activities (API)
- Get activity details (API)
- Update activities (Web)
- Give kudos (Web)
- Get dashboard feed (Web)
- Collect kudos givers (accumulate knowledge)
- Reciprocate kudos (auto-kudo back)

Uses two authentication methods:
1. OAuth API tokens for official API endpoints
2. Browser cookies for web-only features (kudos, dashboard, updates)

Storage (PostgreSQL via StorageClient):
- strava/credentials - OAuth tokens and client info
- strava/cookies - Browser cookies for web features
- strava/kudos_givers - Accumulated knowledge of who gave kudos
"""

import os
import re
import json
import time
import logging
import requests
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..tools import Tool, ToolDefinition
from ..core.storage import StorageClient

logger = logging.getLogger(__name__)


class StravaClientV2:
    """
    Strava API client for v2.
    
    Supports two authentication methods:
    1. OAuth API (official endpoints) - token stored in PostgreSQL
    2. Web cookies (unofficial endpoints) - cookies stored in PostgreSQL
    """
    
    STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
    STORAGE_NAMESPACE = "strava"
    
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self._api_token = None
        self._refresh_token = None
        self._client_id = None
        self._client_secret = None
        self._token_expires = None
        self._cookies = None
        self._csrf_token = None
        self._loaded = False
        self._storage = None
    
    def _get_storage(self) -> StorageClient:
        """Get or create StorageClient."""
        if self._storage is None:
            self._storage = StorageClient()
        return self._storage
    
    def _ensure_loaded(self):
        """Lazy load credentials from PostgreSQL storage."""
        if self._loaded:
            return
        
        storage = self._get_storage()
        
        # Load OAuth credentials from PostgreSQL
        creds = storage.get(self.STORAGE_NAMESPACE, "credentials", {})
        if creds:
            self._api_token = creds.get("access_token")
            self._refresh_token = creds.get("refresh_token")
            self._client_id = creds.get("client_id")
            self._client_secret = creds.get("client_secret")
            self._token_expires = creds.get("expires_at")
        
        # Load browser cookies for web features
        cookies_data = storage.get(self.STORAGE_NAMESPACE, "cookies")
        if cookies_data:
            if isinstance(cookies_data, dict):
                self._cookies = cookies_data
            elif isinstance(cookies_data, str):
                # Parse semicolon-separated format
                self._cookies = self._parse_cookie_string(cookies_data)
            
            if self._cookies:
                self.session.cookies.update(self._cookies)
        
        # Fallback to file-based credentials (for initial setup)
        if not self._api_token:
            token_file = os.environ.get("STRAVA_TOKEN_FILE", ".strava_token")
            if os.path.exists(token_file):
                with open(token_file) as f:
                    self._api_token = f.read().strip()
        
        if not self._cookies:
            cookies_file = os.environ.get("STRAVA_COOKIES_FILE", ".strava_cookies")
            if os.path.exists(cookies_file):
                try:
                    with open(cookies_file) as f:
                        content = f.read().strip()
                        # Try JSON first
                        try:
                            self._cookies = json.loads(content)
                        except json.JSONDecodeError:
                            # Fall back to semicolon-separated format
                            self._cookies = self._parse_cookie_string(content)
                        
                        if self._cookies:
                            self.session.cookies.update(self._cookies)
                except Exception as e:
                    logger.warning(f"Failed to load cookies file: {e}")
        
        self._loaded = True
    
    def _parse_cookie_string(self, cookie_str: str) -> Dict[str, str]:
        """Parse cookies from semicolon-separated format: 'name=value; name2=value2'"""
        cookies = {}
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                name, value = part.split("=", 1)
                cookies[name.strip()] = value.strip()
        return cookies
    
    def _extract_csrf_token(self) -> Optional[str]:
        """Extract CSRF token from Strava dashboard page."""
        if self._csrf_token:
            return self._csrf_token
        
        self._ensure_loaded()
        
        try:
            # Don't use web headers - we need the full HTML page
            response = self.session.get(
                "https://www.strava.com/dashboard",
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=10,
            )
            response.raise_for_status()
            
            # Look for: <meta name="csrf-token" content="...">
            match = re.search(r'csrf-token["\s]+content="([^"]+)"', response.text, re.IGNORECASE)
            if match:
                self._csrf_token = match.group(1)
                return self._csrf_token
                
        except Exception as e:
            logger.debug(f"Failed to extract CSRF token: {e}")
        
        return None
    
    def _get_web_headers(self, referer: str = "https://www.strava.com/dashboard") -> Dict[str, str]:
        """Get headers for web scraping requests."""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript",
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest",
        }
        
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token
        
        return headers
    
    def has_web_auth(self) -> bool:
        """Check if we have cookies for web-based features."""
        self._ensure_loaded()
        return bool(self._cookies)
    
    def _token_needs_refresh(self) -> bool:
        """Check if token is expired or about to expire."""
        if not self._token_expires:
            return False  # No expiry info, assume valid
        
        # Refresh if expires within 5 minutes
        return time.time() > (self._token_expires - 300)
    
    def _refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not all([self._refresh_token, self._client_id, self._client_secret]):
            logger.warning("Missing credentials for token refresh")
            return False
        
        try:
            response = requests.post(
                self.STRAVA_TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            
            # Update tokens
            self._api_token = data["access_token"]
            self._refresh_token = data["refresh_token"]
            self._token_expires = data["expires_at"]
            
            # Save to PostgreSQL
            storage = self._get_storage()
            storage.set(self.STORAGE_NAMESPACE, "credentials", {
                "access_token": self._api_token,
                "refresh_token": self._refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "expires_at": self._token_expires,
            })
            
            logger.info("Strava token refreshed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh Strava token: {e}")
            return False
    
    def _get_api_headers(self) -> Dict[str, str]:
        """Get headers for API requests, refreshing token if needed."""
        self._ensure_loaded()
        
        # Auto-refresh if token is expired or about to expire
        if self._token_needs_refresh():
            logger.info("Strava token expired, attempting refresh...")
            self._refresh_access_token()
        
        headers = {
            "User-Agent": "StravaAgent/1.0",
            "Accept": "application/json",
        }
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        return headers
    
    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        self._ensure_loaded()
        return bool(self._api_token)
    
    def get_athlete(self) -> Dict[str, Any]:
        """Get current athlete info."""
        if not self.is_authenticated():
            return {"error": "Not authenticated with Strava"}
        
        try:
            resp = self.session.get(
                "https://www.strava.com/api/v3/athlete",
                headers=self._get_api_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_activities(
        self,
        page: int = 1,
        per_page: int = 30,
        activity_type: Optional[str] = None,
        after: Optional[int] = None,
        before: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get athlete activities.
        
        Args:
            page: Page number for pagination
            per_page: Number of activities per page
            activity_type: Filter by activity type (e.g., "Ride", "Run")
            after: Unix timestamp - only activities after this time
            before: Unix timestamp - only activities before this time
        """
        if not self.is_authenticated():
            return [{"error": "Not authenticated with Strava"}]
        
        try:
            params = {"page": page, "per_page": per_page}
            if after:
                params["after"] = after
            if before:
                params["before"] = before
            
            resp = self.session.get(
                "https://www.strava.com/api/v3/athlete/activities",
                headers=self._get_api_headers(),
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            activities = resp.json()
            
            # Filter by type if specified
            if activity_type:
                type_lower = activity_type.lower()
                activities = [
                    a for a in activities
                    if a.get("type", "").lower() == type_lower or
                       a.get("sport_type", "").lower() == type_lower
                ]
            
            return activities
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_activity(self, activity_id: int) -> Dict[str, Any]:
        """Get detailed activity info."""
        if not self.is_authenticated():
            return {"error": "Not authenticated with Strava"}
        
        try:
            resp = self.session.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers=self._get_api_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    # ========================================================================
    # WEB-BASED METHODS (require cookies)
    # ========================================================================
    
    def give_kudos(self, activity_id: int) -> Dict[str, Any]:
        """Give kudos to an activity (requires cookies)."""
        self._ensure_loaded()
        
        if not self.has_web_auth():
            return {"error": "Web authentication required. Set strava/cookies in PostgreSQL."}
        
        # Ensure we have CSRF token
        if not self._extract_csrf_token():
            return {"error": "Failed to get CSRF token. Cookies may be expired."}
        
        url = f"https://www.strava.com/feed/activity/{activity_id}/kudo"
        headers = self._get_web_headers(referer=f"https://www.strava.com/activities/{activity_id}")
        
        try:
            # Check if already kudosed
            check_url = f"https://www.strava.com/feed/activity/{activity_id}/kudos"
            check_resp = self.session.get(check_url, headers=headers, timeout=10)
            if check_resp.ok:
                data = check_resp.json() if check_resp.headers.get("content-type", "").startswith("application/json") else {}
                if not data.get("kudosable", True):
                    return {"success": True, "message": "Already gave kudos"}
            
            # Give kudos
            resp = self.session.post(url, headers=headers, data="", timeout=10)
            resp.raise_for_status()
            
            return {"success": True, "activity_id": activity_id, "message": "Kudos given!"}
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_activity_kudos(self, activity_id: int) -> Dict[str, Any]:
        """
        Get list of athletes who gave kudos to an activity.
        Uses the web endpoint which returns athlete IDs.
        """
        self._ensure_loaded()
        
        if not self.has_web_auth():
            return {"error": "Web authentication required. Set strava/cookies in PostgreSQL."}
        
        try:
            url = f"https://www.strava.com/feed/activity/{activity_id}/kudos"
            headers = self._get_web_headers()
            headers["Referer"] = f"https://www.strava.com/activities/{activity_id}"
            
            resp = self.session.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            response = resp.json()
            
            # The web endpoint can return data in different formats
            kudos_list = []
            if isinstance(response, dict):
                for key in ['athletes', 'models', 'kudosers', 'entries', 'data']:
                    if key in response:
                        kudos_list = response[key]
                        break
            elif isinstance(response, list):
                kudos_list = response
            
            # Extract athlete info - web endpoint DOES return IDs!
            givers = []
            for kudoer in kudos_list:
                athlete_id = kudoer.get("id") or kudoer.get("athlete_id")
                firstname = kudoer.get("firstname", "")
                lastname = kudoer.get("lastname", "")
                username = kudoer.get("username", "")
                
                givers.append({
                    "athlete_id": str(athlete_id) if athlete_id else None,
                    "firstname": firstname,
                    "lastname": lastname,
                    "username": username,
                    "display_name": f"{firstname} {lastname}".strip(),
                })
            
            return {
                "activity_id": activity_id,
                "kudos_count": len(givers),
                "givers": givers,
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_dashboard_feed(
        self,
        num_entries: int = 20,
        before: Optional[int] = None,
        cursor: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get dashboard feed (requires cookies)."""
        self._ensure_loaded()
        
        if not self.has_web_auth():
            return {"error": "Web authentication required. Set strava/cookies in PostgreSQL."}
        
        params = {
            "feed_type": "following",
            "num_entries": num_entries,
        }
        if before:
            params["before"] = before
        if cursor:
            params["cursor"] = cursor
        
        try:
            resp = self.session.get(
                "https://www.strava.com/dashboard/feed",
                headers=self._get_web_headers(),
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def update_activity(
        self,
        activity_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        visibility: Optional[str] = None,
        trainer: Optional[bool] = None,
        commute: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update an activity (requires cookies)."""
        self._ensure_loaded()
        
        if not self.has_web_auth():
            return {"error": "Web authentication required. Set strava/cookies in PostgreSQL."}
        
        # Ensure we have CSRF token
        if not self._extract_csrf_token():
            return {"error": "Failed to get CSRF token. Cookies may be expired."}
        
        url = f"https://www.strava.com/activities/{activity_id}"
        headers = self._get_web_headers(referer=url)
        
        data = {
            "utf8": "✓",
            "_method": "patch",
        }
        
        if name is not None:
            data["activity[name]"] = name
        if description is not None:
            data["activity[description]"] = description
        if visibility is not None:
            visibility_map = {
                "everyone": "everyone",
                "public": "everyone",
                "followers_only": "followers_only",
                "followers": "followers_only",
                "only_me": "only_me",
                "private": "only_me",
            }
            data["activity[visibility]"] = visibility_map.get(visibility.lower(), visibility)
        if trainer is not None:
            data["activity[trainer]"] = "1" if trainer else "0"
        if commute is not None:
            data["activity[commute]"] = "1" if commute else "0"
        
        if len(data) <= 2:
            return {"error": "No fields to update"}
        
        try:
            resp = self.session.post(url, headers=headers, data=data, timeout=30)
            resp.raise_for_status()
            
            updated = [k.replace("activity[", "").replace("]", "") for k in data.keys() if k.startswith("activity[")]
            return {"success": True, "activity_id": activity_id, "updated_fields": updated}
            
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# STRAVA TOOLS
# ============================================================================

class StravaGetActivitiesTool(Tool):
    """Get Strava activities."""
    
    def __init__(self, config):
        self._client = StravaClientV2(config)
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_get_activities",
            description="Get your recent Strava activities (runs, rides, etc.)",
            parameters=[
                {"name": "count", "type": "integer", "description": "Number of activities to get (default: 10)"},
                {"name": "activity_type", "type": "string", "description": "Filter by type: run, ride, swim, etc."},
            ],
            required_params=[],
            domain="fitness",
            concepts=["strava", "activities", "running", "cycling", "workout", "exercise", "fitness"],
            synonyms=["my runs", "my rides", "my workouts", "strava activities", "recent activities"],
        )
    
    def execute(self, count: int = 10, activity_type: str = None, **kwargs) -> Dict[str, Any]:
        # Coerce count to int (LLM might pass string)
        try:
            count = int(count) if count is not None else 10
        except (ValueError, TypeError):
            count = 10
        
        # If filtering by type, fetch more to ensure we get enough after filtering
        fetch_count = min(count * 3, 100) if activity_type else min(count, 100)
        
        activities = self._client.get_activities(
            per_page=fetch_count,
            activity_type=activity_type,
        )
        
        if activities and isinstance(activities[0], dict) and "error" in activities[0]:
            return {"error": activities[0]["error"]}
        
        # Format for output
        results = []
        for a in activities[:count]:
            results.append({
                "id": a.get("id"),
                "name": a.get("name"),
                "type": a.get("type") or a.get("sport_type"),
                "distance_km": round(a.get("distance", 0) / 1000, 2),
                "distance_miles": round(a.get("distance", 0) / 1609.34, 2),
                "moving_time_minutes": round(a.get("moving_time", 0) / 60, 1),
                "date": a.get("start_date_local", "")[:10],
                "kudos": a.get("kudos_count", 0),
            })
        
        return {
            "activities": results,
            "count": len(results),
        }


class StravaGetActivityTool(Tool):
    """Get details of a specific Strava activity."""
    
    def __init__(self, config):
        self._client = StravaClientV2(config)
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_get_activity",
            description="Get detailed information about a specific Strava activity",
            parameters=[
                {"name": "activity_id", "type": "integer", "description": "The Strava activity ID"},
            ],
            required_params=["activity_id"],
            domain="fitness",
            concepts=["strava", "activity", "details", "workout"],
            synonyms=["activity details", "show activity"],
        )
    
    def execute(self, activity_id: int = None, **kwargs) -> Dict[str, Any]:
        if not activity_id:
            return {"error": "activity_id is required"}
        
        # Coerce activity_id to int (LLM might pass string)
        try:
            activity_id = int(activity_id)
        except (ValueError, TypeError):
            return {"error": f"Invalid activity_id: {activity_id}"}
        
        activity = self._client.get_activity(activity_id)
        
        if "error" in activity:
            return activity
        
        return {
            "id": activity.get("id"),
            "name": activity.get("name"),
            "type": activity.get("type") or activity.get("sport_type"),
            "description": activity.get("description", ""),
            "distance_km": round(activity.get("distance", 0) / 1000, 2),
            "distance_miles": round(activity.get("distance", 0) / 1609.34, 2),
            "moving_time_minutes": round(activity.get("moving_time", 0) / 60, 1),
            "elapsed_time_minutes": round(activity.get("elapsed_time", 0) / 60, 1),
            "elevation_gain_m": activity.get("total_elevation_gain", 0),
            "average_speed_kmh": round(activity.get("average_speed", 0) * 3.6, 1),
            "max_speed_kmh": round(activity.get("max_speed", 0) * 3.6, 1),
            "calories": activity.get("calories", 0),
            "kudos": activity.get("kudos_count", 0),
            "date": activity.get("start_date_local", "")[:10],
            "location": activity.get("location_city") or activity.get("location_country"),
        }


class StravaCheckAuthTool(Tool):
    """Check Strava authentication status."""
    
    def __init__(self, config):
        self._client = StravaClientV2(config)
        self._config = config
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_check_auth",
            description="Check if Strava is connected and authenticated",
            parameters=[],
            required_params=[],
            domain="fitness",
            concepts=["strava", "authentication", "connected"],
            synonyms=["is strava connected", "strava status"],
        )
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        self._client._ensure_loaded()
        
        # Check what credentials we have
        has_token = bool(self._client._api_token)
        has_refresh = bool(self._client._refresh_token)
        has_client_id = bool(self._client._client_id)
        has_client_secret = bool(self._client._client_secret)
        
        if not has_token:
            return {
                "authenticated": False,
                "message": "No access token found. Please set up authentication.",
                "credentials_status": {
                    "access_token": has_token,
                    "refresh_token": has_refresh,
                    "client_id": has_client_id,
                    "client_secret": has_client_secret,
                },
            }
        
        # Try to get athlete info to verify token works
        athlete = self._client.get_athlete()
        if "error" in athlete:
            # Check if we can refresh
            if has_refresh and has_client_id and has_client_secret:
                if self._client._refresh_access_token():
                    # Retry after refresh
                    athlete = self._client.get_athlete()
                    if "error" not in athlete:
                        return {
                            "authenticated": True,
                            "athlete_name": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
                            "athlete_id": athlete.get("id"),
                            "token_refreshed": True,
                        }
            
            return {
                "authenticated": False,
                "message": f"Token invalid: {athlete['error']}",
                "credentials_status": {
                    "access_token": has_token,
                    "refresh_token": has_refresh,
                    "client_id": has_client_id,
                    "client_secret": has_client_secret,
                },
                "can_refresh": has_refresh and has_client_id and has_client_secret,
            }
        
        return {
            "authenticated": True,
            "athlete_name": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
            "athlete_id": athlete.get("id"),
            "web_auth": self._client.has_web_auth(),
            "web_auth_message": "Web features available (kudos, updates, feed)" if self._client.has_web_auth() else "Set strava/cookies in PostgreSQL for kudos/update/feed features",
        }


class StravaSetupTool(Tool):
    """Set up Strava OAuth credentials."""
    
    def __init__(self, config):
        self._config = config
        self._storage = None
    
    def _get_storage(self) -> StorageClient:
        if self._storage is None:
            self._storage = StorageClient()
        return self._storage
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_setup",
            description="Set up Strava OAuth credentials (client_id, client_secret, tokens)",
            parameters=[
                {"name": "client_id", "type": "string", "description": "Strava app client ID"},
                {"name": "client_secret", "type": "string", "description": "Strava app client secret"},
                {"name": "access_token", "type": "string", "description": "OAuth access token"},
                {"name": "refresh_token", "type": "string", "description": "OAuth refresh token"},
            ],
            required_params=["client_id", "client_secret", "access_token", "refresh_token"],
            domain="fitness",
            concepts=["strava", "setup", "oauth", "credentials"],
            synonyms=["configure strava", "connect strava"],
        )
    
    def execute(
        self,
        client_id: str = None,
        client_secret: str = None,
        access_token: str = None,
        refresh_token: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        if not all([client_id, client_secret, access_token, refresh_token]):
            return {"error": "All parameters required: client_id, client_secret, access_token, refresh_token"}
        
        try:
            storage = self._get_storage()
            storage.set("strava", "credentials", {
                "client_id": str(client_id),
                "client_secret": str(client_secret),
                "access_token": str(access_token),
                "refresh_token": str(refresh_token),
                "expires_at": None,  # Will be set on first refresh
            })
            
            return {
                "success": True,
                "message": "Strava credentials saved to PostgreSQL. Token will auto-refresh when needed.",
            }
        except Exception as e:
            return {"error": f"Failed to save credentials: {e}"}


# ============================================================================
# WEB-BASED TOOLS (require cookies)
# ============================================================================

class StravaGiveKudosTool(Tool):
    """Give kudos to a Strava activity."""
    
    def __init__(self, config):
        self._client = StravaClientV2(config)
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_give_kudos",
            description="Give kudos (like) to a Strava activity",
            parameters=[
                {"name": "activity_id", "type": "integer", "description": "The activity ID to give kudos to"},
            ],
            required_params=["activity_id"],
            domain="fitness",
            concepts=["strava", "kudos", "like", "social", "appreciate"],
            synonyms=["like activity", "give kudos", "thumbs up", "appreciate workout"],
        )
    
    def execute(self, activity_id: int = None, **kwargs) -> Dict[str, Any]:
        if not activity_id:
            return {"error": "activity_id is required"}
        
        try:
            activity_id = int(activity_id)
        except (ValueError, TypeError):
            return {"error": f"Invalid activity_id: {activity_id}"}
        
        return self._client.give_kudos(activity_id)


class StravaGetDashboardFeedTool(Tool):
    """Get Strava dashboard feed (activities from people you follow)."""
    
    def __init__(self, config):
        self._client = StravaClientV2(config)
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_get_dashboard_feed",
            description="Get the Strava dashboard feed showing activities from people you follow",
            parameters=[
                {"name": "count", "type": "integer", "description": "Number of entries to get (default: 20)"},
            ],
            required_params=[],
            domain="fitness",
            concepts=["strava", "feed", "dashboard", "following", "social", "friends"],
            synonyms=["strava feed", "friends activities", "following feed", "dashboard"],
        )
    
    def execute(self, count: int = 20, **kwargs) -> Dict[str, Any]:
        try:
            count = int(count) if count else 20
        except (ValueError, TypeError):
            count = 20
        
        activities = []
        seen_ids = set()  # Track seen activity IDs to avoid duplicates
        cursor = None
        max_pages = 5  # Safety limit to prevent infinite loops
        page_size = 20  # Fetch 20 entries per page
        
        for _ in range(max_pages):
            result = self._client.get_dashboard_feed(num_entries=page_size, cursor=cursor)
            
            if "error" in result:
                return result
            
            entries = result.get("entries", [])
            if not entries:
                break  # No more entries
            
            for entry in entries:
                entity = entry.get("entity")
                if entity == "Activity":
                    activity = entry.get("activity", {})
                    activity_id = activity.get("id")
                    
                    # Skip duplicates
                    if activity_id in seen_ids:
                        continue
                    seen_ids.add(activity_id)
                    
                    athlete = activity.get("athlete", {})
                    kudos_comments = activity.get("kudosAndComments", {})
                    time_loc = activity.get("timeAndLocation", {})
                    stats = activity.get("stats", [])
                    
                    # Parse stats (they come as formatted HTML strings)
                    # Strip HTML tags for cleaner output
                    import re
                    def strip_html(s):
                        return re.sub(r'<[^>]+>', '', s) if s else ""
                    
                    distance_str = ""
                    time_str = ""
                    for stat in stats:
                        key = stat.get("key", "")
                        if key == "stat_one":
                            distance_str = strip_html(stat.get("value", ""))
                        elif key == "stat_three":
                            time_str = strip_html(stat.get("value", ""))
                    
                    activities.append({
                        "id": activity_id,
                        "name": activity.get("activityName"),
                        "type": activity.get("type"),
                        "athlete": athlete.get("athleteName"),
                        "athlete_id": athlete.get("athleteId"),
                        "distance": distance_str,
                        "time": time_str,
                        "kudos": kudos_comments.get("kudosCount", 0),
                        "can_kudo": kudos_comments.get("canKudo", False),
                        "has_kudoed": kudos_comments.get("hasKudoed", False),
                    })
                    
                    # Stop once we have enough unique activities
                    if len(activities) >= count:
                        break
            
            # Check if we have enough
            if len(activities) >= count:
                break
            
            # Get cursor for next page
            cursor = result.get("cursor")
            if not cursor:
                break  # No more pages
        
        return {
            "activities": activities,
            "count": len(activities),
        }


class StravaUpdateActivityTool(Tool):
    """Update a Strava activity."""
    
    def __init__(self, config):
        self._client = StravaClientV2(config)
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_update_activity",
            description="Update a Strava activity (name, description, visibility, etc.)",
            parameters=[
                {"name": "activity_id", "type": "integer", "description": "The activity ID to update"},
                {"name": "name", "type": "string", "description": "New name for the activity"},
                {"name": "description", "type": "string", "description": "New description"},
                {"name": "visibility", "type": "string", "description": "Visibility: everyone, followers_only, or only_me"},
                {"name": "commute", "type": "boolean", "description": "Mark as commute (true/false)"},
            ],
            required_params=["activity_id"],
            domain="fitness",
            concepts=["strava", "update", "edit", "rename", "modify", "activity"],
            synonyms=["rename activity", "edit activity", "change activity name", "update workout"],
        )
    
    def execute(
        self,
        activity_id: int = None,
        name: str = None,
        description: str = None,
        visibility: str = None,
        commute: bool = None,
        **kwargs
    ) -> Dict[str, Any]:
        if not activity_id:
            return {"error": "activity_id is required"}
        
        try:
            activity_id = int(activity_id)
        except (ValueError, TypeError):
            return {"error": f"Invalid activity_id: {activity_id}"}
        
        return self._client.update_activity(
            activity_id=activity_id,
            name=name,
            description=description,
            visibility=visibility,
            commute=commute,
        )


# ============================================================================
# KUDOS AUTOMATION TOOLS (collect givers, reciprocate)
# ============================================================================

class StravaCollectKudosGiversTool(Tool):
    """
    Collect kudos givers from your recent activities and store them.
    
    This builds up persistent knowledge of who gives you kudos,
    which can later be used for reciprocation.
    """
    
    def __init__(self, config):
        self._client = StravaClientV2(config)
        self._storage = None
    
    def _get_storage(self) -> StorageClient:
        if self._storage is None:
            self._storage = StorageClient()
        return self._storage
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_collect_kudos_givers",
            description="Collect and store information about who gave you kudos on recent activities",
            parameters=[
                {"name": "hours_back", "type": "integer", "description": "How many hours back to look (default: 48)"},
                {"name": "max_activities", "type": "integer", "description": "Maximum activities to check (default: 10)"},
            ],
            required_params=[],
            domain="fitness",
            concepts=["strava", "kudos", "collect", "givers", "social", "track"],
            synonyms=["who gave me kudos", "track kudos givers", "collect kudos"],
        )
    
    def execute(self, hours_back: int = 48, max_activities: int = 10, **kwargs) -> Dict[str, Any]:
        try:
            hours_back = int(hours_back) if hours_back else 48
            max_activities = int(max_activities) if max_activities else 10
        except (ValueError, TypeError):
            hours_back, max_activities = 48, 10
        
        # Get my recent activities
        from datetime import datetime, timedelta
        after_timestamp = int((datetime.now() - timedelta(hours=hours_back)).timestamp())
        
        activities_result = self._client.get_activities(per_page=max_activities, after=after_timestamp)
        
        if not activities_result or (isinstance(activities_result, list) and len(activities_result) > 0 and "error" in activities_result[0]):
            return {"error": "Failed to get activities", "details": activities_result}
        
        storage = self._get_storage()
        
        # Get existing kudos givers
        existing_givers = storage.get("strava", "kudos_givers", {})
        
        new_givers_count = 0
        updated_givers_count = 0
        activities_checked = 0
        total_kudos_found = 0
        
        for activity in activities_result:
            activity_id = activity.get("id")
            if not activity_id:
                continue
            
            activities_checked += 1
            
            # Get kudos for this activity
            kudos_result = self._client.get_activity_kudos(activity_id)
            if "error" in kudos_result:
                logger.warning(f"Failed to get kudos for activity {activity_id}: {kudos_result['error']}")
                continue
            
            givers = kudos_result.get("givers", [])
            total_kudos_found += len(givers)
            
            for giver in givers:
                # Use athlete_id as identifier (web endpoint provides it)
                athlete_id = giver.get("athlete_id")
                if not athlete_id:
                    # Fallback to name-based key if no athlete_id
                    athlete_id = f"name:{giver.get('firstname', '')}_{giver.get('lastname', '')}".lower().replace(" ", "_")
                
                display_name = giver.get("display_name", "")
                username = giver.get("username", "")
                now = datetime.now().isoformat()
                
                if athlete_id in existing_givers:
                    # Check if we already counted this activity for this giver (idempotency)
                    counted_activities = existing_givers[athlete_id].get("counted_activities", [])
                    if activity_id in counted_activities:
                        # Already counted this kudos, skip
                        continue
                    
                    # Update existing - new kudos from new activity
                    existing_givers[athlete_id]["kudos_count"] = existing_givers[athlete_id].get("kudos_count", 0) + 1
                    existing_givers[athlete_id]["last_kudos_at"] = now
                    existing_givers[athlete_id]["counted_activities"] = counted_activities + [activity_id]
                    # Update username if we have it now
                    if username and not existing_givers[athlete_id].get("username"):
                        existing_givers[athlete_id]["username"] = username
                    updated_givers_count += 1
                else:
                    # New giver
                    existing_givers[athlete_id] = {
                        "athlete_id": athlete_id,
                        "display_name": display_name,
                        "username": username,
                        "kudos_count": 1,
                        "counted_activities": [activity_id],  # Track which activities we counted
                        "first_kudos_at": now,
                        "last_kudos_at": now,
                        "last_reciprocated_at": None,
                    }
                    new_givers_count += 1
        
        # Save updated givers
        storage.set("strava", "kudos_givers", existing_givers)
        
        return {
            "success": True,
            "activities_checked": activities_checked,
            "total_kudos_found": total_kudos_found,
            "new_givers": new_givers_count,
            "updated_givers": updated_givers_count,
            "total_known_givers": len(existing_givers),
        }


class StravaListKudosGiversTool(Tool):
    """List all known kudos givers from accumulated knowledge."""
    
    def __init__(self, config):
        self._storage = None
    
    def _get_storage(self) -> StorageClient:
        if self._storage is None:
            self._storage = StorageClient()
        return self._storage
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_list_kudos_givers",
            description="List all people who have given you kudos (from accumulated knowledge)",
            parameters=[
                {"name": "limit", "type": "integer", "description": "Maximum number to return (default: all)"},
                {"name": "sort_by", "type": "string", "description": "Sort by: 'count' (most kudos) or 'recent' (most recent)"},
            ],
            required_params=[],
            domain="fitness",
            concepts=["strava", "kudos", "givers", "list", "who"],
            synonyms=["who gave me kudos", "list kudos givers", "kudos supporters"],
        )
    
    def execute(self, limit: int = None, sort_by: str = "count", **kwargs) -> Dict[str, Any]:
        storage = self._get_storage()
        givers = storage.get("strava", "kudos_givers", {})
        
        if not givers:
            return {
                "givers": [],
                "total": 0,
                "message": "No kudos givers recorded yet. Run strava_collect_kudos_givers first.",
            }
        
        # Convert to list for sorting
        givers_list = list(givers.values())
        
        # Sort
        if sort_by == "recent":
            givers_list.sort(key=lambda x: x.get("last_kudos_at", ""), reverse=True)
        else:  # Default: by count
            givers_list.sort(key=lambda x: x.get("kudos_count", 0), reverse=True)
        
        # Limit
        if limit:
            try:
                limit = int(limit)
                givers_list = givers_list[:limit]
            except (ValueError, TypeError):
                pass
        
        return {
            "givers": givers_list,
            "total": len(givers),
            "showing": len(givers_list),
        }


class StravaReciprocateKudosTool(Tool):
    """
    Automatically give kudos to athletes who have given you kudos.
    
    Looks at the dashboard feed, finds activities where:
    1. can_kudo is True
    2. The athlete has previously given you kudos
    
    Optionally runs in dry_run mode to preview without acting.
    """
    
    def __init__(self, config):
        self._client = StravaClientV2(config)
        self._storage = None
    
    def _get_storage(self) -> StorageClient:
        if self._storage is None:
            self._storage = StorageClient()
        return self._storage
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="strava_reciprocate_kudos",
            description="Give kudos back to athletes who have given you kudos (reciprocate)",
            parameters=[
                {"name": "count", "type": "integer", "description": "How many dashboard activities to check (default: 20)"},
                {"name": "max_age_hours", "type": "integer", "description": "Only kudos activities newer than this many hours (default: no limit)"},
                {"name": "dry_run", "type": "boolean", "description": "Preview only, don't actually give kudos (default: false)"},
            ],
            required_params=[],
            domain="fitness",
            concepts=["strava", "kudos", "reciprocate", "auto", "give back"],
            synonyms=["reciprocate kudos", "give kudos back", "auto kudos", "kudos exchange"],
        )
    
    def execute(self, count: int = 20, max_age_hours: int = None, dry_run: bool = False, **kwargs) -> Dict[str, Any]:
        try:
            count = int(count) if count else 20
        except (ValueError, TypeError):
            count = 20
        
        # Handle max_age_hours
        max_age_cutoff = None
        if max_age_hours:
            try:
                max_age_hours = int(max_age_hours)
                max_age_cutoff = datetime.now() - timedelta(hours=max_age_hours)
            except (ValueError, TypeError):
                pass
        
        # Handle string "true"/"false" for dry_run
        if isinstance(dry_run, str):
            dry_run = dry_run.lower() in ("true", "1", "yes")
        
        storage = self._get_storage()
        
        # Get known kudos givers
        known_givers = storage.get("strava", "kudos_givers", {})
        if not known_givers:
            return {
                "error": "No known kudos givers. Run strava_collect_kudos_givers first.",
            }
        
        known_giver_ids = set(known_givers.keys())
        
        # Get dashboard feed
        from neural_engine.v2.tools.strava import StravaGetDashboardFeedTool
        feed_tool = StravaGetDashboardFeedTool.__new__(StravaGetDashboardFeedTool)
        feed_tool._client = self._client
        feed_result = feed_tool.execute(count=count)
        
        if "error" in feed_result:
            return feed_result
        
        activities = feed_result.get("activities", [])
        
        # Find activities to kudos
        to_kudos = []
        already_kudoed = []
        not_a_giver = []
        too_old = []
        
        for activity in activities:
            athlete_id = str(activity.get("athlete_id", ""))
            athlete_name = activity.get("athlete", "")
            can_kudo = activity.get("can_kudo", False)
            has_kudoed = activity.get("has_kudoed", False)
            
            # Check activity age
            if max_age_cutoff:
                activity_time_str = activity.get("time", "")
                if activity_time_str:
                    try:
                        # Parse activity time (format: "2026-01-18T10:30:00Z" or similar)
                        activity_time = datetime.fromisoformat(activity_time_str.replace("Z", "+00:00").replace("+00:00", ""))
                        if activity_time < max_age_cutoff:
                            too_old.append(activity)
                            continue
                    except (ValueError, TypeError):
                        pass  # If we can't parse, don't filter
            
            if has_kudoed:
                already_kudoed.append(activity)
                continue
            
            if not can_kudo:
                continue
            
            # Match by athlete_id first (primary), then by name fallback
            matched_key = None
            matched_giver = None
            
            if athlete_id and athlete_id in known_giver_ids:
                matched_key = athlete_id
                matched_giver = known_givers[athlete_id]
            else:
                # Fallback: try matching by display_name
                for giver_key, giver_info in known_givers.items():
                    if giver_info.get("display_name", "").lower() == athlete_name.lower():
                        matched_key = giver_key
                        matched_giver = giver_info
                        break
            
            if matched_giver:
                to_kudos.append({
                    **activity,
                    "giver_info": matched_giver,
                    "matched_key": matched_key,
                })
            else:
                not_a_giver.append(activity)
        
        # Execute kudos (unless dry_run)
        kudos_given = []
        kudos_failed = []
        
        if not dry_run:
            for activity in to_kudos:
                activity_id = activity.get("id")
                result = self._client.give_kudos(activity_id)
                
                if result.get("success"):
                    kudos_given.append({
                        "activity_id": activity_id,
                        "activity_name": activity.get("name"),
                        "athlete": activity.get("athlete"),
                        "their_kudos_count": activity.get("giver_info", {}).get("kudos_count", 0),
                    })
                    
                    # Update last_reciprocated_at using matched_key
                    matched_key = activity.get("matched_key")
                    if matched_key and matched_key in known_givers:
                        known_givers[matched_key]["last_reciprocated_at"] = datetime.now().isoformat()
                else:
                    kudos_failed.append({
                        "activity_id": activity_id,
                        "error": result.get("error"),
                    })
            
            # Save updated givers with reciprocation timestamps
            if kudos_given:
                storage.set("strava", "kudos_givers", known_givers)
        
        return {
            "dry_run": dry_run,
            "max_age_hours": max_age_hours,
            "activities_checked": len(activities),
            "too_old": len(too_old),
            "known_givers_in_feed": len(to_kudos),
            "already_kudoed": len(already_kudoed),
            "not_a_giver_count": len(not_a_giver),
            "not_a_giver": [
                {"athlete": a.get("athlete"), "activity": a.get("name")}
                for a in not_a_giver
            ],
            "kudos_given" if not dry_run else "would_kudos": [
                {
                    "activity": a.get("name"),
                    "athlete": a.get("athlete"),
                    "their_kudos_to_you": a.get("giver_info", {}).get("kudos_count", 0),
                }
                for a in (kudos_given if not dry_run else to_kudos)
            ],
            "failed": kudos_failed if not dry_run else [],
        }


def create_strava_tools(config) -> List[Tool]:
    """Create all Strava tools."""
    return [
        # API-based tools
        StravaGetActivitiesTool(config),
        StravaGetActivityTool(config),
        StravaCheckAuthTool(config),
        StravaSetupTool(config),
        # Web-based tools (require cookies)
        StravaGiveKudosTool(config),
        StravaGetDashboardFeedTool(config),
        StravaUpdateActivityTool(config),
        # Kudos automation tools
        StravaCollectKudosGiversTool(config),
        StravaListKudosGiversTool(config),
        StravaReciprocateKudosTool(config),
    ]
