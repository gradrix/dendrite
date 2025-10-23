#!/bin/bash

# Quick test script to verify agent setup without Strava cookies

echo "Testing AI Agent Setup..."
echo ""

# Test 1: Check Python dependencies
echo "1. Checking Python environment..."
python3 -c "import yaml, requests; print('✓ Basic dependencies OK')" 2>/dev/null || {
    echo "✗ Missing dependencies. Run: pip install -r requirements.txt"
    exit 1
}

# Test 2: Check Ollama connection
echo "2. Checking Ollama connection..."
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama is running"
else
    echo "✗ Ollama is not accessible. Run: ./setup-ollama.sh"
    exit 1
fi

# Test 3: Test tool discovery
echo "3. Testing tool discovery..."
python3 << 'PYTHON'
import sys
sys.path.insert(0, '.')
from agent.tool_registry import get_registry

registry = get_registry()
count = registry.discover_tools('tools')
print(f'✓ Discovered {count} tools')
for tool in registry.list_tools():
    print(f'  - {tool.name} ({tool.permissions})')
PYTHON

# Test 4: Test instruction loading
echo ""
echo "4. Testing instruction loading..."
python3 << 'PYTHON'
import sys
sys.path.insert(0, '.')
from agent.instruction_loader import InstructionLoader

loader = InstructionLoader()
instructions = loader.load_all()
print(f'✓ Loaded {len(instructions)} instructions')
for inst in instructions:
    print(f'  - {inst.name} ({inst.schedule})')
PYTHON

# Test 5: Test Ollama client
echo ""
echo "5. Testing Ollama client..."
python3 << 'PYTHON'
import sys
sys.path.insert(0, '.')
from agent.ollama_client import OllamaClient

client = OllamaClient()
if client.health_check():
    print('✓ Ollama client working')
else:
    print('✗ Ollama client failed')
    sys.exit(1)
PYTHON

echo ""
echo "========================================="
echo "All tests passed! ✓"
echo "========================================="
echo ""
echo "To run the agent:"
echo "  ./start-agent.sh              # Start scheduler"
echo "  ./start-agent.sh --once       # Run once"
echo ""
echo "Note: You'll need .strava_cookies file for Strava API access"
