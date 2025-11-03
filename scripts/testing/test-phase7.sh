#!/bin/bash

# Phase 7: ToolForge Test Runner
# Tests AI-powered tool creation capabilities

echo "🔨 Phase 7: ToolForge Tests"
echo "============================"
echo ""
echo "Testing AI tool creation:"
echo "  - Code generation from natural language"
echo "  - Code validation (BaseTool requirements)"
echo "  - File writing and registry refresh"
echo "  - End-to-end tool creation and usage"
echo "  - AI tools treated same as admin tools"
echo ""

# Run inside Docker container with GPU support
docker compose run --rm tests pytest neural_engine/tests/test_phase7_tool_forge.py -v

echo ""
echo "✅ Phase 7 tests complete!"
