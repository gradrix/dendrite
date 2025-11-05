#!/usr/bin/env python3
"""
Manual test for Goal Decomposition Learner integration.

This script tests the pattern learning flow:
1. Execute a goal (stores pattern)
2. Execute a similar goal (should suggest pattern)
"""
import sys
import os

# Add project to path
sys.path.insert(0, os.path.abspath('.'))

from neural_engine.core.system_factory import create_neural_engine


def test_pattern_learning():
    """Test pattern learning flow."""
    print("=" * 60)
    print("🧪 TESTING GOAL DECOMPOSITION LEARNER INTEGRATION")
    print("=" * 60)
    
    # Initialize system
    print("\n📦 Initializing system...")
    orchestrator = create_neural_engine()
    
    # Verify goal_learner is available
    if not hasattr(orchestrator, 'goal_learner') or not orchestrator.goal_learner:
        print("❌ FAIL: goal_learner not initialized")
        return False
    
    print("✅ Goal learner initialized")
    
    # Test 1: Execute first goal (should store pattern)
    print("\n" + "=" * 60)
    print("📝 TEST 1: First execution (should store pattern)")
    print("=" * 60)
    goal1 = "Calculate 5 plus 3"
    print(f"Goal: {goal1}")
    
    try:
        result1 = orchestrator.process(goal1)
        print(f"\n✅ Result: {result1.get('result', 'N/A')}")
        print("   Check logs above for: '📚 Stored decomposition pattern'")
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Execute similar goal (should suggest pattern)
    print("\n" + "=" * 60)
    print("📝 TEST 2: Similar goal (should suggest pattern)")
    print("=" * 60)
    goal2 = "Calculate 10 plus 7"
    print(f"Goal: {goal2}")
    
    try:
        result2 = orchestrator.process(goal2)
        print(f"\n✅ Result: {result2.get('result', 'N/A')}")
        print("   Check logs above for: '📚 Found similar goal pattern'")
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ INTEGRATION TEST COMPLETE")
    print("=" * 60)
    print("\nExpected behavior:")
    print("1. First goal: Stores pattern after execution")
    print("2. Similar goal: Suggests pattern before execution")
    print("\nCheck the logs above for pattern messages.")
    
    return True


if __name__ == '__main__':
    success = test_pattern_learning()
    sys.exit(0 if success else 1)
