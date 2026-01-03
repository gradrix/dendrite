"""
Integration tests for the Scheduler.

These tests verify that the Redis-based scheduler works correctly.
"""

import pytest
import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock


# Check if we can import scheduler (croniter must be available)
try:
    from neural_engine.core.scheduler import (
        Scheduler,
        ScheduledJob,
        JobType,
        JobStatus,
        schedule_once,
        schedule_recurring,
    )
    SCHEDULER_AVAILABLE = True
except ImportError as e:
    SCHEDULER_AVAILABLE = False
    IMPORT_ERROR = str(e)


# Check if Redis is available
def check_redis_available() -> bool:
    """Check if Redis is reachable."""
    try:
        import redis
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", 6379))
        r = redis.Redis(host=host, port=port, socket_timeout=2)
        r.ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def redis_available():
    """Skip tests if Redis is not available."""
    if not check_redis_available():
        pytest.skip("Redis not available")
    yield True


@pytest.fixture
def scheduler(redis_available):
    """Create a scheduler instance for testing."""
    if not SCHEDULER_AVAILABLE:
        pytest.skip(f"Scheduler not available: {IMPORT_ERROR}")
    
    async def dummy_executor(goal: str):
        return f"Executed: {goal}"
    
    return Scheduler(goal_executor=dummy_executor)


@pytest.fixture
async def clean_scheduler(scheduler):
    """Scheduler with cleanup after test."""
    # Clear any existing jobs from previous tests
    r = await scheduler._get_redis()
    await r.delete(scheduler.JOBS_KEY)
    await r.delete(scheduler.SCHEDULE_KEY)
    await r.delete(scheduler.HISTORY_KEY)
    
    yield scheduler
    
    # Cleanup
    await r.delete(scheduler.JOBS_KEY)
    await r.delete(scheduler.SCHEDULE_KEY)
    await r.delete(scheduler.HISTORY_KEY)


class TestSchedulerBasic:
    """Test basic scheduler operations."""
    
    @pytest.mark.asyncio
    async def test_schedule_one_time_job(self, clean_scheduler):
        """Test scheduling a one-time job."""
        run_at = datetime.now() + timedelta(hours=1)
        
        job_id = await clean_scheduler.schedule_goal(
            goal="Test one-time job",
            run_at=run_at
        )
        
        assert job_id is not None
        assert len(job_id) == 8  # UUID prefix
        
        # Verify job was stored
        job = await clean_scheduler.get_job(job_id)
        assert job is not None
        assert job.goal == "Test one-time job"
        assert job.job_type == JobType.ONE_TIME
        assert job.status == JobStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_schedule_recurring_job(self, clean_scheduler):
        """Test scheduling a recurring job with cron expression."""
        job_id = await clean_scheduler.schedule_goal(
            goal="Test recurring job",
            cron_expression="0 * * * *"  # Every hour
        )
        
        assert job_id is not None
        
        job = await clean_scheduler.get_job(job_id)
        assert job is not None
        assert job.goal == "Test recurring job"
        assert job.job_type == JobType.RECURRING
        assert job.cron_expression == "0 * * * *"
        assert job.next_run is not None
    
    @pytest.mark.asyncio
    async def test_schedule_with_max_runs(self, clean_scheduler):
        """Test scheduling with max_runs limit."""
        job_id = await clean_scheduler.schedule_goal(
            goal="Limited job",
            cron_expression="*/5 * * * *",  # Every 5 minutes
            max_runs=3
        )
        
        job = await clean_scheduler.get_job(job_id)
        assert job.max_runs == 3
    
    @pytest.mark.asyncio
    async def test_cancel_job(self, clean_scheduler):
        """Test cancelling a scheduled job."""
        run_at = datetime.now() + timedelta(hours=1)
        job_id = await clean_scheduler.schedule_goal(
            goal="Job to cancel",
            run_at=run_at
        )
        
        # Cancel it
        success = await clean_scheduler.cancel_job(job_id)
        assert success is True
        
        # Verify it's cancelled
        job = await clean_scheduler.get_job(job_id)
        assert job.status == JobStatus.CANCELLED
        assert job.next_run is None
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, clean_scheduler):
        """Test cancelling a job that doesn't exist."""
        success = await clean_scheduler.cancel_job("nonexistent")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_list_jobs(self, clean_scheduler):
        """Test listing all jobs."""
        # Create multiple jobs
        await clean_scheduler.schedule_goal(
            goal="Job 1",
            run_at=datetime.now() + timedelta(hours=1)
        )
        await clean_scheduler.schedule_goal(
            goal="Job 2",
            run_at=datetime.now() + timedelta(hours=2)
        )
        
        jobs = await clean_scheduler.list_jobs()
        assert len(jobs) >= 2
    
    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status(self, clean_scheduler):
        """Test listing jobs filtered by status."""
        # Create and cancel a job
        job_id = await clean_scheduler.schedule_goal(
            goal="Cancelled job",
            run_at=datetime.now() + timedelta(hours=1)
        )
        await clean_scheduler.cancel_job(job_id)
        
        # Create a pending job
        await clean_scheduler.schedule_goal(
            goal="Pending job",
            run_at=datetime.now() + timedelta(hours=2)
        )
        
        # List only pending
        pending_jobs = await clean_scheduler.list_jobs(status=JobStatus.PENDING)
        assert all(j.status == JobStatus.PENDING for j in pending_jobs)
        
        # List only cancelled
        cancelled_jobs = await clean_scheduler.list_jobs(status=JobStatus.CANCELLED)
        assert all(j.status == JobStatus.CANCELLED for j in cancelled_jobs)


