#!/usr/bin/env python3
"""
Dendrite CLI - Production-ready goal execution.

Usage:
    # Run a goal immediately
    dendrite run "Say hello"
    
    # Add to queue (processed by worker)
    dendrite queue "Check my Strava activities"
    
    # Start worker daemon
    dendrite worker
    
    # Check status
    dendrite status
    
    # View recent executions
    dendrite history
"""

import argparse
import sys
import os
import json
import time
import signal
import uuid
from datetime import datetime
from typing import Optional

# Ensure neural_engine is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_redis_client():
    """Get Redis client with connection pooling."""
    import redis
    host = os.environ.get('REDIS_HOST', 'localhost')
    return redis.Redis(host=host, port=6379, db=0, decode_responses=True)


def create_orchestrator():
    """Create fully initialized orchestrator."""
    from neural_engine.core.system_factory import create_neural_engine
    return create_neural_engine(enable_all_features=True)


# ============================================================================
# COMMANDS
# ============================================================================

def cmd_run(args):
    """Run a goal immediately and show result."""
    print(f"🎯 Executing: {args.goal}")
    print("-" * 50)
    
    orchestrator = create_orchestrator()
    
    start = time.time()
    result = orchestrator.process(args.goal)
    duration = time.time() - start
    
    print("-" * 50)
    
    if result.get('success', True):
        print(f"✅ Success ({duration:.2f}s)")
        if 'response' in result:
            print(f"\n{result['response']}")
        elif 'result' in result:
            print(f"\nResult: {result['result']}")
    else:
        print(f"❌ Failed ({duration:.2f}s)")
        if 'error' in result:
            print(f"Error: {result['error']}")
    
    return 0 if result.get('success', True) else 1


def cmd_queue(args):
    """Add a goal to the queue for later processing."""
    redis_client = get_redis_client()
    
    goal_data = {
        'id': str(uuid.uuid4()),
        'goal': args.goal,
        'queued_at': datetime.now().isoformat(),
        'priority': args.priority
    }
    
    queue_name = 'dendrite:goals:high' if args.priority == 'high' else 'dendrite:goals:normal'
    redis_client.lpush(queue_name, json.dumps(goal_data))
    
    print(f"✅ Goal queued: {goal_data['id']}")
    print(f"   Priority: {args.priority}")
    print(f"   Queue: {queue_name}")
    
    # Show queue length
    high = redis_client.llen('dendrite:goals:high')
    normal = redis_client.llen('dendrite:goals:normal')
    print(f"\n📊 Queue status: {high} high, {normal} normal priority")
    
    return 0


def cmd_worker(args):
    """Run the goal processing worker."""
    print("🔄 Starting Dendrite worker...")
    print(f"   Poll interval: {args.interval}s")
    print("   Press Ctrl+C to stop\n")
    
    redis_client = get_redis_client()
    orchestrator = create_orchestrator()
    
    running = True
    processed = 0
    
    def signal_handler(sig, frame):
        nonlocal running
        print("\n\n🛑 Shutting down worker...")
        running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while running:
        # Check high priority first, then normal
        goal_json = redis_client.rpop('dendrite:goals:high')
        if not goal_json:
            goal_json = redis_client.rpop('dendrite:goals:normal')
        
        if goal_json:
            goal_data = json.loads(goal_json)
            goal_id = goal_data['id']
            goal = goal_data['goal']
            
            print(f"\n{'='*60}")
            print(f"🎯 Processing: {goal}")
            print(f"   ID: {goal_id}")
            print(f"   Queued: {goal_data['queued_at']}")
            print(f"{'='*60}")
            
            start = time.time()
            try:
                result = orchestrator.process(goal)
                duration = time.time() - start
                
                # Store result
                result_data = {
                    'id': goal_id,
                    'goal': goal,
                    'result': result,
                    'duration': duration,
                    'completed_at': datetime.now().isoformat(),
                    'success': result.get('success', True)
                }
                redis_client.hset('dendrite:results', goal_id, json.dumps(result_data))
                
                processed += 1
                status = "✅ Success" if result.get('success', True) else "❌ Failed"
                print(f"\n{status} ({duration:.2f}s)")
                
            except Exception as e:
                duration = time.time() - start
                print(f"\n❌ Error ({duration:.2f}s): {e}")
                
                # Store error
                result_data = {
                    'id': goal_id,
                    'goal': goal,
                    'error': str(e),
                    'duration': duration,
                    'completed_at': datetime.now().isoformat(),
                    'success': False
                }
                redis_client.hset('dendrite:results', goal_id, json.dumps(result_data))
        else:
            # No goals in queue, sleep
            time.sleep(args.interval)
    
    print(f"\n📊 Worker stopped. Processed {processed} goals.")
    return 0


