"""
Neural Engine v2 - Clean Architecture

Core principles:
1. Single responsibility - each file does ONE thing
2. Dependency injection - config is the single source of truth
3. Fractal structure - neurons emit events, thoughts tracked in MindMap
4. Human readable - simple code, obvious flow
"""

from .config import Config
from .llm import LLMClient
from .base import Neuron
from .events import EventBus, Event, EventType
from .memory import ThoughtTree, GoalContext
from .orchestrator import Orchestrator
from .recovery import RecoveryEngine, ExecutionHistory, RecoveryAction, FailureType

__all__ = [
    'Config',
    'LLMClient', 
    'Neuron',
    'EventBus', 'Event', 'EventType',
    'ThoughtTree', 'GoalContext',
    'Orchestrator',
    'RecoveryEngine', 'ExecutionHistory', 'RecoveryAction', 'FailureType',
]
