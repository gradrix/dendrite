#!/bin/bash

# Script to remove sensitive files from git history
# WARNING: This rewrites history and requires force-push

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}  REMOVE SENSITIVE FILES FROM GIT HISTORY${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will rewrite git history!${NC}"
echo ""
echo "Files to remove:"
echo "  - .strava_token"
echo "  - .strava_refresh_token"
echo ""
echo "What this does:"
echo "  1. Removes files from ALL commits in history"
echo "  2. Requires force-push to remote"
echo "  3. Breaks existing clones (collaborators need fresh clone)"
echo ""
echo "Prerequisites:"
echo "  1. Install git-filter-repo:"
echo "     pip install git-filter-repo"
echo "  2. Backup your repo first!"
echo ""
echo -e "${RED}Have you revoked your Strava tokens? (CRITICAL!)${NC}"
echo "  → https://www.strava.com/settings/apps"
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi

# Check if git-filter-repo is installed
if ! command -v git-filter-repo &> /dev/null; then
    echo -e "${RED}ERROR: git-filter-repo not found${NC}"
    echo ""
    echo "Install it with:"
    echo "  pip install git-filter-repo"
    echo ""
    echo "Or on Ubuntu/Debian:"
    echo "  sudo apt install git-filter-repo"
    exit 1
fi

# Create backup
echo ""
echo "Creating backup..."
BACKUP_DIR="../center-backup-$(date +%Y%m%d-%H%M%S)"
cp -r . "$BACKUP_DIR"
echo -e "${GREEN}✓ Backup created: $BACKUP_DIR${NC}"

# Remove files from history
echo ""
echo "Removing files from git history..."
git-filter-repo --invert-paths \
    --path .strava_token \
    --path .strava_refresh_token \
    --force

echo ""
echo -e "${GREEN}✓ Files removed from history${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "NEXT STEPS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Verify .gitignore has these lines:"
echo "   .strava_token"
echo "   .strava_refresh_token"
echo ""
echo "2. Force-push to remote (DANGER!):"
echo "   git push origin --force --all"
echo "   git push origin --force --tags"
echo ""
echo "3. Notify collaborators (if any) to:"
echo "   - Delete their local clone"
echo "   - Make fresh clone"
echo ""
echo "4. Generate new Strava tokens:"
echo "   ./scripts/setup-strava-auth.sh authorize YOUR_CLIENT_ID"
echo ""
echo -e "${YELLOW}⚠️  Old tokens in GitHub are still valid until revoked!${NC}"
echo ""
