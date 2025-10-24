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
import json
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

def parse_question_to_plan(question, ollama):
    """
    STEP 1: Parse question into a simple execution plan.
    Fresh LLM context - only focused on understanding the question.
    """
    planning_prompt = f"""Question: {question}

Analyze this question and create a simple step-by-step plan.

Available Strava tools:
- getMyActivities: Get my activities (params: per_page, after_unix, before_unix)
- getActivityKudos: Get who gave kudos to specific activity (params: activity_id)
- getDashboardFeed: Get feed of friend activities (params: hours_ago, num_entries)
- getFollowers: Get my followers
- getFollowing: Get who I follow
- updateActivity: Update activity settings
- giveKudos: Give kudos to activity

Create a plan with 1-3 steps maximum. Each step should call ONE tool.

Respond ONLY with valid JSON:
{{
  "reasoning": "brief explanation",
  "plan": [
    {{"step": 1, "tool": "toolName", "description": "what this does"}},
    {{"step": 2, "tool": "toolName", "description": "what this does", "depends_on": 1}}
  ]
}}"""

    context = "You are a query planner. Output ONLY valid JSON, no markdown, no extra text."
    
    try:
        response = ollama.generate(planning_prompt, system=context)
        # Parse JSON from response
        import json
        import re
        
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            plan_data = json.loads(json_match.group())
            return plan_data
        else:
            logger.error(f"Could not parse plan from: {response}")
            return None
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        return None


def execute_step(step_info, previous_results, ollama, registry):
    """
    STEP 2+: Execute a single step with fresh LLM context.
    Only knows about THIS step and relevant previous results.
    """
    tool_name = step_info['tool']
    description = step_info['description']
    depends_on = step_info.get('depends_on')
    
    print_colored(f"\n📍 Step {step_info['step']}: {description}", CYAN)
    print_colored(f"   Tool: {tool_name}", BLUE)
    
    # Get tool definition
    tool = registry.get(tool_name)
    if not tool:
        return {"success": False, "error": f"Tool {tool_name} not found"}
    
    # Build focused context for parameter extraction
    tool_dict = tool.to_dict()
    param_info = tool_dict.get('parameters', [])
    
    param_prompt = f"""Task: {description}

Tool: {tool_name}
Parameters needed: """
    
    # Format parameters in a readable way
    if param_info:
        for p in param_info:
            param_name = p.get('name', 'unknown')
            param_type = p.get('type', 'any')
            required = p.get('required', False)
            param_desc = p.get('description', '')
            req_str = "(required)" if required else "(optional)"
            param_prompt += f"\n  - {param_name} ({param_type}) {req_str}: {param_desc}"
    else:
        param_prompt += "None"
    
    param_prompt += "\n\n"
    
    # Add relevant previous results if this step depends on another
    if depends_on and previous_results:
        prev_step = previous_results.get(depends_on)
        if prev_step:
            param_prompt += f"Previous step result:\n{json.dumps(prev_step, indent=2)}\n\n"
    
    param_prompt += """Determine the parameters for this tool call.

Respond ONLY with valid JSON:
{
  "reasoning": "brief explanation",
  "params": {"param_name": "value"}
}

If you need data from previous results (like activity IDs), extract them.
"""
    
    context = "You are a parameter extractor. Output ONLY valid JSON."
    
    try:
        response = ollama.generate(param_prompt, system=context)
        
        # Parse JSON
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            param_data = json.loads(json_match.group())
            params = param_data.get('params', {})
            reasoning = param_data.get('reasoning', '')
            
            print_colored(f"   💭 {reasoning}", BLUE)
            print_colored(f"   📥 Parameters: {params}", BLUE)
            
            # Execute the tool
            result = tool.execute(**params)
            
            print_colored(f"   ✅ Executed successfully", GREEN)
            return {
                "success": True,
                "tool": tool_name,
                "params": params,
                "result": result
            }
        else:
            return {"success": False, "error": "Could not parse parameters"}
            
    except Exception as e:
        print_colored(f"   ❌ Error: {e}", RED)
        return {"success": False, "error": str(e)}


def main():
    question = """${QUESTION}"""
    
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Override Ollama URL for local execution
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
    
    print_colored(f"✅ Loaded {len(registry.list_tools())} tools", GREEN)
    
    print_colored(f"\n💬 Question: {question}", BLUE)
    print_colored("=" * 80, CYAN)
    
    # STEP 1: Plan the execution
    print_colored("\n📋 Planning execution...", YELLOW)
    plan = parse_question_to_plan(question, ollama)
    
    if not plan or 'plan' not in plan:
        print_colored("❌ Could not create execution plan", RED)
        print_colored("💡 Try using query.py instead for direct queries", YELLOW)
        sys.exit(1)
    
    print_colored(f"💭 Reasoning: {plan.get('reasoning', '')}", BLUE)
    print_colored(f"📝 Plan has {len(plan['plan'])} step(s)", GREEN)
    
    for step in plan['plan']:
        print(f"   {step['step']}. {step['description']} → {step['tool']}")
    
    # STEP 2+: Execute each step independently
    results = {}
    
    for step_info in plan['plan']:
        result = execute_step(step_info, results, ollama, registry)
        results[step_info['step']] = result
        
        if not result.get('success'):
            print_colored(f"\n⚠️  Step {step_info['step']} failed, stopping", YELLOW)
            break
    
    # Final summary
    print_colored("\n" + "=" * 80, CYAN)
    print_colored("📊 SUMMARY", CYAN)
    print_colored("=" * 80, CYAN)
    
    successful = sum(1 for r in results.values() if r.get('success'))
    failed = len(results) - successful
    
    print_colored(f"Total steps: {len(results)}", BLUE)
    print_colored(f"Successful: {successful}", GREEN if successful > 0 else NC)
    print_colored(f"Failed: {failed}", RED if failed > 0 else NC)
    
    # Show final results in human-readable format
    if results:
        print_colored("\n📝 Results:", CYAN)
        for step_num, result in sorted(results.items()):
            tool_name = result.get('tool')
            success = result.get('success')
            result_data = result.get('result')
            
            status = "✅" if success else "❌"
            print(f"\n{status} Step {step_num}: {tool_name}")
            
            if success and result_data:
                # Pretty print common result types
                if isinstance(result_data, dict):
                    if 'activities' in result_data and isinstance(result_data['activities'], list):
                        activities = result_data['activities']
                        print(f"   Found {len(activities)} activities:")
                        for act in activities[:5]:
                            activity_id = act.get('id', '?')
                            name = act.get('name', 'Unknown')
                            kudos = act.get('kudos_count', 0)
                            print(f"     • [{activity_id}] {name} ({kudos} kudos)")
                        if len(activities) > 5:
                            print(f"     ... and {len(activities) - 5} more")
                    
                    elif 'athletes' in result_data and isinstance(result_data['athletes'], list):
                        athletes = result_data['athletes']
                        count = result_data.get('kudos_count', len(athletes))
                        print(f"   Found {count} kudos givers:")
                        for ath in athletes[:10]:
                            name = ath.get('name', 'Unknown')
                            print(f"     • {name}")
                        if len(athletes) > 10:
                            print(f"     ... and {len(athletes) - 10} more")
                    
                    elif 'count' in result_data:
                        print(f"   Count: {result_data['count']}")
                    
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
