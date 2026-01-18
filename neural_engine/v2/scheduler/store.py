"""
Goal Store - Persistent storage for scheduled goals and state.

Uses Redis for production, in-memory for testing.
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .models import ScheduledGoal, GoalState, ScheduledRun, GoalCondition


class GoalStore(ABC):
    """Abstract base for goal persistence."""
    
    @abstractmethod
    async def save_goal(self, goal: ScheduledGoal) -> None:
        """Save or update a scheduled goal."""
        pass
    
    @abstractmethod
    async def get_goal(self, goal_id: str) -> Optional[ScheduledGoal]:
        """Get a scheduled goal by ID."""
        pass
    
    @abstractmethod
    async def list_goals(self, enabled_only: bool = False, tags: Optional[list[str]] = None) -> list[ScheduledGoal]:
        """List all scheduled goals."""
        pass
    
    @abstractmethod
    async def delete_goal(self, goal_id: str) -> bool:
        """Delete a scheduled goal."""
        pass
    
    @abstractmethod
    async def get_state(self, goal_id: str) -> GoalState:
        """Get state for a goal (creates if not exists)."""
        pass
    
    @abstractmethod
    async def save_state(self, state: GoalState) -> None:
        """Save goal state."""
        pass
    
    @abstractmethod
    async def save_run(self, run: ScheduledRun) -> None:
        """Save a run record."""
        pass
    
    @abstractmethod
    async def get_runs(self, goal_id: str, limit: int = 10) -> list[ScheduledRun]:
        """Get recent runs for a goal."""
        pass


class InMemoryGoalStore(GoalStore):
    """In-memory store for testing."""
    
    def __init__(self):
        self._goals: dict[str, ScheduledGoal] = {}
        self._states: dict[str, GoalState] = {}
        self._runs: dict[str, list[ScheduledRun]] = {}
    
    async def save_goal(self, goal: ScheduledGoal) -> None:
        self._goals[goal.id] = goal
    
    async def get_goal(self, goal_id: str) -> Optional[ScheduledGoal]:
        return self._goals.get(goal_id)
    
    async def list_goals(self, enabled_only: bool = False, tags: Optional[list[str]] = None) -> list[ScheduledGoal]:
        goals = list(self._goals.values())
        if enabled_only:
            goals = [g for g in goals if g.enabled]
        if tags:
            goals = [g for g in goals if any(t in g.tags for t in tags)]
        return goals
    
    async def delete_goal(self, goal_id: str) -> bool:
        if goal_id in self._goals:
            del self._goals[goal_id]
            return True
        return False
    
    async def get_state(self, goal_id: str) -> GoalState:
        if goal_id not in self._states:
            self._states[goal_id] = GoalState(goal_id=goal_id)
        return self._states[goal_id]
    
    async def save_state(self, state: GoalState) -> None:
        self._states[state.goal_id] = state
    
    async def save_run(self, run: ScheduledRun) -> None:
        if run.goal_id not in self._runs:
            self._runs[run.goal_id] = []
        self._runs[run.goal_id].insert(0, run)
        # Keep only last 100 runs per goal
        self._runs[run.goal_id] = self._runs[run.goal_id][:100]
    
    async def get_runs(self, goal_id: str, limit: int = 10) -> list[ScheduledRun]:
        runs = self._runs.get(goal_id, [])
        return runs[:limit]
    
    def clear(self):
        """Clear all data (for testing)."""
        self._goals.clear()
        self._states.clear()
        self._runs.clear()


class RedisGoalStore(GoalStore):
    """Redis-backed store for production."""
    
    def __init__(self, redis_client, prefix: str = "scheduler"):
        self._redis = redis_client
        self._prefix = prefix
        # Registry for condition factories (conditions can't be serialized)
        self._condition_registry: dict[str, GoalCondition] = {}
    
    def register_condition(self, condition: GoalCondition):
        """Register a reusable condition."""
        self._condition_registry[condition.name] = condition
    
    def _goal_key(self, goal_id: str) -> str:
        return f"{self._prefix}:goal:{goal_id}"
    
    def _state_key(self, goal_id: str) -> str:
        return f"{self._prefix}:state:{goal_id}"
    
    def _runs_key(self, goal_id: str) -> str:
        return f"{self._prefix}:runs:{goal_id}"
    
    def _goals_index_key(self) -> str:
        return f"{self._prefix}:goals"
    
    async def save_goal(self, goal: ScheduledGoal) -> None:
        key = self._goal_key(goal.id)
        await self._redis.set(key, json.dumps(goal.to_dict()))
        await self._redis.sadd(self._goals_index_key(), goal.id)
    
    async def get_goal(self, goal_id: str) -> Optional[ScheduledGoal]:
        key = self._goal_key(goal_id)
        data = await self._redis.get(key)
        if not data:
            return None
        
        d = json.loads(data)
        # Restore conditions from registry
        condition_names = d.get("condition_names", [])
        conditions = [self._condition_registry[n] for n in condition_names if n in self._condition_registry]
        
        return ScheduledGoal.from_dict(d, conditions)
    
    async def list_goals(self, enabled_only: bool = False, tags: Optional[list[str]] = None) -> list[ScheduledGoal]:
        goal_ids = await self._redis.smembers(self._goals_index_key())
        goals = []
        for goal_id in goal_ids:
            goal = await self.get_goal(goal_id)
            if goal:
                if enabled_only and not goal.enabled:
                    continue
                if tags and not any(t in goal.tags for t in tags):
                    continue
                goals.append(goal)
        return goals
    
    async def delete_goal(self, goal_id: str) -> bool:
        key = self._goal_key(goal_id)
        deleted = await self._redis.delete(key)
        await self._redis.srem(self._goals_index_key(), goal_id)
        return deleted > 0
    
    async def get_state(self, goal_id: str) -> GoalState:
        key = self._state_key(goal_id)
        data = await self._redis.get(key)
        if not data:
            return GoalState(goal_id=goal_id)
        return GoalState.from_dict(json.loads(data))
    
    async def save_state(self, state: GoalState) -> None:
        key = self._state_key(state.goal_id)
        await self._redis.set(key, json.dumps(state.to_dict()))
    
    async def save_run(self, run: ScheduledRun) -> None:
        key = self._runs_key(run.goal_id)
        await self._redis.lpush(key, json.dumps(run.to_dict()))
        await self._redis.ltrim(key, 0, 99)  # Keep last 100
    
    async def get_runs(self, goal_id: str, limit: int = 10) -> list[ScheduledRun]:
        key = self._runs_key(goal_id)
        data = await self._redis.lrange(key, 0, limit - 1)
        runs = []
        for item in data:
            d = json.loads(item)
            runs.append(ScheduledRun(
                goal_id=d["goal_id"],
                run_id=d["run_id"],
                started_at=datetime.fromisoformat(d["started_at"]),
                completed_at=datetime.fromisoformat(d["completed_at"]) if d.get("completed_at") else None,
                success=d.get("success", False),
                result=d.get("result"),
                error=d.get("error"),
                skipped=d.get("skipped", False),
                skip_reason=d.get("skip_reason"),
            ))
        return runs
