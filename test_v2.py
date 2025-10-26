#!/usr/bin/env python3
"""
Test V2 Architecture with Strava test case
"""

import sys
import os
import logging

# Add agent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent.v2 import V2Agent
from agent.ollama_client import OllamaClient
from agent.tool_registry import get_tool_registry

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_v2_strava():
    """Test V2 agent with Strava kudos goal."""

    print("🧪 Testing V2 Architecture with Strava Test Case")
    print("=" * 60)

    # Initialize components
    ollama = OllamaClient()
    tool_registry = get_tool_registry()

    # Create V2 agent
    agent = V2Agent(ollama, tool_registry)

    # Test goal
    goal = "Get my Strava activities from the last 7 days and for each activity that has kudos, get the names of all people who gave kudos."

    print(f"🎯 Goal: {goal}")
    print()

    # Execute with V2
    result = agent.execute_goal(goal)

    print("\n📊 Results:")
    print(f"Success: {result['success']}")
    print(f"Completed Steps: {result['completed_steps']}/{result['total_steps']}")

    if result['success']:
        print("\n✅ Final Results:")
        for step_id, data in result['results'].items():
            print(f"  {step_id}: {type(data).__name__}")
            if isinstance(data, list) and len(data) > 0:
                print(f"    Sample: {data[0] if len(data) == 1 else data[:2]}")
    else:
        print("\n❌ Errors:")
        for step_id, error in result['errors'].items():
            print(f"  {step_id}: {error}")

    print("\n🔍 Debug Info:")
    debug = result.get('debug_info', {})
    for step_id, info in debug.items():
        print(f"  {step_id}:")
        print(f"    Goal: {info['goal'][:50]}...")
        print(f"    Success: {info['success']}")
        if info.get('prompt_used'):
            print(f"    Prompt: {info['prompt_used'][:100]}...")
        if info.get('response_received'):
            print(f"    Response: {info['response_received'][:100]}...")
        if info.get('validation_errors'):
            print(f"    Validation Errors: {info['validation_errors']}")

    print("\n📋 Execution Plan:")
    plan = result.get('plan', {})
    print(f"Complexity: {plan.get('estimated_complexity')}")
    print(f"Data Requirements: {plan.get('data_requirements', [])}")
    print("Steps:")
    for step in plan.get('steps', []):
        print(f"  {step['step_id']}: {step['goal'][:60]}... (type: {step['neuron_type']})")

if __name__ == "__main__":
    test_v2_strava()