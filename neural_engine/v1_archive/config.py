"""
Centralized System Configuration.

This module provides a single source of truth for all system dependencies
and configuration. No more optional parameters scattered everywhere.

Usage:
    config = SystemConfig.create()  # Creates with all defaults
    config = SystemConfig.create_minimal()  # For testing, no external deps
    
    orchestrator = Orchestrator(config)
    neuron = IntentClassifierNeuron(config)
"""

import os
import redis.asyncio as redis
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class Environment(Enum):
    """Runtime environment."""
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TEST = "test"


@dataclass
class SystemConfig:
    """
    Centralized configuration for the entire system.
    
    All dependencies are explicit and required. No hidden auto-creation.
    Use factory methods to create appropriate configurations.
    """
    
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    
    # LLM Client (required)
    llm_client: Any = None
    
    # Redis client for async operations
    redis_client: Optional[redis.Redis] = None
    
    # Message Bus for goal communication
    message_bus: Any = None
    
    # Tool Registry
    tool_registry: Any = None
    
    # Fractal Architecture Components
    public_pipe: Any = None
    mind_map: Any = None
    
    # Execution tracking
    execution_store: Any = None
    
    # Feature flags (explicit, not hidden)
    enable_fractal: bool = True
    enable_tool_discovery: bool = False
    enable_pattern_cache: bool = True
    enable_execution_logging: bool = True
    
    # Derived components (created based on above)
    pattern_cache: Any = None
    tool_discovery: Any = None
    
    @classmethod
    def create(cls, environment: Environment = Environment.DEVELOPMENT) -> 'SystemConfig':
        """
        Create a fully-configured system with all dependencies.
        
        This is the standard way to create a working system.
        """
        from neural_engine.core.llm_client import LLMClient
        from neural_engine.core.message_bus import MessageBus
        from neural_engine.core.tool_registry import ToolRegistry
        from neural_engine.core.public_pipe import PublicPipe
        from neural_engine.core.mind_map import MindMap
        from neural_engine.core.pattern_cache import PatternCache
        
        # Create Redis client
        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        
        # Create core components
        llm_client = LLMClient()
        message_bus = MessageBus()
        tool_registry = ToolRegistry()
        
        # Create fractal components
        public_pipe = PublicPipe(redis_client)
        mind_map = MindMap(redis_client)
        
        # Create optional components based on flags
        pattern_cache = PatternCache() if environment != Environment.TEST else None
        
        # Try to create execution store if postgres available
        execution_store = None
        if os.environ.get("POSTGRES_HOST"):
            try:
                from neural_engine.core.execution_store import ExecutionStore
                execution_store = ExecutionStore()
            except Exception:
                pass  # Postgres not available
        
        return cls(
            environment=environment,
            llm_client=llm_client,
            redis_client=redis_client,
            message_bus=message_bus,
            tool_registry=tool_registry,
            public_pipe=public_pipe,
            mind_map=mind_map,
            pattern_cache=pattern_cache,
            execution_store=execution_store,
            enable_fractal=True,
            enable_pattern_cache=pattern_cache is not None,
            enable_execution_logging=execution_store is not None,
        )
    
    @classmethod
    def create_minimal(cls) -> 'SystemConfig':
        """
        Create a minimal config for unit testing.
        
        No external dependencies (Redis, Postgres, etc).
        Uses mocks or in-memory implementations.
        """
        from neural_engine.core.llm_client import LLMClient
        from neural_engine.core.message_bus import MessageBus
        from neural_engine.core.tool_registry import ToolRegistry
        
        return cls(
            environment=Environment.TEST,
            llm_client=LLMClient(),
            message_bus=MessageBus(),
            tool_registry=ToolRegistry(),
            public_pipe=None,
            mind_map=None,
            pattern_cache=None,
            execution_store=None,
            enable_fractal=False,
            enable_pattern_cache=False,
            enable_execution_logging=False,
        )
    
    @classmethod  
    def create_for_testing(cls, 
                           redis_client: redis.Redis = None,
                           llm_client: Any = None,
                           mock_llm: bool = False) -> 'SystemConfig':
        """
        Create a config for integration testing.
        
        Allows injecting specific components while using defaults for others.
        """
        from neural_engine.core.message_bus import MessageBus
        from neural_engine.core.tool_registry import ToolRegistry
        from neural_engine.core.public_pipe import PublicPipe
        from neural_engine.core.mind_map import MindMap
        
        # Use provided or create new
        if llm_client is None and not mock_llm:
            from neural_engine.core.llm_client import LLMClient
            llm_client = LLMClient()
        
        message_bus = MessageBus()
        tool_registry = ToolRegistry()
        
        # Fractal components if redis provided
        public_pipe = PublicPipe(redis_client) if redis_client else None
        mind_map = MindMap(redis_client) if redis_client else None
        
        return cls(
            environment=Environment.TEST,
            llm_client=llm_client,
            redis_client=redis_client,
            message_bus=message_bus,
            tool_registry=tool_registry,
            public_pipe=public_pipe,
            mind_map=mind_map,
            enable_fractal=redis_client is not None,
        )
    
    def create_neuron_registry(self) -> Dict[str, Any]:
        """
        Create the standard neuron registry with all neurons configured.
        
        This centralizes neuron creation instead of scattering it everywhere.
        """
        from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
        from neural_engine.core.generative_neuron import GenerativeNeuron
        from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
        from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
        from neural_engine.core.sandbox import Sandbox
        
        return {
            "intent_classifier": IntentClassifierNeuron.from_config(self),
            "generative": GenerativeNeuron(self.message_bus, self.llm_client),
            "tool_selector": ToolSelectorNeuron.from_config(self),
            "code_generator": CodeGeneratorNeuron(
                self.message_bus,
                self.llm_client,
                self.tool_registry
            ),
            "sandbox": Sandbox(self.message_bus),
        }
    
    def create_orchestrator(self):
        """
        Create a fully configured Orchestrator.
        
        This is the main entry point for the system.
        """
        from neural_engine.core.orchestrator import Orchestrator
        
        return Orchestrator.from_config(self)
