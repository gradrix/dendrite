#!/bin/bash

# Interactive AI Assistant - One-shot queries with access to all tools
# Usage: ./ask.sh "your question here"

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if question provided
if [ -z "$1" ]; then
    echo "Usage: $0 \"your question here\""
    echo ""
    echo "Examples:"
    echo "  $0 \"Get kudos givers for my activities from last 24 hours\""
    echo "  $0 \"List my last 3 activities\""
    echo "  $0 \"Show me activities that need to be made public\""
    echo "  $0 \"What activities got kudos today?\""
    exit 1
fi

QUESTION="$1"

print_info "Question: $QUESTION"
echo ""
print_info "Thinking..."
echo ""

# Run Python script with the question
python3 << EOF
import sys
import os
import logging
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.getcwd())

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import agent components
from agent.ollama_client import OllamaClient
from agent.tool_registry import get_registry
from agent.action_executor import ActionExecutor
from agent.instruction_loader import InstructionLoader
import yaml

# Color codes
CYAN = '\033[0;36m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'
NC = '\033[0m'

def print_colored(text, color=NC):
    print(f"{color}{text}{NC}")

def main():
    question = """${QUESTION}"""
    
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Override Ollama URL for local execution (not in Docker)
    # Check if we can reach localhost:11434, otherwise use the config value
    import requests
    try:
        requests.get('http://localhost:11434/api/tags', timeout=1)
        config['ollama']['base_url'] = 'http://localhost:11434'
        print_colored("✅ Using local Ollama at localhost:11434", GREEN)
    except:
        print_colored(f"⚠️  Using Ollama at {config['ollama']['base_url']}", YELLOW)
    
    # Initialize components
    print_colored("\n🤖 Initializing AI Assistant...", CYAN)
    
    ollama = OllamaClient(
        base_url=config['ollama']['base_url'],
        model=config['ollama']['model'],
        timeout=config['ollama']['timeout'],
        max_retries=config['ollama']['max_retries'],
        temperature=config['ollama']['temperature']
    )
    
    # Check Ollama health
    if not ollama.health_check():
        print_colored("❌ Ollama is not running!", RED)
        sys.exit(1)
    
    # Get tools
    registry = get_registry()
    registry.discover_tools("tools")
    
    tools = [tool.to_dict() for tool in registry.list_tools()]
    print_colored(f"✅ Loaded {len(tools)} tools", GREEN)
    
    # Simple context focused on answering the question
    context = """You are a helpful AI assistant with access to Strava tools.

CRITICAL: Respond ONLY with valid JSON. No explanations, no markdown, no extra text.
Required format: {"reasoning": "...", "actions": [...], "confidence": 0.8}

Your goal: Answer the user's question using the available tools.
- Keep reasoning brief and focused
- Execute only the actions needed to answer the question
- Return empty actions array when you have the answer
- Output ONLY valid JSON

Available tools: getCurrentDateTime, getDateTimeHoursAgo, loadState, saveState, 
getMyActivities, getActivityKudos, getDashboardFeed, getFollowing, getFollowers, 
getActivityParticipants, giveKudos, updateActivity

Tips:
- For "last N activities": use getMyActivities(per_page=N)
- For "kudos givers": use getActivityKudos(activity_id=X)
- For "feed": use getDashboardFeed(hours_ago=X)
- You can call multiple tools in sequence across iterations
"""
    
    # Create executor
    executor = ActionExecutor(
        registry=registry,
        dry_run=False,
        max_actions=20,
        cooldown_seconds=2
    )
    
    print_colored(f"\n💬 Question: {question}", BLUE)
    print_colored("=" * 80, CYAN)
    
    # Multi-iteration execution
    max_iterations = 10
    all_results = []
    
    for iteration in range(max_iterations):
        print_colored(f"\n🔄 Iteration {iteration + 1}/{max_iterations}", YELLOW)
        
        # Build prompt with previous results
        prompt = f"{question}\n\n"
        
        if all_results:
            prompt += "Previous actions and results:\n"
            for prev in all_results[-5:]:
                tool_name = prev.get('tool_name', 'unknown')
                success = prev.get('success', False)
                result = prev.get('result', {})
                prompt += f"  ✓ {tool_name}: "
                if isinstance(result, dict):
                    if 'count' in result:
                        prompt += f"Count: {result['count']}"
                    elif 'success' in result:
                        prompt += f"Success: {result['success']}"
                    else:
                        prompt += f"{list(result.keys())}"
                else:
                    prompt += f"{str(result)[:100]}"
                prompt += "\n"
            prompt += "\nContinue to the next step, or return empty actions if complete.\n"
        
        # Query LLM
        try:
            decision = ollama.function_call(
                prompt=prompt,
                tools=tools,
                context=context
            )
        except Exception as e:
            print_colored(f"❌ LLM Error: {e}", RED)
            break
        
        print_colored(f"💭 Reasoning: {decision['reasoning']}", BLUE)
        print_colored(f"🎯 Confidence: {decision['confidence']}", BLUE)
        
        # Check if done
        if not decision['actions']:
            print_colored("\n✅ Workflow complete!", GREEN)
            break
        
        print_colored(f"⚡ Executing {len(decision['actions'])} action(s)...", YELLOW)
        
        # Execute actions
        from agent.instruction_loader import Instruction
        
        # Create a permissive instruction for ad-hoc queries
        class AdHocInstruction(Instruction):
            def __init__(self):
                self.name = "AdHoc Query"
                self.description = "Interactive query"
                self.permissions = {
                    "allow_write": True,
                    "allow_updateactivity": True,
                    "allow_kudos": True
                }
                self.tools_allowed = [tool['name'] for tool in tools]
                self.requires_approval_list = []
            
            def is_tool_allowed(self, tool_name):
                return True
            
            def requires_approval_for(self, action_description):
                return False
        
        instruction = AdHocInstruction()
        
        try:
            results = executor.execute_actions(
                actions=decision['actions'],
                instruction=instruction
            )
            
            # Save results
            for action, result in zip(decision['actions'], results):
                result_record = {
                    'tool_name': action['tool'],
                    'parameters': action.get('params'),
                    'result': result.get('result'),
                    'success': result.get('success', False),
                    'error': result.get('error')
                }
                all_results.append(result_record)
                
                # Display result
                if result.get('success'):
                    print_colored(f"  ✅ {action['tool']}: Success", GREEN)
                else:
                    print_colored(f"  ❌ {action['tool']}: {result.get('error', 'Failed')}", RED)
        
        except Exception as e:
            print_colored(f"❌ Execution error: {e}", RED)
            break
    
    # Final summary
    print_colored("\n" + "=" * 80, CYAN)
    print_colored("📊 SUMMARY", CYAN)
    print_colored("=" * 80, CYAN)
    
    successful = sum(1 for r in all_results if r.get('success'))
    failed = len(all_results) - successful
    
    print_colored(f"Total actions: {len(all_results)}", BLUE)
    print_colored(f"Successful: {successful}", GREEN if successful > 0 else NC)
    print_colored(f"Failed: {failed}", RED if failed > 0 else NC)
    
    # Show final results in human-readable format
    if all_results:
        print_colored("\n📝 Results:", CYAN)
        for i, result in enumerate(all_results, 1):
            tool_name = result.get('tool_name')
            success = result.get('success')
            result_data = result.get('result')
            
            status = "✅" if success else "❌"
            print(f"\n{status} {i}. {tool_name}")
            
            if success and result_data:
                # Pretty print common result types
                if isinstance(result_data, dict):
                    if 'activities' in result_data and isinstance(result_data['activities'], list):
                        activities = result_data['activities']
                        print(f"   Found {len(activities)} activities:")
                        for act in activities[:5]:
                            name = act.get('name', 'Unknown')
                            kudos = act.get('kudos_count', 0)
                            print(f"     • {name} ({kudos} kudos)")
                        if len(activities) > 5:
                            print(f"     ... and {len(activities) - 5} more")
                    
                    elif 'athletes' in result_data and isinstance(result_data['athletes'], list):
                        athletes = result_data['athletes']
                        print(f"   Found {len(athletes)} athletes:")
                        for ath in athletes[:10]:
                            name = ath.get('name', 'Unknown')
                            print(f"     • {name}")
                        if len(athletes) > 10:
                            print(f"     ... and {len(athletes) - 10} more")
                    
                    elif 'datetime' in result_data:
                        dt = result_data['datetime']
                        print(f"   Timestamp: {dt.get('iso', 'unknown')}")
                    
                    else:
                        # Generic dict output
                        for key, value in list(result_data.items())[:5]:
                            if isinstance(value, (str, int, float, bool)):
                                print(f"   {key}: {value}")
                
                elif isinstance(result_data, list):
                    print(f"   {len(result_data)} items")
                    for item in result_data[:5]:
                        print(f"     • {item}")
                    if len(result_data) > 5:
                        print(f"     ... and {len(result_data) - 5} more")
    
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[INFO]{NC} Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"{RED}[ERROR]{NC} {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
EOF
