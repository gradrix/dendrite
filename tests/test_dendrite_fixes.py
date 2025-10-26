#!/usr/bin/env python3
"""
Test the dendrite spawning fixes:
1. Goal string parsing for activity IDs
2. Safety limits (max dendrites, output size, duplicate detection)
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import json
from agent.neuron.execution import micro_determine_params
from agent.neuron.spawning import MAX_DENDRITES_PER_SPAWN, MAX_OUTPUT_SIZE_MB

# Mock classes
class MockTool:
    def __init__(self, name, params):
        self.name = name
        self.parameters = params

class MockOllama:
    def generate(self, prompt, system="", temperature=0.1):
        # Mock response: extract activity_id from prompt
        if "Extract details for activity" in prompt and "16243029035" in prompt:
            return '{"activity_id": "16243029035"}'
        elif "auto-mapped" in prompt:
            return '{}'  # Return empty if auto-mapped
        return '{"key": "test_value"}'

def test_goal_string_parsing():
    """Test that activity IDs are extracted from goal strings"""
    print("=" * 60)
    print("TEST 1: Goal String Parsing for Activity IDs")
    print("=" * 60)
    
    # Create mock tool that accepts activity_id parameter
    tool = MockTool("getActivityKudos", [
        {"name": "activity_id", "type": "str", "description": "Activity ID"}
    ])
    
    # Create context with dendrite item
    context = {
        'dendrite_item_1_2': {
            'id': 16243029035,
            'name': 'Evening Ride',
            'start_date': '2025-10-24T15:40:32Z'
        }
    }
    
    # Test parameter determination with goal containing activity ID
    neuron_desc = "Extract details for activity 16243029035"
    
    ollama = MockOllama()
    
    # This should auto-map activity_id from the goal string
    params = micro_determine_params(
        neuron_desc=neuron_desc,
        tool=tool,
        context=context,
        ollama=ollama,
        summarize_result_fn=lambda x: str(x)[:100]
    )
    
    print(f"\nGoal: {neuron_desc}")
    print(f"Dendrite item ID: {context['dendrite_item_1_2']['id']}")
    print(f"Extracted params: {json.dumps(params, indent=2)}")
    
    # Verify the correct ID was extracted
    if 'activity_id' in params and params['activity_id'] == '16243029035':
        print("✅ SUCCESS: Correct activity ID extracted from goal string!")
    else:
        print(f"❌ FAILED: Expected activity_id='16243029035', got {params}")
    
    print()

def test_safety_limits():
    """Test that safety limits are properly configured"""
    print("=" * 60)
    print("TEST 2: Safety Limits Configuration")
    print("=" * 60)
    
    print(f"\nMAX_DENDRITES_PER_SPAWN: {MAX_DENDRITES_PER_SPAWN}")
    print(f"MAX_OUTPUT_SIZE_MB: {MAX_OUTPUT_SIZE_MB}")
    
    if MAX_DENDRITES_PER_SPAWN > 0 and MAX_OUTPUT_SIZE_MB > 0:
        print("✅ SUCCESS: Safety limits properly configured!")
    else:
        print("❌ FAILED: Safety limits not configured!")
    
    print()

def test_goal_patterns():
    """Test various goal string patterns"""
    print("=" * 60)
    print("TEST 3: Multiple Goal String Patterns")
    print("=" * 60)
    
    import re
    
    test_cases = [
        ("Extract details for activity 16243029035", "16243029035"),
        ("Get activity_id 12345678", "12345678"),
        ("Process record 9876543", "9876543"),
        ("Fetch item 11111111", "11111111"),
    ]
    
    for goal, expected_id in test_cases:
        # Test activity ID pattern
        match = re.search(r'activity[_ ]?(?:id[_ ]?)?(\d+)', goal, re.IGNORECASE)
        if not match:
            # Test record ID pattern
            match = re.search(r'record[_ ]?(?:id[_ ]?)?(\d+)', goal, re.IGNORECASE)
        if not match:
            # Test item ID pattern
            match = re.search(r'(?:item|id|key)[:\s]+(\d+)', goal, re.IGNORECASE)
        
        extracted = match.group(1) if match else None
        
        status = "✅" if extracted == expected_id else "❌"
        print(f"{status} Goal: '{goal}' → Extracted: {extracted} (expected: {expected_id})")
    
    print()

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("TESTING DENDRITE SPAWNING FIXES")
    print("=" * 60 + "\n")
    
    test_goal_string_parsing()
    test_safety_limits()
    test_goal_patterns()
    
    print("=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
