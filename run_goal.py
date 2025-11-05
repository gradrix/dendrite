#!/usr/bin/env python3
"""
Simple goal executor with full thinking visibility.

Usage:
    python run_goal.py "Your goal here"
    python run_goal.py "Your goal here" --debug-llm
    
Example:
    python run_goal.py "Say hello to the world"
    python run_goal.py "What is 2 plus 2?" --debug-llm
"""

import sys
import os
import argparse
from neural_engine.core.system_factory import create_neural_engine
from neural_engine.core.thinking_visualizer import ThinkingVisualizer


def main():
    parser = argparse.ArgumentParser(description="Execute a goal with full thinking visibility")
    parser.add_argument("goal", type=str, help="The goal to execute")
    parser.add_argument("--verbose", action="store_true", help="Show detailed thinking process")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    parser.add_argument("--debug-llm", action="store_true", 
                       help="Show all LLM calls with prompts and responses")
    
    args = parser.parse_args()
    
    # Enable LLM debugging via environment variable
    if args.debug_llm:
        os.environ["DEBUG_LLM"] = "true"
        print("🔍 LLM Debug Mode: Enabled")
        print("   You will see: purpose, prompts, tokens, responses for every LLM call\n")
    
    # Create visualizer
    viz = ThinkingVisualizer(verbose=args.verbose and not args.quiet)
    
    # Create fully initialized system
    orchestrator = create_neural_engine(enable_all_features=True)
    
    # Connect visualizer to components for cache hit tracking
    if hasattr(orchestrator, 'intent_classifier'):
        orchestrator.intent_classifier.visualizer = viz
    
    # Connect visualizer to orchestrator for pathway cache visualization
    orchestrator.visualizer = viz
    
    # Execute goal with visualization
    viz.start_goal(args.goal)
    
    try:
        result = orchestrator.process(args.goal)
        viz.show_result(result, success=result.get('success', True))
        
        # Show summary
        if not args.quiet:
            summary = viz.get_summary()
            print(f"\n📊 Execution Summary:")
            print(f"   Total steps: {summary['total_steps']}")
            print(f"   Duration: {summary['duration_seconds']:.2f}s")
            
            # Show cache status
            if summary.get('pathway_cache_hit'):
                print(f"   Pathway cache: ✅ HIT (System 1 - Fast!)")
            elif summary.get('intent_cache_hit'):
                print(f"   Intent cache: ✅ HIT")
                print(f"   Pathway cache: ❌ Miss")
            else:
                print(f"   Cache: ❌ Miss (full reasoning)")
            
            print(f"   Decomposition pattern: {'Yes' if summary['pattern_used'] else 'No (not integrated)'}")
            print(f"   Errors: {'Yes' if summary['errors_occurred'] else 'No'}")
            if summary['errors_occurred']:
                print(f"   Recovery: {'Successful' if summary['recovery_successful'] else 'Failed'}")
        
        # Exit with success
        sys.exit(0 if result.get('success', True) else 1)
        
    except Exception as e:
        viz.show_result({'error': str(e)}, success=False)
        print(f"\n❌ Execution failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
