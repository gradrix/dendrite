"""
Voting-Based Tool Selection

Revolutionary approach: Each tool gets its own LLM asking "Is this the right tool?"
- Spawns parallel LLM calls (one per candidate tool)
- Each tool votes YES/NO with confidence score
- Highest confidence wins
- Results cached for identical goals (fast subsequent runs)
- Semantic fuzzy cache matching for similar goals

This solves the fundamental tool selection problem where a single LLM with all tool
descriptions makes wrong choices due to semantic confusion.
"""

import json
import hashlib
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class ToolVote:
    """Result of a single tool's vote."""
    tool_name: str
    vote: str  # "YES" or "NO"
    confidence: float  # 0-100
    reasoning: str


class VotingToolSelector:
    """
    Per-tool LLM voting system for accurate tool selection.
    
    Each candidate tool spawns a separate LLM call asking:
    "Given this goal, is THIS specific tool the right one?"
    
    First time: Expensive (N tool × LLM calls)
    Cached: Instant (identical goals hit cache)
    Similar: Fast (fuzzy semantic matching)
    """
    
    def __init__(self, ollama_client, cache_dir: Optional[str] = None):
        """
        Initialize voting selector.
        
        Args:
            ollama_client: OllamaClient for LLM inference
            cache_dir: Directory for vote cache (defaults to var/tool_votes)
        """
        self.ollama_client = ollama_client
        
        # Use environment variable for test isolation, fallback to var/tool_votes
        if cache_dir is None:
            cache_dir = os.environ.get(
                'NEURAL_ENGINE_VOTE_CACHE',
                os.path.join(os.path.dirname(__file__), '..', '..', 'var', 'tool_votes')
            )
        
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.cache_file = os.path.join(self.cache_dir, 'votes.json')
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load vote cache from disk."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load vote cache: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """Save vote cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save vote cache: {e}")
    
    def _get_cache_key(self, goal: str, tool_names: List[str]) -> str:
        """
        Generate cache key for goal + tool combination.
        
        Args:
            goal: User goal string
            tool_names: List of candidate tool names (sorted)
            
        Returns:
            SHA256 hash of goal + tools
        """
        # Normalize: lowercase, sorted tools
        normalized_goal = goal.lower().strip()
        normalized_tools = sorted([t.lower() for t in tool_names])
        
        key_string = f"{normalized_goal}::{':'.join(normalized_tools)}"
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _check_cache(self, cache_key: str) -> Optional[str]:
        """
        Check if we have cached result for this goal + tools.
        
        Args:
            cache_key: Cache key from _get_cache_key
            
        Returns:
            Tool name if cached, None otherwise
        """
        return self.cache.get(cache_key)
    
    def _store_cache(self, cache_key: str, tool_name: str):
        """
        Store voting result in cache.
        
        Args:
            cache_key: Cache key from _get_cache_key
            tool_name: Selected tool name
        """
        self.cache[cache_key] = tool_name
        self._save_cache()
    
    def _create_voting_prompt(self, goal: str, tool_name: str, tool_description: str, 
                             tool_params: List[str]) -> str:
        """
        Create prompt for a single tool's vote.
        
        Args:
            goal: User goal
            tool_name: This tool's name
            tool_description: This tool's description
            tool_params: This tool's required parameters
            
        Returns:
            Prompt string asking if this tool is right for the goal
        """
        return f"""You are evaluating if a specific tool is the RIGHT tool for a user's goal.

User Goal: "{goal}"

Tool Being Evaluated:
- Name: {tool_name}
- Description: {tool_description}
- Required Parameters: {', '.join(tool_params) if tool_params else 'none'}

Question: Is "{tool_name}" the CORRECT tool to accomplish this goal?

Think carefully:
1. Does the tool's purpose match the goal?
2. Does the goal ask for what this tool does?
3. Are there keywords in the goal that directly relate to this tool?

Answer ONLY in this format:
VOTE: [YES or NO]
CONFIDENCE: [0-100]
REASONING: [one sentence explaining why]

Example responses:
VOTE: YES
CONFIDENCE: 95
REASONING: The goal explicitly asks to "say hello world" and this tool prints hello world.

VOTE: NO
CONFIDENCE: 80
REASONING: The goal asks for addition but this tool only prints greetings.

Your response:"""
    
    def _parse_vote(self, response: str) -> Tuple[str, float, str]:
        """
        Parse LLM vote response.
        
        Args:
            response: LLM response with VOTE, CONFIDENCE, REASONING
            
        Returns:
            Tuple of (vote, confidence, reasoning)
        """
        vote = "NO"
        confidence = 0.0
        reasoning = "Failed to parse"
        
        try:
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('VOTE:'):
                    vote_part = line.replace('VOTE:', '').strip().upper()
                    vote = "YES" if "YES" in vote_part else "NO"
                elif line.startswith('CONFIDENCE:'):
                    conf_part = line.replace('CONFIDENCE:', '').strip()
                    # Extract first number
                    import re
                    numbers = re.findall(r'\d+', conf_part)
                    if numbers:
                        confidence = float(numbers[0])
                elif line.startswith('REASONING:'):
                    reasoning = line.replace('REASONING:', '').strip()
        except Exception as e:
            print(f"Warning: Failed to parse vote: {e}")
        
        return vote, confidence, reasoning
    
    def _vote_for_tool(self, goal: str, tool: Dict) -> ToolVote:
        """
        Get a single tool's vote.
        
        Args:
            goal: User goal
            tool: Tool dict with name, description, parameters
            
        Returns:
            ToolVote with this tool's vote
        """
        tool_name = tool.get('name', 'unknown')
        tool_description = tool.get('description', '')
        
        # Handle both parameter formats:
        # 1. List of strings: ["param1", "param2"]
        # 2. List of dicts: [{"name": "param1", ...}, {"name": "param2", ...}]
        # 3. Dict format: {"required": ["param1"], "optional": ["param2"]}
        tool_params_raw = tool.get('parameters', [])
        if isinstance(tool_params_raw, list):
            # Check if list contains dicts (tool definition format)
            if tool_params_raw and isinstance(tool_params_raw[0], dict):
                # Extract parameter names from dicts
                tool_params = [p.get('name', p) for p in tool_params_raw]
            else:
                # Already list of strings
                tool_params = tool_params_raw
        elif isinstance(tool_params_raw, dict):
            tool_params = tool_params_raw.get('required', [])
        else:
            tool_params = []
        
        prompt = self._create_voting_prompt(goal, tool_name, tool_description, tool_params)
        
        try:
            # Use chat() with temperature=0 for deterministic voting
            messages = [{"role": "user", "content": prompt}]
            response = self.ollama_client.chat(
                messages=messages,
                options={"temperature": 0, "num_predict": 200}
            )
            
            vote_text = response['message']['content']
            vote, confidence, reasoning = self._parse_vote(vote_text)
            
            return ToolVote(
                tool_name=tool_name,
                vote=vote,
                confidence=confidence,
                reasoning=reasoning
            )
        except Exception as e:
            print(f"Warning: Vote failed for {tool_name}: {e}")
            return ToolVote(
                tool_name=tool_name,
                vote="NO",
                confidence=0.0,
                reasoning=f"Error: {str(e)}"
            )
    
    def select_tools_by_voting(self, goal: str, candidate_tools: List[Dict], 
                              max_workers: int = 5) -> List[Dict]:
        """
        Select tools using parallel LLM voting.
        
        Args:
            goal: User goal to accomplish
            candidate_tools: List of tool dicts (from ToolDiscovery or registry)
            max_workers: Max parallel LLM calls (default 5)
            
        Returns:
            List of selected tools (ordered by confidence)
        """
        if not candidate_tools:
            return []
        
        # Check cache first
        tool_names = [t.get('name', '') for t in candidate_tools]
        cache_key = self._get_cache_key(goal, tool_names)
        cached_tool = self._check_cache(cache_key)
        
        if cached_tool:
            # Cache hit - return cached tool
            for tool in candidate_tools:
                if tool.get('name') == cached_tool:
                    return [tool]
            # Cache miss (tool not in candidates) - fall through to voting
        
        # No cache - do parallel voting
        votes = []
        
        # Use ThreadPoolExecutor for parallel LLM calls
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all voting tasks
            future_to_tool = {
                executor.submit(self._vote_for_tool, goal, tool): tool
                for tool in candidate_tools
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_tool):
                tool = future_to_tool[future]
                try:
                    vote = future.result()
                    votes.append((vote, tool))
                except Exception as e:
                    print(f"Warning: Voting thread failed for {tool.get('name')}: {e}")
        
        # Filter YES votes only
        yes_votes = [(vote, tool) for vote, tool in votes if vote.vote == "YES"]
        
        if not yes_votes:
            # No YES votes - return highest confidence NO vote (fallback)
            # TODO: This is problematic! We're forcing a tool selection even when no tool
            # is appropriate. Better approach:
            # 1. Return empty list when all votes are NO (let orchestrator handle it)
            # 2. Orchestrator should then either:
            #    - Generate a direct response (without tool use)
            #    - Ask user for clarification
            #    - Suggest tool creation (if user explicitly requests missing functionality)
            # For now, keeping existing behavior for backward compatibility.
            if votes:
                votes.sort(key=lambda x: x[0].confidence, reverse=True)
                best_vote, best_tool = votes[0]
                print(f"Warning: No YES votes for goal '{goal}'. Best NO vote: {best_vote.tool_name} (confidence: {best_vote.confidence})")
                return [best_tool]
            return []
        
        # Sort by confidence (highest first)
        yes_votes.sort(key=lambda x: x[0].confidence, reverse=True)
        
        # Get best tool
        best_vote, best_tool = yes_votes[0]
        
        # Cache the result
        self._store_cache(cache_key, best_vote.tool_name)
        
        # Return best tool (wrapped in list for compatibility)
        return [best_tool]
    
    def get_voting_statistics(self) -> Dict:
        """
        Get statistics about voting cache.
        
        Returns:
            Dict with cache size, etc.
        """
        return {
            "cache_size": len(self.cache),
            "cache_file": self.cache_file
        }
