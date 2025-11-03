#!/bin/bash

echo "🧪 Phase 5: Testing Sandbox Execution"
echo "======================================"
echo ""
echo "This tests the code execution sandbox:"
echo "  Generated Code → Sandbox → Tool Execution → Results"
echo ""

# Run the main test script with Phase 5 filter
./scripts/test.sh -k "Phase5"
