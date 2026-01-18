"""
LLM Client - Single interface to language models.

Uses raw HTTP requests to llama.cpp server (no external dependencies).
"""

import os
import asyncio
import json
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any


# Thread pool for running sync requests in async context
_executor = ThreadPoolExecutor(max_workers=4)


class LLMClient:
    """
    Simple LLM client using raw HTTP to llama.cpp server.
    
    Usage:
        llm = LLMClient(config)
        response = await llm.generate("What is 2+2?")
    """
    
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "http://llama-gpu:8080/v1")).rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL", "local-model")
        self.timeout = 120  # 2 minutes for generation
    
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
        
        # Call llama.cpp OpenAI-compatible endpoint
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    
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
            model=config.llm_model,
        )
