#!/bin/bash
set -e

echo "🛑 Stopping Dendrite Neural Engine..."

docker compose down

echo "✅ All services stopped"
