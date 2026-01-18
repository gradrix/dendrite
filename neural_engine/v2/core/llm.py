"""
LLM Client - Single interface to language models.

One client. One way to call LLMs. No wrappers around wrappers.
"""

import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from typing import Optional, Dict, Any


# Thread pool for running sync OpenAI client in async context
_executor = ThreadPoolExecutor(max_workers=4)


class LLMClient:
    """
    Simple LLM client using OpenAI-compatible API.
    
    Usage:
        llm = LLMClient(config)
        response = await llm.generate("What is 2+2?")
    """
    
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or os.environ.get("OPENAI_API_BASE", "http://llama-gpu:8080/v1")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "not-needed")
        self.model = model or os.environ.get("LLM_MODEL", "local-model")
        
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=30.0,
        )
    
    def _generate_sync(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Synchronous generation (internal)."""
        messages = []
        
        if system:
            messages.append({"role": "system", "content": system})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return response.choices[0].message.content.strip()
    
    async def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User message
            system: Optional system prompt
            temperature: Creativity (0=deterministic, 1=creative)
            max_tokens: Maximum response length
            
        Returns:
            Generated text response
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            lambda: self._generate_sync(prompt, system, temperature, max_tokens)
        )
    
    async def generate_json(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.0,  # Deterministic for structured output
    ) -> Dict[str, Any]:
        """
        Generate JSON response from the LLM.
        
        Uses temperature=0 for consistency.
        Parses and returns dict.
        """
        import json
        
        response = await self.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
        )
        
        # Try to extract JSON from response
        try:
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            return json.loads(response.strip())
        except json.JSONDecodeError:
            # Return raw response wrapped in dict
            return {"raw": response, "error": "Failed to parse JSON"}
    
    @classmethod
    def from_config(cls, config: 'Config') -> 'LLMClient':
        """Create from Config object."""
        return cls(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
            model=config.llm_model,
        )
