#!/bin/bash
set -e

echo "🔧 Starting Dendrite in development mode..."
echo "==========================================="

# Start dependencies first
./scripts/start.sh

echo ""
echo "📦 Development mode active"
echo "- Code changes will be reflected immediately (volume mounted)"
echo "- Press Ctrl+C to stop"
echo ""

# Follow logs
docker compose logs -f app
