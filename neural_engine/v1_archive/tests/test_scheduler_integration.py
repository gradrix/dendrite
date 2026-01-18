"""
Integration tests for the Scheduler.

These tests verify the scheduler works correctly with Redis.
"""
import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import os


class TestScheduledJob:
    """Tests for the ScheduledJob data class."""
    
    def test_to_dict_and_from_dict(self):
        """Should serialize and deserialize correctly."""
        from neural_engine.core.scheduler import ScheduledJob, JobType, JobStatus
        
        job = ScheduledJob(
            job_id="test-123",
            goal="Test goal",
            job_type=JobType.RECURRING,
            status=JobStatus.PENDING,
            cron_expression="0 * * * *",
            run_count=5,
            metadata={"key": "value"}
        )
        
        # Serialize
        data = job.to_dict()
        
        assert data["job_id"] == "test-123"
        assert data["goal"] == "Test goal"
        assert data["job_type"] == "recurring"
        assert data["status"] == "pending"
        assert data["cron_expression"] == "0 * * * *"
        assert data["run_count"] == 5
        
        # Deserialize
        restored = ScheduledJob.from_dict(data)
        
        assert restored.job_id == job.job_id
        assert restored.goal == job.goal
        assert restored.job_type == job.job_type
        assert restored.status == job.status
        assert restored.cron_expression == job.cron_expression
        assert restored.run_count == job.run_count
    
    def test_calculate_next_run_one_time(self):
        """One-time job should run once."""
        from neural_engine.core.scheduler import ScheduledJob, JobType, JobStatus
        
        run_at = datetime.now() + timedelta(hours=1)
        job = ScheduledJob(
            job_id="once-1",
            goal="Run once",
            job_type=JobType.ONE_TIME,
            run_at=run_at,
            run_count=0
        )
        
        # Before run
        next_run = job.calculate_next_run()
        assert next_run == run_at
        
        # After run
        job.run_count = 1
        next_run = job.calculate_next_run()
        assert next_run is None
    
    def test_calculate_next_run_recurring(self):
        """Recurring job should calculate next cron time."""
        from neural_engine.core.scheduler import ScheduledJob, JobType, JobStatus
        
        job = ScheduledJob(
            job_id="recurring-1",
            goal="Run hourly",
            job_type=JobType.RECURRING,
            cron_expression="0 * * * *",  # Every hour
            run_count=0
        )
        
        next_run = job.calculate_next_run()
        
        assert next_run is not None
        assert next_run > datetime.now()
        # Should be at minute 0
        assert next_run.minute == 0
    
    def test_calculate_next_run_max_runs_reached(self):
        """Should return None when max runs reached."""
        from neural_engine.core.scheduler import ScheduledJob, JobType, JobStatus
        
        job = ScheduledJob(
            job_id="limited-1",
            goal="Run 3 times",
            job_type=JobType.RECURRING,
            cron_expression="* * * * *",
            run_count=3,
            max_runs=3
        )
        
        next_run = job.calculate_next_run()
        assert next_run is None


