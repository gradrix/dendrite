"""
Mind Map - Persistent thought tree for neuron reasoning.

This is the foundation of memory in the fractal architecture.
Every neuron's input/output is stored as a node in a tree, allowing:
- Recall of past reasoning for similar goals
- Short-term memory across invocations
- Debugging and introspection of thought processes
- Future: learning from past successes/failures

The tree structure:
    Goal (root)
    ├── Thought Node (IntentClassifier)
    │   ├── Thought Node (intent analysis)
    │   └── Thought Node (decision)
    ├── Thought Node (ToolSelector)
    │   ├── Sub-Goal Node (spawned task)
    │   │   └── Thought Node (sub-task reasoning)
    │   └── Thought Node (tool selection)
    └── Thought Node (Result)

Each node contains:
- Neuron type and ID
- Input and output
- Duration and timestamp
- Links to parent/children
- Semantic embedding (for similarity search)
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
import redis.asyncio as redis

from neural_engine.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ThoughtNode:
    """A node in the thought tree."""
    node_id: str
    goal_id: str
    neuron_type: str
    neuron_id: str
    
    # Content
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    thoughts: List[str] = field(default_factory=list)  # Intermediate reasoning
    
    # Tree structure
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    depth: int = 0
    
    # Metadata
    status: str = "pending"  # pending, completed, failed
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    
    # For semantic search (populated by embedding model)
    embedding: Optional[List[float]] = None
    summary: Optional[str] = None  # Human-readable summary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["input_data"] = json.dumps(data["input_data"])
        data["output_data"] = json.dumps(data["output_data"]) if data["output_data"] else ""
        data["thoughts"] = json.dumps(data["thoughts"])
        data["children_ids"] = json.dumps(data["children_ids"])
        data["embedding"] = json.dumps(data["embedding"]) if data["embedding"] else ""
        # Replace None values with empty strings for Redis compatibility
        return {k: (v if v is not None else "") for k, v in data.items()}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThoughtNode':
        """Create from stored dictionary."""
        data = data.copy()
        data["input_data"] = json.loads(data["input_data"]) if isinstance(data["input_data"], str) else data["input_data"]
        data["output_data"] = json.loads(data["output_data"]) if data.get("output_data") else None
        data["thoughts"] = json.loads(data["thoughts"]) if isinstance(data["thoughts"], str) else data["thoughts"]
        data["children_ids"] = json.loads(data["children_ids"]) if isinstance(data["children_ids"], str) else data["children_ids"]
        data["embedding"] = json.loads(data["embedding"]) if data.get("embedding") else None
        # Convert empty strings back to None for optional fields
        if data.get("parent_id") == "":
            data["parent_id"] = None
        if data.get("error") == "":
            data["error"] = None
        if data.get("summary") == "":
            data["summary"] = None
        # Handle numeric fields that might be strings from Redis
        if data.get("depth"):
            data["depth"] = int(data["depth"])
        if data.get("duration_ms") and data["duration_ms"] != "":
            data["duration_ms"] = float(data["duration_ms"])
        elif data.get("duration_ms") == "":
            data["duration_ms"] = None
        return cls(**data)


class MindMap:
    """
    Persistent thought tree storage.
    
    Usage:
        mind = MindMap()
        
        # Start a new thought tree for a goal
        root = await mind.create_root("goal-123", "What's the weather?")
        
        # Add a thought node
        node = await mind.add_thought(
            goal_id="goal-123",
            parent_id=root.node_id,
            neuron_type="IntentClassifierNeuron",
            neuron_id="abc123",
            input_data={"goal": "What's the weather?"},
            output_data={"intent": "tool_use", "confidence": 0.95}
        )
        
        # Get the full thought tree for a goal
        tree = await mind.get_tree("goal-123")
        
        # Find similar past reasoning (semantic search)
        similar = await mind.find_similar("weather query", limit=5)
    """
    
    # Redis key patterns
    NODE_PREFIX = "dendrite:mind:node:"
    TREE_PREFIX = "dendrite:mind:tree:"
    GOAL_PREFIX = "dendrite:mind:goal:"
    INDEX_KEY = "dendrite:mind:index"
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis = redis_client
    
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            host = os.environ.get("REDIS_HOST", "localhost")
            port = int(os.environ.get("REDIS_PORT", 6379))
            self._redis = redis.Redis(host=host, port=port, decode_responses=True)
        return self._redis
    
    async def create_root(
        self,
        goal_id: str,
        goal_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ThoughtNode:
        """
        Create the root node for a goal's thought tree.
        
        Args:
            goal_id: Unique goal identifier
            goal_text: The original goal text
            metadata: Optional additional metadata
        """
        r = await self._get_redis()
        
        node = ThoughtNode(
            node_id=f"root_{goal_id}",
            goal_id=goal_id,
            neuron_type="Goal",
            neuron_id="root",
            input_data={"goal": goal_text, "metadata": metadata or {}},
            depth=0,
            status="pending"
        )
        
        # Store the node
        await r.hset(f"{self.NODE_PREFIX}{node.node_id}", mapping=node.to_dict())
        
        # Create the tree index for this goal
        await r.rpush(f"{self.TREE_PREFIX}{goal_id}", node.node_id)
        
        # Add to goal index
        await r.hset(f"{self.GOAL_PREFIX}{goal_id}", mapping={
            "goal_id": goal_id,
            "goal_text": goal_text,
            "root_node_id": node.node_id,
            "created_at": node.timestamp,
            "status": "pending"
        })
        
        # Add to global index
        await r.zadd(self.INDEX_KEY, {goal_id: datetime.utcnow().timestamp()})
        
        logger.info("mind_map_root_created", goal_id=goal_id, node_id=node.node_id)
        
        return node
    
    async def add_thought(
        self,
        goal_id: str,
        parent_id: str,
        neuron_type: str,
        neuron_id: str,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]] = None,
        thoughts: Optional[List[str]] = None,
        duration_ms: Optional[float] = None,
        status: str = "completed",
        error: Optional[str] = None
    ) -> ThoughtNode:
        """
        Add a thought node to the tree.
        
        Args:
            goal_id: The goal this thought belongs to
            parent_id: The parent node ID
            neuron_type: Type of neuron that generated this thought
            neuron_id: Instance ID of the neuron
            input_data: Input to the neuron
            output_data: Output from the neuron
            thoughts: Intermediate reasoning steps
            duration_ms: How long this thought took
            status: pending, completed, or failed
            error: Error message if failed
        """
        r = await self._get_redis()
        
        # Get parent to determine depth
        parent = await self.get_node(parent_id)
        parent_depth = parent.depth if parent else 0
        
        node = ThoughtNode(
            node_id=str(uuid.uuid4())[:12],
            goal_id=goal_id,
            neuron_type=neuron_type,
            neuron_id=neuron_id,
            input_data=input_data,
            output_data=output_data,
            thoughts=thoughts or [],
            parent_id=parent_id,
            depth=parent_depth + 1,
            duration_ms=duration_ms,
            status=status,
            error=error
        )
        
        # Store the node
        await r.hset(f"{self.NODE_PREFIX}{node.node_id}", mapping=node.to_dict())
        
        # Add to tree index
        await r.rpush(f"{self.TREE_PREFIX}{goal_id}", node.node_id)
        
        # Update parent's children list
        if parent:
            parent.children_ids.append(node.node_id)
            await r.hset(
                f"{self.NODE_PREFIX}{parent_id}",
                "children_ids",
                json.dumps(parent.children_ids)
            )
        
        logger.debug(
            "thought_added",
            goal_id=goal_id,
            node_id=node.node_id,
            neuron_type=neuron_type,
            depth=node.depth
        )
        
        return node
    
    async def update_node(
        self,
        node_id: str,
        output_data: Optional[Dict[str, Any]] = None,
        thoughts: Optional[List[str]] = None,
        duration_ms: Optional[float] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
        summary: Optional[str] = None
    ) -> Optional[ThoughtNode]:
        """Update an existing node."""
        r = await self._get_redis()
        
        node = await self.get_node(node_id)
        if not node:
            return None
        
        updates = {}
        if output_data is not None:
            node.output_data = output_data
            updates["output_data"] = json.dumps(output_data)
        if thoughts is not None:
            node.thoughts = thoughts
            updates["thoughts"] = json.dumps(thoughts)
        if duration_ms is not None:
            node.duration_ms = duration_ms
            updates["duration_ms"] = duration_ms
        if status is not None:
            node.status = status
            updates["status"] = status
        if error is not None:
            node.error = error
            updates["error"] = error
        if summary is not None:
            node.summary = summary
            updates["summary"] = summary
        
        if updates:
            await r.hset(f"{self.NODE_PREFIX}{node_id}", mapping=updates)
        
        return node
    
    async def get_node(self, node_id: str) -> Optional[ThoughtNode]:
        """Get a single node by ID."""
        r = await self._get_redis()
        
        data = await r.hgetall(f"{self.NODE_PREFIX}{node_id}")
        if not data:
            return None
        
        return ThoughtNode.from_dict(data)
    
    async def get_tree(self, goal_id: str) -> List[ThoughtNode]:
        """Get all nodes in a goal's thought tree."""
        r = await self._get_redis()
        
        node_ids = await r.lrange(f"{self.TREE_PREFIX}{goal_id}", 0, -1)
        
        nodes = []
        for node_id in node_ids:
            node = await self.get_node(node_id)
            if node:
                nodes.append(node)
        
        return nodes
    
    async def get_tree_structured(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """Get the tree as a nested structure."""
        nodes = await self.get_tree(goal_id)
        if not nodes:
            return None
        
        # Build node map
        node_map = {n.node_id: n for n in nodes}
        
        # Find root
        root = None
        for node in nodes:
            if node.parent_id is None or node.node_id.startswith("root_"):
                root = node
                break
        
        if not root:
            return None
        
        def build_subtree(node: ThoughtNode) -> Dict[str, Any]:
            return {
                "node_id": node.node_id,
                "neuron_type": node.neuron_type,
                "status": node.status,
                "input": node.input_data,
                "output": node.output_data,
                "thoughts": node.thoughts,
                "duration_ms": node.duration_ms,
                "children": [
                    build_subtree(node_map[child_id])
                    for child_id in node.children_ids
                    if child_id in node_map
                ]
            }
        
        return build_subtree(root)
    
    async def complete_goal(self, goal_id: str, result: Any = None):
        """Mark a goal's thought tree as completed."""
        r = await self._get_redis()
        
        # Update goal status
        await r.hset(f"{self.GOAL_PREFIX}{goal_id}", mapping={
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "result": json.dumps(result) if result else None
        })
        
        # Update root node
        root_id = f"root_{goal_id}"
        await self.update_node(root_id, status="completed", output_data={"result": result})
        
        logger.info("mind_map_goal_completed", goal_id=goal_id)
    
    async def fail_goal(self, goal_id: str, error: str):
        """Mark a goal's thought tree as failed."""
        r = await self._get_redis()
        
        await r.hset(f"{self.GOAL_PREFIX}{goal_id}", mapping={
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "error": error
        })
        
        root_id = f"root_{goal_id}"
        await self.update_node(root_id, status="failed", error=error)
        
        logger.info("mind_map_goal_failed", goal_id=goal_id, error=error)
    
    async def get_recent_goals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent goals ordered by creation time."""
        r = await self._get_redis()
        
        goal_ids = await r.zrevrange(self.INDEX_KEY, 0, limit - 1)
        
        goals = []
        for goal_id in goal_ids:
            goal_data = await r.hgetall(f"{self.GOAL_PREFIX}{goal_id}")
            if goal_data:
                goals.append(goal_data)
        
        return goals
    
    async def get_short_term_memory(
        self,
        goal_id: str,
        max_thoughts: int = 10
    ) -> str:
        """
        Get a short-term memory summary for a goal.
        
        This provides context for neurons to maintain continuity.
        Returns the most recent thoughts as a summary string.
        """
        tree = await self.get_tree(goal_id)
        if not tree:
            return ""
        
        # Get the most recent thoughts
        recent_nodes = sorted(tree, key=lambda n: n.timestamp, reverse=True)[:max_thoughts]
        
        memory_parts = []
        for node in reversed(recent_nodes):  # Chronological order
            if node.neuron_type == "Goal":
                memory_parts.append(f"Goal: {node.input_data.get('goal', 'Unknown')}")
            else:
                status = "✓" if node.status == "completed" else "✗" if node.status == "failed" else "..."
                thought_summary = node.summary or (node.thoughts[-1] if node.thoughts else "")
                if thought_summary:
                    memory_parts.append(f"[{node.neuron_type}] {status} {thought_summary}")
        
        return "\n".join(memory_parts)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the Mind Map."""
        r = await self._get_redis()
        
        total_goals = await r.zcard(self.INDEX_KEY)
        
        # Sample recent goals for status breakdown
        recent = await self.get_recent_goals(limit=100)
        completed = sum(1 for g in recent if g.get("status") == "completed")
        failed = sum(1 for g in recent if g.get("status") == "failed")
        pending = sum(1 for g in recent if g.get("status") == "pending")
        
        return {
            "total_goals": total_goals,
            "recent_completed": completed,
            "recent_failed": failed,
            "recent_pending": pending
        }
    
    async def clear(self):
        """Clear all mind map data (useful for testing)."""
        r = await self._get_redis()
        
        # Get all keys with our prefixes
        async for key in r.scan_iter(f"{self.NODE_PREFIX}*"):
            await r.delete(key)
        async for key in r.scan_iter(f"{self.TREE_PREFIX}*"):
            await r.delete(key)
        async for key in r.scan_iter(f"{self.GOAL_PREFIX}*"):
            await r.delete(key)
        await r.delete(self.INDEX_KEY)


# Global mind map instance
_global_mind: Optional[MindMap] = None


async def get_mind_map() -> MindMap:
    """Get the global MindMap instance."""
    global _global_mind
    if _global_mind is None:
        _global_mind = MindMap()
    return _global_mind
