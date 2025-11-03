"""
Memory Operation Detector Neuron - Detects memory read/write operations.

This is a specialized neuron that answers ONE question:
"Is this goal about storing or retrieving information?"

Part of multi-neuron voting architecture for intent classification.
"""

from typing import Dict


class MemoryOperationDetectorNeuron:
    """
    Specialized neuron that detects if a goal involves memory operations.
    
    Returns confidence scores for read, write, or neither.
    """
    
    def __init__(self, ollama_client):
        self.ollama_client = ollama_client
        self.prompt_template = """You are a memory operation detector. Answer with ONLY one word: READ, WRITE, or NEITHER.

Question: Is this goal about accessing USER'S PERSONAL STORED DATA (not general knowledge)?

WRITE examples (storing user's personal info):
- "Remember my name is Alice" → WRITE (storing user's name)
- "Store my email address" → WRITE
- "Save this for later" → WRITE
- "My favorite color is blue" → WRITE (storing preference)

READ examples (retrieving user's personal stored info):
- "What is my name?" → READ (needs user's stored name)
- "What did I tell you about my email?" → READ
- "Recall my preferences" → READ
- "What is my favorite color?" → READ (needs user's stored preference)

NEITHER examples (general knowledge or other operations):
- "Tell me a joke" → NEITHER (no personal data needed)
- "What time is it?" → NEITHER (external API, not stored data)
- "Calculate 5+3" → NEITHER (math, not memory)
- "What is Python?" → NEITHER (general knowledge, not user data)
- "Explain Docker" → NEITHER (general knowledge)

Goal: {goal}

Answer (READ, WRITE, or NEITHER):"""
    
    def detect(self, goal: str) -> Dict[str, float]:
        """
        Detect if goal involves memory operations.
        
        Returns:
            {"is_memory_read": score, "is_memory_write": score}
            Each score: 0.0 to 1.0
        """
        prompt = self.prompt_template.format(goal=goal)
        
        response = self.ollama_client.client.generate(
            model=self.ollama_client.model,
            prompt=prompt,
            options={"temperature": 0}
        )
        
        answer = response['response'].strip().upper()
        
        # Convert answer to confidence scores
        if "WRITE" in answer:
            return {
                "is_memory_read": 0.05,
                "is_memory_write": 0.95,
                "raw_answer": answer
            }
        elif "READ" in answer:
            return {
                "is_memory_read": 0.95,
                "is_memory_write": 0.05,
                "raw_answer": answer
            }
        else:  # NEITHER or uncertain
            return {
                "is_memory_read": 0.05,
                "is_memory_write": 0.05,
                "raw_answer": answer
            }
