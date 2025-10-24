#!/bin/bash

# Manual OAuth flow - no browser needed!

if [ "$#" -lt 1 ]; then
    echo "============================================"
    echo "  Get Strava Token - Manual Method"
    echo "  (No browser automation required)"
    echo "============================================"
    echo
    echo "Step 1: Get Client ID and Secret"
    echo "  Go to: https://www.strava.com/settings/api"
    echo "  Copy your Client ID and Client Secret"
    echo
    echo "Step 2: Build authorization URL"
    echo "  ./get_token_manual.sh auth YOUR_CLIENT_ID"
    echo
    echo "Step 3: Open URL manually, authorize, copy code"
    echo
    echo "Step 4: Exchange code for token"
    echo "  ./get_token_manual.sh token YOUR_CLIENT_ID YOUR_CLIENT_SECRET CODE"
    echo
    exit 0
fi

COMMAND=$1

if [ "$COMMAND" = "auth" ]; then
    CLIENT_ID=$2
    
    if [ -z "$CLIENT_ID" ]; then
        echo "Usage: $0 auth YOUR_CLIENT_ID"
        exit 1
    fi
    
    # The trick: use "localhost" as redirect - no real server needed
    # After auth, Strava redirects to http://localhost/?code=XXX
    # Just copy the code from the URL bar!
    
    AUTH_URL="https://www.strava.com/oauth/authorize?client_id=${CLIENT_ID}&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=read,activity:read_all,profile:read_all"
    
    echo "============================================"
    echo "  Authorization URL"
    echo "============================================"
    echo
    echo "Copy this URL and paste it in your browser:"
    echo
    echo "$AUTH_URL"
    echo
    echo "After clicking 'Authorize', the browser will try to redirect to:"
    echo "  http://localhost/?code=SOME_LONG_CODE_HERE&scope=..."
    echo
    echo "The page won't load (that's OK!). Just look at the URL bar and copy the 'code' parameter."
    echo
    echo "Example URL:"
    echo "  http://localhost/?code=abc123def456&scope=read,activity:read_all"
    echo "  ^^^^^^^^^^^^^^^^"
    echo "  Copy this part: abc123def456"
    echo
    echo "Then run:"
    echo "  $0 token $CLIENT_ID YOUR_CLIENT_SECRET THE_CODE"
    echo

elif [ "$COMMAND" = "token" ]; then
    CLIENT_ID=$2
    CLIENT_SECRET=$3
    CODE=$4
    
    if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ] || [ -z "$CODE" ]; then
        echo "Usage: $0 token CLIENT_ID CLIENT_SECRET CODE"
        exit 1
    fi
    
    echo "============================================"
    echo "  Exchanging Code for Token"
    echo "============================================"
    echo
    echo "Making API call to oauth/token..."
    
    RESPONSE=$(curl -s -X POST "https://www.strava.com/oauth/token" \
        -d "client_id=${CLIENT_ID}" \
        -d "client_secret=${CLIENT_SECRET}" \
        -d "code=${CODE}" \
        -d "grant_type=authorization_code")
    
    # Check for errors
    if echo "$RESPONSE" | grep -q '"error"'; then
        echo "❌ ERROR:"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
        echo
        echo "Common errors:"
        echo "  - 'Bad Request' = Code already used or invalid"
        echo "  - 'invalid_grant' = Code expired (valid for 30 seconds only!)"
        echo
        echo "Solution: Run step 2 again to get a fresh code"
        exit 1
    fi
    
    # Parse response
    ACCESS_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null)
    REFRESH_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('refresh_token',''))" 2>/dev/null)
    EXPIRES_AT=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('expires_at',''))" 2>/dev/null)
    ATHLETE_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('athlete',{}).get('id',''))" 2>/dev/null)
    ATHLETE_NAME=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('athlete',{}).get('firstname',''))" 2>/dev/null)
    
    if [ -z "$ACCESS_TOKEN" ]; then
        echo "❌ Failed to parse token from response"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
        exit 1
    fi
    
    echo "✅ SUCCESS!"
    echo
    echo "Athlete: $ATHLETE_NAME (ID: $ATHLETE_ID)"
    echo "Token: ${ACCESS_TOKEN:0:10}...${ACCESS_TOKEN: -4}"
    
    if [ -n "$EXPIRES_AT" ]; then
        EXPIRE_DATE=$(date -d "@$EXPIRES_AT" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || date -r "$EXPIRES_AT" "+%Y-%m-%d %H:%M:%S" 2>/dev/null)
        echo "Expires: $EXPIRE_DATE (in 6 hours)"
    fi
    
    echo
    echo "Saving tokens..."
    echo "$ACCESS_TOKEN" > .strava_token
    echo "$REFRESH_TOKEN" > .strava_refresh_token
    
    echo "✅ Saved to .strava_token and .strava_refresh_token"
    echo
    echo "Testing token..."
    
    # Quick test
    TEST=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
        "https://www.strava.com/api/v3/athlete/activities?per_page=1")
    
    if echo "$TEST" | grep -q '\['; then
        echo "✅ Token works! Can fetch activities!"
        
        # Show count
        COUNT=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "https://www.strava.com/api/v3/athlete/activities?per_page=3" | \
            python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
        
        if [ -n "$COUNT" ]; then
            echo "   Found $COUNT recent activities"
        fi
    else
        echo "⚠️  Token saved but couldn't verify activities access"
        echo "   Response: $TEST" | head -c 100
    fi
    
    echo
    echo "============================================"
    echo "  Setup Complete!"
    echo "============================================"

else
    echo "Unknown command: $COMMAND"
    echo "Use: auth or token"
    exit 1
fi
