"""
Dendrite CLI (v2)

Simple command-line interface for the neural engine.

Usage:
    python -m neural_engine.v2.cli --goal "What is 2+2?"
    python -m neural_engine.v2.cli --interactive
"""

import argparse
import asyncio
import sys

from .core import Config, Orchestrator


async def process_goal(goal: str) -> None:
    """Process a single goal."""
    config = Config.from_env()
    orchestrator = await Orchestrator.from_config(config)
    
    print(f"🧠 Processing: {goal}")
    print("-" * 40)
    
    result = await orchestrator.process(goal)
    
    if result["success"]:
        print(f"✅ Intent: {result.get('intent', 'unknown')}")
        print(f"📝 Result: {result['result']}")
    else:
        print(f"❌ Error: {result['error']}")
    
    print("-" * 40)
    print(f"⏱️  Duration: {result.get('duration_ms', 0)}ms")
    print(f"🔑 Goal ID: {result['goal_id']}")


async def interactive_mode() -> None:
    """Run in interactive mode."""
    config = Config.from_env()
    orchestrator = await Orchestrator.from_config(config)
    
    print("🧠 Dendrite Neural Engine v2")
    print("   Type 'quit' or 'exit' to stop")
    print("-" * 40)
    
    while True:
        try:
            goal = input("\n> ").strip()
            
            if not goal:
                continue
            
            if goal.lower() in ("quit", "exit", "q"):
                print("👋 Goodbye!")
                break
            
            result = await orchestrator.process(goal)
            
            if result["success"]:
                print(f"\n{result['result']}")
            else:
                print(f"\n❌ {result['error']}")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(
        description="Dendrite Neural Engine CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m neural_engine.v2.cli --goal "What is Python?"
    python -m neural_engine.v2.cli --goal "Calculate 5 * 7"
    python -m neural_engine.v2.cli --interactive
        """,
    )
    
    parser.add_argument(
        "--goal", "-g",
        type=str,
        help="Goal to process",
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    
    args = parser.parse_args()
    
    if args.interactive:
        asyncio.run(interactive_mode())
    elif args.goal:
        asyncio.run(process_goal(args.goal))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
