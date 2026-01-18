"""
Public Pipe - Redis Streams based event bus for neuron observation.

This is the foundation of self-awareness in the fractal architecture.
Every neuron emits events to the Public Pipe, allowing:
- PerformanceMonitorNeuron to observe and optimize
- Mind Map to record thought trees
- Debugging and introspection
- Future: distributed neuron coordination

Events are structured as:
{
    "event_type": "neuron_started|neuron_completed|neuron_failed|thought|sub_goal",
    "neuron_id": "unique-neuron-instance-id",
    "neuron_type": "IntentClassifierNeuron|ToolSelectorNeuron|...",
    "goal_id": "goal-123",
    "parent_id": "parent-neuron-id or null",
    "timestamp": "2024-01-03T12:00:00Z",
    "duration_ms": 150,
    "data": { ... event-specific payload ... }
}
"""

import os
import json
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, AsyncGenerator
from dataclasses import dataclass, field, asdict
from enum import Enum
import asyncio
import redis.asyncio as redis

from neural_engine.core.logging import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """Types of events emitted to the Public Pipe."""
    NEURON_STARTED = "neuron_started"
    NEURON_COMPLETED = "neuron_completed"
    NEURON_FAILED = "neuron_failed"
    THOUGHT = "thought"  # Intermediate reasoning step
    SUB_GOAL = "sub_goal"  # Neuron spawning a sub-goal
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    MEMORY_STORED = "memory_stored"
    MEMORY_RECALLED = "memory_recalled"


