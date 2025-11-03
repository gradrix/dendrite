#!/bin/bash
set -e

echo "🧪 Running Unit Tests Only"
echo "=========================="

# Run tests that don't require integration (mock-based tests)
./scripts/test.sh -m "not integration" "${@}"
