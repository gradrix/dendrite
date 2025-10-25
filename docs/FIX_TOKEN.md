# Quick Fix: Get Token with Activity Access

## Problem
Your current token works for profile but not activities:
- ✅ Profile access works (you saw: "Gražvydas Jučius") 
- ❌ Activities fail with 401 (missing `activity:read_all` scope)

## Solution: Get New Token with Correct Scopes

### Step 1: Get Your App Credentials
```bash
# Open Strava API settings
open https://www.strava.com/settings/api
```
- Find your app (or create one if needed)
- Copy **Client ID** (looks like: 123456)
- Copy **Client Secret** (looks like: abc123def456...)

### Step 2: Authorize with Correct Scopes
```bash
./get_strava_token.sh authorize YOUR_CLIENT_ID
```
This will:
- Open browser with authorization URL
- Request these scopes:
  - `read` - View public data
  - `activity:read_all` - **Read all your activities** ⭐
  - `profile:read_all` - Read your profile

After clicking "Authorize", browser redirects to:
```
http://localhost/?code=abc123def456...
```
Copy the `code` value from the URL!

### Step 3: Exchange Code for Token
```bash
./get_strava_token.sh exchange YOUR_CLIENT_ID YOUR_CLIENT_SECRET THE_CODE_FROM_URL
```

This will:
- Exchange code for access token
- Save token to `.strava_token`
- Save refresh token to `.strava_refresh_token`
- Test that it works!

### Step 4: Verify
```bash
/tmp/test_strava_token.sh
```

Should now show:
```
✅ SUCCESS! API call worked
✅ SUCCESS! Found 3 recent activities
```

## Why This Happened

The "Your Access Token" shown on the settings page has **limited scopes**. It's meant for quick testing, not full API access.

To get activities, you MUST use the OAuth flow with explicit `activity:read_all` scope.

## Token Expires in 6 Hours

Strava tokens expire after 6 hours. To refresh:

```bash
# Use the refresh token
TOKEN=$(cat .strava_refresh_token)
CLIENT_ID="your_client_id"
CLIENT_SECRET="your_client_secret"

curl -X POST https://www.strava.com/oauth/token \
  -d client_id=$CLIENT_ID \
  -d client_secret=$CLIENT_SECRET \
  -d grant_type=refresh_token \
  -d refresh_token=$TOKEN
```

We can automate this later if needed!

## Summary

Current token: Profile only ❌  
New token: Profile + Activities ✅

Run the 3 steps above and you'll be all set! 🚀
