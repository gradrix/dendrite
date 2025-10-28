#!/bin/bash

# Phase 9b: Self-Investigation Neuron Test Runner
# Tests autonomous monitoring and self-awareness capabilities

echo "🧠 Phase 9b: Self-Investigation Neuron Tests"
echo "============================================="
echo ""
echo "Testing autonomous monitoring capabilities:"
echo "  - Health investigation"
echo "  - Anomaly detection"
echo "  - Degradation detection"
echo "  - Insight generation"
echo "  - Background monitoring loop"
echo "  - Smart alerting system"
echo "  - Integration with Phase 9a tools"
echo ""

# Run inside Docker container
docker compose run --rm tests pytest neural_engine/tests/test_self_investigation_neuron.py -v

echo ""
echo "✅ Phase 9b tests complete!"
