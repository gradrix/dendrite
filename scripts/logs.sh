#!/bin/bash

# Default to following all logs
SERVICE=${1:-}

if [ -z "$SERVICE" ]; then
    echo "📋 Showing logs from all services (Ctrl+C to exit)..."
    docker compose logs -f
else
    echo "📋 Showing logs from $SERVICE (Ctrl+C to exit)..."
    docker compose logs -f "$SERVICE"
fi
