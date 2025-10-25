#!/usr/bin/env python3
"""
Test script to verify Python code execution error handling.
"""

from tools.analysis_tools import execute_data_analysis

print("=" * 60)
print("Python Code Execution Error Handling Tests")
print("=" * 60)

# Test 1: Valid code
print("\n✓ Test 1: Valid code")
result = execute_data_analysis("result = sum([1, 2, 3, 4, 5])")
print(f"Result: {result}")
assert result['success'] == True
assert result['result'] == 15
print("PASS ✓")

# Test 2: Syntax error
print("\n✓ Test 2: Syntax error (missing bracket)")
result = execute_data_analysis("result = [x for x in range(10) if x > 5")
print(f"Result: {result}")
assert result['success'] == False
assert 'Syntax error' in result['error']
assert result['retry'] == True
print("PASS ✓")

# Test 3: Missing result variable
print("\n✓ Test 3: Missing result variable")
result = execute_data_analysis("x = 42")
print(f"Result: {result}")
assert result['success'] == False
assert 'must assign result' in result['error']
assert result['retry'] == True
print("PASS ✓")

# Test 4: Dangerous pattern
print("\n✓ Test 4: Dangerous pattern (import os)")
result = execute_data_analysis("import os; result = 1")
print(f"Result: {result}")
assert result['success'] == False
assert 'dangerous pattern' in result['error']
assert result['retry'] == False
print("PASS ✓")

# Test 5: Runtime error
print("\n✓ Test 5: Runtime error (division by zero)")
result = execute_data_analysis("result = 1 / 0")
print(f"Result: {result}")
assert result['success'] == False
assert result['retry'] == True
print("PASS ✓")

# Test 6: Timeout (infinite loop)
print("\n✓ Test 6: Timeout (10 second limit)")
import time
start = time.time()
result = execute_data_analysis("while True: pass")
elapsed = time.time() - start
print(f"Result: {result}")
print(f"Elapsed time: {elapsed:.1f}s")
assert result['success'] == False
assert 'Timeout' in result['error'] or 'timeout' in result['error']
assert elapsed >= 9.9 and elapsed <= 10.5  # Should timeout at ~10s
print("PASS ✓")

# Test 7: Valid code with context
print("\n✓ Test 7: Valid code with context data")
result = execute_data_analysis("result = len(data.get('test_list', []))", test_list=[1, 2, 3])
print(f"Result: {result}")
assert result['success'] == True
assert result['result'] == 3
print("PASS ✓")

print("\n" + "=" * 60)
print("All tests passed! ✓")
print("=" * 60)