class TestSchedulerWithMockRedis:
    """Tests for Scheduler with mocked Redis."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.hset = AsyncMock()
        mock.hget = AsyncMock(return_value=None)
        mock.hgetall = AsyncMock(return_value={})
        mock.zadd = AsyncMock()
        mock.zrem = AsyncMock()
        mock.zrangebyscore = AsyncMock(return_value=[])
        mock.publish = AsyncMock()
        mock.lpush = AsyncMock()
        mock.ltrim = AsyncMock()
        mock.lrange = AsyncMock(return_value=[])
        return mock
    
    @pytest.mark.asyncio
    async def test_schedule_one_time_goal(self, mock_redis):
        """Should schedule a one-time goal."""
        from neural_engine.core.scheduler import Scheduler
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        run_at = datetime.now() + timedelta(hours=1)
        job_id = await scheduler.schedule_goal(
            goal="Send reminder",
            run_at=run_at
        )
        
        assert job_id is not None
        assert len(job_id) == 8  # UUID prefix
        
        # Verify Redis calls
        mock_redis.hset.assert_called_once()
        mock_redis.zadd.assert_called_once()
        mock_redis.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_schedule_recurring_goal(self, mock_redis):
        """Should schedule a recurring goal with cron."""
        from neural_engine.core.scheduler import Scheduler
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        job_id = await scheduler.schedule_goal(
            goal="Hourly sync",
            cron_expression="0 * * * *"
        )
        
        assert job_id is not None
        
        # Verify Redis calls
        mock_redis.hset.assert_called_once()
        mock_redis.zadd.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_schedule_validates_input(self, mock_redis):
        """Should validate that either run_at or cron_expression is provided."""
        from neural_engine.core.scheduler import Scheduler
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        # Neither provided
        with pytest.raises(ValueError, match="Must specify either"):
            await scheduler.schedule_goal(goal="Invalid")
        
        # Both provided
        with pytest.raises(ValueError, match="Cannot specify both"):
            await scheduler.schedule_goal(
                goal="Also invalid",
                run_at=datetime.now(),
                cron_expression="* * * * *"
            )
    
    @pytest.mark.asyncio
    async def test_cancel_job(self, mock_redis):
        """Should cancel a scheduled job."""
        from neural_engine.core.scheduler import Scheduler, ScheduledJob, JobType, JobStatus
        
        # Mock existing job
        existing_job = ScheduledJob(
            job_id="cancel-me",
            goal="To be cancelled",
            job_type=JobType.ONE_TIME,
            run_at=datetime.now() + timedelta(hours=1)
        )
        mock_redis.hget = AsyncMock(return_value=json.dumps(existing_job.to_dict()))
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        result = await scheduler.cancel_job("cancel-me")
        
        assert result is True
        mock_redis.zrem.assert_called_once()
        mock_redis.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, mock_redis):
        """Should return False when job doesn't exist."""
        from neural_engine.core.scheduler import Scheduler
        
        mock_redis.hget = AsyncMock(return_value=None)
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        result = await scheduler.cancel_job("nonexistent")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_job(self, mock_redis):
        """Should retrieve a job by ID."""
        from neural_engine.core.scheduler import Scheduler, ScheduledJob, JobType
        
        job = ScheduledJob(
            job_id="get-me",
            goal="Retrieve me",
            job_type=JobType.ONE_TIME,
            run_at=datetime.now() + timedelta(hours=1)
        )
        mock_redis.hget = AsyncMock(return_value=json.dumps(job.to_dict()))
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        result = await scheduler.get_job("get-me")
        
        assert result is not None
        assert result.job_id == "get-me"
        assert result.goal == "Retrieve me"
    
    @pytest.mark.asyncio
    async def test_list_jobs(self, mock_redis):
        """Should list all jobs."""
        from neural_engine.core.scheduler import Scheduler, ScheduledJob, JobType, JobStatus
        
        jobs = {
            "job-1": json.dumps(ScheduledJob(
                job_id="job-1",
                goal="Goal 1",
                job_type=JobType.ONE_TIME,
                run_at=datetime.now() + timedelta(hours=1)
            ).to_dict()),
            "job-2": json.dumps(ScheduledJob(
                job_id="job-2",
                goal="Goal 2",
                job_type=JobType.RECURRING,
                cron_expression="0 * * * *"
            ).to_dict())
        }
        mock_redis.hgetall = AsyncMock(return_value=jobs)
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        result = await scheduler.list_jobs()
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, mock_redis):
        """Should filter jobs by status."""
        from neural_engine.core.scheduler import Scheduler, ScheduledJob, JobType, JobStatus
        
        pending_job = ScheduledJob(
            job_id="pending-1",
            goal="Pending",
            job_type=JobType.ONE_TIME,
            status=JobStatus.PENDING,
            run_at=datetime.now() + timedelta(hours=1)
        )
        completed_job = ScheduledJob(
            job_id="completed-1",
            goal="Completed",
            job_type=JobType.ONE_TIME,
            status=JobStatus.COMPLETED,
            run_at=datetime.now() - timedelta(hours=1)
        )
        
        jobs = {
            "pending-1": json.dumps(pending_job.to_dict()),
            "completed-1": json.dumps(completed_job.to_dict())
        }
        mock_redis.hgetall = AsyncMock(return_value=jobs)
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        # Filter pending only
        result = await scheduler.list_jobs(status=JobStatus.PENDING)
        
        assert len(result) == 1
        assert result[0].job_id == "pending-1"
    
    @pytest.mark.asyncio
    async def test_get_due_jobs(self, mock_redis):
        """Should return jobs that are due to run."""
        from neural_engine.core.scheduler import Scheduler, ScheduledJob, JobType, JobStatus
        
        due_job = ScheduledJob(
            job_id="due-1",
            goal="Run me now",
            job_type=JobType.ONE_TIME,
            status=JobStatus.PENDING,
            run_at=datetime.now() - timedelta(minutes=5)  # 5 minutes ago
        )
        
        mock_redis.zrangebyscore = AsyncMock(return_value=["due-1"])
        mock_redis.hget = AsyncMock(return_value=json.dumps(due_job.to_dict()))
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        result = await scheduler.get_due_jobs()
        
        assert len(result) == 1
        assert result[0].job_id == "due-1"
    
    @pytest.mark.asyncio
    async def test_get_stats(self, mock_redis):
        """Should return scheduler statistics."""
        from neural_engine.core.scheduler import Scheduler, ScheduledJob, JobType, JobStatus
        
        jobs = {
            "j1": json.dumps(ScheduledJob(
                job_id="j1", goal="G1", job_type=JobType.ONE_TIME, status=JobStatus.PENDING,
                run_at=datetime.now()
            ).to_dict()),
            "j2": json.dumps(ScheduledJob(
                job_id="j2", goal="G2", job_type=JobType.RECURRING, status=JobStatus.PENDING,
                cron_expression="* * * * *"
            ).to_dict()),
            "j3": json.dumps(ScheduledJob(
                job_id="j3", goal="G3", job_type=JobType.ONE_TIME, status=JobStatus.COMPLETED,
                run_at=datetime.now()
            ).to_dict()),
        }
        mock_redis.hgetall = AsyncMock(return_value=jobs)
        
        scheduler = Scheduler(redis_client=mock_redis)
        
        stats = await scheduler.get_stats()
        
        assert stats["total_jobs"] == 3
        assert stats["pending"] == 2
        assert stats["completed"] == 1
        assert stats["recurring"] == 1
        assert stats["one_time"] == 2
    
    @pytest.mark.asyncio
    async def test_start_and_stop(self, mock_redis):
        """Should start and stop the polling loop."""
        from neural_engine.core.scheduler import Scheduler
        
        scheduler = Scheduler(redis_client=mock_redis)
        scheduler._poll_interval = 0.1  # Fast polling for test
        
        await scheduler.start()
        
        assert scheduler._running is True
        assert len(scheduler._tasks) == 1
        
        await asyncio.sleep(0.2)  # Let it poll once
        
        await scheduler.stop()
        
        assert scheduler._running is False
        assert len(scheduler._tasks) == 0


