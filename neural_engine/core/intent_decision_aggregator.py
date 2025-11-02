"""
Intent Decision Aggregator - Democratic voting system for intent classification.

Takes votes from multiple specialized detector neurons and makes final decision.
Like a parliament - each specialist gets a vote, and we count them democratically.
"""

from typing import Dict, List


class IntentDecisionAggregator:
    """
    Aggregates votes from multiple detector neurons to decide final intent.
    
    Architecture:
    - Multiple specialized neurons vote
    - Each vote has a confidence weight
    - Final decision based on weighted voting
    - No single neuron has absolute power (democratic)
    """
    
    def __init__(self):
        # Voting thresholds
        self.tool_use_threshold = 0.6  # If tool_use confidence > 0.6, it's tool_use
        self.memory_threshold = 0.7    # If memory confidence > 0.7, prioritize memory
    
    def aggregate(self, votes: Dict[str, Dict]) -> str:
        """
        Aggregate votes from detector neurons and decide final intent.
        
        Args:
            votes: Dict of detector results, e.g.:
                {
                    "tool_use_detector": {"needs_tools": 0.95},
                    "memory_detector": {"is_memory_read": 0.95, "is_memory_write": 0.05},
                }
        
        Returns:
            "tool_use" or "generative"
        
        Decision Logic:
        1. If tool_use_detector says NO (< 0.4) → generative
        2. If memory_detector says YES (> 0.7) → tool_use (memory is always tool use)
        3. If tool_use_detector says YES (> 0.6) → tool_use
        4. Otherwise → generative (default safe choice)
        """
        # Extract votes
        tool_use_vote = votes.get("tool_use_detector", {}).get("needs_tools", 0.5)
        memory_read_vote = votes.get("memory_detector", {}).get("is_memory_read", 0.0)
        memory_write_vote = votes.get("memory_detector", {}).get("is_memory_write", 0.0)
        
        # Calculate aggregate scores
        memory_score = max(memory_read_vote, memory_write_vote)
        
        # Decision tree (order matters - most specific first)
        
        # 1. Strong memory signal → always tool_use
        if memory_score > self.memory_threshold:
            return "tool_use"
        
        # 2. Strong tool_use signal → tool_use
        if tool_use_vote > self.tool_use_threshold:
            return "tool_use"
        
        # 3. Weak tool_use signal (< 0.4) → generative
        if tool_use_vote < 0.4:
            return "generative"
        
        # 4. Ambiguous case - default to generative
        # (Conversational response is safer than wrong tool call)
        return "generative"
    
    def get_explanation(self, votes: Dict[str, Dict], decision: str) -> str:
        """
        Generate human-readable explanation of decision.
        
        Useful for debugging and understanding why a decision was made.
        """
        tool_use_vote = votes.get("tool_use_detector", {}).get("needs_tools", 0.5)
        memory_read_vote = votes.get("memory_detector", {}).get("is_memory_read", 0.0)
        memory_write_vote = votes.get("memory_detector", {}).get("is_memory_write", 0.0)
        
        explanation = f"Decision: {decision}\n"
        explanation += f"  Tool Use Detector: {tool_use_vote:.2f}\n"
        explanation += f"  Memory Read: {memory_read_vote:.2f}\n"
        explanation += f"  Memory Write: {memory_write_vote:.2f}\n"
        
        return explanation
