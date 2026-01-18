"""
Memory Neuron - Read and write memories.

Handles:
- memory_read: Retrieve stored information
- memory_write: Store new information

Uses LLM to extract what to read/write from natural language.
"""

import json
from typing import Any, Dict

from ..core.base import Neuron
from ..core.memory import GoalContext


# Memory extraction prompt
MEMORY_EXTRACT_PROMPT = """Extract memory information from this request.

Request: {goal}
Action: {action}

For READ requests, extract:
- key: What to look up (topic, name, or search term)

For WRITE requests, extract:
- key: What topic/name to store under
- value: What information to store

Respond with JSON:
{{"key": "the_key", "value": "the_value_if_writing"}}"""


class MemoryNeuron(Neuron):
    """
    Read and write memories using Redis.
    
    Uses LLM to understand natural language memory requests.
    """
    
    name = "memory"
    
    MEMORY_PREFIX = "memory:"
    
    async def process(self, ctx: GoalContext, input_data: Any = None) -> str:
        """
        Process memory request.
        
        Args:
            ctx: Goal context
            input_data: Dict with "action" (read/write) and "goal"
        
        Returns:
            Memory value or confirmation
        """
        if isinstance(input_data, dict):
            action = input_data.get("action", "read")
            goal = input_data.get("goal", ctx.goal_text)
        else:
            # Guess action from context intent
            action = "read" if ctx.intent == "memory_read" else "write"
            goal = input_data or ctx.goal_text
        
        # Extract key/value using LLM
        extracted = await self._extract_memory_info(goal, action)
        
        key = extracted.get("key", "").strip()
        if not key:
            return "Could not determine what to remember/recall"
        
        if action == "read":
            return await self._read(key)
        else:
            value = extracted.get("value", "").strip()
            if not value:
                return "Could not determine what value to store"
            return await self._write(key, value)
    
    async def _extract_memory_info(self, goal: str, action: str) -> Dict[str, str]:
        """Use LLM to extract key/value from natural language."""
        prompt = MEMORY_EXTRACT_PROMPT.format(goal=goal, action=action.upper())
        
        try:
            return await self.llm.generate_json(prompt)
        except Exception:
            return {}
    
    async def _read(self, key: str) -> str:
        """Read from memory."""
        r = await self.config.get_redis()
        
        # Try exact key first
        value = await r.get(f"{self.MEMORY_PREFIX}{key}")
        if value:
            return f"I remember: {value}"
        
        # Try searching keys
        pattern = f"{self.MEMORY_PREFIX}*{key}*"
        keys = []
        async for k in r.scan_iter(match=pattern, count=10):
            keys.append(k)
        
        if keys:
            results = []
            for k in keys[:5]:  # Limit to 5 results
                val = await r.get(k)
                clean_key = k.replace(self.MEMORY_PREFIX, "")
                results.append(f"- {clean_key}: {val}")
            return "Found related memories:\n" + "\n".join(results)
        
        return f"I don't have any memory about '{key}'"
    
    async def _write(self, key: str, value: str) -> str:
        """Write to memory."""
        r = await self.config.get_redis()
        
        await r.set(f"{self.MEMORY_PREFIX}{key}", value)
        
        return f"I'll remember that {key} = {value}"
