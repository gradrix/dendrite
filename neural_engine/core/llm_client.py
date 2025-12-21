"""
LLM Client for llama.cpp

Uses the OpenAI-compatible API provided by llama.cpp server.
"""

import os
import logging
from typing import Optional
from .exceptions import TokenLimitExceeded

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM client for llama.cpp via OpenAI-compatible API.
    
    Environment variables:
    - OPENAI_API_BASE: URL of llama.cpp server (default: http://localhost:8080/v1)
    - LLM_MODEL: Model name (default: local-model)
    """
    
    def __init__(self, debug_mode: bool = None):
        self.debug_mode = debug_mode or os.environ.get("DEBUG_LLM", "false").lower() == "true"
        self._call_counter = 0
        
        # Token limits by model family
        self.token_limits = {
            "mistral": 4096,
            "qwen": 8192,
            "llama": 8192,
            "phi": 4096,
            "gemma": 8192,
        }
        
        # Initialize llama.cpp backend
        self._backend = "llama.cpp"
        self._init_backend()
        
        if self.debug_mode:
            print(f"🔍 LLM Debug Mode: ENABLED")
            print(f"   Backend: {self._backend}")
    
    def _init_backend(self):
        """Initialize llama.cpp backend via OpenAI-compatible API."""
        base_url = os.environ.get("OPENAI_API_BASE", "http://localhost:8080/v1")
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required: pip install openai")
        
        self._openai_client = OpenAI(
            base_url=base_url,
            api_key=os.environ.get("OPENAI_API_KEY", "not-needed"),
        )
        self.model = os.environ.get("LLM_MODEL", "local-model")
        self.token_limit = 8192  # llama.cpp default
        
        if self.debug_mode:
            print(f"   API Base: {base_url}")
            print(f"   Model: {self.model}")
    
    def generate(self, prompt: str, context: str = None, check_tokens: bool = True) -> dict:
        """
        Generate response from prompt.
        
        Args:
            prompt: Text prompt
            context: Description for debugging
            check_tokens: Whether to check token limit
        
        Returns:
            Dict with 'response' key containing generated text
        """
        if check_tokens:
            estimated = self._estimate_tokens(prompt)
            if estimated > self.token_limit:
                raise TokenLimitExceeded(
                    prompt_length=estimated,
                    limit=self.token_limit,
                    context=context or "generate()"
                )
        
        if self.debug_mode:
            self._call_counter += 1
            self._log_call("generate", context, prompt)
        
        response = self._generate_openai(prompt)
        
        if self.debug_mode:
            self._log_response(response)
        
        return response
    
    def _generate_openai(self, prompt: str) -> dict:
        """Generate using OpenAI-compatible API."""
        completion = self._openai_client.completions.create(
            model=self.model,
            prompt=prompt,
            max_tokens=2048,
            temperature=0.7,
        )
        return {"response": completion.choices[0].text}
    
    def chat(self, messages: list, options: dict = None, context: str = None) -> dict:
        """
        Chat API with message history.
        
        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            options: Generation options (temperature, etc.)
            context: Description for debugging
        
        Returns:
            Dict with 'message' -> 'content' containing response
        """
        if self.debug_mode:
            self._call_counter += 1
            user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            self._log_call("chat", context, user_msg)
        
        response = self._chat_openai(messages, options)
        
        if self.debug_mode:
            self._log_response(response)
        
        return response
    
    def _chat_openai(self, messages: list, options: dict = None) -> dict:
        """Chat using OpenAI-compatible API."""
        opts = options or {}
        completion = self._openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=opts.get("temperature", 0.7),
            max_tokens=opts.get("max_tokens", 2048),
        )
        return {
            "message": {
                "role": "assistant",
                "content": completion.choices[0].message.content,
            }
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (~3-4 chars per token)."""
        return len(text) // 3
    
    def _log_call(self, call_type: str, context: str, prompt: str):
        """Log call in debug mode."""
        preview = prompt[:150].replace("\n", " ")
        if len(prompt) > 150:
            preview += "..."
        print(f"\n🔍 LLM Call #{self._call_counter} ({call_type})")
        print(f"   Purpose: {context or 'unknown'}")
        print(f"   Prompt: {preview}")
    
    def _log_response(self, response: dict):
        """Log response in debug mode."""
        if "response" in response:
            text = response["response"]
        elif "message" in response:
            text = response["message"]["content"]
        else:
            text = str(response)
        
        preview = text[:150].replace("\n", " ")
        if len(text) > 150:
            preview += "..."
        print(f"   Response: {preview}\n")


# Factory function for backwards compatibility
def create_llm_client(debug_mode: bool = None) -> LLMClient:
    """Create an LLM client."""
    return LLMClient(debug_mode=debug_mode)
