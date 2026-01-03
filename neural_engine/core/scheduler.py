"""
Dendrite Scheduler - Redis-based job queue with cron-like scheduling.

This module provides:
- Scheduled goal execution (cron syntax)
- One-time delayed goal execution
- Recurring goal management
- Job status tracking
"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
import os
import redis.asyncio as redis
from croniter import croniter

from neural_engine.core.logging import get_logger

logger = get_logger(__name__)


class JobStatus(Enum):
    """Status of a scheduled job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(Enum):
    """Type of scheduled job."""
    ONE_TIME = "one_time"
    RECURRING = "recurring"


@dataclass
class ScheduledJob:
    """A scheduled job definition."""
    job_id: str
    goal: str
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    cron_expression: Optional[str] = None  # For recurring jobs
    run_at: Optional[datetime] = None  # For one-time jobs
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    run_count: int = 0
    max_runs: Optional[int] = None  # None = unlimited
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_result: Optional[str] = None
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        data = asdict(self)
        data['job_type'] = self.job_type.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['run_at'] = self.run_at.isoformat() if self.run_at else None
        data['next_run'] = self.next_run.isoformat() if self.next_run else None
        data['last_run'] = self.last_run.isoformat() if self.last_run else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledJob':
        """Create from dictionary."""
        data = data.copy()
        data['job_type'] = JobType(data['job_type'])
        data['status'] = JobStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('run_at'):
            data['run_at'] = datetime.fromisoformat(data['run_at'])
        if data.get('next_run'):
            data['next_run'] = datetime.fromisoformat(data['next_run'])
        if data.get('last_run'):
            data['last_run'] = datetime.fromisoformat(data['last_run'])
        return cls(**data)
    
    def calculate_next_run(self) -> Optional[datetime]:
        """Calculate the next run time based on job type."""
        if self.job_type == JobType.ONE_TIME:
            if self.run_count == 0:
                return self.run_at
            return None  # Already ran
        elif self.job_type == JobType.RECURRING:
            if self.max_runs and self.run_count >= self.max_runs:
                return None  # Reached max runs
            if self.cron_expression:
                cron = croniter(self.cron_expression, datetime.now())
                return cron.get_next(datetime)
        return None


