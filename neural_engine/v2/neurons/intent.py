"""
Intent Neuron - Classify what the user wants.

Simple categories:
- generative: Questions, explanations, chat
- tool: Run a tool or perform an action
- memory_read: Retrieve stored information
- memory_write: Store new information
"""

from typing import Any

from ..core.base import Neuron
from ..core.memory import GoalContext


# Intent classification prompt
INTENT_PROMPT = """Classify this user request into ONE category:

Categories:
- generative: Questions, explanations, conversation, creative writing
- tool: Actions that need external tools (weather, search, calculations, API calls)  
- memory_read: Asking about previously stored information ("what did I tell you about...", "do you remember...")
- memory_write: Storing new information for later ("remember that...", "my name is...", "save this...")

Request: {goal}

Respond with ONLY the category name, nothing else."""


class IntentNeuron(Neuron):
    """
    Classify user intent into categories.
    
    Uses LLM to determine what kind of processing is needed.
    Simple and focused.
    """
    
    name = "intent"
    
    async def process(self, ctx: GoalContext, input_data: Any = None) -> str:
        """
        Classify the goal into an intent category.
        
        Args:
            ctx: Goal context
            input_data: Goal text (or uses ctx.goal_text)
        
        Returns:
            Intent string: "generative", "tool", "memory_read", or "memory_write"
        """
        goal = input_data or ctx.goal_text
        
        prompt = INTENT_PROMPT.format(goal=goal)
        
        response = await self.llm.generate(prompt)
        
        # Parse response - just get the category
        intent = response.strip().lower()
        
        # Validate - default to generative if unknown
        valid_intents = {"generative", "tool", "memory_read", "memory_write"}
        
        if intent not in valid_intents:
            # Try to extract from response
            for valid in valid_intents:
                if valid in intent:
                    return valid
            # Default
            return "generative"
        
        return intent