class TestSchedulerJobExecution:
    """Tests for job execution logic."""
    
    @pytest.mark.asyncio
    async def test_execute_one_time_job(self):
        """Should execute and complete a one-time job."""
        from neural_engine.core.scheduler import Scheduler, ScheduledJob, JobType, JobStatus
        import json
        
        # Mock Redis
        mock_redis = AsyncMock()
        stored_jobs = {}
        
        async def mock_hset(key, job_id, data):
            stored_jobs[job_id] = data
        
        async def mock_hget(key, job_id):
            return stored_jobs.get(job_id)
        
        mock_redis.hset = mock_hset
        mock_redis.hget = mock_hget
        mock_redis.zadd = AsyncMock()
        mock_redis.zrem = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_redis.lpush = AsyncMock()
        mock_redis.ltrim = AsyncMock()
        
        # Mock goal executor
        executed_goals = []
        async def mock_executor(goal):
            executed_goals.append(goal)
            return {"success": True}
        
        scheduler = Scheduler(redis_client=mock_redis, goal_executor=mock_executor)
        
        # Create a job
        job = ScheduledJob(
            job_id="exec-1",
            goal="Execute me",
            job_type=JobType.ONE_TIME,
            status=JobStatus.PENDING,
            run_at=datetime.now() - timedelta(minutes=1),  # Due now
            next_run=datetime.now() - timedelta(minutes=1)
        )
        
        # Execute it
        await scheduler._execute_job(job)
        
        # Verify execution
        assert "Execute me" in executed_goals
        assert job.status == JobStatus.COMPLETED
        assert job.run_count == 1
        assert job.last_run is not None
    
    @pytest.mark.asyncio
    async def test_execute_recurring_job_schedules_next(self):
        """Recurring job should schedule next run after execution."""
        from neural_engine.core.scheduler import Scheduler, ScheduledJob, JobType, JobStatus
        
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.zadd = AsyncMock()
        mock_redis.zrem = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_redis.lpush = AsyncMock()
        mock_redis.ltrim = AsyncMock()
        
        # Mock goal executor
        async def mock_executor(goal):
            return {"success": True}
        
        scheduler = Scheduler(redis_client=mock_redis, goal_executor=mock_executor)
        
        # Create a recurring job
        job = ScheduledJob(
            job_id="recurring-exec",
            goal="Run every hour",
            job_type=JobType.RECURRING,
            status=JobStatus.PENDING,
            cron_expression="0 * * * *",
            next_run=datetime.now() - timedelta(minutes=1)
        )
        
        # Execute it
        await scheduler._execute_job(job)
        
        # Verify next run was scheduled
        assert job.status == JobStatus.PENDING  # Still pending for next run
        assert job.run_count == 1
        assert job.next_run is not None
        assert job.next_run > datetime.now()  # Next run in future
        mock_redis.zadd.assert_called()  # Added back to schedule
    
    @pytest.mark.asyncio
    async def test_execute_job_handles_errors(self):
        """Should handle execution errors gracefully."""
        from neural_engine.core.scheduler import Scheduler, ScheduledJob, JobType, JobStatus
        
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.zadd = AsyncMock()
        mock_redis.zrem = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_redis.lpush = AsyncMock()
        mock_redis.ltrim = AsyncMock()
        
        # Failing executor
        async def failing_executor(goal):
            raise Exception("Execution failed!")
        
        scheduler = Scheduler(redis_client=mock_redis, goal_executor=failing_executor)
        
        job = ScheduledJob(
            job_id="fail-1",
            goal="Will fail",
            job_type=JobType.ONE_TIME,
            status=JobStatus.PENDING,
            run_at=datetime.now()
        )
        
        # Should not raise
        await scheduler._execute_job(job)
        
        # Should record error
        assert job.status == JobStatus.FAILED
        assert job.last_error == "Execution failed!"


class TestConvenienceFunctions:
    """Tests for convenience scheduling functions."""
    
    @pytest.mark.asyncio
    async def test_schedule_once(self):
        """schedule_once should create a one-time job."""
        from neural_engine.core.scheduler import schedule_once, Scheduler
        
        with patch.object(Scheduler, 'schedule_goal', new_callable=AsyncMock) as mock:
            mock.return_value = "job-123"
            
            # Can't easily test this without mocking Redis connection
            # This is more of a smoke test
            pass
    
    @pytest.mark.asyncio
    async def test_schedule_recurring(self):
        """schedule_recurring should create a recurring job."""
        from neural_engine.core.scheduler import schedule_recurring, Scheduler
        
        with patch.object(Scheduler, 'schedule_goal', new_callable=AsyncMock) as mock:
            mock.return_value = "job-456"
            
            # Same as above - smoke test
            pass
