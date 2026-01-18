"""
Generative Neuron - Generate text responses.

Handles:
- Questions and explanations
- Conversation
- Creative writing
- Anything that needs text generation
"""

from typing import Any

from ..core.base import Neuron
from ..core.memory import GoalContext


# System prompt for generative responses
SYSTEM_PROMPT = """You are a helpful AI assistant. Provide clear, accurate, and helpful responses.

Guidelines:
- Be direct and concise
- Provide accurate information
- Admit when you don't know something
- Use simple language when possible"""


class GenerativeNeuron(Neuron):
    """
    Generate text responses to user queries.
    
    Uses LLM directly with a helpful system prompt.
    No complex logic - just good prompting.
    """
    
    name = "generative"
    
    async def process(self, ctx: GoalContext, input_data: Any = None) -> str:
        """
        Generate a response to the user's query.
        
        Args:
            ctx: Goal context
            input_data: Query text (or uses ctx.goal_text)
        
        Returns:
            Generated text response
        """
        query = input_data or ctx.goal_text
        
        # Build prompt with system context
        prompt = f"{SYSTEM_PROMPT}\n\nUser: {query}\n\nAssistant:"
        
        response = await self.llm.generate(prompt)
        
        return response.strip()