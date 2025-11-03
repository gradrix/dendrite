#!/bin/bash

SERVICE=${1:-app}

echo "🐚 Opening shell in $SERVICE container..."
docker compose exec "$SERVICE" /bin/bash || docker compose exec "$SERVICE" /bin/sh
