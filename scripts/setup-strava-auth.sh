#!/bin/bash

# Unified Strava OAuth setup script
# Supports both browser-automated and manual authorization flows

set -e

show_usage() {
    cat << EOF
============================================
  Strava OAuth Token Setup
============================================

Two modes available:
  1. BROWSER MODE (default) - Opens browser automatically
  2. MANUAL MODE - Copy/paste URL manually

USAGE:

  Step 1: Get Client Credentials
    Go to: https://www.strava.com/settings/api
    Copy your Client ID and Client Secret

  Step 2a: Browser Authorization (automatic):
    $0 authorize YOUR_CLIENT_ID

  Step 2b: Manual Authorization (no browser):
    $0 authorize --manual YOUR_CLIENT_ID
    (Then open the URL in any browser, copy the code)

  Step 3: Exchange code for token:
    $0 exchange YOUR_CLIENT_ID YOUR_CLIENT_SECRET AUTHORIZATION_CODE

SCOPES REQUESTED:
  ✅ read - View public data
  ✅ activity:read_all - View private activities
  ✅ profile:read_all - View private profile data

NOTES:
  - Token saved to: .strava_token
  - Refresh token saved to: .strava_refresh_token
  - Use scripts/refresh-token.sh to renew expired tokens
EOF
    exit 1
}

authorize_browser() {
    CLIENT_ID=$1
    
    if [ -z "$CLIENT_ID" ]; then
        echo "❌ Error: Missing CLIENT_ID"
        echo "Usage: $0 authorize YOUR_CLIENT_ID"
        exit 1
    fi
    
    SCOPES="read,activity:read_all,profile:read_all"
    AUTH_URL="https://www.strava.com/oauth/authorize?client_id=${CLIENT_ID}&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=${SCOPES}"
    
    echo "============================================"
    echo "  Browser Authorization"
    echo "============================================"
    echo
    echo "Opening authorization URL in browser..."
    echo "URL: $AUTH_URL"
    echo
    
    # Try to open browser (cross-platform)
    if command -v xdg-open > /dev/null; then
        xdg-open "$AUTH_URL" 2>/dev/null
    elif command -v open > /dev/null; then
        open "$AUTH_URL" 2>/dev/null
    else
        echo "⚠️  Could not open browser automatically"
        echo "Please open this URL manually:"
        echo "$AUTH_URL"
    fi
    
    echo
    echo "After authorizing:"
    echo "  1. Browser redirects to: http://localhost/?code=XXX&scope=..."
    echo "  2. Copy the 'code' value from the URL"
    echo "  3. Run: $0 exchange YOUR_CLIENT_ID YOUR_CLIENT_SECRET CODE"
    echo
}

authorize_manual() {
    CLIENT_ID=$1
    
    if [ -z "$CLIENT_ID" ]; then
        echo "❌ Error: Missing CLIENT_ID"
        echo "Usage: $0 authorize --manual YOUR_CLIENT_ID"
        exit 1
    fi
    
    SCOPES="read,activity:read_all,profile:read_all"
    AUTH_URL="https://www.strava.com/oauth/authorize?client_id=${CLIENT_ID}&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=${SCOPES}"
    
    echo "============================================"
    echo "  Manual Authorization"
    echo "============================================"
    echo
    echo "Copy this URL and paste it in your browser:"
    echo
    echo "$AUTH_URL"
    echo
    echo "After clicking 'Authorize':"
    echo "  - Browser will try to load: http://localhost/?code=XXX"
    echo "  - It may show an error (that's OK - no server running)"
    echo "  - Look at the URL bar and copy the 'code' parameter"
    echo
    echo "Example:"
    echo "  http://localhost/?code=abc123def456&scope=read,activity:read_all"
    echo "                         ^^^^^^^^^^^^ Copy this part"
    echo
    echo "Then run:"
    echo "  $0 exchange YOUR_CLIENT_ID YOUR_CLIENT_SECRET abc123def456"
    echo
}

exchange_token() {
    CLIENT_ID=$1
    CLIENT_SECRET=$2
    AUTH_CODE=$3
    
    if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ] || [ -z "$AUTH_CODE" ]; then
        echo "❌ Error: Missing required parameters"
        echo "Usage: $0 exchange CLIENT_ID CLIENT_SECRET AUTHORIZATION_CODE"
        exit 1
    fi
    
    echo "============================================"
    echo "  Exchanging Code for Token"
    echo "============================================"
    echo
    echo "Requesting token from Strava..."
    
    # Exchange authorization code for access token
    RESPONSE=$(curl -s -X POST https://www.strava.com/oauth/token \
        -d client_id="$CLIENT_ID" \
        -d client_secret="$CLIENT_SECRET" \
        -d code="$AUTH_CODE" \
        -d grant_type=authorization_code)
    
    # Check for errors
    if echo "$RESPONSE" | grep -q '"errors"'; then
        echo "❌ Error from Strava API:"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
        exit 1
    fi
    
    # Extract tokens using python json
    ACCESS_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
    REFRESH_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['refresh_token'])" 2>/dev/null)
    EXPIRES_AT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['expires_at'])" 2>/dev/null)
    
    if [ -z "$ACCESS_TOKEN" ] || [ -z "$REFRESH_TOKEN" ]; then
        echo "❌ Failed to extract tokens from response"
        echo "$RESPONSE"
        exit 1
    fi
    
    # Save tokens
    echo "$ACCESS_TOKEN" > .strava_token
    echo "$REFRESH_TOKEN" > .strava_refresh_token
    
    echo "✅ Success! Tokens saved:"
    echo "   Access Token:  .strava_token"
    echo "   Refresh Token: .strava_refresh_token"
    echo
    echo "Token expires: $(date -d @${EXPIRES_AT} 2>/dev/null || echo 'in ~6 hours')"
    echo
    echo "💡 To refresh an expired token, run:"
    echo "   scripts/refresh-token.sh $CLIENT_ID $CLIENT_SECRET"
    echo
}

# Main command dispatcher
if [ "$#" -lt 1 ]; then
    show_usage
fi

COMMAND=$1

case "$COMMAND" in
    authorize)
        # Check if --manual flag is present
        if [ "$2" = "--manual" ]; then
            authorize_manual "$3"
        else
            authorize_browser "$2"
        fi
        ;;
    exchange)
        exchange_token "$2" "$3" "$4"
        ;;
    -h|--help|help)
        show_usage
        ;;
    *)
        echo "❌ Unknown command: $COMMAND"
        echo
        show_usage
        ;;
esac
