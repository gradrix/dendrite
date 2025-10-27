import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import requests
from neural_engine.core.key_value_store import KeyValueStore
from neural_engine.core.exceptions import AuthenticationRequiredError

class StravaClient:
    def __init__(self, kv_store: KeyValueStore):
        self.kv_store = kv_store
        self.session = requests.Session()
        self.api_token = None
        self.csrf_token = None
        self._load_credentials()

    def _load_credentials(self):
        cookies = self.kv_store.get("strava_cookies")
        if cookies:
            self.session.cookies.update(cookies)

        self.api_token = self.kv_store.get("strava_token")

        if not cookies or not self.api_token:
            raise AuthenticationRequiredError("Strava credentials not found in KeyValueStore. Please set 'strava_cookies' and 'strava_token'.")

        self._extract_csrf_token()

    def _extract_csrf_token(self):
        try:
            response = self.session.get("https://www.strava.com/dashboard", timeout=10)
            response.raise_for_status()

            import re
            match = re.search(r'"csrf-token"\s*content="([^"]+)"', response.text)
            if not match:
                match = re.search(r'csrf[_-]?token[":\s]+(["\'])([^"\']+)\1', response.text, re.IGNORECASE)

            if match:
                self.csrf_token = match.group(2) if len(match.groups()) > 1 else match.group(1)
        except Exception as e:
            pass

    def _refresh_token(self):
        # Placeholder for future implementation
        pass

    def _get_headers(self, referer: str = "https://www.strava.com/dashboard") -> Dict[str, str]:
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

            try:
                return response.json()
            except:
                return response.text

        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 401:
                if self._refresh_token():
                    try:
                        if headers is None:
                            headers = self._get_headers()

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

                        try:
                            return response.json()
                        except:
                            return response.text
                    except Exception as retry_error:
                        raise
            raise
        except Exception as e:
            raise

    def update_activity(
        self,
        activity_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        visibility: Optional[str] = None,
        trainer: Optional[bool] = None,
        commute: Optional[bool] = None,
        hide_from_home: Optional[bool] = None,
        map_visibility: Optional[str] = None,
        selected_polyline_style: Optional[str] = None
    ) -> Dict[str, Any]:
        url = f"https://www.strava.com/activities/{activity_id}"
        headers = self._get_headers(referer=url)

        data = {
            "utf8": "✓",
            "_method": "patch"
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
                "private": "only_me"
            }
            data["activity[visibility]"] = visibility_map.get(visibility.lower(), visibility)
        if trainer is not None:
            data["activity[trainer]"] = "1" if trainer else "0"
        if commute is not None:
            data["activity[commute]"] = "1" if commute else "0"
        if hide_from_home is not None:
            data["activity[hide_from_home]"] = "1" if hide_from_home else "0"
        if map_visibility is not None:
            data["activity[map_visibility]"] = map_visibility
        if selected_polyline_style is not None:
            data["activity[selected_polyline_style]"] = selected_polyline_style

        if len(data) <= 2:
            return {"success": False, "error": "No fields to update"}

        try:
            response = self.session.request(
                method="POST",
                url=url,
                headers=headers,
                data=data,
                timeout=30
            )

            response.raise_for_status()

            updated_fields = list(k for k in data.keys() if k not in ['utf8', '_method'])
            return {"success": True, "activity_id": activity_id, "updated_fields": updated_fields}

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 'unknown'
            return {"success": False, "error": f"HTTP {status}", "activity_id": activity_id}
        except Exception as e:
            return {"success": False, "error": str(e), "activity_id": activity_id}

    def get_activity_kudos(self, activity_id: int) -> List[Dict[str, Any]]:
        url = f"https://www.strava.com/feed/activity/{activity_id}/kudos"
        headers = self._get_headers(referer=f"https://www.strava.com/activities/{activity_id}")

        try:
            response = self._make_request("GET", url, headers=headers)

            if isinstance(response, dict):
                if 'athletes' in response:
                    return response['athletes']
                elif 'models' in response:
                    return response['models']
                elif 'kudosers' in response:
                    return response['kudosers']
                elif 'entries' in response:
                    return response['entries']
                elif 'data' in response:
                    return response['data']
            elif isinstance(response, list):
                return response

            return []

        except Exception as e:
            return []

    def get_following(self) -> List[Dict[str, Any]]:
        url = "https://www.strava.com/athlete/following"
        return self._make_request("GET", url)

    def get_followers(self, per_page: int = 1000) -> List[Dict[str, Any]]:
        url = f"https://www.strava.com/athlete/followers?per_page={per_page}"
        response = self._make_request("GET", url)

        if isinstance(response, dict) and 'results' in response:
            return response['results'].get('followers', [])
        return response

    def get_activity_participants(self, activity_id: int) -> List[Dict[str, Any]]:
        url = f"https://www.strava.com/feed/activity/{activity_id}/group_athletes"
        headers = self._get_headers(referer=f"https://www.strava.com/activities/{activity_id}")
        response = self._make_request("GET", url, headers=headers)

        if isinstance(response, dict) and 'athletes' in response:
            return response['athletes']
        return response

    def is_activity_kudosable(self, activity_id: int) -> bool:
        url = f"https://www.strava.com/feed/activity/{activity_id}/kudos"
        headers = self._get_headers(referer=f"https://www.strava.com/activities/{activity_id}")

        try:
            response = self._make_request("GET", url, headers=headers)
            if isinstance(response, dict):
                return response.get('kudosable', False)
            return False
        except Exception as e:
            return False

    def give_kudos(self, activity_id: int) -> bool:
        url = f"https://www.strava.com/feed/activity/{activity_id}/kudo"
        headers = self._get_headers(referer=f"https://www.strava.com/activities/{activity_id}")

        try:
            if not self.is_activity_kudosable(activity_id):
                return False

            self._make_request("POST", url, headers=headers, data="")
            return True
        except Exception as e:
            return False

    def get_dashboard_feed(
        self,
        before: Optional[int] = None,
        cursor: Optional[int] = None,
        num_entries: int = 20
    ) -> Dict[str, Any]:
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

    def get_logged_in_athlete_activities(
        self,
        after: Optional[int] = None,
        before: Optional[int] = None,
        page: int = 1,
        per_page: int = 30
    ) -> List[Dict[str, Any]]:
        if not self.api_token:
            raise AuthenticationRequiredError("Strava API token not available.")

        url = "https://www.strava.com/api/v3/athlete/activities"

        params = {
            "page": page,
            "per_page": min(per_page, 200)
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

            if response.status_code == 401:
                if self._refresh_token():
                    headers = self._get_api_headers()
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
                return activities
            else:
                return []

        except requests.exceptions.HTTPError as e:
            raise
        except Exception as e:
            raise
