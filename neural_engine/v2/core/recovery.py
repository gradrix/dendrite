"""
Error Recovery System

Provides:
1. Tool capability detection (can we handle this?)
2. Retry with learning (if tool fails, try to fix)
3. Fallback routing (no tool → generative, or tool forge)
4. Execution history for learning

No hardcoded examples - learns from execution patterns.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of failures we can recover from."""
    NO_MATCHING_TOOL = "no_matching_tool"      # No tool found for request
    TOOL_EXECUTION_ERROR = "tool_execution_error"  # Tool threw exception
    INVALID_PARAMETERS = "invalid_parameters"  # Bad params extracted
    INVALID_RESULT = "invalid_result"          # Result doesn't match expected
    TIMEOUT = "timeout"                        # Execution too slow
    AUTH_REQUIRED = "auth_required"            # Missing credentials/tokens


@dataclass
class ExecutionRecord:
    """Record of a tool execution attempt."""
    goal: str
    tool_name: Optional[str]
    parameters: Dict[str, Any]
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    failure_type: Optional[FailureType] = None
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    recovery_attempted: bool = False
    recovery_action: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "success": self.success,
            "result": self.result[:200] if self.result else None,
            "error": self.error,
            "failure_type": self.failure_type.value if self.failure_type else None,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "recovery_attempted": self.recovery_attempted,
            "recovery_action": self.recovery_action,
        }


class ExecutionHistory:
    """
    Tracks execution history for learning.
    
    Provides:
    - Recent failures for pattern detection
    - Tool success rates
    - Common parameter patterns
    """
    
    def __init__(self, max_records: int = 1000):
        self._records: List[ExecutionRecord] = []
        self._max_records = max_records
        self._tool_stats: Dict[str, Dict[str, int]] = {}  # tool -> {success: N, failure: N}
    
    def record(self, record: ExecutionRecord) -> None:
        """Add execution record."""
        self._records.append(record)
        
        # Trim old records
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]
        
        # Update tool stats
        if record.tool_name:
            if record.tool_name not in self._tool_stats:
                self._tool_stats[record.tool_name] = {"success": 0, "failure": 0}
            
            key = "success" if record.success else "failure"
            self._tool_stats[record.tool_name][key] += 1
    
    def get_recent_failures(self, limit: int = 10) -> List[ExecutionRecord]:
        """Get recent failed executions."""
        return [r for r in reversed(self._records) if not r.success][:limit]
    
    def get_similar_failures(self, goal: str, limit: int = 5) -> List[ExecutionRecord]:
        """Find failures with similar goals (simple word overlap)."""
        goal_words = set(goal.lower().split())
        
        scored = []
        for record in self._records:
            if not record.success:
                record_words = set(record.goal.lower().split())
                overlap = len(goal_words & record_words) / max(len(goal_words), 1)
                if overlap > 0.3:  # 30% word overlap
                    scored.append((overlap, record))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]
    
    def get_tool_success_rate(self, tool_name: str) -> float:
        """Get success rate for a tool."""
        stats = self._tool_stats.get(tool_name, {"success": 0, "failure": 0})
        total = stats["success"] + stats["failure"]
        return stats["success"] / total if total > 0 else 0.5
    
    def get_failing_tools(self, min_failures: int = 3, max_rate: float = 0.3) -> List[str]:
        """Get tools that are failing frequently."""
        failing = []
        for tool_name, stats in self._tool_stats.items():
            total = stats["success"] + stats["failure"]
            if total >= min_failures:
                rate = stats["success"] / total
                if rate < max_rate:
                    failing.append(tool_name)
        return failing


@dataclass
class RecoveryAction:
    """An action to take for recovery."""
    action: str  # "retry", "fallback_generative", "forge_tool", "refine_params"
    reason: str
    context: Dict[str, Any] = field(default_factory=dict)


