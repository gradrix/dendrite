"""
Configuration - Single source of truth for the entire system.

No optional parameters. Everything is explicit.
"""

import os
import redis.asyncio as redis
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """
    System configuration. Create once, pass everywhere.
    
    Usage:
        config = Config.from_env()
        orchestrator = Orchestrator(config)
    """
    
    # LLM settings (llama.cpp server)
    llm_base_url: str = "http://llama-gpu:8080/v1"
    llm_model: str = "local-model"
    
    # Redis settings  
    redis_host: str = "redis"
    redis_port: int = 6379
    
    # Postgres settings
    postgres_host: str = "postgres"
    postgres_db: str = "dendrite"
    postgres_user: str = "dendrite"
    postgres_password: str = "dendrite_pass"
    
    # Paths
    tools_dir: str = "neural_engine/tools"
    prompts_dir: str = "neural_engine/prompts"
    
    # Runtime (set after initialization)
    _redis_client: Optional[redis.Redis] = field(default=None, repr=False)
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create config from environment variables."""
        return cls(
            llm_base_url=os.environ.get("LLM_BASE_URL", "http://llama-gpu:8080/v1"),
            llm_model=os.environ.get("LLM_MODEL", "local-model"),
            redis_host=os.environ.get("REDIS_HOST", "redis"),
            redis_port=int(os.environ.get("REDIS_PORT", 6379)),
            postgres_host=os.environ.get("POSTGRES_HOST", "postgres"),
            postgres_db=os.environ.get("POSTGRES_DB", "dendrite"),
            postgres_user=os.environ.get("POSTGRES_USER", "dendrite"),
            postgres_password=os.environ.get("POSTGRES_PASSWORD", "dendrite_pass"),
            tools_dir=os.environ.get("TOOLS_DIR", "neural_engine/tools"),
            prompts_dir=os.environ.get("PROMPTS_DIR", "neural_engine/prompts"),
        )
    
    @classmethod
    def for_testing(cls, redis_client: redis.Redis = None) -> 'Config':
        """Create config for tests with optional injected Redis."""
        config = cls.from_env()
        config._redis_client = redis_client
        return config
    
    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis_client is None:
            self._redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True
            )
        return self._redis_client
