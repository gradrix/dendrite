"""
Thinking Visualizer: Show the AI's thought process in real-time.

Provides visibility into:
- Goal understanding
- Decomposition into subgoals
- Tool selection reasoning
- Execution steps
- Error recovery attempts
- Cache hits/misses
- Final result

This makes the "black box" transparent.
"""

from typing import Dict, List, Optional
from datetime import datetime
import json


class ThinkingVisualizer:
    """
    Visualize the AI's thinking process in real-time.
    
    Shows what the system is doing at each step.
    """
    
    def __init__(self, verbose: bool = True):
        """
        Initialize visualizer.
        
        Args:
            verbose: If True, show detailed thinking. If False, show summary only.
        """
        self.verbose = verbose
        self.steps = []
        self.start_time = None
    
    def start_goal(self, goal: str):
        """Start tracking a new goal."""
        self.start_time = datetime.now()
        self.steps = []
        
        print("\n" + "="*80)
        print("🎯 NEW GOAL")
        print("="*80)
        print(f"Goal: {goal}")
        print(f"Time: {self.start_time.strftime('%H:%M:%S')}")
        print("="*80 + "\n")
        
        self._add_step("goal_received", {"goal": goal})
    
    def show_cache_check(self, cache_result: Optional[Dict]):
        """Show cache lookup result."""
        if cache_result:
            print("💨 CACHE HIT (System 1 - Fast Path)")
            print(f"   Similarity: {cache_result.get('similarity', 0):.0%}")
            print(f"   Cached pathway: {cache_result.get('pathway_id', 'unknown')}")
            print(f"   Tools: {', '.join(cache_result.get('tools_used', []))}")
            print(f"   Usage count: {cache_result.get('usage_count', 0)}")
            print(f"   ⚡ Executing cached pathway...\n")
            self._add_step("cache_hit", cache_result)
        else:
            print("🧠 CACHE MISS (System 2 - Full Reasoning)")
            print("   No similar cached pathway found")
            print("   Proceeding with full decomposition...\n")
            self._add_step("cache_miss", {})
    
    def show_pattern_suggestion(self, suggestion: Optional[Dict]):
        """Show learned pattern suggestion."""
        if suggestion:
            print("📚 LEARNED PATTERN FOUND")
            print(f"   Confidence: {suggestion.get('confidence', 0):.0%}")
            print(f"   Based on: \"{suggestion.get('pattern_goal', 'unknown')}\"")
            print(f"   Used {suggestion.get('usage_count', 0)} times before")
            print(f"   Suggested subgoals:")
            for i, subgoal in enumerate(suggestion.get('suggested_subgoals', []), 1):
                print(f"      {i}. {subgoal}")
            print()
            self._add_step("pattern_suggested", suggestion)
        else:
            if self.verbose:
                print("📚 No learned pattern found - creating fresh decomposition\n")
            self._add_step("no_pattern", {})
    
    def show_decomposition(self, subgoals: List[str]):
        """Show goal decomposition."""
        print("🎯 GOAL DECOMPOSITION")
        print(f"   Breaking goal into {len(subgoals)} subgoals:")
        for i, subgoal in enumerate(subgoals, 1):
            print(f"      {i}. {subgoal}")
        print()
        self._add_step("decomposition", {"subgoals": subgoals})
    
    def show_tool_selection(self, tool_name: str, reasoning: Optional[str] = None):
        """Show tool selection."""
        print(f"🔧 TOOL SELECTED: {tool_name}")
        if reasoning and self.verbose:
            print(f"   Reasoning: {reasoning}")
        print()
        self._add_step("tool_selected", {"tool": tool_name, "reasoning": reasoning})
    
    def show_execution(self, tool_name: str, parameters: Dict):
        """Show tool execution."""
        print(f"⚙️  EXECUTING: {tool_name}")
        if self.verbose:
            print(f"   Parameters: {json.dumps(parameters, indent=6)}")
        print()
        self._add_step("execution", {"tool": tool_name, "parameters": parameters})
    
    def show_error(self, error: Exception, error_type: str):
        """Show error occurrence."""
        print(f"❌ ERROR OCCURRED")
        print(f"   Type: {error_type}")
        print(f"   Message: {str(error)}")
        print()
        self._add_step("error", {"error": str(error), "type": error_type})
    
    def show_recovery_attempt(self, strategy: str, attempt: int):
        """Show error recovery attempt."""
        print(f"🔄 RECOVERY ATTEMPT #{attempt}")
        print(f"   Strategy: {strategy}")
        self._add_step("recovery_attempt", {"strategy": strategy, "attempt": attempt})
    
    def show_recovery_success(self, strategy: str, explanation: str):
        """Show successful recovery."""
        print(f"✅ RECOVERY SUCCESSFUL")
        print(f"   Strategy: {strategy}")
        print(f"   {explanation}")
        print()
        self._add_step("recovery_success", {"strategy": strategy, "explanation": explanation})
    
    def show_recovery_failure(self, explanation: str):
        """Show failed recovery."""
        print(f"❌ RECOVERY FAILED")
        print(f"   {explanation}")
        print()
        self._add_step("recovery_failed", {"explanation": explanation})
    
    def show_result(self, result: Dict, success: bool):
        """Show final result."""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        print("="*80)
        if success:
            print("✅ GOAL COMPLETED SUCCESSFULLY")
        else:
            print("❌ GOAL FAILED")
        print("="*80)
        
        if self.verbose:
            print(f"Result: {json.dumps(result, indent=2)[:500]}...")
        else:
            print(f"Result: {str(result)[:200]}...")
        
        print(f"\nDuration: {duration:.2f}s")
        print(f"Steps: {len(self.steps)}")
        print("="*80 + "\n")
        
        self._add_step("completed", {"result": result, "success": success, "duration": duration})
    
    def show_cache_stored(self, pathway_id: str, tools_used: List[str]):
        """Show that result was cached."""
        if self.verbose:
            print(f"💾 CACHED FOR FUTURE USE")
            print(f"   Pathway ID: {pathway_id}")
            print(f"   Tools: {', '.join(tools_used)}")
            print()
        self._add_step("cached", {"pathway_id": pathway_id, "tools": tools_used})
    
    def show_pattern_stored(self, pattern_id: int, goal_type: str):
        """Show that pattern was learned."""
        if self.verbose:
            print(f"📚 PATTERN LEARNED")
            print(f"   Pattern ID: {pattern_id}")
            print(f"   Goal Type: {goal_type}")
            print()
        self._add_step("pattern_learned", {"pattern_id": pattern_id, "goal_type": goal_type})
    
    def _add_step(self, step_type: str, data: Dict):
        """Add step to history."""
        self.steps.append({
            "type": step_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        })
    
    def get_summary(self) -> Dict:
        """Get summary of thinking process."""
        if not self.start_time:
            return {}
        
        duration = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "total_steps": len(self.steps),
            "duration_seconds": duration,
            "steps": self.steps,
            "cache_hit": any(s['type'] == 'cache_hit' for s in self.steps),
            "pattern_used": any(s['type'] == 'pattern_suggested' for s in self.steps),
            "errors_occurred": any(s['type'] == 'error' for s in self.steps),
            "recovery_successful": any(s['type'] == 'recovery_success' for s in self.steps)
        }
