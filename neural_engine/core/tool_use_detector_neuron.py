"""
Tool Use Detector Neuron - Binary classifier for tool usage detection.

This is a specialized neuron that answers ONE question:
"Does this goal require using external tools?"

Part of multi-neuron voting architecture for intent classification.
"""

from typing import Dict


class ToolUseDetectorNeuron:
    """
    Specialized neuron that detects if a goal requires tool usage.
    
    Returns a confidence score (0.0 to 1.0) that the goal needs tools.
    """
    
    def __init__(self, ollama_client):
        self.ollama_client = ollama_client
        self.prompt_template = """You are a tool usage detector. Answer with ONLY a single word: YES or NO.

Question: Does this goal require using external tools, APIs, stored data, or external actions?

Examples that need tools (YES):
- "What time is it?" - needs time API
- "What is my name?" - needs to read stored memory
- "Remember my email is..." - needs to write to storage
- "Show my Strava activities" - needs Strava API
- "Calculate 5+3" - needs calculator tool

Examples that DON'T need tools (NO):
- "Tell me a joke" - can be answered conversationally
- "Explain quantum physics" - general knowledge
- "Write a poem" - creative generation

Goal: {goal}

Answer (YES or NO):"""
    
    def detect(self, goal: str) -> Dict[str, float]:
        """
        Detect if goal needs tools.
        
        Returns:
            {"needs_tools": confidence_score}
            confidence_score: 0.0 (definitely NO) to 1.0 (definitely YES)
        """
        prompt = self.prompt_template.format(goal=goal)
        
        response = self.ollama_client.client.generate(
            model=self.ollama_client.model,
            prompt=prompt,
            options={"temperature": 0}
        )
        
        answer = response['response'].strip().upper()
        
        # Convert YES/NO to confidence score
        if "YES" in answer:
            confidence = 0.95
        elif "NO" in answer:
            confidence = 0.05
        else:
            # Uncertain - default to needs tools (safer)
            confidence = 0.60
        
        return {
            "needs_tools": confidence,
            "raw_answer": answer
        }
