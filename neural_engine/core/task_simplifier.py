"""
Task Simplifier: Helps small LLMs by breaking down and clarifying tasks.

REFACTORED: Now uses semantic tool discovery instead of hardcoded keyword mappings!

Instead of maintaining a giant keyword→tool dictionary, we:
1. Use ToolDiscovery.semantic_search() to find relevant tools
2. Use tool metadata (domain, concepts, actions) for hints
3. Let embeddings handle the "runs" → "running/fitness" matching

Key Insight: Small LLM + Semantically Narrowed Tools = Success
"""

import re
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neural_engine.core.tool_discovery import ToolDiscovery


class TaskSimplifier:
    """
    Makes tasks easier for small LLMs by pre-processing and clarifying.
    
    Uses SEMANTIC SEARCH to narrow down tools - no hardcoded keywords!
    """
    
    def __init__(self, tool_discovery: Optional['ToolDiscovery'] = None):
        """
        Initialize task simplifier.
        
        Args:
            tool_discovery: ToolDiscovery instance for semantic search.
                           If None, falls back to returning all tools.
        """
        self.tool_discovery = tool_discovery
    
    def set_tool_discovery(self, tool_discovery: 'ToolDiscovery'):
        """Set tool discovery after initialization (for dependency injection)."""
        self.tool_discovery = tool_discovery
    
    def simplify_for_intent_classification(self, goal: str) -> Dict:
        """
        Simplify goal for intent classification using semantic matching.
        
        If any tools match the goal semantically → tool_use
        Otherwise → generative
        
        Args:
            goal: User's original goal
        
        Returns:
            {
                "intent": "tool_use|generative",
                "confidence": 0.0-1.0,
                "reasoning": "explanation",
                "simplified_goal": "clearer version of goal",
                "hints": ["tool1", "tool2"]
            }
        """
        if not self.tool_discovery:
            # No semantic search available - return low confidence generative
            return {
                "intent": "generative",
                "confidence": 0.5,
                "reasoning": "No tool discovery available, defaulting to generative",
                "simplified_goal": goal,
                "hints": [],
                "matched_tools": []
            }
        
        # Semantic search for matching tools
        candidates = self.tool_discovery.semantic_search(goal, n_results=3)
        
        if not candidates:
            return {
                "intent": "generative",
                "confidence": 0.7,
                "reasoning": "No tools match this goal semantically",
                "simplified_goal": goal,
                "hints": [],
                "matched_tools": []
            }
        
        # Check semantic distance - lower distance = better match
        # ChromaDB returns cosine distance: 0 = identical, 2 = opposite
        top_match = candidates[0]
        distance = top_match.get('distance', 1.0)
        
        # If top match is close enough, it's a tool_use intent
        # Distance < 0.65 is a good semantic match
        # - 0.5 is too strict: misses "Store my data" → memory_write
        # - 0.8 is too loose: matches "What is Python?" → python_script
        if distance < 0.65:
            tool_names = [c['tool_name'] for c in candidates[:3]]
            domain = top_match.get('domain', 'general')
            
            # Higher confidence for closer matches
            confidence = max(0.6, min(0.95, 1.0 - (distance / 2)))
            
            return {
                "intent": "tool_use",
                "confidence": confidence,
                "reasoning": f"Semantically matches {tool_names[0]} (domain: {domain}, distance: {distance:.2f})",
                "simplified_goal": goal,
                "hints": tool_names,
                "matched_tools": candidates[:3],
                "top_domain": domain
            }
        else:
            # Weak match - probably generative
            return {
                "intent": "generative",
                "confidence": 0.6,
                "reasoning": f"Weak tool matches (distance: {distance:.2f}), likely generative",
                "simplified_goal": goal,
                "hints": [],
                "matched_tools": candidates[:1]
            }
    
    def simplify_for_tool_selection(self, goal: str, all_tools: List[str]) -> Dict:
        """
        Narrow down tool choices using semantic search.
        
        Instead of choosing from 20 tools, give the LLM 3-5 relevant options
        based on SEMANTIC SIMILARITY, not keywords.
        
        Args:
            goal: User's goal
            all_tools: All available tool names (for fallback)
        
        Returns:
            {
                "narrowed_tools": ["tool1", "tool2"],
                "reasoning": "why these tools",
                "explicit_hint": "Clear instruction for LLM",
                "confidence": 0.0-1.0
            }
        """
        if not self.tool_discovery:
            # No semantic search - return all tools
            return {
                "narrowed_tools": all_tools,
                "reasoning": "No tool discovery available, returning all tools",
                "explicit_hint": f"Choose the tool that best matches: '{goal}'",
                "confidence": 0.3,
                "semantic_matches": []
            }
        
        # Semantic search for matching tools
        candidates = self.tool_discovery.semantic_search(goal, n_results=5)
        
        if not candidates:
            return {
                "narrowed_tools": all_tools,
                "reasoning": "No semantic matches found, returning all tools",
                "explicit_hint": f"Choose the tool that best matches: '{goal}'",
                "confidence": 0.3,
                "semantic_matches": []
            }
        
        # Extract tool names that exist in all_tools
        narrowed = []
        for candidate in candidates:
            tool_name = candidate['tool_name']
            if tool_name in all_tools:
                narrowed.append(tool_name)
        
        if not narrowed:
            return {
                "narrowed_tools": all_tools,
                "reasoning": "Semantic matches not in available tools",
                "explicit_hint": f"Choose the tool that best matches: '{goal}'",
                "confidence": 0.3,
                "semantic_matches": candidates
            }
        
        # Generate hint based on semantic match metadata
        top_match = candidates[0]
        hint = self._generate_semantic_hint(goal, narrowed, top_match)
        
        # Confidence based on semantic distance
        distance = top_match.get('distance', 1.0)
        confidence = max(0.5, min(0.95, 1.0 - (distance / 2)))
        
        return {
            "narrowed_tools": narrowed,
            "reasoning": f"Semantic search matched: {', '.join(narrowed)} (top distance: {distance:.2f})",
            "explicit_hint": hint,
            "confidence": confidence,
            "semantic_matches": candidates,
            "top_domain": top_match.get('domain', 'general')
        }
    
    def _generate_semantic_hint(self, goal: str, tools: List[str], top_match: Dict) -> str:
        """
        Generate hint based on semantic match metadata.
        
        Uses tool description and domain from the match, not hardcoded patterns.
        """
        if len(tools) == 1:
            description = top_match.get('description', '')
            return f"Use '{tools[0]}' - {description[:100]}"
        
        domain = top_match.get('domain', 'general')
        
        # Generate domain-aware hint
        if domain == 'memory':
            return f"Memory operation detected. Choose from: {', '.join(tools)}"
        elif domain == 'fitness':
            return f"Fitness/activity request. Choose from: {', '.join(tools)}"
        elif domain == 'math':
            return f"Calculation needed. Choose from: {', '.join(tools)}"
        else:
            return f"Best matches for '{goal[:50]}...': {', '.join(tools)}"
    
    def simplify_for_code_generation(self, goal: str, tool_name: str, tool_definition: Dict) -> Dict:
        """
        Simplify code generation task.
        
        Provide clear template and reduce ambiguity.
        
        Args:
            goal: User's goal
            tool_name: Selected tool name
            tool_definition: Tool definition with parameters
        
        Returns:
            {
                "simplified_goal": "Clear instruction",
                "template_hint": "Code structure to follow",
                "parameter_hints": ["hint1", "hint2"]
            }
        """
        # Extract parameters from goal using regex (simple heuristics are OK here)
        param_hints = []
        
        # Check if name is mentioned
        if "name is" in goal.lower():
            match = re.search(r"name is (\w+)", goal, re.IGNORECASE)
            if match:
                param_hints.append(f"Use name parameter: '{match.group(1)}'")
        
        # Generate template hint
        module_name = tool_definition.get('module_name', f'neural_engine.tools.{tool_name}_tool')
        class_name = tool_definition.get('class_name', f'{tool_name.title().replace("_", "")}Tool')
        
        template_hint = f"""
# Import the tool
from {module_name} import {class_name}

# Create tool instance
tool = {class_name}()

# Execute tool with extracted parameters
result = tool.execute()

# Return result
sandbox.set_result(result)
"""
        
        return {
            "simplified_goal": goal,
            "template_hint": template_hint.strip(),
            "parameter_hints": param_hints,
            "tool_name": tool_name
        }
    
    def get_stats(self) -> Dict:
        """Get statistics about simplifier usage."""
        return {
            "mode": "semantic" if self.tool_discovery else "fallback",
            "tool_discovery_available": self.tool_discovery is not None,
            "description": "Uses semantic embeddings for tool matching"
        }
