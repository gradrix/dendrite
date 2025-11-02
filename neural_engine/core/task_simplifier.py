"""
Task Simplifier: Helps small LLMs by breaking down and clarifying tasks.

Instead of requiring a bigger model, this uses the SAME small model but:
1. Pre-processes goals to extract key information
2. Narrows down tool choices to relevant subset (5 instead of 20)
3. Provides explicit hints based on keywords
4. Reformulates ambiguous goals into clear instructions

Key Insight: Small LLM + Simple Task = Success
"""

import json
import re
from typing import Dict, List, Optional


class TaskSimplifier:
    """
    Makes tasks easier for small LLMs by pre-processing and clarifying.
    
    Uses the SAME model, just with better prepared inputs.
    """
    
    def __init__(self):
        """Initialize task simplifier with keyword mappings."""
        
        # Map keywords to specific tool categories
        self.keyword_to_tools = {
            # Greetings
            "hello": ["hello_world"],
            "hi": ["hello_world"],
            "greet": ["hello_world"],
            "say hello": ["hello_world"],
            
            # Memory operations
            "store": ["memory_write"],
            "save": ["memory_write"],
            "remember me": ["memory_write"],  # "remember" alone is ambiguous
            "remember that": ["memory_write"],
            "write": ["memory_write"],
            "record": ["memory_write"],
            
            "recall": ["memory_read"],
            "retrieve": ["memory_read"],
            "what did i": ["memory_read"],
            "remember what": ["memory_read"],  # "remember what..." is retrieval
            "tell me what": ["memory_read"],
            "get": ["memory_read"],
            
            # Calculations
            "add": ["addition", "add_numbers"],
            "sum": ["addition", "add_numbers"],
            "calculate": ["addition", "add_numbers", "buggy_calculator"],
            "compute": ["addition", "add_numbers"],
            
            # Strava/Activities
            "strava": ["strava_get_my_activities", "strava_get_activity_kudos", "strava_get_dashboard_feed"],
            "activity": ["strava_get_my_activities", "strava_get_activity_kudos"],
            "activities": ["strava_get_my_activities"],
            "kudos": ["strava_get_activity_kudos", "strava_give_kudos"],
            
            # Scripts
            "script": ["python_script"],
            "python": ["python_script"],
            "execute": ["python_script"],
            
            # Analysis
            "analyze": ["analyze_tool_performance"],
            "performance": ["analyze_tool_performance"],
            
            # Prime numbers
            "prime": ["prime_checker"],
        }
    
    def simplify_for_intent_classification(self, goal: str) -> Dict:
        """
        Simplify goal for intent classification.
        
        Returns clear intent with high confidence based on keywords.
        
        Args:
            goal: User's original goal
        
        Returns:
            {
                "intent": "tool_use|generative",
                "confidence": 0.0-1.0,
                "reasoning": "explanation",
                "simplified_goal": "clearer version of goal",
                "hints": ["keyword1", "keyword2"]
            }
        """
        goal_lower = goal.lower()
        hints = []
        
        # Check for tool use indicators
        tool_indicators = [
            ("store", "memory_write", 0.95),
            ("save", "memory_write", 0.95),
            ("remember", "memory_write", 0.95),
            ("recall", "memory_read", 0.95),
            ("what did i", "memory_read", 0.95),
            ("retrieve", "memory_read", 0.90),
            ("time", "time_tool", 0.95),
            ("date", "date_tool", 0.95),
            ("weather", "weather_tool", 0.95),
            ("activity", "strava", 0.90),
            ("strava", "strava", 0.95),
            ("add", "calculation", 0.85),
            ("calculate", "calculation", 0.90),
            ("prime", "prime_checker", 0.95),
        ]
        
        for keyword, tool_hint, confidence in tool_indicators:
            if keyword in goal_lower:
                hints.append(tool_hint)
                return {
                    "intent": "tool_use",
                    "confidence": confidence,
                    "reasoning": f"Keyword '{keyword}' indicates {tool_hint} tool needed",
                    "simplified_goal": goal,
                    "hints": hints,
                    "keyword_matched": keyword
                }
        
        # Check for generative indicators
        generative_indicators = [
            ("hello", 0.95),
            ("hi", 0.95),
            ("greet", 0.90),
            ("joke", 0.95),
            ("story", 0.95),
            ("poem", 0.95),
            ("explain", 0.85),
            ("what is", 0.80),
            ("tell me about", 0.75),
        ]
        
        for keyword, confidence in generative_indicators:
            if keyword in goal_lower:
                return {
                    "intent": "generative",
                    "confidence": confidence,
                    "reasoning": f"Keyword '{keyword}' indicates conversational/creative request",
                    "simplified_goal": goal,
                    "hints": [keyword],
                    "keyword_matched": keyword
                }
        
        # Default to generative with low confidence
        return {
            "intent": "generative",
            "confidence": 0.5,
            "reasoning": "No clear tool indicators, defaulting to generative",
            "simplified_goal": goal,
            "hints": [],
            "keyword_matched": None
        }
    
    def simplify_for_tool_selection(self, goal: str, all_tools: List[str]) -> Dict:
        """
        Narrow down tool choices for small LLM.
        
        Instead of choosing from 20 tools, give it 2-5 relevant options.
        
        Args:
            goal: User's goal
            all_tools: All available tool names
        
        Returns:
            {
                "narrowed_tools": ["tool1", "tool2"],
                "reasoning": "why these tools",
                "explicit_hint": "Clear instruction for LLM",
                "confidence": 0.0-1.0
            }
        """
        goal_lower = goal.lower()
        narrowed = set()
        matched_keywords = []
        
        # Check keywords and collect relevant tools
        for keyword, tools in self.keyword_to_tools.items():
            if keyword in goal_lower:
                matched_keywords.append(keyword)
                for tool in tools:
                    if tool in all_tools:
                        narrowed.add(tool)
        
        if narrowed:
            narrowed_list = list(narrowed)
            return {
                "narrowed_tools": narrowed_list,
                "reasoning": f"Keywords {matched_keywords} match these tools",
                "explicit_hint": self._generate_tool_hint(goal, narrowed_list, matched_keywords),
                "confidence": 0.9,
                "keywords_matched": matched_keywords
            }
        
        # No keywords matched - return all tools but with warning
        return {
            "narrowed_tools": all_tools,
            "reasoning": "No specific keywords detected, showing all tools",
            "explicit_hint": f"Choose the tool that best matches: '{goal}'",
            "confidence": 0.3,
            "keywords_matched": []
        }
    
    def _generate_tool_hint(self, goal: str, tools: List[str], keywords: List[str]) -> str:
        """
        Generate explicit hint for tool selection.
        
        Makes it crystal clear which tool to use.
        """
        if len(tools) == 1:
            return f"Use '{tools[0]}' tool for this task."
        
        # Create hint based on keywords
        if "hello" in keywords or "greet" in keywords:
            return "This is a greeting request. Use 'hello_world' tool."
        
        if any(kw in keywords for kw in ["store", "save", "remember"]):
            return "This is a storage request. Use 'memory_write' tool to save data."
        
        if any(kw in keywords for kw in ["recall", "what did i", "retrieve"]):
            return "This is a retrieval request. Use 'memory_read' tool to get saved data."
        
        if any(kw in keywords for kw in ["add", "calculate", "sum"]):
            return "This is a calculation request. Use 'addition' or 'add_numbers' tool."
        
        if "strava" in keywords or "activity" in keywords:
            return "This is about Strava activities. Use a strava_* tool."
        
        if "prime" in keywords:
            return "This is about prime numbers. Use 'prime_checker' tool."
        
        # Generic hint
        return f"Choose from: {', '.join(tools)}"
    
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
        # Extract parameters from goal
        param_hints = []
        
        # Check if parameters are mentioned in goal
        if "name is" in goal.lower():
            match = re.search(r"name is (\w+)", goal, re.IGNORECASE)
            if match:
                param_hints.append(f"Use name parameter: '{match.group(1)}'")
        
        # Generate template hint
        template_hint = f"""
# Import the tool
from neural_engine.tools.{tool_definition.get('module_name', '')} import {tool_definition.get('class_name', '')}

# Create tool instance
tool = {tool_definition.get('class_name', '')}()

# Execute tool
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
            "total_tool_mappings": len(self.keyword_to_tools),
            "total_keywords": sum(1 for keywords in self.keyword_to_tools.keys()),
            "mapped_tools": len(set(tool for tools in self.keyword_to_tools.values() for tool in tools))
        }
