"""
Dendrite HTTP API Server (v2)

Simple, clean REST API for the neural engine.

Endpoints:
    POST /api/v1/goals      - Process a goal
    POST /api/v1/chat       - Chat-style interaction
    GET  /api/v1/health     - Health check
    GET  /api/v1/tools      - List available tools

Usage:
    uvicorn neural_engine.v2.api:app --host 0.0.0.0 --port 8000
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .core import Config, Orchestrator, EventBus


# =============================================================================
# Request/Response Models
# =============================================================================

class GoalRequest(BaseModel):
    """Request to process a goal."""
    goal: str = Field(..., description="The goal/task to accomplish", min_length=1)
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class GoalResponse(BaseModel):
    """Response from goal processing."""
    goal_id: str
    status: str  # completed, failed
    goal: str
    intent: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class ChatRequest(BaseModel):
    """Chat-style request."""
    message: str = Field(..., description="User message", min_length=1)


class ChatResponse(BaseModel):
    """Chat-style response."""
    response: str
    goal_id: str


class ToolInfo(BaseModel):
    """Information about a tool."""
    name: str
    description: str
    parameters: List[Dict[str, Any]] = []


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str = "2.0.0"
    llm_status: str = "unknown"
    redis_status: str = "unknown"


# =============================================================================
# Application Setup
# =============================================================================

# Global instances (set on startup)
_config: Optional[Config] = None
_orchestrator: Optional[Orchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - setup and teardown."""
    global _config, _orchestrator
    
    # Startup
    _config = Config.from_env()
    _orchestrator = await Orchestrator.from_config(_config)
    
    print(f"🧠 Neural Engine v2 API started")
    print(f"   LLM: {_config.llm_base_url}")
    print(f"   Redis: {_config.redis_host}:{_config.redis_port}")
    
    yield
    
    # Shutdown
    print("🧠 Neural Engine v2 API stopped")


app = FastAPI(
    title="Dendrite Neural Engine",
    description="AI agent with fractal neural architecture",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
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

@app.get("/health")
@app.get("/api/v1/health")
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    response = HealthResponse(status="healthy")
    
    try:
        # Check Redis
        r = await _config.get_redis()
        await r.ping()
        response.redis_status = "connected"
    except Exception:
        response.redis_status = "error"
    
    try:
        # Check LLM (quick test)
        from .core import LLMClient
        llm = LLMClient.from_config(_config)
        # Don't actually call LLM in health check - just verify config
        response.llm_status = "configured"
    except Exception:
        response.llm_status = "error"
    
    return response


@app.post("/api/v1/goals")
async def process_goal(request: GoalRequest) -> GoalResponse:
    """Process a goal and return result."""
    if not _orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    result = await _orchestrator.process(request.goal)
    
    return GoalResponse(
        goal_id=result["goal_id"],
        status="completed" if result["success"] else "failed",
        goal=result["goal"],
        intent=result.get("intent"),
        result=result.get("result"),
        error=result.get("error"),
        duration_ms=result.get("duration_ms"),
    )


@app.post("/api/v1/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat-style interaction."""
    if not _orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    result = await _orchestrator.process(request.message)
    
    return ChatResponse(
        response=result.get("result", result.get("error", "No response")),
        goal_id=result["goal_id"],
    )


@app.get("/api/v1/tools")
async def list_tools() -> List[ToolInfo]:
    """List available tools."""
    if not _orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    # Get tools from tool neuron registry
    definitions = _orchestrator.tool_neuron.registry.get_all_definitions()
    
    return [
        ToolInfo(
            name=d.name,
            description=d.description,
            parameters=d.parameters,
        )
        for d in definitions.values()
    ]


@app.get("/api/v1/events/{goal_id}")
async def get_events(goal_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get events for a goal (fractal observability)."""
    bus = EventBus.from_config(_config)
    events = await bus.get_events(goal_id=goal_id, limit=limit)
    
    return [
        {
            "event_type": e.event_type.value,
            "neuron": e.neuron_type,
            "timestamp": e.timestamp,
            "data": e.metadata,
        }
        for e in events
    ]


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port)
