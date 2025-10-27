#!/bin/bash

# Phase 6: Full Pipeline Integration Test Runner
# Tests complete orchestrated flow from user goal to final result

echo "🚀 Phase 6: Full Pipeline Integration Tests"
echo "============================================"
echo ""
echo "Testing complete orchestrated flow:"
echo "  User Goal → IntentClassifier → Orchestrator → ToolSelector"
echo "            → CodeGenerator → Sandbox → Result"
echo ""

# Run inside Docker container with GPU support
docker compose run --rm tests pytest neural_engine/tests/test_phase6_full_pipeline.py -v

echo ""
echo "✅ Phase 6 tests complete!"
