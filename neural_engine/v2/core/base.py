"""
Base Neuron - Foundation for all neurons with fractal event emission.

Every neuron:
1. Has a simple process() method
2. Automatically emits events to EventBus
3. Records thoughts to ThoughtTree

Simple, clean, readable.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, TypeVar, Generic
from functools import wraps
import time

from .config import Config
from .llm import LLMClient
from .events import EventBus, EventType
from .memory import ThoughtTree, GoalContext


@dataclass
class NeuronResult:
    """Result from a neuron process."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: int = 0


class Neuron(ABC):
    """
    Base class for all neurons.
    
    A neuron is a focused processing unit that:
    1. Takes input (goal context + specific data)
    2. Processes with LLM or logic
    3. Returns result
    4. Automatically emits events
    
    Usage:
        class MyNeuron(Neuron):
            async def process(self, ctx, input_data):
                result = await self.llm.generate("Do something with: " + input_data)
                return result
    
    Events are automatic - no need to manually emit.
    """
    
    # Subclasses set this
    name: str = "base"
    
    def __init__(self, config: Config):
        self.config = config
        self.llm = LLMClient.from_config(config)
        self._event_bus: Optional[EventBus] = None
        self._thought_tree: Optional[ThoughtTree] = None
    
    @classmethod
    def from_config(cls, config: Config) -> 'Neuron':
        """Create neuron from config."""
        return cls(config)
    
    async def _get_event_bus(self) -> EventBus:
        """Lazy load event bus."""
        if self._event_bus is None:
            self._event_bus = EventBus.from_config(self.config)
        return self._event_bus
    
    async def _get_thought_tree(self) -> ThoughtTree:
        """Lazy load thought tree."""
        if self._thought_tree is None:
            redis_client = await self.config.get_redis()
            self._thought_tree = ThoughtTree(redis_client)
        return self._thought_tree
    
    async def run(self, ctx: GoalContext, input_data: Any = None) -> NeuronResult:
        """
        Run the neuron with automatic event emission.
        
        This wraps process() with:
        1. Start event
        2. Thought recording
        3. End event (success or failure)
        4. Timing
        """
        start_time = time.time()
        event_bus = await self._get_event_bus()
        thought_tree = await self._get_thought_tree()
        
        # Emit start event
        await event_bus.emit(
            event_type=EventType.NEURON_START,
            source=self.name,
            goal_id=ctx.goal_id,
            data={"input": str(input_data)[:200] if input_data else None},
        )
        
        # Record thought
        await thought_tree.add_thought(
            parent_id=f"root_{ctx.goal_id}",
            content=f"{self.name} processing",
            thought_type="action",
            goal_id=ctx.goal_id,
            metadata={"neuron": self.name},
        )
        
        try:
            # Call the actual process method
            result = await self.process(ctx, input_data)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Emit success event
            await event_bus.emit(
                event_type=EventType.NEURON_COMPLETE,
                source=self.name,
                goal_id=ctx.goal_id,
                data={"result": str(result)[:200] if result else None, "duration_ms": duration_ms},
            )
            
            # Add message to context
            ctx.add_message(self.name, "result", result)
            
            return NeuronResult(success=True, data=result, duration_ms=duration_ms)
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            
            # Emit error event
            await event_bus.emit(
                event_type=EventType.NEURON_ERROR,
                source=self.name,
                goal_id=ctx.goal_id,
                data={"error": error_msg, "duration_ms": duration_ms},
            )
            
            # Add error to context
            ctx.add_message(self.name, "error", error_msg)
            
            return NeuronResult(success=False, error=error_msg, duration_ms=duration_ms)
    
    @abstractmethod
    async def process(self, ctx: GoalContext, input_data: Any = None) -> Any:
        """
        Process the input and return result.
        
        Subclasses implement this. Events are handled by run().
        
        Args:
            ctx: Goal context with state and messages
            input_data: Optional input specific to this neuron
        
        Returns:
            Any result (string, dict, etc.)
        """
        pass
