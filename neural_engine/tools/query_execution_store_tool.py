"""
QueryExecutionStoreTool: Safe read-only queries to execution history.
Phase 9a: Enables neurons to investigate system performance.

This tool provides predefined safe queries that neurons can use to analyze:
- Tool statistics and performance
- Recent execution history
- Failure patterns
- Slow executions
- Usage trends
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from neural_engine.tools.base_tool import BaseTool
from neural_engine.core.execution_store import ExecutionStore


class QueryExecutionStoreTool(BaseTool):
    """
    Tool for querying execution history with safe, predefined queries.
    
    Neurons can ask questions like:
    - "Show me recent failed executions"
    - "What are the slowest tools?"
    - "Get statistics for prime_checker tool"
    """
    
    def __init__(self, execution_store: Optional[ExecutionStore] = None):
        """
        Initialize QueryExecutionStoreTool.
        
        Args:
            execution_store: ExecutionStore instance (creates new if None)
        """
        super().__init__()
        self._owns_store = execution_store is None
        self.execution_store = execution_store or ExecutionStore()
        
        # Map query types to handler methods
        self.query_handlers = {
            "tool_stats": self._query_tool_stats,
            "recent_failures": self._query_recent_failures,
            "recent_successes": self._query_recent_successes,
            "slow_executions": self._query_slow_executions,
            "recent_executions": self._query_recent_executions,
            "top_tools": self._query_top_tools,
            "tool_usage_trend": self._query_tool_usage_trend,
            "execution_by_intent": self._query_execution_by_intent,
        }
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return tool definition for LLM."""
        return {
            "name": "query_execution_store",
            "description": (
                "Query the execution history database to analyze system performance. "
                "Provides safe, read-only access to execution logs, tool statistics, "
                "failure patterns, and performance metrics. Use this to investigate "
                "issues, identify trends, and understand system behavior."
            ),
            "parameters": {
                "query_type": {
                    "type": "string",
                    "description": (
                        "Type of query to execute. Options: "
                        "'tool_stats' (get statistics for a specific tool), "
                        "'recent_failures' (show recent failed executions), "
                        "'recent_successes' (show recent successful executions), "
                        "'slow_executions' (find slow executions over threshold), "
                        "'recent_executions' (get recent execution history), "
                        "'top_tools' (most frequently used tools), "
                        "'tool_usage_trend' (usage over time for a tool), "
                        "'execution_by_intent' (group executions by intent type)"
                    ),
                    "required": True
                },
                "tool_name": {
                    "type": "string",
                    "description": "Tool name (required for 'tool_stats' and 'tool_usage_trend')",
                    "required": False
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10)",
                    "required": False
                },
                "threshold_ms": {
                    "type": "integer",
                    "description": "Duration threshold in milliseconds (for 'slow_executions', default: 5000)",
                    "required": False
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (for trend queries, default: 7)",
                    "required": False
                }
            }
        }
    
    def execute(self, query_type: str, tool_name: Optional[str] = None, 
                limit: int = 10, threshold_ms: int = 5000, days: int = 7) -> Dict[str, Any]:
        """
        Execute a predefined safe query.
        
        Args:
            query_type: Type of query to run
            tool_name: Tool name (for tool-specific queries)
            limit: Maximum results
            threshold_ms: Duration threshold for slow execution queries
            days: Days to look back for trend queries
            
        Returns:
            Query results with metadata
        """
        # Validate query type
        if query_type not in self.query_handlers:
            return {
                "success": False,
                "error": f"Unknown query type: {query_type}",
                "available_queries": list(self.query_handlers.keys())
            }
        
        # Execute query via handler
        try:
            handler = self.query_handlers[query_type]
            results = handler(
                tool_name=tool_name,
                limit=limit,
                threshold_ms=threshold_ms,
                days=days
            )
            
            return {
                "success": True,
                "query_type": query_type,
                "results": results,
                "count": len(results) if isinstance(results, list) else 1,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "query_type": query_type,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _query_tool_stats(self, tool_name: Optional[str], **kwargs) -> Dict[str, Any]:
        """Get statistics for a specific tool."""
        if not tool_name:
            raise ValueError("tool_name is required for 'tool_stats' query")
        
        stats = self.execution_store.get_tool_statistics(tool_name)
        
        if stats is None:
            return {
                "tool_name": tool_name,
                "message": "No statistics found - tool may not have been executed yet"
            }
        
        return stats
    
    def _query_recent_failures(self, limit: int, **kwargs) -> List[Dict[str, Any]]:
        """Get recent failed executions."""
        all_recent = self.execution_store.get_recent_executions(limit=limit * 2)
        
        # Filter for failures
        failures = [
            exec for exec in all_recent 
            if not exec.get('success', True)
        ]
        
        return failures[:limit]
    
    def _query_recent_successes(self, limit: int, **kwargs) -> List[Dict[str, Any]]:
        """Get recent successful executions."""
        all_recent = self.execution_store.get_recent_executions(limit=limit * 2)
        
        # Filter for successes
        successes = [
            exec for exec in all_recent 
            if exec.get('success', False)
        ]
        
        return successes[:limit]
    
    def _query_slow_executions(self, limit: int, threshold_ms: int, **kwargs) -> List[Dict[str, Any]]:
        """Get executions that took longer than threshold."""
        all_recent = self.execution_store.get_recent_executions(limit=100)
        
        # Filter for slow executions
        slow = [
            exec for exec in all_recent
            if exec.get('duration_ms', 0) and exec['duration_ms'] > threshold_ms
        ]
        
        # Sort by duration (slowest first)
        slow.sort(key=lambda x: x.get('duration_ms', 0), reverse=True)
        
        return slow[:limit]
    
    def _query_recent_executions(self, limit: int, **kwargs) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        return self.execution_store.get_recent_executions(limit=limit)
    
    def _query_top_tools(self, limit: int, **kwargs) -> List[Dict[str, Any]]:
        """Get most frequently used tools."""
        return self.execution_store.get_top_tools(limit=limit, min_executions=1)
    
    def _query_tool_usage_trend(self, tool_name: Optional[str], days: int, **kwargs) -> Dict[str, Any]:
        """Get usage trend for a tool over time."""
        if not tool_name:
            raise ValueError("tool_name is required for 'tool_usage_trend' query")
        
        # Get tool statistics
        stats = self.execution_store.get_tool_statistics(tool_name)
        
        if stats is None:
            return {
                "tool_name": tool_name,
                "message": "No usage data found"
            }
        
        # For now, return current stats
        # TODO: Add time-series query to ExecutionStore for historical trends
        return {
            "tool_name": tool_name,
            "current_stats": stats,
            "period_days": days,
            "note": "Time-series analysis coming soon"
        }
    
    def _query_execution_by_intent(self, limit: int, **kwargs) -> Dict[str, Any]:
        """Get executions grouped by intent type."""
        recent = self.execution_store.get_recent_executions(limit=limit)
        
        # Group by intent
        by_intent = {}
        for exec in recent:
            intent = exec.get('intent', 'unknown')
            if intent not in by_intent:
                by_intent[intent] = []
            by_intent[intent].append(exec)
        
        # Calculate statistics per intent
        intent_stats = {}
        for intent, executions in by_intent.items():
            total = len(executions)
            successes = sum(1 for e in executions if e.get('success', False))
            failures = total - successes
            
            intent_stats[intent] = {
                "total": total,
                "successes": successes,
                "failures": failures,
                "success_rate": successes / total if total > 0 else 0,
                "sample_executions": executions[:3]  # Show first 3 examples
            }
        
        return intent_stats
    
    def close(self):
        """Close ExecutionStore connection if we own it."""
        if self._owns_store and self.execution_store:
            self.execution_store.close()
