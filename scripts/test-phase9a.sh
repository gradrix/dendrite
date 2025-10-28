#!/bin/bash

# Phase 9a: Neuron-Driven Analytics Test Runner
# Tests self-aware analytics tools for system introspection

echo "🧠 Phase 9a: Neuron-Driven Analytics Tests"
echo "==========================================="
echo ""
echo "Testing analytics tools:"
echo "  - QueryExecutionStoreTool (8 query types)"
echo "  - AnalyzeToolPerformanceTool (6 analysis types)"
echo "  - GenerateReportTool (6 report formats)"
echo "  - Query → Analyze → Report pipeline"
echo "  - Self-investigation capabilities"
echo ""

# Run inside Docker container
docker compose run --rm tests pytest neural_engine/tests/test_phase9a_analytics_tools.py -v

echo ""
echo "✅ Phase 9a tests complete!"
