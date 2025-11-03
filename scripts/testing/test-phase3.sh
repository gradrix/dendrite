#!/bin/bash

echo "🧪 Phase 3: Testing Tool Selection"
echo "===================================="
echo ""
echo "This tests the intelligent tool selection system:"
echo "  User Goal → LLM Analysis → Best Tool Match → Metadata for Code Gen"
echo ""

# Run the main test script with Phase 3 filter
./scripts/test.sh -k "Phase3"
