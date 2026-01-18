"""
Scheduled Goals System - v2

Provides periodic goal execution with:
- Cron-like scheduling
- State persistence between runs
- Goal conditions (skip/modify based on previous results)
- Self-modifying goals
"""

from .models import ScheduledGoal, GoalState, GoalCondition, ScheduleType, ScheduledRun
from .scheduler import Scheduler
from .store import GoalStore, InMemoryGoalStore, RedisGoalStore

__all__ = [
    'ScheduledGoal',
    'GoalState', 
    'GoalCondition',
    'ScheduleType',
    'ScheduledRun',
    'Scheduler',
    'GoalStore',
    'InMemoryGoalStore',
    'RedisGoalStore',
]
