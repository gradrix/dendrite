"""
End-to-End Demo: Autonomous Self-Improvement with Real Code Generation

This demo shows the complete self-modification cycle:
1. Create/use a buggy tool
2. Execute it multiple times to generate failures in ExecutionStore
3. Detect improvement opportunities automatically
4. Generate real improved code using ToolForgeNeuron
5. Deploy the improved code to disk
6. Verify the improvement works
7. Demonstrate rollback capability

This is REAL self-modification - the system will actually write improved code to files!

Run this inside Docker:
  docker compose run --rm app python -c "exec(open('neural_engine/scripts/demo_autonomous_improvement.py').read())"
"""

import os
import sys
import time
from datetime import datetime

# Add current directory to path for Docker
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

from neural_engine.core.message_bus import MessageBus
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.core.autonomous_improvement_neuron import AutonomousImprovementNeuron
from neural_engine.core.tool_forge_neuron import ToolForgeNeuron
from neural_engine.tools.buggy_calculator_tool import BuggyCalculatorTool


def print_section(title: str):
    """Print a fancy section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def print_subsection(title: str):
    """Print a subsection header."""
    print(f"\n--- {title} ---\n")


def wait_for_user(message: str = "Press ENTER to continue..."):
    """Wait for user input (or skip in non-interactive mode)."""
    if os.isatty(0):  # Check if running interactively
        input(f"\n👉 {message}")
    else:
        print(f"\n⏭️  {message} (auto-continuing in non-interactive mode)")
        time.sleep(1)  # Brief pause for readability


def execute_tool_safely(tool, execution_store, execution_id, **kwargs):
    """Execute a tool and record in ExecutionStore, even if it fails."""
    start_time = time.time()
    
    try:
        result = tool.execute(**kwargs)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Record success
        execution_store.store_tool_execution(
            execution_id=execution_id,
            tool_name='buggy_calculator',
            parameters=kwargs,
            result=result,
            success=result.get('success', True),
            duration_ms=duration_ms,
            error=None
        )
        return result
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Record failure
        execution_store.store_tool_execution(
            execution_id=execution_id,
            tool_name='buggy_calculator',
            parameters=kwargs,
            result=None,
            success=False,
            duration_ms=duration_ms,
            error=str(e)
        )
        return {'success': False, 'error': str(e)}


def main():
    print_section("🚀 AUTONOMOUS SELF-IMPROVEMENT DEMO - REAL CODE GENERATION")
    
    print("This demo will:")
    print("  1. Execute a buggy calculator tool to generate failures")
    print("  2. Detect the problems automatically")
    print("  3. Generate REAL improved code using AI")
    print("  4. Deploy the improved code to disk")
    print("  5. Verify the improvement works")
    print("  6. Show rollback capability")
    print("\n⚠️  WARNING: This will ACTUALLY MODIFY FILES in neural_engine/tools/")
    print("⚠️  Backups will be created automatically in neural_engine/tools/backups/")
    
    wait_for_user("Press ENTER to continue...")
    
    # =========================================================================
    # PART 1: Setup
    # =========================================================================
    print_section("PART 1: Initialize System Components")
    
    print("Creating message bus...")
    message_bus = MessageBus()
    
    print("Creating Ollama client (for AI code generation)...")
    ollama_client = OllamaClient()
    
    print("Creating tool registry...")
    tool_registry = ToolRegistry()
    
    print("Creating execution store (PostgreSQL database)...")
    execution_store = ExecutionStore()  # Uses default env vars in Docker
    
    print("Creating ToolForge neuron (for AI code generation)...")
    tool_forge = ToolForgeNeuron(
        message_bus=message_bus,
        ollama_client=ollama_client,
        tool_registry=tool_registry
    )
    
    print("Creating AutonomousImprovement neuron...")
    improvement_neuron = AutonomousImprovementNeuron(
        message_bus=message_bus,
        ollama_client=ollama_client,
        execution_store=execution_store,
        tool_forge=tool_forge,
        tool_registry=tool_registry,
        enable_real_improvements=True,  # 🔥 ENABLE REAL MODE!
        enable_auto_improvement=False   # Manual approval for demo
    )
    
    print("\n✅ All components initialized!")
    print(f"   - Real improvements: ENABLED")
    print(f"   - Auto deployment: DISABLED (manual approval)")
    
    # =========================================================================
    # PART 2: Generate Failures
    # =========================================================================
    print_section("PART 2: Execute Buggy Tool to Generate Failures")
    
    print("Creating buggy calculator tool...")
    buggy_tool = BuggyCalculatorTool()
    
    print("\nExecuting tool with various inputs (some will fail)...\n")
    
    # Create a goal execution first
    execution_id = execution_store.store_execution(
        goal_id=f"demo_{int(time.time())}",
        goal_text="Testing buggy calculator tool",
        intent="tool_use",
        success=True
    )
    
    test_cases = [
        # These will succeed
        {'operation': 'add', 'a': 5, 'b': 3, 'expected': 'success'},
        {'operation': 'multiply', 'a': 4, 'b': 7, 'expected': 'success'},
        {'operation': 'subtract', 'a': 10, 'b': 3, 'expected': 'success'},
        
        # These will FAIL - division by zero
        {'operation': 'divide', 'a': 10, 'b': 0, 'expected': 'FAIL - divide by zero'},
        {'operation': 'divide', 'a': 100, 'b': 0, 'expected': 'FAIL - divide by zero'},
        {'operation': 'divide', 'a': 5, 'b': 0, 'expected': 'FAIL - divide by zero'},
        {'operation': 'divide', 'a': 42, 'b': 0, 'expected': 'FAIL - divide by zero'},
        {'operation': 'divide', 'a': 99, 'b': 0, 'expected': 'FAIL - divide by zero'},
        
        # More successes
        {'operation': 'divide', 'a': 20, 'b': 4, 'expected': 'success'},
        {'operation': 'add', 'a': 1, 'b': 1, 'expected': 'success'},
    ]
    
    success_count = 0
    failure_count = 0
    
    for i, test_case in enumerate(test_cases, 1):
        expected = test_case.pop('expected')
        print(f"Test {i}/{len(test_cases)}: {test_case} → {expected}")
        
        result = execute_tool_safely(buggy_tool, execution_store, execution_id, **test_case)
        
        if result.get('success'):
            print(f"  ✅ Result: {result.get('result')}")
            success_count += 1
        else:
            print(f"  ❌ Error: {result.get('error')}")
            failure_count += 1
    
    print(f"\n📊 Results: {success_count} successes, {failure_count} failures")
    print(f"   Success rate: {success_count / len(test_cases) * 100:.1f}%")
    
    wait_for_user("Press ENTER to continue to opportunity detection...")
    
    # =========================================================================
    # PART 3: Detect Improvement Opportunities
    # =========================================================================
    print_section("PART 3: Detect Improvement Opportunities")
    
    print("Analyzing execution data for improvement opportunities...")
    opportunities = improvement_neuron.detect_improvement_opportunities()
    
    if not opportunities['success']:
        print(f"❌ Failed to detect opportunities: {opportunities.get('error')}")
        return
    
    print(f"\n✅ Found {opportunities['opportunities_count']} improvement opportunity(ies)!\n")
    
    for i, opp in enumerate(opportunities['opportunities'], 1):
        print(f"Opportunity {i}:")
        print(f"  Tool: {opp['tool_name']}")
        print(f"  Issue: {opp['issue_type']}")
        print(f"  Severity: {opp['severity']}")
        print(f"  Current metrics:")
        print(f"    - Success rate: {opp['current_metrics']['success_rate'] * 100:.1f}%")
        print(f"    - Total executions: {opp['current_metrics']['total_executions']}")
        print(f"  Evidence:")
        for evidence in opp['evidence']:
            print(f"    - {evidence}")
        print()
    
    if opportunities['opportunities_count'] == 0:
        print("⚠️  No opportunities found. Need more failures!")
        print("   Try running more test cases with errors.")
        return
    
    # Look for buggy_calculator specifically, otherwise use first
    target_tool = 'buggy_calculator'
    found_buggy_calc = any(opp['tool_name'] == 'buggy_calculator' for opp in opportunities['opportunities'])
    
    if not found_buggy_calc:
        print(f"\n⚠️  buggy_calculator not found in opportunities (found old test data)")
        print("   Let's manually target buggy_calculator instead...")
        target_tool = 'buggy_calculator'
    else:
        target_tool = 'buggy_calculator'
    
    print(f"🎯 Target for improvement: {target_tool}")
    
    wait_for_user("Press ENTER to generate improved code using AI...")
    
    # =========================================================================
    # PART 4: Generate Improved Code (REAL AI!)
    # =========================================================================
    print_section("PART 4: Generate Improved Code Using ToolForgeNeuron")
    
    print(f"Generating improved version of '{target_tool}' using AI...")
    print("This will:")
    print("  1. Read the current buggy code from disk")
    print("  2. Analyze failure patterns from ExecutionStore")
    print("  3. Create detailed improvement prompt")
    print("  4. Send to AI (Ollama) to generate fixed code")
    print("  5. Validate the generated code")
    print("\n⏳ This may take 30-60 seconds...\n")
    
    improvement_result = improvement_neuron.improve_tool(target_tool)
    
    if not improvement_result['success']:
        print(f"❌ Failed to generate improvement: {improvement_result.get('error')}")
        return
    
    print("✅ Improvement generated successfully!\n")
    
    improvement = improvement_result['improvement']
    print(f"📋 Improvement Details:")
    print(f"  Generated at: {improvement.get('generated_at', 'N/A')}")
    print(f"  Status: {improvement.get('status', 'N/A')}")
    
    if 'changes' in improvement:
        print(f"  Changes: {len(improvement['changes'])} modification(s)")
        for i, change in enumerate(improvement['changes'][:3], 1):  # Show first 3
            print(f"    {i}. {change}")
    
    if 'estimated_impact' in improvement:
        impact = improvement['estimated_impact']
        if 'success_rate_improvement' in impact:
            print(f"  Estimated impact: {impact['success_rate_improvement'] * 100:.0f}% success rate improvement")
    
    if 'generated_code' in improvement:
        code = improvement['generated_code']
        print(f"\n📝 Generated Code Preview (first 500 chars):")
        print("-" * 80)
        print(code[:500] + "..." if len(code) > 500 else code)
        print("-" * 80)
    else:
        print(f"\n⚠️  Note: No generated_code in improvement (this might be placeholder mode)")
    
    wait_for_user("Press ENTER to deploy the improved code to disk...")
    
    # =========================================================================
    # PART 5: Deploy Improved Code (WRITES TO DISK!)
    # =========================================================================
    print_section("PART 5: Deploy Improved Code to Disk")
    
    print("⚠️  About to WRITE improved code to:")
    print(f"   neural_engine/tools/{target_tool}_tool.py")
    print("✅ Backup will be created at:")
    print(f"   neural_engine/tools/backups/{target_tool}_backup_<timestamp>.py")
    
    wait_for_user("Press ENTER to proceed with deployment...")
    
    print(f"\nDeploying improved version of '{target_tool}'...")
    deployment_result = improvement_neuron.deploy_improvement(target_tool)
    
    if not deployment_result['success']:
        print(f"❌ Deployment failed: {deployment_result.get('error')}")
        if deployment_result.get('backup_restored'):
            print("✅ Backup was automatically restored (rollback)")
        return
    
    print("✅ Deployment successful!\n")
    
    deployment = deployment_result['deployment']
    print(f"📋 Deployment Details:")
    print(f"  Tool: {deployment['tool_name']}")
    print(f"  Deployed at: {deployment['deployed_at']}")
    print(f"  Mode: {deployment['mode']}")
    print(f"  Backup created: {deployment['backup_created']}")
    print(f"  Backup path: {deployment.get('backup_path', 'N/A')}")
    print(f"  File path: {deployment.get('file_path', 'N/A')}")
    print(f"  Verification: {deployment['verification']['success']}")
    
    wait_for_user("Press ENTER to test the improved tool...")
    
    # =========================================================================
    # PART 6: Verify Improvement
    # =========================================================================
    print_section("PART 6: Test Improved Tool")
    
    print("Reloading tool registry to get improved version...")
    tool_registry.refresh()
    
    print("Testing with same failing cases that broke before...\n")
    
    failing_cases = [
        {'operation': 'divide', 'a': 10, 'b': 0},
        {'operation': 'divide', 'a': 100, 'b': 0},
        {'operation': 'divide', 'a': 5, 'b': 0},
    ]
    
    print("Previous behavior: These all crashed with 'ZeroDivisionError'")
    print("Expected new behavior: Graceful error handling\n")
    
    improved_tool = tool_registry.get_tool(target_tool)
    if not improved_tool:
        print(f"❌ Could not load improved tool '{target_tool}'")
        return
    
    improved_success = 0
    improved_handled = 0
    
    # Create execution for improved tool testing
    improved_execution_id = execution_store.store_execution(
        goal_id=f"demo_improved_{int(time.time())}",
        goal_text="Testing improved calculator tool",
        intent="tool_use",
        success=True
    )
    
    for i, test_case in enumerate(failing_cases, 1):
        print(f"Test {i}/{len(failing_cases)}: {test_case}")
        result = execute_tool_safely(improved_tool, execution_store, improved_execution_id, **test_case)
        
        if result.get('success'):
            print(f"  ✅ Success: {result}")
            improved_success += 1
        else:
            error = result.get('error', '')
            if 'ZeroDivisionError' in error:
                print(f"  ❌ Still crashing: {error}")
            else:
                print(f"  ✅ Handled gracefully: {error}")
                improved_handled += 1
    
    print(f"\n📊 Improved Results:")
    print(f"   {improved_success} returned success with error handling")
    print(f"   {improved_handled} handled errors gracefully (no crash)")
    print(f"   {len(failing_cases) - improved_success - improved_handled} still crashing")
    
    if improved_success + improved_handled == len(failing_cases):
        print("\n🎉 SUCCESS! All previously failing cases now handled correctly!")
    else:
        print("\n⚠️  Some cases still failing. May need another improvement cycle.")
    
    wait_for_user("Press ENTER to demonstrate rollback capability...")
    
    # =========================================================================
    # PART 7: Demonstrate Rollback
    # =========================================================================
    print_section("PART 7: Rollback Capability")
    
    print("Demonstrating rollback to previous version...")
    print(f"This will restore the buggy version from backup.\n")
    
    rollback_result = improvement_neuron.rollback_improvement(
        target_tool,
        reason="Demo: showing rollback capability"
    )
    
    if not rollback_result['success']:
        print(f"❌ Rollback failed: {rollback_result.get('error')}")
        return
    
    print("✅ Rollback successful!\n")
    
    rollback = rollback_result['rollback']
    print(f"📋 Rollback Details:")
    print(f"  Tool: {rollback['tool_name']}")
    print(f"  Rolled back at: {rollback['rolled_back_at']}")
    print(f"  Reason: {rollback['reason']}")
    print(f"  Verification: {rollback['verification']['success']}")
    
    print("\n🔄 Tool is now back to original buggy version")
    print("   (In production, we'd only rollback if the improvement failed)")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print_section("🎉 DEMO COMPLETE - SUMMARY")
    
    print("What we just demonstrated:")
    print()
    print("  ✅ 1. Executed buggy tool and recorded failures in ExecutionStore")
    print("  ✅ 2. Automatically detected improvement opportunities")
    print("  ✅ 3. Generated REAL improved code using AI (ToolForgeNeuron + Ollama)")
    print("  ✅ 4. Deployed improved code to disk with automatic backup")
    print("  ✅ 5. Verified deployment (checked tool loads correctly)")
    print("  ✅ 6. Tested improved tool against failing cases")
    print("  ✅ 7. Demonstrated rollback from backup")
    print()
    print("🚀 This is REAL SELF-MODIFICATION!")
    print("   The system read its own code, identified problems, generated")
    print("   improvements using AI, and wrote the changes to disk.")
    print()
    print("📁 Files modified:")
    print(f"   - neural_engine/tools/{target_tool}_tool.py (improved, then rolled back)")
    print(f"   - neural_engine/tools/backups/{target_tool}_backup_*.py (created)")
    print()
    print("Next steps:")
    print("  - Add proper A/B testing (shadow mode)")
    print("  - Add tool classification (safe vs side-effects)")
    print("  - Add continuous monitoring for regressions")
    print("  - Add background improvement loop")
    print()
    print("See docs/TESTING_STRATEGY.md for the complete testing roadmap!")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
