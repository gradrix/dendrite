"""
Dendrite CLI (v2)

Simple command-line interface for the neural engine.

Usage:
    python -m neural_engine.v2.cli --goal "What is 2+2?"
    python -m neural_engine.v2.cli --interactive
    python -m neural_engine.v2.cli --scheduler --interval 30
    python -m neural_engine.v2.cli --daemon --config goals.yaml
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from .core import Config, Orchestrator
from .scheduler import Scheduler, ScheduledGoal, ScheduleType, GoalCondition


def load_goals_config(config_path: str) -> dict:
    """Load goals from YAML config file."""
    try:
        import yaml
    except ImportError:
        print("❌ PyYAML required for config files. Install with: pip install pyyaml")
        sys.exit(1)
    
    path = Path(config_path)
    if not path.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)
    
    with open(path) as f:
        return yaml.safe_load(f)


def create_goal_from_config(goal_config: dict) -> ScheduledGoal:
    """Create a ScheduledGoal from config dict."""
    schedule_type = goal_config.get("schedule", "interval")
    
    if schedule_type == "interval":
        stype = ScheduleType.INTERVAL
        svalue = str(goal_config.get("interval", 300))
    elif schedule_type == "cron":
        stype = ScheduleType.CRON
        svalue = goal_config.get("cron", "0 * * * *")
    elif schedule_type == "once":
        stype = ScheduleType.ONCE
        svalue = None
    else:
        stype = ScheduleType.ON_DEMAND
        svalue = None
    
    return ScheduledGoal(
        id=goal_config["id"],
        goal=goal_config["goal"],
        schedule_type=stype,
        schedule_value=svalue,
        enabled=goal_config.get("enabled", True),
        tags=goal_config.get("tags", []),
        max_failures=goal_config.get("max_failures", 5),
    )


async def process_goal(goal: str, enable_forge: bool = False) -> None:
    """Process a single goal."""
    config = Config.from_env()
    orchestrator = await Orchestrator.from_config(config, enable_forge=enable_forge)
    
    if enable_forge:
        print("🔧 ToolForge enabled - dynamic tool creation available")
    
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


async def scheduler_mode(goal: str, interval: int) -> None:
    """Run scheduler with a periodic goal."""
    config = Config.from_env()
    orchestrator = await Orchestrator.from_config(config)
    
    # Create scheduler with orchestrator as executor
    scheduler = Scheduler(
        executor=orchestrator.process,
        check_interval=5,  # Check every 5 seconds for due goals
    )
    
    # Track run count in goal
    run_counter = [0]
    
    def on_complete(state, result):
        """Update state after each run."""
        state.data["last_response"] = result.get("result", "")[:100]
    
    # Create the periodic goal
    scheduled_goal = ScheduledGoal(
        id="demo_goal",
        goal=goal,
        schedule_type=ScheduleType.INTERVAL,
        schedule_value=str(interval),
        on_complete=on_complete,
    )
    
    await scheduler.add_goal(scheduled_goal)
    
    print("🗓️  Dendrite Scheduler Mode")
    print(f"   Goal: {goal}")
    print(f"   Interval: {interval}s")
    print("   Press Ctrl+C to stop")
    print("=" * 50)
    
    # Run first immediately
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⏳ Running initial goal...")
    run = await scheduler.run_now("demo_goal")
    run_counter[0] += 1
    _print_run_result(run, run_counter[0])
    
    # Then loop checking for scheduled runs
    try:
        while True:
            await asyncio.sleep(scheduler._check_interval)
            runs = await scheduler.check_and_run()
            for run in runs:
                run_counter[0] += 1
                _print_run_result(run, run_counter[0])
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n\n👋 Scheduler stopped")
        state = await scheduler.get_state("demo_goal")
        print(f"   Total runs: {state.run_count}")
        if state.last_run:
            print(f"   Last run: {state.last_run.strftime('%H:%M:%S')}")


def _print_run_result(run, count: int):
    """Pretty print a scheduled run result."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    
    if run.skipped:
        print(f"\n[{timestamp}] ⏭️  Run #{count} SKIPPED: {run.skip_reason}")
        return
    
    if run.success:
        result_text = run.result.get("result", "") if run.result else ""
        # Truncate long results
        if len(result_text) > 200:
            result_text = result_text[:200] + "..."
        print(f"\n[{timestamp}] ✅ Run #{count} ({run.duration_ms}ms)")
        print(f"   {result_text}")
    else:
        print(f"\n[{timestamp}] ❌ Run #{count} FAILED")
        print(f"   Error: {run.error}")


