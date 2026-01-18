"""
Scheduler - Runs goals on schedule with state persistence.

Features:
- Cron and interval scheduling
- Condition checking before runs
- State persistence between runs
- Goal self-modification
- Circuit breaker for failing goals
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Callable, Optional
import logging

from .models import ScheduledGoal, GoalState, ScheduledRun, ScheduleType
from .store import GoalStore, InMemoryGoalStore

logger = logging.getLogger(__name__)


def parse_cron(expr: str) -> dict:
    """
    Parse simple cron expression.
    Format: minute hour day_of_month month day_of_week
    Supports: *, */N, N
    """
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expr}")
    
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "weekday": parts[4],
    }


def cron_matches(cron: dict, dt: datetime) -> bool:
    """Check if datetime matches cron expression."""
    def matches_field(field: str, value: int) -> bool:
        if field == "*":
            return True
        if field.startswith("*/"):
            step = int(field[2:])
            return value % step == 0
        if "," in field:
            return value in [int(x) for x in field.split(",")]
        if "-" in field:
            start, end = map(int, field.split("-"))
            return start <= value <= end
        return int(field) == value
    
    return (
        matches_field(cron["minute"], dt.minute) and
        matches_field(cron["hour"], dt.hour) and
        matches_field(cron["day"], dt.day) and
        matches_field(cron["month"], dt.month) and
        matches_field(cron["weekday"], dt.weekday())
    )


class Scheduler:
    """
    Goal scheduler with persistent state.
    
    Example usage:
        scheduler = Scheduler(store, orchestrator.process)
        
        # Add a periodic goal
        await scheduler.add_goal(ScheduledGoal(
            id="daily_summary",
            goal="Summarize my activities today",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 18 * * *",  # 6pm daily
        ))
        
        # Start scheduler loop
        await scheduler.start()
        
        # Or run a specific goal immediately
        result = await scheduler.run_now("daily_summary")
    """
    
    def __init__(
        self,
        store: Optional[GoalStore] = None,
        executor: Optional[Callable[[str], dict]] = None,
        check_interval: int = 60,  # seconds
    ):
        self.store = store or InMemoryGoalStore()
        self._executor = executor
        self._check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_check: dict[str, datetime] = {}  # goal_id -> last check time
    
    def set_executor(self, executor: Callable[[str], dict]):
        """Set the goal executor (usually orchestrator.process)."""
        self._executor = executor
    
    async def add_goal(self, goal: ScheduledGoal) -> None:
        """Add or update a scheduled goal."""
        await self.store.save_goal(goal)
        logger.info(f"Added goal: {goal.id}")
    
    async def remove_goal(self, goal_id: str) -> bool:
        """Remove a scheduled goal."""
        return await self.store.delete_goal(goal_id)
    
    async def get_goal(self, goal_id: str) -> Optional[ScheduledGoal]:
        """Get a goal by ID."""
        return await self.store.get_goal(goal_id)
    
    async def list_goals(self, enabled_only: bool = False) -> list[ScheduledGoal]:
        """List all goals."""
        return await self.store.list_goals(enabled_only=enabled_only)
    
    async def get_state(self, goal_id: str) -> GoalState:
        """Get state for a goal."""
        return await self.store.get_state(goal_id)
    
    async def update_state(self, goal_id: str, **updates) -> GoalState:
        """Update goal state data."""
        state = await self.store.get_state(goal_id)
        state.data.update(updates)
        await self.store.save_state(state)
        return state
    
    async def get_history(self, goal_id: str, limit: int = 10) -> list[ScheduledRun]:
        """Get run history for a goal."""
        return await self.store.get_runs(goal_id, limit)
    
    async def enable_goal(self, goal_id: str) -> bool:
        """Enable a disabled goal."""
        goal = await self.store.get_goal(goal_id)
        if not goal:
            return False
        goal.enabled = True
        await self.store.save_goal(goal)
        # Reset failure counter
        state = await self.store.get_state(goal_id)
        state.consecutive_failures = 0
        await self.store.save_state(state)
        return True
    
    async def disable_goal(self, goal_id: str) -> bool:
        """Disable a goal."""
        goal = await self.store.get_goal(goal_id)
        if not goal:
            return False
        goal.enabled = False
        await self.store.save_goal(goal)
        return True
    
    async def run_now(self, goal_id: str, force: bool = False) -> ScheduledRun:
        """
        Run a goal immediately.
        
        Args:
            goal_id: The goal to run
            force: If True, skip condition checks
        
        Returns:
            ScheduledRun with results
        """
        goal = await self.store.get_goal(goal_id)
        if not goal:
            raise ValueError(f"Goal not found: {goal_id}")
        
        return await self._execute_goal(goal, force_run=force)
    
    async def _execute_goal(self, goal: ScheduledGoal, force_run: bool = False) -> ScheduledRun:
        """Execute a single goal with full lifecycle."""
        run = ScheduledRun(
            goal_id=goal.id,
            run_id=str(uuid.uuid4()),
            started_at=datetime.now(),
        )
        
        state = await self.store.get_state(goal.id)
        goal_text = goal.goal
        
        # Check conditions (unless forced)
        if not force_run:
            for condition in goal.conditions:
                try:
                    if condition.check(state):
                        if condition.action == "skip":
                            run.skipped = True
                            run.skip_reason = condition.message or f"Condition: {condition.name}"
                            run.completed_at = datetime.now()
                            await self.store.save_run(run)
                            logger.info(f"Skipped {goal.id}: {run.skip_reason}")
                            return run
                        
                        elif condition.action == "disable":
                            goal.enabled = False
                            await self.store.save_goal(goal)
                            run.skipped = True
                            run.skip_reason = f"Disabled by condition: {condition.name}"
                            run.completed_at = datetime.now()
                            await self.store.save_run(run)
                            logger.warning(f"Disabled {goal.id}: {condition.name}")
                            return run
                        
                        elif condition.action == "modify" and condition.modifier:
                            goal_text = condition.modifier(goal_text, state)
                            logger.info(f"Modified goal {goal.id} by condition {condition.name}")
                
                except Exception as e:
                    logger.error(f"Condition {condition.name} failed: {e}")
        
        # Execute
        if not self._executor:
            raise RuntimeError("No executor set. Call set_executor() first.")
        
        try:
            # Run the goal
            result = self._executor(goal_text)
            
            # Handle async executor
            if asyncio.iscoroutine(result):
                result = await result
            
            run.success = result.get("success", True) if isinstance(result, dict) else True
            run.result = result if isinstance(result, dict) else {"response": str(result)}
            run.completed_at = datetime.now()
            
            # Update state
            state.run_count += 1
            state.last_run = datetime.now()
            state.last_result = run.result
            state.last_success = run.success
            
            if run.success:
                state.consecutive_failures = 0
            else:
                state.consecutive_failures += 1
            
            # Call on_complete hook
            if goal.on_complete:
                try:
                    goal.on_complete(state, run.result)
                except Exception as e:
                    logger.error(f"on_complete hook failed: {e}")
            
            # Check max runs
            if goal.max_runs and state.run_count >= goal.max_runs:
                goal.enabled = False
                await self.store.save_goal(goal)
                logger.info(f"Goal {goal.id} reached max_runs ({goal.max_runs})")
            
        except Exception as e:
            run.success = False
            run.error = str(e)
            run.completed_at = datetime.now()
            
            state.run_count += 1
            state.last_run = datetime.now()
            state.last_success = False
            state.consecutive_failures += 1
            
            # Call on_error hook
            if goal.on_error:
                try:
                    goal.on_error(state, e)
                except Exception as hook_err:
                    logger.error(f"on_error hook failed: {hook_err}")
            
            # Circuit breaker
            if state.consecutive_failures >= goal.max_failures:
                goal.enabled = False
                await self.store.save_goal(goal)
                logger.warning(f"Goal {goal.id} disabled: {goal.max_failures} consecutive failures")
            
            logger.error(f"Goal {goal.id} failed: {e}")
        
        # Persist
        await self.store.save_state(state)
        await self.store.save_run(run)
        
        return run
    
    def _should_run(self, goal: ScheduledGoal, state: GoalState) -> bool:
        """Check if goal should run based on schedule."""
        if not goal.enabled:
            return False
        
        now = datetime.now()
        
        if goal.schedule_type == ScheduleType.ONCE:
            # Run once if never run
            return state.run_count == 0
        
        elif goal.schedule_type == ScheduleType.INTERVAL:
            if not goal.schedule_value:
                return False
            interval = int(goal.schedule_value)
            if not state.last_run:
                return True
            return (now - state.last_run).total_seconds() >= interval
        
        elif goal.schedule_type == ScheduleType.CRON:
            if not goal.schedule_value:
                return False
            
            try:
                cron = parse_cron(goal.schedule_value)
            except ValueError:
                logger.error(f"Invalid cron for {goal.id}: {goal.schedule_value}")
                return False
            
            # Only run if we match the current minute and haven't run this minute
            if cron_matches(cron, now):
                last_check = self._last_check.get(goal.id)
                if not last_check or (now - last_check).total_seconds() >= 60:
                    self._last_check[goal.id] = now
                    return True
            return False
        
        elif goal.schedule_type == ScheduleType.ON_DEMAND:
            return False  # Only via run_now()
        
        return False
    
    async def check_and_run(self) -> list[ScheduledRun]:
        """Check all goals and run those that are due."""
        goals = await self.store.list_goals(enabled_only=True)
        runs = []
        
        for goal in goals:
            state = await self.store.get_state(goal.id)
            if self._should_run(goal, state):
                logger.info(f"Running scheduled goal: {goal.id}")
                run = await self._execute_goal(goal)
                runs.append(run)
        
        return runs
    
    async def start(self):
        """Start the scheduler loop."""
        if self._running:
            return
        
        self._running = True
        logger.info(f"Scheduler started (check interval: {self._check_interval}s)")
        
        while self._running:
            try:
                await self.check_and_run()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            await asyncio.sleep(self._check_interval)
    
    async def start_background(self):
        """Start scheduler as a background task."""
        self._task = asyncio.create_task(self.start())
        return self._task
    
    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")
