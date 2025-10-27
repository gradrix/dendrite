#!/bin/bash
set -e

echo "🧪 Phase 0: Testing Intent Classification"
echo "=========================================="
echo ""
echo "This tests the first LLM interaction:"
echo "  User Goal → IntentClassifierNeuron → LLM → Intent"
echo ""

# Run only Phase 0 tests
./scripts/test.sh -k test_phase0 -v
