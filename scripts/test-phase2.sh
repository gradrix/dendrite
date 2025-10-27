#!/bin/bash

echo "🧪 Phase 2: Testing Tool Registry & Discovery"
echo "=============================================="
echo ""
echo "This tests the tool discovery and registration system:"
echo "  Tool Discovery → Metadata Extraction → Registration → Querying"
echo ""

# Run the main test script with Phase 2 filter
./scripts/test.sh -k "Phase2"
