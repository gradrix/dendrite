import ollama
import os
from .exceptions import TokenLimitExceeded


class OllamaClient:
    def __init__(self):
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "mistral")
        self.client = ollama.Client(host=host)
        
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

        except Exception as e:
            # If we can't connect to Ollama at all, we'll get an error here.
            # The user will see this when the app starts up.
            print(f"Error checking for or pulling model '{self.model}': {e}")
            # We'll re-raise for now to make the startup failure obvious.
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
        
        response = self.client.generate(model=self.model, prompt=prompt)
        return response
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimation: ~4 characters per token on average.
        This is conservative - better to overestimate than underestimate.
        """
        return len(text) // 3  # Conservative: 3 chars/token
    
    def chat(self, messages, options=None):
        """
        Chat API with message history support for few-shot learning.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
                     Roles: 'system', 'user', 'assistant'
            options: Optional dict of generation options (temperature, etc.)
        
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
        response = self.client.chat(
            model=self.model, 
            messages=messages,
            options=options or {}
        )
        return response
