"""
Memory Operations Specialist - Expert in memory read/write distinction.

This specialized classifier focuses ONLY on memory operations,
achieving higher accuracy than the general classifier.
"""

from typing import Dict
from .neuron import BaseNeuron


class MemoryOperationsSpecialist(BaseNeuron):
    """
    Specialist for memory operations.
    
    Distinguishes between:
    - memory_write: Storing information
    - memory_read: Retrieving information
    """
    
    def __init__(self, message_bus, ollama_client):
        super().__init__(message_bus, ollama_client)
    
    def classify_memory_operation(self, goal: str) -> str:
        """
        Classify memory operation type.
        
        Args:
            goal: User goal text
        
        Returns:
            "write" or "read"
        """
        # Build focused prompt for memory operations
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a memory operations expert. Classify user requests as either:\n"
                    "- 'write' (storing, saving, remembering NEW information)\n"
                    "- 'read' (retrieving, recalling, asking WHAT was stored)\n\n"
                    "Key distinctions:\n"
                    "- Questions (What? Tell me? Recall?) → read\n"
                    "- Commands to store (Remember that X, Save Y) → write\n"
                    "- Past tense recall (what I told you, what you know) → read\n\n"
                    "Examples:\n"
                    "User: Remember that my name is Alice\n"
                    "Assistant: write\n\n"
                    "User: What is my name?\n"
                    "Assistant: read\n\n"
                    "User: Remember what I told you about my favorite color\n"
                    "Assistant: read\n\n"
                    "User: Store the value 42 for key 'answer'\n"
                    "Assistant: write\n\n"
                    "User: Recall what I told you about my birthday\n"
                    "Assistant: read\n\n"
                    "User: What did I tell you?\n"
                    "Assistant: read\n\n"
                    "Respond with ONLY 'write' or 'read'."
                )
            },
            {"role": "user", "content": goal}
        ]
        
        response = self.ollama_client.chat(messages)
        operation = response['message']['content'].strip().lower()
        
        # Fallback: analyze keywords FIRST before trusting LLM response
        goal_lower = goal.lower()
        
        # Strongest WRITE signals - statements of fact with "my X is Y" pattern
        if any(p in goal_lower for p in ["my name is", "my favorite", "i am", "i'm from", "i like", "i live", "actually"]):
            # Check if it's a question (would be read)
            if not any(q in goal_lower for q in ["what", "who", "when", "where", "why", "how", "tell me", "?", "recall"]):
                return "write"
        
        # Strongest READ signals - past tense recall patterns
        if any(p in goal_lower for p in ["what i told", "what i said", "what you know", "told you about", "said earlier", "remember what"]):
            return "read"
        
        # Question words strongly indicate read
        if any(q in goal_lower for q in ["what is", "who is", "when did", "where is", "why did", "how did", "tell me", "show me", "recall"]):
            return "read"
        
        # Validate and clean LLM response
        if "write" in operation or "stor" in operation or "save" in operation:
            return "write"
        elif "read" in operation or "recall" in operation or "get" in operation:
            return "read"
        else:
            # Final fallback: check for explicit write commands
            write_patterns = ["remember that", "store", "save", "write", "note that", "set"]
            read_patterns = ["recall", "retrieve", "get", "fetch"]
            
            # Check for explicit write patterns with "that" clause
            for pattern in write_patterns:
                if pattern in goal_lower and "that" in goal_lower:
                    return "write"
            
            # Check for read patterns
            if any(p in goal_lower for p in read_patterns):
                return "read"
            
            # Default to read if uncertain (safer - read has no side effects)
            return "read"
    
    def select_memory_tool(self, goal: str) -> Dict:
        """
        Select appropriate memory tool.
        
        Args:
            goal: User goal text
        
        Returns:
            Tool selection dict
        """
        operation = self.classify_memory_operation(goal)
        
        if operation == "write":
            return {
                "name": "memory_write",
                "module": "neural_engine.tools.memory_write_tool",
                "class": "MemoryWriteTool",
                "confidence": 0.95,
                "specialist": "memory"
            }
        else:
            return {
                "name": "memory_read",
                "module": "neural_engine.tools.memory_read_tool",
                "class": "MemoryReadTool",
                "confidence": 0.95,
                "specialist": "memory"
            }
