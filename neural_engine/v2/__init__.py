"""
Neural Engine v2 - Clean Architecture

A simpler, more maintainable version of the neural engine.

Structure:
    v2/
    ├── core/           # Foundation (config, llm, events, base, memory, orchestrator)
    └── neurons/        # Processing units (intent, generative, tools, memory)

Usage:
    from neural_engine.v2.core import Config, Orchestrator
    
    config = Config.for_testing()
    orchestrator = await Orchestrator.from_config(config)
    result = await orchestrator.process("What is 2+2?")

Compare to v1:
    - 47 files → 10 files
    - No optional parameter hell
    - No wrapper around wrapper
    - Clear, simple flow
"""

from .core import (
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

from .neurons import (
    IntentNeuron,
    GenerativeNeuron,
    ToolNeuron,
    MemoryNeuron,
)

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
]
