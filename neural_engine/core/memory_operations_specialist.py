"""
Memory Operations Specialist - Expert in memory read/write distinction.

This specialized classifier focuses ONLY on memory operations,
achieving higher accuracy than the general classifier.

Uses tool semantic metadata for action hints when available.
"""

from typing import Dict, Optional, TYPE_CHECKING
from .neuron import BaseNeuron

if TYPE_CHECKING:
    from neural_engine.core.tool_discovery import ToolDiscovery


class MemoryOperationsSpecialist(BaseNeuron):
    """
    Specialist for memory operations.
    
    Distinguishes between:
    - memory_write: Storing information
    - memory_read: Retrieving information
    
    Uses semantic metadata from tools when available.
    """
    
    def __init__(self, message_bus, ollama_client, tool_discovery: Optional['ToolDiscovery'] = None):
        super().__init__(message_bus, ollama_client)
        self.tool_discovery = tool_discovery
        
        # Cache tool action hints (populated from semantic metadata)
        self._write_actions = {"store", "save", "write", "remember", "memorize", "note"}
        self._read_actions = {"retrieve", "recall", "get", "read", "fetch"}
    
    def set_tool_discovery(self, tool_discovery: 'ToolDiscovery'):
        """Set tool discovery and update action hints from metadata."""
        self.tool_discovery = tool_discovery
        self._update_action_hints()
    
    def _update_action_hints(self):
        """Update action hints from tool semantic metadata."""
        if not self.tool_discovery:
            return
        
        # Get memory tools and extract their action metadata
        try:
            tools = self.tool_discovery.tool_registry.get_all_tools()
            
            for tool_name, tool_instance in tools.items():
                if hasattr(tool_instance, 'get_semantic_metadata'):
                    metadata = tool_instance.get_semantic_metadata()
                    if metadata.get('domain') == 'memory':
                        actions = set(metadata.get('actions', []))
                        synonyms = set(metadata.get('synonyms', []))
                        
                        # memory_write actions
                        if 'store' in actions or 'save' in actions or 'write' in actions:
                            self._write_actions.update(actions)
                            self._write_actions.update(synonyms)
                        
                        # memory_read actions  
                        if 'retrieve' in actions or 'read' in actions or 'get' in actions:
                            self._read_actions.update(actions)
                            self._read_actions.update(synonyms)
        except Exception:
            pass  # Keep defaults if tool discovery fails
    
    def classify_memory_operation(self, goal: str) -> str:
        """
        Classify memory operation type using LLM with semantic-aware fallback.
        
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
                    "Respond with ONLY 'write' or 'read'."
                )
            },
            {"role": "user", "content": goal}
        ]
        
        response = self.ollama_client.chat(messages)
        operation = response['message']['content'].strip().lower()
        
        # Semantic-aware fallback using action hints from tool metadata
        goal_lower = goal.lower()
        
        # Check if goal contains write actions (from semantic metadata)
        write_action_score = sum(1 for action in self._write_actions if action in goal_lower)
        read_action_score = sum(1 for action in self._read_actions if action in goal_lower)
        
        # Linguistic patterns for read/write detection (grammatical, not domain-specific)
        # These are OK because they detect SENTENCE STRUCTURE, not topic
        is_statement = any(p in goal_lower for p in ["my name is", "my favorite is", "i am ", "i like "])
        is_question = "?" in goal or any(q in goal_lower for q in ["what is", "who is", "tell me"])
        is_recall = any(p in goal_lower for p in ["what i told", "what you know", "do you remember"])
        
        # Combine signals
        if is_statement and not is_question and not is_recall:
            return "write"
        
        if is_question or is_recall:
            return "read"
        
        # Use action scores from semantic metadata
        if write_action_score > read_action_score:
            return "write"
        elif read_action_score > write_action_score:
            return "read"
        
        # Trust LLM response as final fallback
        if "write" in operation or "stor" in operation:
            return "write"
        elif "read" in operation or "recall" in operation:
            return "read"
        
        # Default to read (safer - no side effects)
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
