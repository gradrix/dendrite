"""
Dendrite HTTP API Server

Provides a REST API for interacting with the Dendrite neural engine.

Endpoints:
    POST /api/v1/goals          - Submit a new goal
    GET  /api/v1/goals/:id      - Get goal status/result
    GET  /api/v1/goals          - List recent goals
    POST /api/v1/chat           - Chat-style interaction
    GET  /api/v1/health         - Health check
    GET  /api/v1/tools          - List available tools

Usage:
    # Start server
    python -m neural_engine.api.server
    
    # Or via uvicorn
    uvicorn neural_engine.api.server:app --host 0.0.0.0 --port 8000

Environment variables:
    API_HOST: Host to bind (default: 0.0.0.0)
    API_PORT: Port to bind (default: 8000)
    API_KEY: Optional API key for authentication
"""

import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from neural_engine.core.logging import get_logger, log_event, EventType

logger = get_logger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================

class GoalRequest(BaseModel):
    """Request to process a goal."""
    goal: str = Field(..., description="The goal/task to accomplish", min_length=1)
    async_mode: bool = Field(False, description="If true, returns immediately with goal_id")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for the goal")


class GoalResponse(BaseModel):
    """Response from goal processing."""
    goal_id: str
    status: str  # pending, processing, completed, failed
    goal: str
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None


class ChatRequest(BaseModel):
    """Chat-style request."""
    message: str = Field(..., description="User message", min_length=1)
    conversation_id: Optional[str] = Field(None, description="For multi-turn conversations")


class ChatResponse(BaseModel):
    """Chat-style response."""
    response: str
    conversation_id: str
    goal_id: str


class ToolInfo(BaseModel):
    """Information about an available tool."""
    name: str
    description: str
    parameters: Optional[Dict[str, Any]] = None


class ScheduleRequest(BaseModel):
    """Request to schedule a goal."""
    goal: str = Field(..., description="The goal to schedule", min_length=1)
    cron_expression: Optional[str] = Field(None, description="Cron expression for recurring jobs (e.g., '0 * * * *' for hourly)")
    run_at: Optional[str] = Field(None, description="ISO datetime for one-time jobs")
    max_runs: Optional[int] = Field(None, description="Maximum number of runs (None = unlimited)")


class ScheduledJobResponse(BaseModel):
    """Response for a scheduled job."""
    job_id: str
    goal: str
    job_type: str
    status: str
    cron_expression: Optional[str] = None
    next_run: Optional[str] = None
    last_run: Optional[str] = None
    run_count: int = 0


class SchedulerStatsResponse(BaseModel):
    """Scheduler statistics."""
    total_jobs: int
    pending: int
    running: int
    completed: int
    failed: int
    cancelled: int
    recurring: int
    one_time: int
    is_running: bool


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    llm_status: str
    uptime_seconds: float


# =============================================================================
# In-Memory State (would use Redis in production)
# =============================================================================

class GoalStore:
    """Simple in-memory store for goals. Replace with Redis for production."""
    
    def __init__(self):
        self.goals: Dict[str, GoalResponse] = {}
        self.lock = asyncio.Lock()
    
    async def create(self, goal_id: str, goal: str) -> GoalResponse:
        async with self.lock:
            response = GoalResponse(
                goal_id=goal_id,
                status="pending",
                goal=goal,
                created_at=datetime.utcnow().isoformat() + "Z"
            )
            self.goals[goal_id] = response
            return response
    
    async def update(self, goal_id: str, **kwargs):
        async with self.lock:
            if goal_id in self.goals:
                goal = self.goals[goal_id]
                for key, value in kwargs.items():
                    setattr(goal, key, value)
    
    async def get(self, goal_id: str) -> Optional[GoalResponse]:
        return self.goals.get(goal_id)
    
    async def list_recent(self, limit: int = 20) -> List[GoalResponse]:
        sorted_goals = sorted(
            self.goals.values(),
            key=lambda g: g.created_at,
            reverse=True
        )
        return sorted_goals[:limit]


# Global store
goal_store = GoalStore()
start_time = datetime.utcnow()


# =============================================================================
# Orchestrator & Scheduler Initialization
# =============================================================================

_orchestrator = None
_orchestrator_lock = asyncio.Lock()
_scheduler = None
_scheduler_lock = asyncio.Lock()


async def get_orchestrator():
    """Lazy initialization of orchestrator."""
    global _orchestrator
    
    if _orchestrator is not None:
        return _orchestrator
    
    async with _orchestrator_lock:
        if _orchestrator is not None:
            return _orchestrator
        
        logger.info("Initializing orchestrator...")
        
        # Import here to avoid circular imports
        from neural_engine.core.system_factory import create_default_system
        
        try:
            _orchestrator = create_default_system()
            logger.info("Orchestrator initialized")
        except Exception as e:
            logger.error("Failed to initialize orchestrator", error=str(e))
            raise
        
        return _orchestrator


