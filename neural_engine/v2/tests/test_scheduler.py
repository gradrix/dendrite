"""
Tests for Scheduled Goals System.

Tests periodic execution, state persistence, conditions, and self-modification.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from neural_engine.v2.scheduler import (
    Scheduler,
    ScheduledGoal,
    GoalState,
    GoalCondition,
    ScheduleType,
    InMemoryGoalStore,
)
from neural_engine.v2.scheduler.scheduler import parse_cron, cron_matches


# ============================================================================
# CRON PARSING TESTS
# ============================================================================

class TestCronParsing:
    """Test cron expression parsing."""
    
    def test_parse_simple_cron(self):
        """Parse basic cron expression."""
        cron = parse_cron("0 8 * * *")
        assert cron["minute"] == "0"
        assert cron["hour"] == "8"
        assert cron["day"] == "*"
        assert cron["month"] == "*"
        assert cron["weekday"] == "*"
    
    def test_parse_invalid_cron(self):
        """Invalid cron raises error."""
        with pytest.raises(ValueError):
            parse_cron("0 8 *")
    
    def test_cron_matches_exact(self):
        """Cron matches exact time."""
        cron = parse_cron("30 14 * * *")  # 2:30pm
        dt = datetime(2026, 1, 18, 14, 30, 0)
        assert cron_matches(cron, dt)
        
        dt_wrong = datetime(2026, 1, 18, 14, 31, 0)
        assert not cron_matches(cron, dt_wrong)
    
    def test_cron_matches_wildcard(self):
        """Wildcard matches any value."""
        cron = parse_cron("* * * * *")  # Every minute
        assert cron_matches(cron, datetime.now())
    
    def test_cron_matches_step(self):
        """Step pattern matches."""
        cron = parse_cron("*/15 * * * *")  # Every 15 minutes
        
        assert cron_matches(cron, datetime(2026, 1, 18, 10, 0, 0))
        assert cron_matches(cron, datetime(2026, 1, 18, 10, 15, 0))
        assert cron_matches(cron, datetime(2026, 1, 18, 10, 30, 0))
        assert not cron_matches(cron, datetime(2026, 1, 18, 10, 7, 0))
    
    def test_cron_matches_weekday(self):
        """Weekday matching (Python: 0=Monday, 6=Sunday)."""
        cron = parse_cron("0 9 * * 6")  # Sunday 9am (weekday=6)
        
        # Jan 18, 2026 is a Sunday (weekday=6)
        assert cron_matches(cron, datetime(2026, 1, 18, 9, 0, 0))
        # Jan 19, 2026 is a Monday (weekday=0)
        assert not cron_matches(cron, datetime(2026, 1, 19, 9, 0, 0))


# ============================================================================
# GOAL STATE TESTS
# ============================================================================

class TestGoalState:
    """Test goal state persistence."""
    
    def test_state_serialization(self):
        """State serializes to/from dict."""
        state = GoalState(
            goal_id="test",
            run_count=5,
            last_run=datetime(2026, 1, 18, 12, 0, 0),
            last_result={"value": 42},
            data={"custom": "data"}
        )
        
        d = state.to_dict()
        restored = GoalState.from_dict(d)
        
        assert restored.goal_id == "test"
        assert restored.run_count == 5
        assert restored.last_result == {"value": 42}
        assert restored.data["custom"] == "data"
    
    def test_state_defaults(self):
        """New state has proper defaults."""
        state = GoalState(goal_id="new")
        
        assert state.run_count == 0
        assert state.last_run is None
        assert state.last_success is True
        assert state.consecutive_failures == 0
        assert state.data == {}


# ============================================================================
# SCHEDULED GOAL TESTS
# ============================================================================

class TestScheduledGoal:
    """Test scheduled goal model."""
    
    def test_goal_creation(self):
        """Create a basic goal."""
        goal = ScheduledGoal(
            id="daily_task",
            goal="Do something daily",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 8 * * *"
        )
        
        assert goal.id == "daily_task"
        assert goal.enabled is True
        assert goal.max_failures == 5
    
    def test_goal_serialization(self):
        """Goal serializes to dict."""
        goal = ScheduledGoal(
            id="test",
            goal="Test goal",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="3600",
            tags=["test", "daily"]
        )
        
        d = goal.to_dict()
        assert d["id"] == "test"
        assert d["schedule_type"] == "interval"
        assert d["tags"] == ["test", "daily"]


# ============================================================================
# SCHEDULER TESTS
# ============================================================================

class TestScheduler:
    """Test scheduler functionality."""
    
    @pytest.fixture
    def scheduler(self):
        """Create scheduler with mock executor."""
        store = InMemoryGoalStore()
        executor = Mock(return_value={"success": True, "result": "done"})
        scheduler = Scheduler(store=store, executor=executor)
        return scheduler
    
    @pytest.mark.asyncio
    async def test_add_and_get_goal(self, scheduler):
        """Add and retrieve a goal."""
        goal = ScheduledGoal(
            id="test",
            goal="Test goal"
        )
        
        await scheduler.add_goal(goal)
        retrieved = await scheduler.get_goal("test")
        
        assert retrieved is not None
        assert retrieved.id == "test"
    
    @pytest.mark.asyncio
    async def test_list_goals(self, scheduler):
        """List all goals."""
        await scheduler.add_goal(ScheduledGoal(id="g1", goal="Goal 1"))
        await scheduler.add_goal(ScheduledGoal(id="g2", goal="Goal 2", enabled=False))
        
        all_goals = await scheduler.list_goals()
        assert len(all_goals) == 2
        
        enabled = await scheduler.list_goals(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].id == "g1"
    
    @pytest.mark.asyncio
    async def test_run_now(self, scheduler):
        """Run a goal immediately."""
        goal = ScheduledGoal(id="run_test", goal="Run me")
        await scheduler.add_goal(goal)
        
        run = await scheduler.run_now("run_test")
        
        assert run.success is True
        assert run.skipped is False
        assert run.result == {"success": True, "result": "done"}
    
    @pytest.mark.asyncio
    async def test_run_updates_state(self, scheduler):
        """Running updates goal state."""
        goal = ScheduledGoal(id="state_test", goal="State test")
        await scheduler.add_goal(goal)
        
        await scheduler.run_now("state_test")
        state = await scheduler.get_state("state_test")
        
        assert state.run_count == 1
        assert state.last_run is not None
        assert state.last_success is True
        assert state.consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_run_history(self, scheduler):
        """Run history is recorded."""
        goal = ScheduledGoal(id="history_test", goal="History test")
        await scheduler.add_goal(goal)
        
        await scheduler.run_now("history_test")
        await scheduler.run_now("history_test")
        
        history = await scheduler.get_history("history_test")
        assert len(history) == 2
    
    @pytest.mark.asyncio
    async def test_failure_tracking(self, scheduler):
        """Failed runs are tracked."""
        scheduler._executor = Mock(side_effect=Exception("Boom!"))
        
        goal = ScheduledGoal(id="fail_test", goal="Will fail")
        await scheduler.add_goal(goal)
        
        run = await scheduler.run_now("fail_test")
        
        assert run.success is False
        assert "Boom!" in run.error
        
        state = await scheduler.get_state("fail_test")
        assert state.consecutive_failures == 1
        assert state.last_success is False
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, scheduler):
        """Goal disabled after max failures."""
        scheduler._executor = Mock(side_effect=Exception("Fail"))
        
        goal = ScheduledGoal(id="circuit_test", goal="Will fail", max_failures=3)
        await scheduler.add_goal(goal)
        
        for _ in range(3):
            await scheduler.run_now("circuit_test")
        
        retrieved = await scheduler.get_goal("circuit_test")
        assert retrieved.enabled is False
    
    @pytest.mark.asyncio
    async def test_condition_skip(self, scheduler):
        """Condition can skip execution."""
        condition = GoalCondition(
            name="always_skip",
            check=lambda state: True,
            action="skip",
            message="Skipped by test"
        )
        
        goal = ScheduledGoal(
            id="skip_test",
            goal="Will be skipped",
            conditions=[condition]
        )
        await scheduler.add_goal(goal)
        
        run = await scheduler.run_now("skip_test")
        
        assert run.skipped is True
        assert run.skip_reason == "Skipped by test"
        
        # Executor should not have been called
        scheduler._executor.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_condition_disable(self, scheduler):
        """Condition can disable goal."""
        condition = GoalCondition(
            name="disable_it",
            check=lambda state: True,
            action="disable"
        )
        
        goal = ScheduledGoal(
            id="disable_test",
            goal="Will be disabled",
            conditions=[condition]
        )
        await scheduler.add_goal(goal)
        
        await scheduler.run_now("disable_test")
        
        retrieved = await scheduler.get_goal("disable_test")
        assert retrieved.enabled is False
    
    @pytest.mark.asyncio
    async def test_condition_modify(self, scheduler):
        """Condition can modify goal text."""
        condition = GoalCondition(
            name="add_prefix",
            check=lambda state: True,
            action="modify",
            modifier=lambda goal, state: f"[Modified] {goal}"
        )
        
        goal = ScheduledGoal(
            id="modify_test",
            goal="Original goal",
            conditions=[condition]
        )
        await scheduler.add_goal(goal)
        
        await scheduler.run_now("modify_test")
        
        # Check the executor was called with modified text
        scheduler._executor.assert_called_once()
        call_args = scheduler._executor.call_args[0][0]
        assert call_args == "[Modified] Original goal"
    
    @pytest.mark.asyncio
    async def test_force_run_skips_conditions(self, scheduler):
        """Force run ignores conditions."""
        condition = GoalCondition(
            name="always_skip",
            check=lambda state: True,
            action="skip"
        )
        
        goal = ScheduledGoal(
            id="force_test",
            goal="Force me",
            conditions=[condition]
        )
        await scheduler.add_goal(goal)
        
        run = await scheduler.run_now("force_test", force=True)
        
        assert run.skipped is False
        scheduler._executor.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_complete_callback(self, scheduler):
        """on_complete callback is called."""
        callback_data = {}
        
        def on_complete(state, result):
            callback_data["called"] = True
            callback_data["run_count"] = state.run_count
            state.data["custom"] = "value"
        
        goal = ScheduledGoal(
            id="callback_test",
            goal="Callback test",
            on_complete=on_complete
        )
        await scheduler.add_goal(goal)
        
        await scheduler.run_now("callback_test")
        
        assert callback_data["called"] is True
        assert callback_data["run_count"] == 1
        
        state = await scheduler.get_state("callback_test")
        assert state.data["custom"] == "value"
    
    @pytest.mark.asyncio
    async def test_max_runs_limit(self, scheduler):
        """Goal disabled after max runs."""
        goal = ScheduledGoal(
            id="max_runs_test",
            goal="Limited runs",
            max_runs=2
        )
        await scheduler.add_goal(goal)
        
        await scheduler.run_now("max_runs_test")
        await scheduler.run_now("max_runs_test")
        
        retrieved = await scheduler.get_goal("max_runs_test")
        assert retrieved.enabled is False
    
    @pytest.mark.asyncio
    async def test_interval_schedule(self, scheduler):
        """Interval schedule triggers correctly."""
        goal = ScheduledGoal(
            id="interval_test",
            goal="Every hour",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="3600"  # 1 hour
        )
        await scheduler.add_goal(goal)
        
        # Should run first time (never run before)
        state = await scheduler.get_state("interval_test")
        assert scheduler._should_run(goal, state) is True
        
        # After running, shouldn't run again immediately
        await scheduler.run_now("interval_test")
        state = await scheduler.get_state("interval_test")
        assert scheduler._should_run(goal, state) is False
    
    @pytest.mark.asyncio
    async def test_once_schedule(self, scheduler):
        """Once schedule only runs once."""
        goal = ScheduledGoal(
            id="once_test",
            goal="Run once",
            schedule_type=ScheduleType.ONCE
        )
        await scheduler.add_goal(goal)
        
        state = await scheduler.get_state("once_test")
        assert scheduler._should_run(goal, state) is True
        
        await scheduler.run_now("once_test")
        state = await scheduler.get_state("once_test")
        assert scheduler._should_run(goal, state) is False
    
    @pytest.mark.asyncio
    async def test_on_demand_never_auto_runs(self, scheduler):
        """On-demand goals don't auto-run."""
        goal = ScheduledGoal(
            id="ondemand_test",
            goal="Manual only",
            schedule_type=ScheduleType.ON_DEMAND
        )
        await scheduler.add_goal(goal)
        
        state = await scheduler.get_state("ondemand_test")
        assert scheduler._should_run(goal, state) is False
    
    @pytest.mark.asyncio
    async def test_update_state(self, scheduler):
        """Update state data."""
        goal = ScheduledGoal(id="update_test", goal="Test")
        await scheduler.add_goal(goal)
        
        await scheduler.update_state("update_test", key1="value1", key2=42)
        
        state = await scheduler.get_state("update_test")
        assert state.data["key1"] == "value1"
        assert state.data["key2"] == 42
    
    @pytest.mark.asyncio
    async def test_enable_disable_goal(self, scheduler):
        """Enable and disable goals."""
        goal = ScheduledGoal(id="toggle_test", goal="Test")
        await scheduler.add_goal(goal)
        
        await scheduler.disable_goal("toggle_test")
        retrieved = await scheduler.get_goal("toggle_test")
        assert retrieved.enabled is False
        
        await scheduler.enable_goal("toggle_test")
        retrieved = await scheduler.get_goal("toggle_test")
        assert retrieved.enabled is True
    
    @pytest.mark.asyncio
    async def test_remove_goal(self, scheduler):
        """Remove a goal."""
        goal = ScheduledGoal(id="remove_test", goal="Test")
        await scheduler.add_goal(goal)
        
        removed = await scheduler.remove_goal("remove_test")
        assert removed is True
        
        retrieved = await scheduler.get_goal("remove_test")
        assert retrieved is None