class RecoveryEngine:
    """
    Determines how to recover from failures.
    
    Uses execution history to learn patterns, not hardcoded rules.
    """
    
    def __init__(self, history: ExecutionHistory = None):
        self.history = history or ExecutionHistory()
        self._forge_callback: Optional[Callable] = None  # Set when ToolForge is available
    
    def set_forge_callback(self, callback: Callable):
        """Set callback for creating new tools."""
        self._forge_callback = callback
    
    def analyze_failure(
        self,
        goal: str,
        tool_name: Optional[str],
        error: str,
        parameters: Dict[str, Any],
    ) -> RecoveryAction:
        """
        Analyze a failure and determine recovery action.
        
        Returns what to do next.
        """
        # Detect failure type
        failure_type = self._classify_failure(error, tool_name)
        
        # Record for learning
        record = ExecutionRecord(
            goal=goal,
            tool_name=tool_name,
            parameters=parameters,
            success=False,
            error=error,
            failure_type=failure_type,
        )
        self.history.record(record)
        
        # Determine action based on failure type and history
        return self._determine_action(goal, failure_type, tool_name, error)
    
    def _classify_failure(self, error: str, tool_name: Optional[str]) -> FailureType:
        """Classify the type of failure from error message."""
        error_lower = error.lower()
        
        if not tool_name or "no tool" in error_lower or "not found" in error_lower:
            return FailureType.NO_MATCHING_TOOL
        
        # Auth/credential failures
        if any(x in error_lower for x in ["401", "403", "unauthorized", "forbidden", 
                                           "authentication", "not authenticated",
                                           "token", "credential", "api key"]):
            return FailureType.AUTH_REQUIRED
        
        if "parameter" in error_lower or "argument" in error_lower or "missing" in error_lower:
            return FailureType.INVALID_PARAMETERS
        
        if "timeout" in error_lower:
            return FailureType.TIMEOUT
        
        if "syntax" in error_lower or "undefined" in error_lower or "error" in error_lower:
            return FailureType.TOOL_EXECUTION_ERROR
        
        return FailureType.TOOL_EXECUTION_ERROR
    
    def _determine_action(
        self,
        goal: str,
        failure_type: FailureType,
        tool_name: Optional[str],
        error: str,
    ) -> RecoveryAction:
        """Determine the best recovery action."""
        
        # Check for similar past failures
        similar = self.history.get_similar_failures(goal, limit=3)
        
        # NO MATCHING TOOL - either forge or fallback
        if failure_type == FailureType.NO_MATCHING_TOOL:
            if self._forge_callback:
                return RecoveryAction(
                    action="forge_tool",
                    reason="No existing tool matches request. Creating new tool.",
                    context={"goal": goal},
                )
            else:
                return RecoveryAction(
                    action="fallback_generative",
                    reason="No matching tool available. Using generative response.",
                    context={"goal": goal},
                )
        
        # AUTH REQUIRED - ask user for credentials
        if failure_type == FailureType.AUTH_REQUIRED:
            # Detect which service needs auth based on tool name
            service = self._detect_service(tool_name or "")
            return RecoveryAction(
                action="request_config",
                reason=f"Authentication required for {service}",
                context={
                    "tool_name": tool_name,
                    "service": service,
                    "error": error,
                    "config_key": self._get_config_key(service),
                    "instructions": self._get_auth_instructions(service),
                },
            )
        
        # INVALID PARAMETERS - try to refine
        if failure_type == FailureType.INVALID_PARAMETERS:
            return RecoveryAction(
                action="refine_params",
                reason=f"Parameter extraction failed: {error}",
                context={"tool_name": tool_name, "error": error},
            )
        
        # TOOL EXECUTION ERROR - check if tool is consistently failing
        if failure_type == FailureType.TOOL_EXECUTION_ERROR:
            if tool_name:
                success_rate = self.history.get_tool_success_rate(tool_name)
                
                # If tool has low success rate, maybe it needs refactoring
                if success_rate < 0.3:
                    if self._forge_callback:
                        return RecoveryAction(
                            action="refactor_tool",
                            reason=f"Tool '{tool_name}' has {success_rate:.0%} success rate. Needs refactoring.",
                            context={"tool_name": tool_name, "error": error},
                        )
                
                # Otherwise try retry with more context
                if len(similar) < 2:  # Not a repeated failure
                    return RecoveryAction(
                        action="retry",
                        reason=f"Tool execution failed: {error}. Retrying with more context.",
                        context={"tool_name": tool_name, "error": error, "attempt": 1},
                    )
            
            # Fall back to generative
            return RecoveryAction(
                action="fallback_generative",
                reason=f"Tool execution failed and retry unlikely to help: {error}",
                context={"original_error": error},
            )
        
        # Default: fallback to generative
        return RecoveryAction(
            action="fallback_generative",
            reason=f"Unable to recover from {failure_type.value}: {error}",
            context={},
        )
    
    def record_success(
        self,
        goal: str,
        tool_name: str,
        parameters: Dict[str, Any],
        result: str,
        duration_ms: int = 0,
    ) -> None:
        """Record successful execution."""
        record = ExecutionRecord(
            goal=goal,
            tool_name=tool_name,
            parameters=parameters,
            success=True,
            result=result,
            duration_ms=duration_ms,
        )
        self.history.record(record)
    
    # Service detection and auth instructions
    
    def _detect_service(self, tool_name: str) -> str:
        """Detect which service a tool belongs to."""
        tool_lower = tool_name.lower()
        
        if "strava" in tool_lower:
            return "Strava"
        elif "github" in tool_lower:
            return "GitHub"
        elif "spotify" in tool_lower:
            return "Spotify"
        elif "slack" in tool_lower:
            return "Slack"
        elif "openai" in tool_lower or "gpt" in tool_lower:
            return "OpenAI"
        else:
            return tool_name.replace("_", " ").title()
    
    def _get_config_key(self, service: str) -> str:
        """Get the Redis config key for a service."""
        service_lower = service.lower().replace(" ", "_")
        return f"{service_lower}:token"
    
    def _get_auth_instructions(self, service: str) -> str:
        """Get human-readable auth instructions for a service."""
        instructions = {
            "Strava": (
                "To connect Strava:\n"
                "1. Go to https://www.strava.com/settings/api to get your app credentials\n"
                "2. Do OAuth flow to get access_token and refresh_token with scope 'activity:read_all'\n"
                "3. Set all credentials in Redis:\n"
                "   docker compose exec redis redis-cli SET strava:client_id YOUR_CLIENT_ID\n"
                "   docker compose exec redis redis-cli SET strava:client_secret YOUR_SECRET\n"
                "   docker compose exec redis redis-cli SET strava:token YOUR_ACCESS_TOKEN\n"
                "   docker compose exec redis redis-cli SET strava:refresh_token YOUR_REFRESH_TOKEN\n"
                "\n"
                "Or use the strava_setup tool with all four parameters."
            ),
            "GitHub": (
                "To connect GitHub:\n"
                "1. Go to https://github.com/settings/tokens and create a Personal Access Token\n"
                "2. Run: docker compose exec redis redis-cli SET github:token YOUR_TOKEN"
            ),
            "Spotify": (
                "To connect Spotify:\n"
                "1. Go to https://developer.spotify.com/dashboard and create an app\n"
                "2. Copy your Access Token\n"
                "3. Run: docker compose exec redis redis-cli SET spotify:token YOUR_TOKEN"
            ),
            "OpenAI": (
                "To connect OpenAI:\n"
                "1. Go to https://platform.openai.com/api-keys and create an API key\n"
                "2. Run: docker compose exec redis redis-cli SET openai:token YOUR_KEY"
            ),
        }
        
        return instructions.get(service, (
            f"To connect {service}:\n"
            f"1. Get an API token from {service}\n"
            f"2. Run: docker compose exec redis redis-cli SET {service.lower()}:token YOUR_TOKEN"
        ))
