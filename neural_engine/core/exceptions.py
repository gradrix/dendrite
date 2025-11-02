class AuthenticationRequiredError(Exception):
    pass


class TokenLimitExceeded(Exception):
    """
    Exception raised when an Ollama prompt exceeds token limits.
    
    Attributes:
        prompt_length: Number of tokens in the prompt
        limit: Model's token limit
        truncated_to: What the prompt was truncated to (if applicable)
        context: Additional context about what was being generated
    """
    
    def __init__(self, 
                 prompt_length: int, 
                 limit: int, 
                 truncated_to: int = None,
                 context: str = None):
        self.prompt_length = prompt_length
        self.limit = limit
        self.truncated_to = truncated_to
        self.context = context
        
        msg = f"⚠️  Prompt token limit exceeded: {prompt_length} tokens > {limit} limit"
        if truncated_to:
            msg += f" (truncated to {truncated_to})"
        if context:
            msg += f"\n   Context: {context}"
        
        super().__init__(msg)
