#!/bin/bash
set -e

echo "🔄 Resetting Dendrite (this will delete all data)..."
read -p "Are you sure? This will remove all Redis data and volumes. (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Reset cancelled"
    exit 1
fi

echo "🛑 Stopping services..."
docker compose down -v

echo "🗑️  Removing volumes..."
docker volume rm center_ai_tools center_kv_store center_ollama_data 2>/dev/null || true

echo "✅ Reset complete. Run ./scripts/start.sh to start fresh"
