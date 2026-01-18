"""
Memory - Thought tracking and goal context.

Two simple concepts:
1. ThoughtTree - Track the thinking process (MindMap simplified)
2. GoalContext - Messages and state for a single goal
"""

import json
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
import redis.asyncio as redis


@dataclass
class Thought:
    """
    A single thought in the thinking process.
    
    Thoughts form a tree: goal → sub-thoughts → results
    """
    thought_id: str
    goal_id: str
    content: str
    thought_type: str  # "goal", "reasoning", "action", "result"
    
    parent_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Status
    status: str = "active"  # active, completed, failed
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Thought':
        return cls(**data)


class ThoughtTree:
    """
    Track the thinking process for goals.
    
    Simple tree structure in Redis:
    - Each goal has a root thought
    - Neurons add child thoughts as they process
    - Final result completes the tree
    
    Usage:
        tree = ThoughtTree(config)
        root = await tree.create_root("goal_123", "What is 2+2?")
        await tree.add_thought(root.thought_id, "Calculating...", "reasoning")
        await tree.complete(root.thought_id, "4")
    """
    
    KEY_PREFIX = "neural:thoughts:"
    INDEX_KEY = "neural:thoughts:index"
    
    def __init__(self, redis_client: redis.Redis = None):
        self._redis = redis_client
    
    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.Redis(host='redis', port=6379, decode_responses=True)
        return self._redis
    
    async def create_root(self, goal_id: str, goal_text: str) -> Thought:
        """Create root thought for a goal."""
        r = await self._get_redis()
        
        thought = Thought(
            thought_id=f"root_{goal_id}",
            goal_id=goal_id,
            content=goal_text,
            thought_type="goal",
        )
        
        # Store thought
        key = f"{self.KEY_PREFIX}{goal_id}"
        await r.hset(key, thought.thought_id, json.dumps(thought.to_dict()))
        
        # Add to index
        await r.zadd(self.INDEX_KEY, {goal_id: datetime.now(timezone.utc).timestamp()})
        
        return thought
    
    async def add_thought(
        self,
        parent_id: str,
        content: str,
        thought_type: str,
        goal_id: str = None,
        metadata: Dict[str, Any] = None,
    ) -> Thought:
        """Add a child thought."""
        r = await self._get_redis()
        
        # Extract goal_id from parent if not provided
        if goal_id is None:
            goal_id = parent_id.split("_", 1)[1] if "_" in parent_id else parent_id
        
        thought = Thought(
            thought_id=str(uuid.uuid4()),
            goal_id=goal_id,
            content=content,
            thought_type=thought_type,
            parent_id=parent_id,
            metadata=metadata or {},
        )
        
        key = f"{self.KEY_PREFIX}{goal_id}"
        await r.hset(key, thought.thought_id, json.dumps(thought.to_dict()))
        
        return thought
    
    async def complete(self, goal_id: str, result: str = None):
        """Mark goal as completed."""
        r = await self._get_redis()
        key = f"{self.KEY_PREFIX}{goal_id}"
        
        # Get root thought
        root_data = await r.hget(key, f"root_{goal_id}")
        if root_data:
            root = Thought.from_dict(json.loads(root_data))
            root.status = "completed"
            if result:
                root.metadata["result"] = result
            await r.hset(key, root.thought_id, json.dumps(root.to_dict()))
    
    async def fail(self, goal_id: str, error: str):
        """Mark goal as failed."""
        r = await self._get_redis()
        key = f"{self.KEY_PREFIX}{goal_id}"
        
        root_data = await r.hget(key, f"root_{goal_id}")
        if root_data:
            root = Thought.from_dict(json.loads(root_data))
            root.status = "failed"
            root.metadata["error"] = error
            await r.hset(key, root.thought_id, json.dumps(root.to_dict()))
    
    async def get_thoughts(self, goal_id: str) -> List[Thought]:
        """Get all thoughts for a goal."""
        r = await self._get_redis()
        key = f"{self.KEY_PREFIX}{goal_id}"
        
        data = await r.hgetall(key)
        thoughts = []
        for thought_data in data.values():
            thoughts.append(Thought.from_dict(json.loads(thought_data)))
        
        return sorted(thoughts, key=lambda t: t.timestamp)
    
    async def get_root(self, goal_id: str) -> Optional[Thought]:
        """Get root thought for a goal."""
        r = await self._get_redis()
        key = f"{self.KEY_PREFIX}{goal_id}"
        
        root_data = await r.hget(key, f"root_{goal_id}")
        if root_data:
            return Thought.from_dict(json.loads(root_data))
        return None


@dataclass
class GoalContext:
    """
    Context for a single goal being processed.
    
    Tracks messages, state, and results as goal is processed.
    Passed between neurons.
    """
    goal_id: str
    goal_text: str
    
    # Processing state
    intent: Optional[str] = None
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Results
    result: Optional[str] = None
    error: Optional[str] = None
    success: bool = False
    
    # Messages (for debugging)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timing
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    
    def add_message(self, neuron: str, message_type: str, data: Any):
        """Add a message from a neuron."""
        self.messages.append({
            "neuron": neuron,
            "type": message_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    def complete(self, result: str):
        """Mark as completed."""
        self.result = result
        self.success = True
        self.completed_at = datetime.now(timezone.utc).isoformat()
    
    def fail(self, error: str):
        """Mark as failed."""
        self.error = error
        self.success = False
        self.completed_at = datetime.now(timezone.utc).isoformat()
    
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate duration in milliseconds."""
        if not self.completed_at:
            return None
        
        start = datetime.fromisoformat(self.started_at.replace('Z', '+00:00'))
        end = datetime.fromisoformat(self.completed_at.replace('Z', '+00:00'))
        return int((end - start).total_seconds() * 1000)
