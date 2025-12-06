"""
Overseer Neuron: High-level decision maker and task decomposer.

This neuron uses a more capable LLM (or the same model with better prompting) to:
1. Understand user intent deeply
2. Classify request type accurately  
3. Break down complex goals into simpler subtasks
4. Delegate to specialized smaller LLMs for execution

Architecture Pattern:
- Overseer (larger/better model): Strategic decisions, planning, decomposition
- Worker neurons (smaller models): Execute specific well-defined tasks

This is more effective than having a small model try to do everything.
"""

import json
from typing import Dict, List, Optional, TYPE_CHECKING
from neural_engine.core.ollama_client import OllamaClient

if TYPE_CHECKING:
    from neural_engine.core.tool_discovery import ToolDiscovery


class OverseerNeuron:
    """
    Overseer LLM that makes high-level decisions and decomposes tasks.
    
    Can use a different (larger) model than worker neurons for better reasoning.
    Uses semantic tool discovery for intelligent fallback classification.
    """
    
    def __init__(self, 
                 ollama_client: OllamaClient,
                 overseer_model: Optional[str] = None,
                 tool_discovery: Optional['ToolDiscovery'] = None):
        """
        Initialize Overseer Neuron.
        
        Args:
            ollama_client: Client for LLM communication
            overseer_model: Optional specific model for overseer (e.g., "mistral", "llama2:13b")
                          If None, uses same model as workers
            tool_discovery: Optional ToolDiscovery for semantic classification
        """
        self.ollama_client = ollama_client
        self.overseer_model = overseer_model
        self.tool_discovery = tool_discovery
        
        # Track overseer decisions for analysis
        self.decision_history = []
    
    def set_tool_discovery(self, tool_discovery: 'ToolDiscovery'):
        """Set tool discovery after initialization."""
        self.tool_discovery = tool_discovery
    
    def classify_intent(self, goal: str) -> Dict:
        """
        Classify user intent with better accuracy than worker neurons.
        
        Args:
            goal: User's goal/request
        
        Returns:
            {
                "intent": "tool_use|generative|decompose",
                "confidence": 0.0-1.0,
                "reasoning": "why this classification",
                "suggested_approach": "how to handle this"
            }
        """
        prompt = f"""You are an expert AI overseer that understands user intent deeply.

Analyze this user goal and classify it accurately:

**Goal**: "{goal}"

**Classification Options**:

1. **tool_use**: Goal requires specific external tools or actions
   - Examples: "what time is it", "check my activities", "calculate 5+3", "save my name"
   - Key indicators: Needs real-time data, external APIs, computation, storage

2. **generative**: Goal is conversational/creative, no tools needed
   - Examples: "tell me a joke", "explain quantum physics", "write a poem"
   - Key indicators: Information already in training data, creative tasks

3. **decompose**: Goal is complex and should be broken into subtasks
   - Examples: "analyze my fitness and give recommendations"
   - Key indicators: Multiple steps, requires coordination

**Important Classification Rules**:
- "say hello" / "greet" → generative (simple response, no tool needed)
- "store X" / "remember X" → tool_use (needs storage tool)
- "what did I tell you" / "recall X" → tool_use (needs retrieval tool)
- "current time" / "weather" → tool_use (needs real-time data)

Respond in JSON:
{{
    "intent": "tool_use",
    "confidence": 0.95,
    "reasoning": "Goal requires [specific capability]",
    "suggested_approach": "Use [specific tool type] to [action]",
    "keywords_detected": ["list", "of", "keywords"]
}}"""

        # Use overseer model if specified, otherwise default
        model = self.overseer_model or self.ollama_client.model
        response = self.ollama_client.generate(prompt=prompt, model=model)
        
        try:
            # Extract JSON from response
            json_str = response.get('response', response) if isinstance(response, dict) else response
            json_str = str(json_str).strip()
            
            # Clean markdown formatting
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            
            # Validate and add metadata
            result["goal"] = goal
            result["overseer_model"] = model
            
            # Track decision
            self.decision_history.append(result)
            
            return result
            
        except Exception as e:
            print(f"⚠️  Overseer failed to parse response: {e}")
            # Fallback to heuristic classification
            return self._fallback_classification(goal)
    
    def _fallback_classification(self, goal: str) -> Dict:
        """
        Semantic-based fallback classification when LLM fails.
        
        Uses tool discovery to determine if any tools match the goal semantically.
        If yes → tool_use. If no → generative.
        
        NO MORE HARDCODED KEYWORDS!
        """
        # Try semantic tool discovery first
        if self.tool_discovery:
            candidates = self.tool_discovery.semantic_search(goal, n_results=3)
            
            if candidates:
                top_match = candidates[0]
                distance = top_match.get('distance', 1.0)
                
                # Good semantic match → tool_use
                if distance < 0.7:
                    return {
                        "intent": "tool_use",
                        "confidence": max(0.6, 1.0 - distance),
                        "reasoning": f"Semantically matches {top_match['tool_name']} (distance: {distance:.2f})",
                        "suggested_approach": f"Use {top_match['tool_name']} tool",
                        "matched_tools": [c['tool_name'] for c in candidates[:3]],
                        "goal": goal,
                        "overseer_model": "semantic_fallback"
                    }
                
                # Weak match → still might be tool_use for certain domains
                domain = top_match.get('domain', 'general')
                if domain in ['memory', 'fitness', 'math'] and distance < 1.0:
                    return {
                        "intent": "tool_use",
                        "confidence": 0.6,
                        "reasoning": f"Domain '{domain}' detected with weak match",
                        "suggested_approach": f"Try {top_match['tool_name']} tool",
                        "matched_tools": [c['tool_name'] for c in candidates[:3]],
                        "goal": goal,
                        "overseer_model": "semantic_fallback"
                    }
        
        # No tool discovery or no matches - default to generative
        return {
            "intent": "generative",
            "confidence": 0.5,
            "reasoning": "No semantic tool matches, defaulting to generative",
            "suggested_approach": "Generate direct response",
            "matched_tools": [],
            "goal": goal,
            "overseer_model": "semantic_fallback"
        }
    
    def decompose_goal(self, goal: str) -> Dict:
        """
        Break down complex goal into simpler subtasks.
        
        Args:
            goal: Complex user goal
        
        Returns:
            {
                "original_goal": "...",
                "subtasks": [
                    {"step": 1, "task": "...", "type": "tool_use|generative"},
                    ...
                ],
                "execution_order": "sequential|parallel"
            }
        """
        prompt = f"""You are an expert task decomposer.

Break down this complex goal into simple, executable subtasks:

**Goal**: "{goal}"

Each subtask should be:
1. Simple enough for a small LLM to handle
2. Clearly typed (tool_use or generative)
3. Executable independently where possible

Respond in JSON:
{{
    "original_goal": "{goal}",
    "subtasks": [
        {{
            "step": 1,
            "task": "Specific simple task",
            "type": "tool_use",
            "required_tool": "tool_name or null",
            "depends_on": []
        }}
    ],
    "execution_order": "sequential"
}}"""

        model = self.overseer_model or self.ollama_client.model
        response = self.ollama_client.generate(prompt=prompt, model=model)
        
        try:
            json_str = response.get('response', response) if isinstance(response, dict) else response
            json_str = str(json_str).strip()
            
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            result["overseer_model"] = model
            
            return result
            
        except Exception as e:
            print(f"⚠️  Overseer failed to decompose goal: {e}")
            # Return single task as fallback
            return {
                "original_goal": goal,
                "subtasks": [{"step": 1, "task": goal, "type": "generative", "required_tool": None, "depends_on": []}],
                "execution_order": "sequential",
                "overseer_model": "fallback"
            }
    
    def select_tool_category(self, goal: str, available_tools: List[str]) -> Dict:
        """
        High-level tool category selection (helps smaller LLMs).
        
        Instead of choosing from 20+ specific tools, overseer identifies the
        category (memory, calculation, external_api, etc.) to narrow choices.
        
        Args:
            goal: User's goal
            available_tools: List of all available tool names
        
        Returns:
            {
                "category": "memory|calculation|external_api|greeting|other",
                "reasoning": "why this category",
                "suggested_tools": ["tool1", "tool2"],
                "confidence": 0.0-1.0
            }
        """
        # Categorize tools
        tool_categories = {
            "memory": [t for t in available_tools if "memory" in t],
            "calculation": [t for t in available_tools if any(x in t for x in ["add", "calculator", "compute"])],
            "external_api": [t for t in available_tools if "strava" in t or "api" in t],
            "greeting": [t for t in available_tools if "hello" in t or "greet" in t],
            "analysis": [t for t in available_tools if "analyze" in t or "performance" in t],
            "script": [t for t in available_tools if "script" in t or "python" in t],
        }
        
        prompt = f"""You are an expert at categorizing tasks and selecting appropriate tool types.

**Goal**: "{goal}"

**Available Tool Categories**:
{json.dumps({k: len(v) for k, v in tool_categories.items()}, indent=2)}

Which category of tools would best serve this goal?

Respond in JSON:
{{
    "category": "memory",
    "reasoning": "Goal involves storing/retrieving data",
    "confidence": 0.95
}}"""

        model = self.overseer_model or self.ollama_client.model
        response = self.ollama_client.generate(prompt=prompt, model=model)
        
        try:
            json_str = response.get('response', response) if isinstance(response, dict) else response
            json_str = str(json_str).strip()
            
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            
            # Add suggested tools from category
            category = result.get("category", "other")
            result["suggested_tools"] = tool_categories.get(category, [])
            result["overseer_model"] = model
            
            return result
            
        except Exception as e:
            print(f"⚠️  Overseer failed to select category: {e}")
            # Fallback to all tools
            return {
                "category": "other",
                "reasoning": "fallback",
                "suggested_tools": available_tools,
                "confidence": 0.3,
                "overseer_model": "fallback"
            }
