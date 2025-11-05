#!/usr/bin/env python3
"""
Quick debug script to test system_factory initialization.
This helps isolate where the hang is occurring.
"""

import sys
import time

print("="*80)
print("QUICK DEBUG: Testing system_factory initialization")
print("="*80)
print()

print("Step 1: Importing create_neural_engine...")
sys.stdout.flush()
start = time.time()
from neural_engine.core.system_factory import create_neural_engine
print(f"   ✓ Import completed in {time.time() - start:.2f}s")
sys.stdout.flush()

print("\nStep 2: Creating neural engine...")
print("   (Watch for where it hangs)")
sys.stdout.flush()

start = time.time()
try:
    orchestrator = create_neural_engine(enable_all_features=True)
    print(f"\n✅ SUCCESS! Initialization completed in {time.time() - start:.2f}s")
    sys.stdout.flush()
except Exception as e:
    print(f"\n❌ FAILED after {time.time() - start:.2f}s: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nStep 3: Testing orchestrator...")
sys.stdout.flush()

# Try a simple process call
try:
    result = orchestrator.process("Hello world")
    print(f"✅ Process call worked: {str(result)[:100]}...")
except Exception as e:
    print(f"⚠️  Process call failed: {e}")

print("\n" + "="*80)
print("DEBUG COMPLETE")
print("="*80)