@dataclass
class NeuronEvent:
    """An event emitted by a neuron."""
    event_type: EventType
    neuron_type: str
    goal_id: str
    neuron_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    duration_ms: Optional[float] = None
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        result = asdict(self)
        result["event_type"] = self.event_type.value
        # Serialize data as JSON string for Redis
        result["data"] = json.dumps(self.data)
        # Remove None values (Redis doesn't accept them)
        return {k: v for k, v in result.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NeuronEvent':
        """Create from Redis data."""
        data = data.copy()
        data["event_type"] = EventType(data["event_type"])
        if isinstance(data.get("data"), str):
            data["data"] = json.loads(data["data"])
        # Handle optional fields that might be missing
        if "parent_id" not in data:
            data["parent_id"] = None
        if "duration_ms" not in data:
            data["duration_ms"] = None
        elif data["duration_ms"]:
            data["duration_ms"] = float(data["duration_ms"])
        return cls(**data)


class PublicPipe:
    """
    Redis Streams based event bus for neuron observation.
    
    Usage:
        pipe = PublicPipe()
        
        # Emit an event
        await pipe.emit(NeuronEvent(
            event_type=EventType.NEURON_STARTED,
            neuron_type="IntentClassifierNeuron",
            goal_id="goal-123",
            data={"input": "What's the weather?"}
        ))
        
        # Read recent events
        events = await pipe.read_recent(limit=100)
        
        # Subscribe to events (for monitors)
        async for event in pipe.subscribe():
            print(f"Got event: {event.event_type}")
    """
    
    STREAM_KEY = "dendrite:public_pipe"
    MAX_LEN = 10000  # Keep last 10k events
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis = redis_client
        self._subscribers: List[Callable[[NeuronEvent], None]] = []
    
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            host = os.environ.get("REDIS_HOST", "localhost")
            port = int(os.environ.get("REDIS_PORT", 6379))
            self._redis = redis.Redis(host=host, port=port, decode_responses=True)
        return self._redis
    
    async def emit(self, event: NeuronEvent) -> str:
        """
        Emit an event to the Public Pipe.
        
        Returns:
            The event ID assigned by Redis.
        """
        r = await self._get_redis()
        
        event_data = event.to_dict()
        
        # Add to stream with max length cap
        event_id = await r.xadd(
            self.STREAM_KEY,
            event_data,
            maxlen=self.MAX_LEN
        )
        
        logger.debug(
            "event_emitted",
            event_type=event.event_type.value,
            neuron_type=event.neuron_type,
            goal_id=event.goal_id,
            event_id=event_id
        )
        
        # Notify local subscribers
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error("subscriber_error", error=str(e))
        
        return event_id
    
    async def read_recent(
        self,
        limit: int = 100,
        goal_id: Optional[str] = None,
        neuron_type: Optional[str] = None,
        event_type: Optional[EventType] = None
    ) -> List[NeuronEvent]:
        """
        Read recent events from the pipe.
        
        Args:
            limit: Maximum events to return
            goal_id: Filter by goal ID
            neuron_type: Filter by neuron type
            event_type: Filter by event type
        """
        r = await self._get_redis()
        
        # Read from stream (newest first)
        raw_events = await r.xrevrange(self.STREAM_KEY, count=limit * 2)  # Over-fetch for filtering
        
        events = []
        for event_id, event_data in raw_events:
            try:
                event = NeuronEvent.from_dict(event_data)
                
                # Apply filters
                if goal_id and event.goal_id != goal_id:
                    continue
                if neuron_type and event.neuron_type != neuron_type:
                    continue
                if event_type and event.event_type != event_type:
                    continue
                
                events.append(event)
                
                if len(events) >= limit:
                    break
            except Exception as e:
                logger.warning("event_parse_error", event_id=event_id, error=str(e))
        
        return events
    
    async def read_goal_events(self, goal_id: str) -> List[NeuronEvent]:
        """Read all events for a specific goal."""
        return await self.read_recent(limit=1000, goal_id=goal_id)
    
    async def subscribe(
        self,
        last_id: str = "$",
        block_ms: int = 5000
    ) -> AsyncGenerator[NeuronEvent, None]:
        """
        Subscribe to new events as they arrive.
        
        Args:
            last_id: Start from this ID ("$" for new events only, "0" for all)
            block_ms: How long to block waiting for events
            
        Yields:
            NeuronEvent objects as they arrive
        """
        r = await self._get_redis()
        
        while True:
            try:
                results = await r.xread(
                    {self.STREAM_KEY: last_id},
                    block=block_ms,
                    count=10
                )
                
                if not results:
                    continue
                
                for stream_name, events in results:
                    for event_id, event_data in events:
                        try:
                            event = NeuronEvent.from_dict(event_data)
                            yield event
                            last_id = event_id
                        except Exception as e:
                            logger.warning("event_parse_error", event_id=event_id, error=str(e))
                            last_id = event_id
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("subscribe_error", error=str(e))
                await asyncio.sleep(1)
    
    def add_subscriber(self, callback: Callable[[NeuronEvent], None]):
        """Add a local subscriber for immediate notification."""
        self._subscribers.append(callback)
    
    def remove_subscriber(self, callback: Callable[[NeuronEvent], None]):
        """Remove a local subscriber."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the Public Pipe."""
        r = await self._get_redis()
        
        info = await r.xinfo_stream(self.STREAM_KEY)
        
        return {
            "length": info.get("length", 0),
            "first_entry_id": info.get("first-entry", [None])[0] if info.get("first-entry") else None,
            "last_entry_id": info.get("last-entry", [None])[0] if info.get("last-entry") else None,
            "max_length": self.MAX_LEN
        }
    
    async def clear(self):
        """Clear all events (useful for testing)."""
        r = await self._get_redis()
        await r.delete(self.STREAM_KEY)


# Convenience context manager for neuron execution tracking
class NeuronExecutionContext:
    """
    Context manager that automatically emits start/complete/fail events.
    
    Usage:
        async with NeuronExecutionContext(pipe, "IntentClassifierNeuron", goal_id) as ctx:
            ctx.thought("Analyzing intent...")
            result = do_classification()
            ctx.set_result(result)
    """
    
    def __init__(
        self,
        pipe: PublicPipe,
        neuron_type: str,
        goal_id: str,
        parent_id: Optional[str] = None,
        input_data: Optional[Dict] = None
    ):
        self.pipe = pipe
        self.neuron_type = neuron_type
        self.goal_id = goal_id
        self.parent_id = parent_id
        self.neuron_id = str(uuid.uuid4())[:8]
        self.input_data = input_data or {}
        self.start_time: Optional[float] = None
        self.result: Optional[Any] = None
        self.thoughts: List[str] = []
    
    async def __aenter__(self) -> 'NeuronExecutionContext':
        self.start_time = time.time()
        
        await self.pipe.emit(NeuronEvent(
            event_type=EventType.NEURON_STARTED,
            neuron_type=self.neuron_type,
            goal_id=self.goal_id,
            neuron_id=self.neuron_id,
            parent_id=self.parent_id,
            data={"input": self.input_data}
        ))
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000 if self.start_time else 0
        
        if exc_type is not None:
            # Failed
            await self.pipe.emit(NeuronEvent(
                event_type=EventType.NEURON_FAILED,
                neuron_type=self.neuron_type,
                goal_id=self.goal_id,
                neuron_id=self.neuron_id,
                parent_id=self.parent_id,
                duration_ms=duration_ms,
                data={
                    "error": str(exc_val),
                    "error_type": exc_type.__name__,
                    "thoughts": self.thoughts
                }
            ))
        else:
            # Completed
            await self.pipe.emit(NeuronEvent(
                event_type=EventType.NEURON_COMPLETED,
                neuron_type=self.neuron_type,
                goal_id=self.goal_id,
                neuron_id=self.neuron_id,
                parent_id=self.parent_id,
                duration_ms=duration_ms,
                data={
                    "result": self.result,
                    "thoughts": self.thoughts
                }
            ))
        
        return False  # Don't suppress exceptions
    
    async def thought(self, content: str):
        """Record an intermediate thought."""
        self.thoughts.append(content)
        
        await self.pipe.emit(NeuronEvent(
            event_type=EventType.THOUGHT,
            neuron_type=self.neuron_type,
            goal_id=self.goal_id,
            neuron_id=self.neuron_id,
            parent_id=self.parent_id,
            data={"content": content}
        ))
    
    def set_result(self, result: Any):
        """Set the result to be included in the completion event."""
        self.result = result


# Global pipe instance for convenience
_global_pipe: Optional[PublicPipe] = None


async def get_public_pipe() -> PublicPipe:
    """Get the global PublicPipe instance."""
    global _global_pipe
    if _global_pipe is None:
        _global_pipe = PublicPipe()
    return _global_pipe