def cmd_status(args):
    """Show system status."""
    print("📊 Dendrite Status\n")
    
    redis_client = get_redis_client()
    
    # Queue status
    high = redis_client.llen('dendrite:goals:high')
    normal = redis_client.llen('dendrite:goals:normal')
    total_results = redis_client.hlen('dendrite:results')
    
    print(f"Queue:")
    print(f"  High priority:   {high}")
    print(f"  Normal priority: {normal}")
    print(f"  Total pending:   {high + normal}")
    print(f"\nCompleted: {total_results}")
    
    # Check services
    print(f"\nServices:")
    
    # Redis
    try:
        redis_client.ping()
        print(f"  Redis:      ✅ Connected")
    except:
        print(f"  Redis:      ❌ Not connected")
    
    # LLM (llama.cpp)
    try:
        from neural_engine.core.llm_client import LLMClient
        client = LLMClient()
        print(f"  LLM:        ✅ Connected ({client._backend}, {client.model})")
    except Exception as e:
        print(f"  LLM:        ❌ {e}")
    
    # PostgreSQL
    try:
        from neural_engine.core.execution_store import ExecutionStore
        store = ExecutionStore()
        print(f"  PostgreSQL: ✅ Connected")
    except Exception as e:
        print(f"  PostgreSQL: ⚠️  Not available")
    
    return 0


def cmd_history(args):
    """Show recent execution history."""
    redis_client = get_redis_client()
    
    results = redis_client.hgetall('dendrite:results')
    
    if not results:
        print("No execution history found.")
        return 0
    
    # Parse and sort by completion time
    entries = []
    for goal_id, data_json in results.items():
        data = json.loads(data_json)
        entries.append(data)
    
    entries.sort(key=lambda x: x.get('completed_at', ''), reverse=True)
    
    # Show last N
    limit = args.limit
    print(f"📜 Last {min(limit, len(entries))} executions:\n")
    
    for entry in entries[:limit]:
        status = "✅" if entry.get('success', False) else "❌"
        goal = entry.get('goal', 'Unknown')[:50]
        completed = entry.get('completed_at', 'Unknown')[:19]
        duration = entry.get('duration', 0)
        
        print(f"{status} [{completed}] ({duration:.1f}s) {goal}")
    
    return 0


def cmd_clear(args):
    """Clear queue or history."""
    redis_client = get_redis_client()
    
    if args.what == 'queue':
        redis_client.delete('dendrite:goals:high', 'dendrite:goals:normal')
        print("✅ Queue cleared")
    elif args.what == 'history':
        redis_client.delete('dendrite:results')
        print("✅ History cleared")
    elif args.what == 'all':
        redis_client.delete('dendrite:goals:high', 'dendrite:goals:normal', 'dendrite:results')
        print("✅ Queue and history cleared")
    
    return 0


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Dendrite - Neural goal execution engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    dendrite run "Say hello"              # Execute immediately
    dendrite queue "Check my runs"        # Add to queue
    dendrite worker                       # Start processing queue
    dendrite status                       # Check system status
    dendrite history                      # View past executions
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # run command
    run_parser = subparsers.add_parser('run', help='Run a goal immediately')
    run_parser.add_argument('goal', type=str, help='Goal to execute')
    run_parser.set_defaults(func=cmd_run)
    
    # queue command
    queue_parser = subparsers.add_parser('queue', help='Add goal to queue')
    queue_parser.add_argument('goal', type=str, help='Goal to queue')
    queue_parser.add_argument('--priority', choices=['normal', 'high'], default='normal')
    queue_parser.set_defaults(func=cmd_queue)
    
    # worker command
    worker_parser = subparsers.add_parser('worker', help='Run worker daemon')
    worker_parser.add_argument('--interval', type=float, default=1.0, help='Poll interval in seconds')
    worker_parser.set_defaults(func=cmd_worker)
    
    # status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    status_parser.set_defaults(func=cmd_status)
    
    # history command
    history_parser = subparsers.add_parser('history', help='Show execution history')
    history_parser.add_argument('--limit', '-n', type=int, default=10, help='Number of entries')
    history_parser.set_defaults(func=cmd_history)
    
    # clear command
    clear_parser = subparsers.add_parser('clear', help='Clear queue or history')
    clear_parser.add_argument('what', choices=['queue', 'history', 'all'])
    clear_parser.set_defaults(func=cmd_clear)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
