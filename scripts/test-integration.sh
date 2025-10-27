#!/bin/bash
set -e

echo "🧪 Running Integration Tests Only"
echo "================================="

# Run tests marked as integration (require real services)
./scripts/test.sh neural_engine/tests/it_*.py "${@}"