class TestSchedulerExecution:
    """Test scheduler job execution."""
    
    @pytest.mark.asyncio
    async def test_get_due_jobs(self, clean_scheduler):
        """Test getting jobs that are due to run."""
        # Create a job due now
        past_time = datetime.now() - timedelta(seconds=10)
        job_id = await clean_scheduler.schedule_goal(
            goal="Due job",
            run_at=past_time
        )
        
        # Override next_run to be in the past
        job = await clean_scheduler.get_job(job_id)
        r = await clean_scheduler._get_redis()
        await r.zadd(clean_scheduler.SCHEDULE_KEY, {job_id: past_time.timestamp()})
        
        due_jobs = await clean_scheduler.get_due_jobs()
        assert len(due_jobs) >= 1
        assert any(j.job_id == job_id for j in due_jobs)
    
    @pytest.mark.asyncio
    async def test_get_stats(self, clean_scheduler):
        """Test getting scheduler statistics."""
        # Create some jobs
        await clean_scheduler.schedule_goal(
            goal="Stats job 1",
            run_at=datetime.now() + timedelta(hours=1)
        )
        
        stats = await clean_scheduler.get_stats()
        
        assert "total_jobs" in stats
        assert "pending" in stats
        assert "running" in stats
        assert "completed" in stats
        assert "recurring" in stats
        assert "one_time" in stats
        assert stats["total_jobs"] >= 1
    
    @pytest.mark.asyncio
    async def test_start_stop_scheduler(self, clean_scheduler):
        """Test starting and stopping the scheduler."""
        # Start scheduler
        await clean_scheduler.start()
        assert clean_scheduler._running is True
        
        # Stop scheduler
        await clean_scheduler.stop()
        assert clean_scheduler._running is False


class TestScheduledJobModel:
    """Test ScheduledJob dataclass."""
    
    def test_to_dict_and_from_dict(self, redis_available):
        """Test serialization and deserialization."""
        if not SCHEDULER_AVAILABLE:
            pytest.skip(f"Scheduler not available: {IMPORT_ERROR}")
        
        job = ScheduledJob(
            job_id="test123",
            goal="Test goal",
            job_type=JobType.RECURRING,
            cron_expression="0 * * * *",
            next_run=datetime.now() + timedelta(hours=1)
        )
        
        # Serialize
        data = job.to_dict()
        assert data["job_id"] == "test123"
        assert data["job_type"] == "recurring"
        assert data["status"] == "pending"
        
        # Deserialize
        restored = ScheduledJob.from_dict(data)
        assert restored.job_id == job.job_id
        assert restored.goal == job.goal
        assert restored.job_type == job.job_type
    
    def test_calculate_next_run_one_time(self, redis_available):
        """Test next run calculation for one-time jobs."""
        if not SCHEDULER_AVAILABLE:
            pytest.skip(f"Scheduler not available: {IMPORT_ERROR}")
        
        run_at = datetime.now() + timedelta(hours=1)
        job = ScheduledJob(
            job_id="onetime",
            goal="One time",
            job_type=JobType.ONE_TIME,
            run_at=run_at
        )
        
        # Before first run
        assert job.calculate_next_run() == run_at
        
        # After first run
        job.run_count = 1
        assert job.calculate_next_run() is None
    
    def test_calculate_next_run_recurring(self, redis_available):
        """Test next run calculation for recurring jobs."""
        if not SCHEDULER_AVAILABLE:
            pytest.skip(f"Scheduler not available: {IMPORT_ERROR}")
        
        job = ScheduledJob(
            job_id="recurring",
            goal="Recurring",
            job_type=JobType.RECURRING,
            cron_expression="0 * * * *"  # Every hour
        )
        
        next_run = job.calculate_next_run()
        assert next_run is not None
        assert next_run > datetime.now()
    
    def test_calculate_next_run_with_max_runs(self, redis_available):
        """Test next run respects max_runs."""
        if not SCHEDULER_AVAILABLE:
            pytest.skip(f"Scheduler not available: {IMPORT_ERROR}")
        
        job = ScheduledJob(
            job_id="limited",
            goal="Limited",
            job_type=JobType.RECURRING,
            cron_expression="0 * * * *",
            max_runs=5,
            run_count=5
        )
        
        # Should return None when max_runs reached
        assert job.calculate_next_run() is None


class TestCronExpressions:
    """Test cron expression parsing."""
    
    @pytest.mark.asyncio
    async def test_valid_cron_expressions(self, clean_scheduler):
        """Test various valid cron expressions."""
        expressions = [
            "* * * * *",       # Every minute
            "0 * * * *",       # Every hour
            "0 0 * * *",       # Every day at midnight
            "0 9 * * 1-5",     # Weekdays at 9am
            "*/5 * * * *",     # Every 5 minutes
            "0 0 1 * *",       # First of month
        ]
        
        for expr in expressions:
            job_id = await clean_scheduler.schedule_goal(
                goal=f"Test {expr}",
                cron_expression=expr
            )
            job = await clean_scheduler.get_job(job_id)
            assert job.next_run is not None, f"Failed for: {expr}"
    
    @pytest.mark.asyncio
    async def test_invalid_cron_expression(self, clean_scheduler):
        """Test that invalid cron expressions raise errors."""
        with pytest.raises(Exception):  # croniter raises ValueError
            await clean_scheduler.schedule_goal(
                goal="Invalid cron",
                cron_expression="invalid"
            )
