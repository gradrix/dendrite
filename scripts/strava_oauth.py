#!/usr/bin/env python3
"""
Strava OAuth Helper Script

This script helps you get OAuth tokens with the correct scopes.

Usage:
  1. Run: python scripts/strava_oauth.py
  2. Click the link it generates
  3. Authorize in browser
  4. Copy the 'code' from the redirect URL
  5. Paste it back and it will save tokens to Redis
"""

import os
import sys
import requests
import webbrowser

# Get from environment or hardcode for convenience
CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "182379")
CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "66b6a95f19b2b2278004822e381004b693c55e69")
REDIRECT_URI = "http://localhost"

# Scopes we need
SCOPES = "read,activity:read_all,profile:read_all"

def get_auth_url():
    """Generate the authorization URL."""
    return (
        f"https://www.strava.com/oauth/authorize?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={SCOPES}"
    )

def exchange_code(code: str):
    """Exchange authorization code for tokens."""
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        }
    )
    
    if not response.ok:
        print(f"Error: {response.text}")
        sys.exit(1)
    
    return response.json()

def save_to_redis(data: dict):
    """Save tokens to Redis."""
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.set("strava:client_id", CLIENT_ID)
        r.set("strava:client_secret", CLIENT_SECRET)
        r.set("strava:token", data["access_token"])
        r.set("strava:refresh_token", data["refresh_token"])
        r.set("strava:token_expires", data["expires_at"])
        print("\n✅ Tokens saved to Redis!")
        r.close()
    except Exception as e:
        print(f"\n⚠️  Could not save to Redis: {e}")
        print("\nRun these commands manually:")
        print(f"  docker compose exec redis redis-cli SET strava:client_id {CLIENT_ID}")
        print(f"  docker compose exec redis redis-cli SET strava:client_secret {CLIENT_SECRET}")
        print(f"  docker compose exec redis redis-cli SET strava:token {data['access_token']}")
        print(f"  docker compose exec redis redis-cli SET strava:refresh_token {data['refresh_token']}")
        print(f"  docker compose exec redis redis-cli SET strava:token_expires {data['expires_at']}")

def main():
    print("=" * 60)
    print("STRAVA OAUTH HELPER")
    print("=" * 60)
    print(f"\nClient ID: {CLIENT_ID}")
    print(f"Scopes: {SCOPES}")
    
    auth_url = get_auth_url()
    
    print("\n1. Open this URL in your browser:")
    print(f"\n   {auth_url}\n")
    
    # Try to open browser
    try:
        webbrowser.open(auth_url)
        print("   (Browser should have opened automatically)")
    except:
        pass
    
    print("\n2. Click 'Authorize' in the Strava popup")
    print("\n3. You'll be redirected to localhost with a 'code' parameter")
    print("   The URL will look like: http://localhost?state=&code=XXXX&scope=...")
    print("\n4. Copy the code value and paste it here:")
    
    code = input("\nAuthorization code: ").strip()
    
    if not code:
        print("No code provided. Exiting.")
        sys.exit(1)
    
    print("\nExchanging code for tokens...")
    data = exchange_code(code)
    
    print(f"\n✅ Got tokens!")
    print(f"   Access Token: {data['access_token'][:20]}...")
    print(f"   Refresh Token: {data['refresh_token'][:20]}...")
    print(f"   Expires At: {data['expires_at']}")
    print(f"   Athlete: {data.get('athlete', {}).get('firstname', 'Unknown')}")
    
    save_to_redis(data)
    
    print("\n✅ Done! You can now use Strava tools with activity scope.")

if __name__ == "__main__":
    main()
