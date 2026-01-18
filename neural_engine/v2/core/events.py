"""
Events - Fractal event system for neuron observation.

Every neuron emits events. Events flow to EventBus.
Simple, observable, debuggable.
"""

import json
import uuid
import asyncio
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Callable
import redis.asyncio as redis


class EventType(Enum):
    """Types of events neurons can emit."""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    THOUGHT = "thought"  # Intermediate thinking
    # Also support alternative names used by base.py
    GOAL_START = "goal_start"
    GOAL_COMPLETE = "goal_complete"
    NEURON_START = "neuron_start"
    NEURON_COMPLETE = "neuron_complete"
    NEURON_ERROR = "neuron_error"


@dataclass
class Event:
    """
    A single event from a neuron.
    
    Immutable record of what happened.
    """
    event_type: EventType
    neuron_type: str
    goal_id: str
    
    # Timing
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: Optional[int] = None
    
    # Context
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Unique ID
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for Redis storage."""
        d = asdict(self)
        d['event_type'] = self.event_type.value
        # Remove None values
        return {k: v for k, v in d.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Reconstruct from dict."""
        data = data.copy()
        data['event_type'] = EventType(data['event_type'])
        return cls(**data)


class EventBus:
    """
    Central event bus using Redis Streams.
    
    Neurons emit events → EventBus stores them → Observers can subscribe.
    
    Usage:
        bus = EventBus(config)
        await bus.emit(Event(...))
        
        async for event in bus.subscribe():
            print(event)
    """
    
    STREAM_KEY = "neural:events"
    MAX_LEN = 10000  # Keep last 10k events
    
    def __init__(self, redis_client: redis.Redis = None):
        self._redis = redis_client
    
    @classmethod
    def from_config(cls, config) -> 'EventBus':
        """Create EventBus from config."""
        # Config has get_redis() async method, but we can create without it
        # and lazily connect
        return cls(redis_client=None)
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection."""
        if self._redis is None:
            self._redis = redis.Redis(host='redis', port=6379, decode_responses=True)
        return self._redis
    
    async def emit(
        self,
        event: Event = None,
        *,
        event_type: EventType = None,
        source: str = None,
        goal_id: str = None,
        data: Dict[str, Any] = None,
    ) -> Event:
        """
        Emit an event to the bus.
        
        Can be called with an Event object or keyword arguments:
            await bus.emit(event)
            await bus.emit(event_type=EventType.STARTED, source="intent", goal_id="123")
        
        Returns the Event (with event_id set).
        """
        r = await self._get_redis()
        
        # Build event from kwargs if not provided
        if event is None:
            if event_type is None or source is None or goal_id is None:
                raise ValueError("Must provide event or (event_type, source, goal_id)")
            
            event = Event(
                event_type=event_type,
                neuron_type=source,
                goal_id=goal_id,
                metadata=data or {},
            )
        
        event_data = event.to_dict()
        
        # Serialize complex fields
        for key in ['metadata', 'input_data', 'output_data']:
            if key in event_data and event_data[key]:
                if isinstance(event_data[key], (dict, list)):
                    event_data[key] = json.dumps(event_data[key])
        
        event_id = await r.xadd(
            self.STREAM_KEY,
            event_data,
            maxlen=self.MAX_LEN,
        )
        
        # Store the Redis event ID
        event.event_id = event_id
        
        return event
    
    async def get_events(
        self,
        goal_id: str = None,
        neuron_type: str = None,
        limit: int = 100,
    ) -> List[Event]:
        """
        Get events, optionally filtered.
        """
        r = await self._get_redis()
        
        # Get all recent events
        raw_events = await r.xrevrange(self.STREAM_KEY, count=limit * 2)
        
        events = []
        for event_id, data in raw_events:
            # Parse JSON fields
            for key in ['metadata']:
                if key in data and data[key]:
                    try:
                        data[key] = json.loads(data[key])
                    except json.JSONDecodeError:
                        pass
            
            try:
                event = Event.from_dict(data)
                
                # Apply filters
                if goal_id and event.goal_id != goal_id:
                    continue
                if neuron_type and event.neuron_type != neuron_type:
                    continue
                
                events.append(event)
                
                if len(events) >= limit:
                    break
                    
            except (KeyError, ValueError):
                continue
        
        return events
    
    async def subscribe(self, last_id: str = "$"):
        """
        Subscribe to new events.
        
        Yields events as they arrive.
        
        Usage:
            async for event in bus.subscribe():
                handle(event)
        """
        r = await self._get_redis()
        
        while True:
            results = await r.xread(
                {self.STREAM_KEY: last_id},
                block=5000,  # 5 second timeout
                count=10,
            )
            
            if not results:
                continue
            
            for stream_name, messages in results:
                for msg_id, data in messages:
                    last_id = msg_id
                    
                    # Parse JSON fields
                    for key in ['metadata']:
                        if key in data and data[key]:
                            try:
                                data[key] = json.loads(data[key])
                            except json.JSONDecodeError:
                                pass
                    
                    try:
                        yield Event.from_dict(data)
                    except (KeyError, ValueError):
                        continue
    
    async def clear(self):
        """Clear all events (for testing)."""
        r = await self._get_redis()
        await r.delete(self.STREAM_KEY)
    
    async def count(self) -> int:
        """Count events in stream."""
        r = await self._get_redis()
        return await r.xlen(self.STREAM_KEY)
