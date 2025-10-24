# Strava API Token Setup

The agent uses **dual authentication** for Strava:

1. **Cookies** (`.strava_cookies`) - For web frontend features (dashboard feed, kudos)
2. **API Token** (`.strava_token`) - For official API v3 (your activities, detailed stats)

## Getting Your API Token

### Quick Method (Testing/Personal Use):

1. **Go to**: https://www.strava.com/settings/api
2. **Create an Application**:
   - Application Name: `My Strava Agent` (or any name)
   - Category: Choose any (e.g., "Training")
   - Club: Leave blank
   - Website: `http://localhost` (for testing)
   - Authorization Callback Domain: `localhost`

3. **Get Your Token**:
   - After creating, you'll see "Your Access Token"
   - Copy this token
   - Create `.strava_token` file:
     ```bash
     echo "YOUR_ACCESS_TOKEN_HERE" > .strava_token
     ```

4. **Done!** The token has basic read scopes (read activities, read profile)

### Token Scopes

The quick token from settings page has these scopes:
- `read` - View public activities
- `read_all` - View private activities
- `profile:read_all` - Read profile info

For write operations (update activities), you need:
- `activity:write` - Modify activities

### Full OAuth Flow (For Write Access):

If you need to update activities, use the OAuth flow:

```bash
# 1. Get your Client ID and Secret from settings page
CLIENT_ID="your_client_id"
CLIENT_SECRET="your_client_secret"

# 2. Open this URL in browser (replace CLIENT_ID):
https://www.strava.com/oauth/authorize?client_id=CLIENT_ID&response_type=code&redirect_uri=http://localhost&scope=read,activity:read_all,activity:write&approval_prompt=force

# 3. After approving, browser redirects to:
http://localhost/?code=AUTHORIZATION_CODE

# 4. Exchange code for token:
curl -X POST https://www.strava.com/oauth/token \
  -d client_id=CLIENT_ID \
  -d client_secret=CLIENT_SECRET \
  -d code=AUTHORIZATION_CODE \
  -d grant_type=authorization_code

# 5. Response contains access_token:
{
  "access_token": "your_access_token_here",
  "refresh_token": "your_refresh_token",
  "expires_at": 1234567890
}

# 6. Save to file:
echo "your_access_token_here" > .strava_token
```

## File Format

The `.strava_token` file should contain just the token (no quotes, no JSON):

```
abc123def456ghi789jkl012mno345pqr678stu901
```

**Do NOT commit this file to git!** (Already in `.gitignore`)

## Testing

Test if your token works:

```bash
# Check if file exists
cat .strava_token

# Test API call
TOKEN=$(cat .strava_token)
curl -H "Authorization: Bearer $TOKEN" \
  "https://www.strava.com/api/v3/athlete"
```

Should return your athlete profile!

## Troubleshooting

### 401 Unauthorized
- Token is expired (tokens expire after 6 hours)
- Need to refresh token or get new one
- Check token is in `.strava_token` file correctly

### 403 Forbidden
- Token doesn't have required scope
- For reading activities: need `activity:read_all`
- For updating activities: need `activity:write`

### Missing Token
- Agent will log: "API token not available"
- Create `.strava_token` file with your token
- Restart agent

## Security Notes

- **Never share your access token**
- **Don't commit `.strava_token` to git**
- Tokens expire after 6 hours (use refresh token to renew)
- Revoke tokens at: https://www.strava.com/settings/apps
