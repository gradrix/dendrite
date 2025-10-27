#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: ./scripts/run.sh 'your goal here'"
    echo ""
    echo "Example:"
    echo "  ./scripts/run.sh 'How many running activities did I have in September?'"
    exit 1
fi

GOAL="$1"

echo "🧠 Executing Neural Engine Goal"
echo "==============================="
echo "Goal: $GOAL"
echo ""

# Ensure services are running
if ! docker compose ps | grep -q "Up"; then
    echo "🚀 Starting services..."
    ./scripts/start.sh
fi

# Execute the goal
docker compose exec -T app python main.py --goal "$GOAL"