async def get_scheduler():
    """Lazy initialization of scheduler."""
    global _scheduler
    
    if _scheduler is not None:
        return _scheduler
    
    async with _scheduler_lock:
        if _scheduler is not None:
            return _scheduler
        
        logger.info("Initializing scheduler...")
        
        from neural_engine.core.scheduler import Scheduler
        
        # Create goal executor function
        async def execute_goal(goal: str) -> Any:
            orchestrator = await get_orchestrator()
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: orchestrator.process(goal)
            )
        
        _scheduler = Scheduler(goal_executor=execute_goal)
        await _scheduler.start()
        logger.info("Scheduler initialized and started")
        
        return _scheduler


# =============================================================================
# Authentication
# =============================================================================

API_KEY = os.environ.get("API_KEY")


async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key if configured."""
    if API_KEY is None:
        return  # No auth configured
    
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# =============================================================================
# Background Task Processing
# =============================================================================

async def process_goal_async(goal_id: str, goal: str, context: Optional[Dict] = None):
    """Process a goal in the background."""
    start = datetime.utcnow()
    
    try:
        await goal_store.update(goal_id, status="processing")
        log_event(EventType.GOAL_STARTED, goal_id=goal_id, goal=goal)
        
        orchestrator = await get_orchestrator()
        
        # Run in thread pool since orchestrator is synchronous
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: orchestrator.process(goal, goal_id=goal_id)
        )
        
        duration = (datetime.utcnow() - start).total_seconds() * 1000
        
        await goal_store.update(
            goal_id,
            status="completed",
            result=result,
            completed_at=datetime.utcnow().isoformat() + "Z",
            duration_ms=int(duration)
        )
        
        log_event(EventType.GOAL_COMPLETED, goal_id=goal_id, duration_ms=duration)
        logger.info("Goal completed", goal_id=goal_id, duration_ms=duration)
        
    except Exception as e:
        duration = (datetime.utcnow() - start).total_seconds() * 1000
        
        await goal_store.update(
            goal_id,
            status="failed",
            error=str(e),
            completed_at=datetime.utcnow().isoformat() + "Z",
            duration_ms=int(duration)
        )
        
        log_event(EventType.GOAL_FAILED, goal_id=goal_id, error=str(e))
        logger.error("Goal failed", goal_id=goal_id, error=str(e))


# =============================================================================
# FastAPI App
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("Dendrite API starting...")
    
    # Pre-initialize orchestrator
    try:
        await get_orchestrator()
    except Exception as e:
        logger.warning("Orchestrator not ready at startup", error=str(e))
    
    # Start scheduler
    try:
        await get_scheduler()
    except Exception as e:
        logger.warning("Scheduler not ready at startup", error=str(e))
    
    yield
    
    # Shutdown scheduler
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
    
    logger.info("Dendrite API shutting down...")


app = FastAPI(
    title="Dendrite API",
    description="Neural Engine for autonomous goal processing",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse)
@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Check API and dependencies health."""
    llm_status = "unknown"
    
    try:
        # Check LLM health
        import requests
        llm_url = os.environ.get("OPENAI_API_BASE", "http://localhost:8080/v1")
        base_url = llm_url.replace("/v1", "")
        response = requests.get(f"{base_url}/health", timeout=5)
        llm_status = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        llm_status = "unreachable"
    
    uptime = (datetime.utcnow() - start_time).total_seconds()
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        llm_status=llm_status,
        uptime_seconds=uptime
    )


@app.post("/api/v1/goals", response_model=GoalResponse, dependencies=[Depends(verify_api_key)])
async def create_goal(request: GoalRequest, background_tasks: BackgroundTasks):
    """
    Submit a new goal for processing.
    
    If async_mode=true, returns immediately with a goal_id that can be polled.
    If async_mode=false (default), waits for completion and returns the result.
    """
    goal_id = f"goal_{uuid.uuid4().hex[:12]}"
    
    # Create goal record
    goal_response = await goal_store.create(goal_id, request.goal)
    
    if request.async_mode:
        # Queue for background processing
        background_tasks.add_task(process_goal_async, goal_id, request.goal, request.context)
        return goal_response
    else:
        # Process synchronously
        await process_goal_async(goal_id, request.goal, request.context)
        return await goal_store.get(goal_id)


