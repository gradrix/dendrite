#!/bin/bash

# Strava Token Refresh Script
# Refreshes the access token using the refresh token

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔄 Strava Token Refresh${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found${NC}"
    echo "Create .env with STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET"
    exit 1
fi

# Load environment variables
source .env

# Check for required variables
if [ -z "$STRAVA_CLIENT_ID" ] || [ -z "$STRAVA_CLIENT_SECRET" ]; then
    echo -e "${RED}❌ Missing credentials in .env${NC}"
    echo "Required: STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET"
    exit 1
fi

# Check if refresh token exists
if [ ! -f .strava_refresh_token ]; then
    echo -e "${RED}❌ .strava_refresh_token file not found${NC}"
    echo "Run ./get_token_manual.sh to get initial tokens"
    exit 1
fi

# Read refresh token
REFRESH_TOKEN=$(cat .strava_refresh_token | tr -d '"' | tr -d "'")

echo -e "${YELLOW}📡 Requesting new access token...${NC}"
echo ""

# Make token refresh request
RESPONSE=$(curl -s -X POST https://www.strava.com/api/v3/oauth/token \
  -d client_id="$STRAVA_CLIENT_ID" \
  -d client_secret="$STRAVA_CLIENT_SECRET" \
  -d grant_type=refresh_token \
  -d refresh_token="$REFRESH_TOKEN")

# Check if request was successful
if echo "$RESPONSE" | grep -q "access_token"; then
    # Extract tokens from response
    ACCESS_TOKEN=$(echo "$RESPONSE" | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//')
    NEW_REFRESH_TOKEN=$(echo "$RESPONSE" | grep -o '"refresh_token":"[^"]*' | sed 's/"refresh_token":"//')
    EXPIRES_AT=$(echo "$RESPONSE" | grep -o '"expires_at":[0-9]*' | sed 's/"expires_at"://')
    EXPIRES_IN=$(echo "$RESPONSE" | grep -o '"expires_in":[0-9]*' | sed 's/"expires_in"://')
    
    if [ -z "$ACCESS_TOKEN" ]; then
        echo -e "${RED}❌ Failed to extract access token from response${NC}"
        echo "Response: $RESPONSE"
        exit 1
    fi
    
    # Save new access token
    echo "$ACCESS_TOKEN" > .strava_token
    echo -e "${GREEN}✅ Access token saved to .strava_token${NC}"
    
    # Save new refresh token (it may have changed)
    if [ -n "$NEW_REFRESH_TOKEN" ]; then
        echo "$NEW_REFRESH_TOKEN" > .strava_refresh_token
        echo -e "${GREEN}✅ Refresh token updated${NC}"
    fi
    
    # Show expiration info
    if [ -n "$EXPIRES_AT" ]; then
        EXPIRES_DATE=$(date -d "@$EXPIRES_AT" 2>/dev/null || date -r "$EXPIRES_AT" 2>/dev/null || echo "unknown")
        echo -e "${BLUE}⏰ Token expires at: $EXPIRES_DATE${NC}"
    fi
    
    if [ -n "$EXPIRES_IN" ]; then
        HOURS=$((EXPIRES_IN / 3600))
        echo -e "${BLUE}⏰ Valid for: $HOURS hours ($EXPIRES_IN seconds)${NC}"
    fi
    
    # Mask tokens for display
    ACCESS_DISPLAY="${ACCESS_TOKEN:0:8}...${ACCESS_TOKEN: -4}"
    echo ""
    echo -e "${GREEN}✅ Token refresh successful!${NC}"
    echo -e "${BLUE}New access token: $ACCESS_DISPLAY${NC}"
    
else
    echo -e "${RED}❌ Token refresh failed${NC}"
    echo ""
    echo "Response:"
    echo "$RESPONSE"
    echo ""
    
    # Check for common errors
    if echo "$RESPONSE" | grep -q "invalid"; then
        echo -e "${YELLOW}💡 Refresh token may be invalid or expired${NC}"
        echo "Run ./get_token_manual.sh to get new tokens"
    fi
    
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Ready to use Strava API!${NC}"