class Scheduler:
    """
    Redis-based scheduler for recurring and one-time goal execution.
    
    Uses Redis for:
    - Job definitions storage (hash)
    - Sorted set for next run times (for efficient polling)
    - Pub/sub for job notifications
    """
    
    JOBS_KEY = "dendrite:scheduler:jobs"
    SCHEDULE_KEY = "dendrite:scheduler:schedule"
    HISTORY_KEY = "dendrite:scheduler:history"
    CHANNEL = "dendrite:scheduler:events"
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        goal_executor: Optional[Callable[[str], Any]] = None
    ):
        """
        Initialize the scheduler.
        
        Args:
            redis_client: Redis client instance
            goal_executor: Async function to execute goals
        """
        self._redis = redis_client
        self._goal_executor = goal_executor
        self._running = False
        self._poll_interval = 5  # seconds
        self._tasks: List[asyncio.Task] = []
    
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            host = os.environ.get("REDIS_HOST", "localhost")
            port = int(os.environ.get("REDIS_PORT", 6379))
            self._redis = redis.Redis(host=host, port=port, decode_responses=True)
        return self._redis
    
    async def schedule_goal(
        self,
        goal: str,
        run_at: Optional[datetime] = None,
        cron_expression: Optional[str] = None,
        max_runs: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a goal for execution.
        
        Args:
            goal: The goal to execute
            run_at: When to run (for one-time jobs)
            cron_expression: Cron expression (for recurring jobs)
            max_runs: Maximum number of runs (None = unlimited)
            metadata: Additional metadata
            
        Returns:
            Job ID
            
        Examples:
            # Run once in 5 minutes
            await scheduler.schedule_goal("Check weather", run_at=datetime.now() + timedelta(minutes=5))
            
            # Run every hour
            await scheduler.schedule_goal("Sync data", cron_expression="0 * * * *")
            
            # Run daily at 9am, max 30 times
            await scheduler.schedule_goal("Morning report", cron_expression="0 9 * * *", max_runs=30)
        """
        r = await self._get_redis()
        
        if not run_at and not cron_expression:
            raise ValueError("Must specify either run_at or cron_expression")
        
        if run_at and cron_expression:
            raise ValueError("Cannot specify both run_at and cron_expression")
        
        job_id = str(uuid.uuid4())[:8]
        job_type = JobType.RECURRING if cron_expression else JobType.ONE_TIME
        
        job = ScheduledJob(
            job_id=job_id,
            goal=goal,
            job_type=job_type,
            cron_expression=cron_expression,
            run_at=run_at,
            max_runs=max_runs,
            metadata=metadata or {}
        )
        
        # Calculate next run
        job.next_run = job.calculate_next_run()
        
        if job.next_run is None:
            raise ValueError("Could not calculate next run time")
        
        # Store job definition
        await r.hset(self.JOBS_KEY, job_id, json.dumps(job.to_dict()))
        
        # Add to schedule sorted set (score = timestamp)
        await r.zadd(self.SCHEDULE_KEY, {job_id: job.next_run.timestamp()})
        
        # Publish event
        await r.publish(self.CHANNEL, json.dumps({
            "event": "job_scheduled",
            "job_id": job_id,
            "goal": goal,
            "next_run": job.next_run.isoformat()
        }))
        
        logger.info(
            "job_scheduled",
            job_id=job_id,
            goal=goal,
            job_type=job_type.value,
            next_run=job.next_run.isoformat()
        )
        
        return job_id
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a scheduled job.
        
        Args:
            job_id: The job ID to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        r = await self._get_redis()
        
        job_data = await r.hget(self.JOBS_KEY, job_id)
        if not job_data:
            return False
        
        job = ScheduledJob.from_dict(json.loads(job_data))
        job.status = JobStatus.CANCELLED
        job.next_run = None
        
        # Update job
        await r.hset(self.JOBS_KEY, job_id, json.dumps(job.to_dict()))
        
        # Remove from schedule
        await r.zrem(self.SCHEDULE_KEY, job_id)
        
        # Publish event
        await r.publish(self.CHANNEL, json.dumps({
            "event": "job_cancelled",
            "job_id": job_id
        }))
        
        logger.info("job_cancelled", job_id=job_id)
        
        return True
    
    async def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get a job by ID."""
        r = await self._get_redis()
        job_data = await r.hget(self.JOBS_KEY, job_id)
        if not job_data:
            return None
        return ScheduledJob.from_dict(json.loads(job_data))
    
    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100
    ) -> List[ScheduledJob]:
        """List all scheduled jobs."""
        r = await self._get_redis()
        
        all_jobs = await r.hgetall(self.JOBS_KEY)
        jobs = []
        
        for job_data in all_jobs.values():
            job = ScheduledJob.from_dict(json.loads(job_data))
            if status is None or job.status == status:
                jobs.append(job)
        
        # Sort by next_run
        jobs.sort(key=lambda j: j.next_run or datetime.max)
        
        return jobs[:limit]
    
    async def get_due_jobs(self) -> List[ScheduledJob]:
        """Get jobs that are due to run."""
        r = await self._get_redis()
        
        now = datetime.now().timestamp()
        
        # Get job IDs that are due (score <= now)
        due_ids = await r.zrangebyscore(self.SCHEDULE_KEY, "-inf", now)
        
        jobs = []
        for job_id in due_ids:
            job = await self.get_job(job_id)
            if job and job.status == JobStatus.PENDING:
                jobs.append(job)
        
        return jobs
    
    async def _execute_job(self, job: ScheduledJob) -> None:
        """Execute a single job."""
        r = await self._get_redis()
        
        try:
            # Update status to running
            job.status = JobStatus.RUNNING
            job.last_run = datetime.now()
            await r.hset(self.JOBS_KEY, job.job_id, json.dumps(job.to_dict()))
            
            logger.info("job_started", job_id=job.job_id, goal=job.goal)
            
            # Execute the goal
            result = None
            if self._goal_executor:
                result = await self._goal_executor(job.goal)
                job.last_result = str(result)[:1000] if result else None
            
            # Update job
            job.status = JobStatus.COMPLETED if job.job_type == JobType.ONE_TIME else JobStatus.PENDING
            job.run_count += 1
            job.last_error = None
            
            # Calculate next run for recurring jobs
            if job.job_type == JobType.RECURRING:
                job.next_run = job.calculate_next_run()
                if job.next_run:
                    await r.zadd(self.SCHEDULE_KEY, {job.job_id: job.next_run.timestamp()})
                else:
                    job.status = JobStatus.COMPLETED
                    await r.zrem(self.SCHEDULE_KEY, job.job_id)
            else:
                await r.zrem(self.SCHEDULE_KEY, job.job_id)
            
            await r.hset(self.JOBS_KEY, job.job_id, json.dumps(job.to_dict()))
            
            # Store in history
            await r.lpush(self.HISTORY_KEY, json.dumps({
                "job_id": job.job_id,
                "goal": job.goal,
                "ran_at": job.last_run.isoformat(),
                "status": "success",
                "result": job.last_result
            }))
            await r.ltrim(self.HISTORY_KEY, 0, 999)  # Keep last 1000
            
            logger.info(
                "job_completed",
                job_id=job.job_id,
                goal=job.goal,
                run_count=job.run_count,
                next_run=job.next_run.isoformat() if job.next_run else None
            )
            
        except Exception as e:
            job.status = JobStatus.FAILED if job.job_type == JobType.ONE_TIME else JobStatus.PENDING
            job.last_error = str(e)
            
            # Still schedule next run for recurring jobs
            if job.job_type == JobType.RECURRING:
                job.next_run = job.calculate_next_run()
                if job.next_run:
                    await r.zadd(self.SCHEDULE_KEY, {job.job_id: job.next_run.timestamp()})
            
            await r.hset(self.JOBS_KEY, job.job_id, json.dumps(job.to_dict()))
            
            # Store in history
            await r.lpush(self.HISTORY_KEY, json.dumps({
                "job_id": job.job_id,
                "goal": job.goal,
                "ran_at": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            }))
            
            logger.error(
                "job_failed",
                job_id=job.job_id,
                goal=job.goal,
                error=str(e)
            )
    
    async def _poll_loop(self) -> None:
        """Main polling loop for due jobs."""
        while self._running:
            try:
                due_jobs = await self.get_due_jobs()
                
                for job in due_jobs:
                    # Execute each job (could parallelize if needed)
                    await self._execute_job(job)
                
            except Exception as e:
                logger.error("scheduler_poll_error", error=str(e))
            
            await asyncio.sleep(self._poll_interval)
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        
        # Start poll loop
        task = asyncio.create_task(self._poll_loop())
        self._tasks.append(task)
        
        logger.info("scheduler_started", poll_interval=self._poll_interval)
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        
        logger.info("scheduler_stopped")
    
    async def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history."""
        r = await self._get_redis()
        
        history = await r.lrange(self.HISTORY_KEY, 0, limit - 1)
        return [json.loads(item) for item in history]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        r = await self._get_redis()
        
        all_jobs = await r.hgetall(self.JOBS_KEY)
        
        stats = {
            "total_jobs": len(all_jobs),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "recurring": 0,
            "one_time": 0,
            "is_running": self._running
        }
        
        for job_data in all_jobs.values():
            job = ScheduledJob.from_dict(json.loads(job_data))
            stats[job.status.value] += 1
            if job.job_type == JobType.RECURRING:
                stats["recurring"] += 1
            else:
                stats["one_time"] += 1
        
        return stats


# Convenience functions

async def schedule_once(goal: str, delay_seconds: int = 0) -> str:
    """Schedule a goal to run once after a delay."""
    scheduler = Scheduler()
    run_at = datetime.now() + timedelta(seconds=delay_seconds)
    return await scheduler.schedule_goal(goal, run_at=run_at)


async def schedule_recurring(goal: str, cron_expression: str, max_runs: Optional[int] = None) -> str:
    """Schedule a recurring goal with cron expression."""
    scheduler = Scheduler()
    return await scheduler.schedule_goal(goal, cron_expression=cron_expression, max_runs=max_runs)


# Cron expression examples:
# "* * * * *"      - Every minute
# "0 * * * *"      - Every hour
# "0 0 * * *"      - Every day at midnight
# "0 9 * * 1-5"    - 9am on weekdays
# "0 0 1 * *"      - First day of every month
# "*/5 * * * *"    - Every 5 minutes