def _print_daemon_run(run, goal_id: str):
    """Print a daemon run result with goal ID."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    
    if run.skipped:
        print(f"[{timestamp}] ⏭️  {goal_id}: SKIPPED - {run.skip_reason}")
        return
    
    if run.success:
        result_text = run.result.get("result", "") if run.result else ""
        if len(result_text) > 150:
            result_text = result_text[:150] + "..."
        print(f"[{timestamp}] ✅ {goal_id} ({run.duration_ms}ms): {result_text}")
    else:
        print(f"[{timestamp}] ❌ {goal_id}: FAILED - {run.error}")


async def run_goals_with_streaming(scheduler, due_goals: list):
    """Run goals in parallel but print each result as it completes."""
    async def run_and_print(goal):
        run = await scheduler._execute_goal(goal)
        _print_daemon_run(run, run.goal_id)
        return run
    
    tasks = [run_and_print(goal) for goal in due_goals]
    return await asyncio.gather(*tasks, return_exceptions=True)


async def daemon_mode(config_path: str) -> None:
    """Run as daemon with multiple goals from config file."""
    config_data = load_goals_config(config_path)
    goals_config = config_data.get("goals", [])
    settings = config_data.get("settings", {})
    
    if not goals_config:
        print("❌ No goals defined in config file")
        sys.exit(1)
    
    # Filter enabled goals
    enabled_goals = [g for g in goals_config if g.get("enabled", True)]
    
    if not enabled_goals:
        print("❌ No enabled goals in config file")
        sys.exit(1)
    
    config = Config.from_env()
    orchestrator = await Orchestrator.from_config(config)
    
    check_interval = settings.get("check_interval", 30)
    scheduler = Scheduler(
        executor=orchestrator.process,
        check_interval=check_interval,
    )
    
    # Add all goals
    for goal_config in enabled_goals:
        goal = create_goal_from_config(goal_config)
        await scheduler.add_goal(goal)
    
    print("🚀 Dendrite Daemon Mode")
    print(f"   Config: {config_path}")
    print(f"   Goals: {len(enabled_goals)} enabled")
    print(f"   Check interval: {check_interval}s")
    print("   Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    # List loaded goals
    for g in enabled_goals:
        schedule_str = g.get("schedule", "interval")
        if schedule_str == "interval":
            schedule_str = f"every {g.get('interval', 300)}s"
        elif schedule_str == "cron":
            schedule_str = f"cron: {g.get('cron', '?')}"
        print(f"   📋 {g['id']}: {schedule_str}")
    print()
    
    # Run all "once" goals immediately
    for goal_config in enabled_goals:
        if goal_config.get("schedule") == "once":
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ Running once: {goal_config['id']}")
            run = await scheduler.run_now(goal_config["id"])
            _print_daemon_run(run, goal_config["id"])
    
    # Main loop - find due goals and run with streaming output
    try:
        while True:
            await asyncio.sleep(check_interval)
            
            # Find due goals
            goals = await scheduler.list_goals(enabled_only=True)
            due_goals = []
            for goal in goals:
                state = await scheduler.get_state(goal.id)
                if scheduler._should_run(goal, state):
                    due_goals.append(goal)
            
            # Run in parallel with streaming output
            if due_goals:
                await run_goals_with_streaming(scheduler, due_goals)
                
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n\n👋 Daemon stopped")
        goals = await scheduler.list_goals()
        for goal in goals:
            state = await scheduler.get_state(goal.id)
            if state.run_count > 0:
                print(f"   {goal.id}: {state.run_count} runs, last: {state.last_run.strftime('%H:%M:%S') if state.last_run else 'never'}")


async def list_goals_cmd(config_path: str) -> None:
    """List goals from config file."""
    config_data = load_goals_config(config_path)
    goals_config = config_data.get("goals", [])
    
    if not goals_config:
        print("No goals defined")
        return
    
    print(f"Goals in {config_path}:")
    print("-" * 50)
    
    for g in goals_config:
        enabled = "✅" if g.get("enabled", True) else "❌"
        schedule = g.get("schedule", "interval")
        
        if schedule == "interval":
            schedule_str = f"every {g.get('interval', 300)}s"
        elif schedule == "cron":
            schedule_str = f"cron '{g.get('cron', '?')}'"
        else:
            schedule_str = schedule
        
        print(f"{enabled} {g['id']}")
        print(f"   Schedule: {schedule_str}")
        print(f"   Goal: {g['goal'][:60]}{'...' if len(g['goal']) > 60 else ''}")
        if g.get("tags"):
            print(f"   Tags: {', '.join(g['tags'])}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Dendrite Neural Engine CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Single goal
    python -m neural_engine.v2.cli --goal "What is Python?"
    
    # Interactive mode
    python -m neural_engine.v2.cli --interactive
    
    # Single periodic goal
    python -m neural_engine.v2.cli --scheduler --interval 30 --goal "Tell me a fun fact"
    
    # Daemon mode with config file
    python -m neural_engine.v2.cli --daemon --config goals.yaml
    
    # List goals from config
    python -m neural_engine.v2.cli --list-goals --config goals.yaml
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
    
    parser.add_argument(
        "--scheduler", "-s",
        action="store_true",
        help="Run in scheduler mode (single periodic goal)",
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Interval in seconds for scheduler mode (default: 30)",
    )
    
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run as daemon with multiple goals from config file",
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="goals.yaml",
        help="Config file for daemon mode (default: goals.yaml)",
    )
    
    parser.add_argument(
        "--forge",
        action="store_true",
        help="Enable ToolForge for dynamic tool creation",
    )
    
    parser.add_argument(
        "--list-goals",
        action="store_true",
        help="List goals from config file",
    )
    
    args = parser.parse_args()
    
    if args.list_goals:
        asyncio.run(list_goals_cmd(args.config))
    elif args.daemon:
        asyncio.run(daemon_mode(args.config))
    elif args.scheduler:
        goal = args.goal or "Tell me a random fun fact about technology"
        asyncio.run(scheduler_mode(goal, args.interval))
    elif args.interactive:
        asyncio.run(interactive_mode())
    elif args.goal:
        asyncio.run(process_goal(args.goal, enable_forge=args.forge))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
