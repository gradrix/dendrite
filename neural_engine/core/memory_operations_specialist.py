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
                    "- 'write' (storing, saving, remembering new information)\n"
                    "- 'read' (retrieving, recalling, asking for stored information)\n\n"
                    "Examples:\n"
                    "User: Remember that my name is Alice\n"
                    "Assistant: write\n\n"
                    "User: What is my name?\n"
                    "Assistant: read\n\n"
                    "User: Store the value 42 for key 'answer'\n"
                    "Assistant: write\n\n"
                    "User: Recall what I told you about my birthday\n"
                    "Assistant: read\n\n"
                    "Respond with ONLY 'write' or 'read'."
                )
            },
            {"role": "user", "content": goal}
        ]
        
        response = self.ollama_client.chat(messages)
        operation = response['message']['content'].strip().lower()
        
        # Validate and clean
        if "write" in operation or "stor" in operation or "save" in operation:
            return "write"
        elif "read" in operation or "recall" in operation or "get" in operation:
            return "read"
        else:
            # Fallback: analyze keywords
            goal_lower = goal.lower()
            write_keywords = ["remember", "store", "save", "write", "note"]
            read_keywords = ["what", "recall", "retrieve", "tell me", "get"]
            
            write_score = sum(1 for kw in write_keywords if kw in goal_lower)
            read_score = sum(1 for kw in read_keywords if kw in goal_lower)
            
            if write_score > read_score:
                return "write"
            else:
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