# ============================================================================
# SELF-MODIFYING GOAL TESTS
# ============================================================================

class TestSelfModifyingGoals:
    """Test goals that modify themselves based on previous results."""
    
    @pytest.mark.asyncio
    async def test_goal_adapts_based_on_state(self):
        """Goal modifies itself based on accumulated state."""
        store = InMemoryGoalStore()
        
        # Track what goals were executed
        executed_goals = []
        def executor(goal_text):
            executed_goals.append(goal_text)
            return {"success": True}
        
        scheduler = Scheduler(store=store, executor=executor)
        
        # Condition that modifies goal based on run count
        condition = GoalCondition(
            name="progressive_difficulty",
            check=lambda state: state.run_count > 0,  # After first run
            action="modify",
            modifier=lambda goal, state: f"{goal} (level {state.run_count + 1})"
        )
        
        goal = ScheduledGoal(
            id="adaptive",
            goal="Process data",
            conditions=[condition]
        )
        await scheduler.add_goal(goal)
        
        # First run - no modification
        await scheduler.run_now("adaptive")
        assert executed_goals[-1] == "Process data"
        
        # Second run - modified
        await scheduler.run_now("adaptive")
        assert executed_goals[-1] == "Process data (level 2)"
        
        # Third run
        await scheduler.run_now("adaptive")
        assert executed_goals[-1] == "Process data (level 3)"
    
    @pytest.mark.asyncio
    async def test_goal_skips_based_on_previous_result(self):
        """Goal skips if previous result indicates no work needed."""
        store = InMemoryGoalStore()
        
        # First run returns no data, second would have data
        call_count = [0]
        def executor(goal_text):
            call_count[0] += 1
            # First call: no new data. If we get a second call, it has data.
            has_new_data = call_count[0] > 1
            return {"success": True, "has_new_data": has_new_data}
        
        scheduler = Scheduler(store=store, executor=executor)
        
        # Skip if last result had no new data
        condition = GoalCondition(
            name="skip_if_no_data",
            check=lambda state: (
                state.last_result is not None and 
                not state.last_result.get("has_new_data", True)
            ),
            action="skip",
            message="No new data to process"
        )
        
        goal = ScheduledGoal(
            id="data_processor",
            goal="Process new data",
            conditions=[condition]
        )
        await scheduler.add_goal(goal)
        
        # First run - executes (no prior result to check)
        run1 = await scheduler.run_now("data_processor")
        assert run1.skipped is False
        
        # Second run - skipped (last result had has_new_data=False)
        run2 = await scheduler.run_now("data_processor")
        assert run2.skipped is True
        assert "No new data" in run2.skip_reason
    
    @pytest.mark.asyncio
    async def test_goal_accumulates_data_across_runs(self):
        """Goal accumulates data in state across multiple runs."""
        store = InMemoryGoalStore()
        
        # Simulate returning different data each time
        run_data = [
            {"items": ["a", "b"]},
            {"items": ["c", "d"]},
            {"items": ["e"]},
        ]
        call_idx = [0]
        
        def executor(goal_text):
            result = run_data[min(call_idx[0], len(run_data) - 1)]
            call_idx[0] += 1
            return {"success": True, **result}
        
        scheduler = Scheduler(store=store, executor=executor)
        
        # Accumulate all items across runs
        def on_complete(state, result):
            if "all_items" not in state.data:
                state.data["all_items"] = []
            state.data["all_items"].extend(result.get("items", []))
        
        goal = ScheduledGoal(
            id="accumulator",
            goal="Collect items",
            on_complete=on_complete
        )
        await scheduler.add_goal(goal)
        
        await scheduler.run_now("accumulator")
        await scheduler.run_now("accumulator")
        await scheduler.run_now("accumulator")
        
        state = await scheduler.get_state("accumulator")
        assert state.data["all_items"] == ["a", "b", "c", "d", "e"]
