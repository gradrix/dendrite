#!/bin/bash

# Script to get a Strava OAuth token with full scopes

if [ "$#" -lt 1 ]; then
    echo "============================================"
    echo "  Get Strava OAuth Token"
    echo "============================================"
    echo
    echo "This script helps you get an OAuth token with activity access."
    echo
    echo "Usage:"
    echo "  Step 1: Get your Client ID and Secret"
    echo "    Go to: https://www.strava.com/settings/api"
    echo "    Copy your 'Client ID' and 'Client Secret'"
    echo
    echo "  Step 2: Authorize (run this with your client ID):"
    echo "    $0 authorize YOUR_CLIENT_ID"
    echo
    echo "  Step 3: Exchange code for token:"
    echo "    $0 exchange YOUR_CLIENT_ID YOUR_CLIENT_SECRET AUTHORIZATION_CODE"
    echo
    exit 1
fi

COMMAND=$1

if [ "$COMMAND" = "authorize" ]; then
    if [ "$#" -lt 2 ]; then
        echo "❌ Error: Missing CLIENT_ID"
        echo "Usage: $0 authorize YOUR_CLIENT_ID"
        exit 1
    fi
    
    CLIENT_ID=$2
    
    # Build OAuth URL with required scopes
    SCOPES="read,activity:read_all,profile:read_all"
    AUTH_URL="https://www.strava.com/oauth/authorize?client_id=${CLIENT_ID}&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=${SCOPES}"
    
    echo "============================================"
    echo "  Step 1: Authorize Application"
    echo "============================================"
    echo
    echo "Opening authorization URL..."
    echo
    echo "URL: $AUTH_URL"
    echo
    echo "This will request these scopes:"
    echo "  ✅ read - View public data"
    echo "  ✅ activity:read_all - Read all your activities (public + private)"
    echo "  ✅ profile:read_all - Read your profile"
    echo
    echo "After clicking 'Authorize', you'll be redirected to:"
    echo "  http://localhost/?code=AUTHORIZATION_CODE"
    echo
    echo "Copy the code from the URL and run:"
    echo "  $0 exchange $CLIENT_ID YOUR_CLIENT_SECRET THE_CODE"
    echo
    
    # Try to open browser (works on macOS, Linux with xdg-open)
    if command -v open &> /dev/null; then
        open "$AUTH_URL"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "$AUTH_URL"
    else
        echo "Couldn't open browser automatically. Please open the URL manually."
    fi

elif [ "$COMMAND" = "exchange" ]; then
    if [ "$#" -lt 4 ]; then
        echo "❌ Error: Missing arguments"
        echo "Usage: $0 exchange CLIENT_ID CLIENT_SECRET AUTHORIZATION_CODE"
        exit 1
    fi
    
    CLIENT_ID=$2
    CLIENT_SECRET=$3
    AUTH_CODE=$4
    
    echo "============================================"
    echo "  Step 2: Exchange Code for Token"
    echo "============================================"
    echo
    echo "Exchanging authorization code for access token..."
    
    RESPONSE=$(curl -s -X POST https://www.strava.com/oauth/token \
        -d client_id="$CLIENT_ID" \
        -d client_secret="$CLIENT_SECRET" \
        -d code="$AUTH_CODE" \
        -d grant_type=authorization_code)
    
    # Check if response contains error
    if echo "$RESPONSE" | grep -q '"error"'; then
        echo "❌ ERROR:"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
        exit 1
    fi
    
    # Extract access token
    ACCESS_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)
    REFRESH_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('refresh_token', ''))" 2>/dev/null)
    EXPIRES_AT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('expires_at', ''))" 2>/dev/null)
    
    if [ -z "$ACCESS_TOKEN" ]; then
        echo "❌ Failed to extract access token"
        echo "Response:"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
        exit 1
    fi
    
    echo "✅ SUCCESS!"
    echo
    echo "Token Details:"
    echo "  Access Token: ${ACCESS_TOKEN:0:8}...${ACCESS_TOKEN: -4}"
    echo "  Refresh Token: ${REFRESH_TOKEN:0:8}...${REFRESH_TOKEN: -4}"
    
    if [ -n "$EXPIRES_AT" ]; then
        EXPIRES_DATE=$(date -r "$EXPIRES_AT" 2>/dev/null || date -d "@$EXPIRES_AT" 2>/dev/null || echo "N/A")
        echo "  Expires: $EXPIRES_DATE"
    fi
    
    echo
    echo "Saving token to .strava_token..."
    echo "$ACCESS_TOKEN" > .strava_token
    
    echo "Saving refresh token to .strava_refresh_token..."
    echo "$REFRESH_TOKEN" > .strava_refresh_token
    
    echo
    echo "✅ Token saved! Testing API access..."
    echo
    
    # Test the token
    ./test_strava_token.sh 2>/dev/null || {
        # If test script doesn't exist, do a simple test
        TEST_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" "https://www.strava.com/api/v3/athlete/activities?per_page=1")
        
        if echo "$TEST_RESPONSE" | grep -q '\[' 2>/dev/null; then
            echo "✅ Token works! Can access activities!"
        else
            echo "⚠️  Token saved but couldn't test activities endpoint"
        fi
    }
    
    echo
    echo "============================================"
    echo "  Setup Complete!"
    echo "============================================"
    echo
    echo "Your token is saved and ready to use."
    echo "The agent will now be able to fetch your activities."
    echo

else
    echo "❌ Unknown command: $COMMAND"
    echo "Use: authorize or exchange"
    exit 1
fi
