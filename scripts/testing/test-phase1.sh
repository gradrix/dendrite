#!/bin/bash
set -e

echo "🧪 Phase 1: Testing Generative Pipeline"
echo "========================================="
echo ""
echo "This tests the complete conversational flow:"
echo "  User Goal → Intent → Generative Neuron → LLM → Response"
echo ""

# Run only Phase 1 tests
./scripts/test.sh -k test_phase1 -v