@app.get("/api/v1/goals/{goal_id}", response_model=GoalResponse, dependencies=[Depends(verify_api_key)])
async def get_goal(goal_id: str):
    """Get the status and result of a goal."""
    goal = await goal_store.get(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.get("/api/v1/goals", response_model=List[GoalResponse], dependencies=[Depends(verify_api_key)])
async def list_goals(limit: int = 20):
    """List recent goals."""
    return await goal_store.list_recent(limit)


@app.post("/api/v1/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat(request: ChatRequest):
    """
    Chat-style interaction - simpler interface for conversational use.
    Always processes synchronously.
    """
    goal_id = f"chat_{uuid.uuid4().hex[:12]}"
    conversation_id = request.conversation_id or uuid.uuid4().hex[:16]
    
    try:
        orchestrator = await get_orchestrator()
        
        # Run synchronously
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: orchestrator.process(request.message, goal_id=goal_id)
        )
        
        # Extract response text
        if isinstance(result, dict):
            response_text = result.get("result", result.get("response", str(result)))
        else:
            response_text = str(result)
        
        return ChatResponse(
            response=response_text,
            conversation_id=conversation_id,
            goal_id=goal_id
        )
        
    except Exception as e:
        logger.error("Chat failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tools", response_model=List[ToolInfo], dependencies=[Depends(verify_api_key)])
async def list_tools():
    """List available tools."""
    try:
        orchestrator = await get_orchestrator()
        
        tools = []
        if hasattr(orchestrator, 'tool_selector') and orchestrator.tool_selector:
            registry = orchestrator.tool_selector.tool_registry
            for name, tool in registry.tools.items():
                tools.append(ToolInfo(
                    name=name,
                    description=tool.get("description", ""),
                    parameters=tool.get("parameters")
                ))
        
        return tools
        
    except Exception as e:
        logger.error("Failed to list tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Scheduler Endpoints
# =============================================================================

@app.post("/api/v1/schedule", response_model=ScheduledJobResponse, dependencies=[Depends(verify_api_key)])
async def schedule_goal(request: ScheduleRequest):
    """
    Schedule a goal for future or recurring execution.
    
    Provide either:
    - run_at: ISO datetime for one-time execution
    - cron_expression: Cron syntax for recurring execution (e.g., "0 * * * *" for hourly)
    
    Cron format: minute hour day_of_month month day_of_week
    Examples:
    - "*/5 * * * *" - Every 5 minutes
    - "0 9 * * *" - Daily at 9am
    - "0 9 * * 1-5" - Weekdays at 9am
    """
    from datetime import datetime as dt
    
    scheduler = await get_scheduler()
    
    try:
        run_at_dt = None
        if request.run_at:
            run_at_dt = dt.fromisoformat(request.run_at.replace("Z", "+00:00"))
        
        job_id = await scheduler.schedule_goal(
            goal=request.goal,
            run_at=run_at_dt,
            cron_expression=request.cron_expression,
            max_runs=request.max_runs
        )
        
        job = await scheduler.get_job(job_id)
        
        return ScheduledJobResponse(
            job_id=job.job_id,
            goal=job.goal,
            job_type=job.job_type.value,
            status=job.status.value,
            cron_expression=job.cron_expression,
            next_run=job.next_run.isoformat() if job.next_run else None,
            last_run=job.last_run.isoformat() if job.last_run else None,
            run_count=job.run_count
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to schedule goal", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/schedule", response_model=List[ScheduledJobResponse], dependencies=[Depends(verify_api_key)])
async def list_scheduled_jobs(status: Optional[str] = None, limit: int = 100):
    """List scheduled jobs, optionally filtered by status."""
    from neural_engine.core.scheduler import JobStatus
    
    scheduler = await get_scheduler()
    
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    jobs = await scheduler.list_jobs(status=status_filter, limit=limit)
    
    return [
        ScheduledJobResponse(
            job_id=job.job_id,
            goal=job.goal,
            job_type=job.job_type.value,
            status=job.status.value,
            cron_expression=job.cron_expression,
            next_run=job.next_run.isoformat() if job.next_run else None,
            last_run=job.last_run.isoformat() if job.last_run else None,
            run_count=job.run_count
        )
        for job in jobs
    ]


@app.get("/api/v1/schedule/{job_id}", response_model=ScheduledJobResponse, dependencies=[Depends(verify_api_key)])
async def get_scheduled_job(job_id: str):
    """Get details of a scheduled job."""
    scheduler = await get_scheduler()
    
    job = await scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return ScheduledJobResponse(
        job_id=job.job_id,
        goal=job.goal,
        job_type=job.job_type.value,
        status=job.status.value,
        cron_expression=job.cron_expression,
        next_run=job.next_run.isoformat() if job.next_run else None,
        last_run=job.last_run.isoformat() if job.last_run else None,
        run_count=job.run_count
    )


@app.delete("/api/v1/schedule/{job_id}", dependencies=[Depends(verify_api_key)])
async def cancel_scheduled_job(job_id: str):
    """Cancel a scheduled job."""
    scheduler = await get_scheduler()
    
    success = await scheduler.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"status": "cancelled", "job_id": job_id}


@app.get("/api/v1/schedule/stats", response_model=SchedulerStatsResponse, dependencies=[Depends(verify_api_key)])
async def get_scheduler_stats():
    """Get scheduler statistics."""
    scheduler = await get_scheduler()
    stats = await scheduler.get_stats()
    return SchedulerStatsResponse(**stats)


@app.get("/api/v1/schedule/history", dependencies=[Depends(verify_api_key)])
async def get_schedule_history(limit: int = 50):
    """Get scheduler execution history."""
    scheduler = await get_scheduler()
    return await scheduler.get_history(limit=limit)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run the API server."""
    import uvicorn
    
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    
    logger.info("Starting Dendrite API", host=host, port=port)
    
    uvicorn.run(
        "neural_engine.api.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
