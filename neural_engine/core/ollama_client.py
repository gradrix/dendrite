import ollama
import os
import logging
from .exceptions import TokenLimitExceeded


class OllamaClient:
    def __init__(self, debug_mode: bool = None):
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "mistral")
        self.client = ollama.Client(host=host)
        
        # Debug mode can be set explicitly or via environment variable
        if debug_mode is None:
            debug_mode = os.environ.get("DEBUG_LLM", "false").lower() == "true"
        self.debug_mode = debug_mode
        
        if self.debug_mode:
            print("🔍 LLM Debug Mode: ENABLED")
            print(f"   Model: {self.model}")
            print(f"   Host: {host}")
        
        self._call_counter = 0
        
        # Model-specific token limits (can be overridden)
        self.token_limits = {
            "mistral": 4096,
            "llama2": 4096,
            "codellama": 16384,
            "llama3": 8192,
        }
        self.token_limit = self.token_limits.get(self.model.split(":")[0], 4096)
        
        self._ensure_model_is_available()

    def _ensure_model_is_available(self):
        """
        Checks if the required model is available locally and pulls it if not.
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                local_models = self.client.list()["models"]
                model_names = [model["model"] for model in local_models]

                # The API might return the model name with a default tag, e.g., 'mistral:latest'
                # We should check if our model name is a prefix of any of the available models.
                if any(m.startswith(self.model) for m in model_names):
                    print(f"Model '{self.model}' is available locally.")
                    return

                print(f"Model '{self.model}' not found locally. Pulling from registry...")
                self.client.pull(self.model)
                print(f"Model '{self.model}' pulled successfully.")
                return

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                    print(f"Retrying in {retry_delay} seconds...")
                    import time
                    time.sleep(retry_delay)
                else:
                    # Final attempt failed
                    print(f"Error checking for or pulling model '{self.model}': {e}")
                    # Re-raise to make the startup failure obvious
                    raise

    def generate(self, prompt, context: str = None, check_tokens: bool = True):
        """
        Generate response from prompt.
        
        Args:
            prompt: Text prompt
            context: Optional context description for error messages
            check_tokens: Whether to estimate and check token count
        
        Returns:
            Response dict
            
        Raises:
            TokenLimitExceeded: If prompt exceeds model's token limit
        """
        if check_tokens:
            estimated_tokens = self._estimate_tokens(prompt)
            if estimated_tokens > self.token_limit:
                raise TokenLimitExceeded(
                    prompt_length=estimated_tokens,
                    limit=self.token_limit,
                    context=context or "generate() call"
                )
        
        # Debug logging before call
        if self.debug_mode:
            self._call_counter += 1
            self._log_llm_call(
                call_type="generate",
                context=context or "unknown",
                prompt=prompt,
                estimated_tokens=self._estimate_tokens(prompt) if check_tokens else None
            )
        
        response = self.client.generate(model=self.model, prompt=prompt)
        
        # Debug logging after call
        if self.debug_mode:
            self._log_llm_response(response)
        
        return response
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimation: ~4 characters per token on average.
        This is conservative - better to overestimate than underestimate.
        """
        return len(text) // 3  # Conservative: 3 chars/token
    
    def chat(self, messages, options=None, context: str = None):
        """
        Chat API with message history support for few-shot learning.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
                     Roles: 'system', 'user', 'assistant'
            options: Optional dict of generation options (temperature, etc.)
            context: Optional context description for debugging
        
        Returns:
            Response dict with 'message' containing 'content'
        
        Example:
            messages = [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi there!"},  # Example
                {"role": "user", "content": "How are you?"}  # Actual query
            ]
        """
        # Debug logging before call
        if self.debug_mode:
            self._call_counter += 1
            # For chat, show the user message
            user_msg = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), "")
            self._log_llm_call(
                call_type="chat",
                context=context or "unknown",
                prompt=user_msg,
                estimated_tokens=None
            )
        
        response = self.client.chat(
            model=self.model, 
            messages=messages,
            options=options or {}
        )
        
        # Debug logging after call
        if self.debug_mode:
            self._log_llm_response(response)
        
        return response
    
    def _log_llm_call(self, call_type: str, context: str, prompt: str, estimated_tokens: int = None):
        """Log LLM call details in debug mode."""
        print(f"\n🔍 LLM Call #{self._call_counter} ({call_type})")
        print(f"   Purpose: {context}")
        
        # Show prompt preview (first 150 chars)
        prompt_preview = prompt[:150].replace('\n', ' ')
        if len(prompt) > 150:
            prompt_preview += "..."
        print(f"   Prompt: {prompt_preview}")
        
        if estimated_tokens:
            print(f"   Tokens: ~{estimated_tokens} / {self.token_limit}")
    
    def _log_llm_response(self, response: dict):
        """Log LLM response details in debug mode."""
        # Extract response text based on response type
        if 'response' in response:
            # generate() response
            text = response['response']
        elif 'message' in response and 'content' in response['message']:
            # chat() response
            text = response['message']['content']
        else:
            text = str(response)
        
        # Show response preview (first 150 chars)
        response_preview = text[:150].replace('\n', ' ')
        if len(text) > 150:
            response_preview += "..."
        print(f"   Response: {response_preview}\n")
