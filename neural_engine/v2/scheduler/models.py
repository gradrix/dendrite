"""
Scheduled Goal Models

Dataclasses for defining periodic goals with state and conditions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
import json


class ScheduleType(Enum):
    """How often to run the goal."""
    ONCE = "once"           # Run once at scheduled time
    INTERVAL = "interval"   # Run every N seconds
    CRON = "cron"           # Cron expression
    ON_DEMAND = "on_demand" # Manual trigger only


@dataclass
class GoalState:
    """
    Persistent state for a scheduled goal.
    
    Accessible in goal execution and conditions.
    Persisted between runs.
    """
    goal_id: str
    run_count: int = 0
    last_run: Optional[datetime] = None
    last_result: Optional[dict] = None
    last_success: bool = True
    consecutive_failures: int = 0
    
    # User-defined state (any JSON-serializable data)
    data: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "run_count": self.run_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_result": self.last_result,
            "last_success": self.last_success,
            "consecutive_failures": self.consecutive_failures,
            "data": self.data,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "GoalState":
        return cls(
            goal_id=d["goal_id"],
            run_count=d.get("run_count", 0),
            last_run=datetime.fromisoformat(d["last_run"]) if d.get("last_run") else None,
            last_result=d.get("last_result"),
            last_success=d.get("last_success", True),
            consecutive_failures=d.get("consecutive_failures", 0),
            data=d.get("data", {}),
        )


@dataclass
class GoalCondition:
    """
    Condition to check before running a goal.
    
    Examples:
        # Skip if last run was successful and data unchanged
        GoalCondition(
            name="skip_if_unchanged",
            check=lambda state: state.data.get("hash") == compute_current_hash(),
            action="skip"
        )
        
        # Disable after 5 consecutive failures
        GoalCondition(
            name="circuit_breaker",
            check=lambda state: state.consecutive_failures >= 5,
            action="disable"
        )
    """
    name: str
    check: Callable[[GoalState], bool]  # Returns True if condition is met
    action: str = "skip"  # "skip", "disable", "modify", "alert"
    message: Optional[str] = None
    
    # For "modify" action - transform the goal text
    modifier: Optional[Callable[[str, GoalState], str]] = None


@dataclass
class ScheduledGoal:
    """
    A goal scheduled for periodic execution.
    
    Example:
        goal = ScheduledGoal(
            id="daily_strava_sync",
            goal="Check my Strava activities and summarize new ones",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 8 * * *",  # 8am daily
            conditions=[
                GoalCondition(
                    name="skip_weekends",
                    check=lambda s: datetime.now().weekday() >= 5,
                    action="skip",
                    message="Skipping weekend"
                )
            ],
            on_complete=lambda state, result: state.data.update({
                "last_activity_count": result.get("activity_count", 0)
            })
        )
    """
    id: str
    goal: str  # The goal text to execute
    
    # Scheduling
    schedule_type: ScheduleType = ScheduleType.ON_DEMAND
    schedule_value: Optional[str] = None  # Cron expr or interval seconds
    
    # Conditions (checked before each run)
    conditions: list[GoalCondition] = field(default_factory=list)
    
    # Callbacks
    on_complete: Optional[Callable[[GoalState, dict], None]] = None
    on_error: Optional[Callable[[GoalState, Exception], None]] = None
    
    # Metadata
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)
    
    # Limits
    max_runs: Optional[int] = None  # Disable after N runs
    max_failures: int = 5  # Disable after N consecutive failures
    
    def to_dict(self) -> dict:
        """Serialize to dict (excludes callables)."""
        return {
            "id": self.id,
            "goal": self.goal,
            "schedule_type": self.schedule_type.value,
            "schedule_value": self.schedule_value,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "max_runs": self.max_runs,
            "max_failures": self.max_failures,
            "condition_names": [c.name for c in self.conditions],
        }
    
    @classmethod
    def from_dict(cls, d: dict, conditions: Optional[list[GoalCondition]] = None) -> "ScheduledGoal":
        """Deserialize from dict. Conditions must be provided separately."""
        return cls(
            id=d["id"],
            goal=d["goal"],
            schedule_type=ScheduleType(d.get("schedule_type", "on_demand")),
            schedule_value=d.get("schedule_value"),
            conditions=conditions or [],
            enabled=d.get("enabled", True),
            created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else datetime.now(),
            tags=d.get("tags", []),
            max_runs=d.get("max_runs"),
            max_failures=d.get("max_failures", 5),
        )


@dataclass
class ScheduledRun:
    """Record of a single goal execution."""
    goal_id: str
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    result: Optional[dict] = None
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    
    @property
    def duration_ms(self) -> Optional[int]:
        if self.completed_at and self.started_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None
    
    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "duration_ms": self.duration_ms,
        }
