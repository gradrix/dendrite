"""
Neural Engine - Fractal AI Agent System

v2 Architecture - Clean, simple, maintainable.

Usage:
    from neural_engine import Config, Orchestrator
    
    config = Config.from_env()
    orchestrator = await Orchestrator.from_config(config)
    result = await orchestrator.process("What is 2+2?")

Modules:
    v2.core     - Core infrastructure (Config, LLM, EventBus, etc.)
    v2.neurons  - Processing units (Intent, Generative, Tools, Memory)
    v2.tools    - Tool registry and built-in tools
    v2.api      - HTTP API server
    v2.cli      - Command-line interface
"""

# Re-export v2 as the default
from .v2.core import (
    Config,
    LLMClient,
    Neuron,
    EventBus,
    Event,
    EventType,
    ThoughtTree,
    GoalContext,
    Orchestrator,
)

from .v2.neurons import (
    IntentNeuron,
    GenerativeNeuron,
    ToolNeuron,
    MemoryNeuron,
)

from .v2.tools import (
    Tool,
    ToolDefinition,
    ToolRegistry,
)

__version__ = "2.0.0"

__all__ = [
    # Core
    "Config",
    "LLMClient",
    "Neuron",
    "EventBus",
    "Event",
    "EventType",
    "ThoughtTree",
    "GoalContext",
    "Orchestrator",
    # Neurons
    "IntentNeuron",
    "GenerativeNeuron",
    "ToolNeuron",
    "MemoryNeuron",
    # Tools
    "Tool",
    "ToolDefinition",
    "ToolRegistry",
]
