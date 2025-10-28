"""
AnalyzeToolPerformanceTool: Statistical analysis of tool performance.
Phase 9a: Enables neurons to detect patterns, trends, and degradation.

This tool performs advanced analytics on tool execution data:
- Performance trend analysis
- Degradation detection
- Comparative analysis
- Health scoring
- Anomaly detection
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from neural_engine.tools.base_tool import BaseTool
from neural_engine.core.execution_store import ExecutionStore


class AnalyzeToolPerformanceTool(BaseTool):
    """
    Tool for analyzing tool performance with statistical methods.
    
    Neurons can request analysis like:
    - "Analyze performance degradation for strava_get_my_activities"
    - "Compare success rates across all tools"
    - "Detect anomalies in tool execution patterns"
    """
    
    def __init__(self, execution_store: Optional[ExecutionStore] = None):
        """
        Initialize AnalyzeToolPerformanceTool.
        
        Args:
            execution_store: ExecutionStore instance (creates new if None)
        """
        super().__init__()
        self._owns_store = execution_store is None
        self.execution_store = execution_store or ExecutionStore()
        
        # Map analysis types to handler methods
        self.analysis_handlers = {
            "health_check": self._analyze_health_check,
            "performance_degradation": self._analyze_performance_degradation,
            "comparative_analysis": self._analyze_comparative,
            "success_rate_trend": self._analyze_success_rate_trend,
            "failure_patterns": self._analyze_failure_patterns,
            "usage_patterns": self._analyze_usage_patterns,
        }
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return tool definition for LLM."""
        return {
            "name": "analyze_tool_performance",
            "description": (
                "Perform statistical analysis on tool performance data. "
                "Detects trends, degradation, anomalies, and patterns in tool execution. "
                "Use this to understand tool health, identify issues, and recommend improvements."
            ),
            "parameters": {
                "analysis_type": {
                    "type": "string",
                    "description": (
                        "Type of analysis to perform. Options: "
                        "'health_check' (overall tool health assessment), "
                        "'performance_degradation' (detect declining performance), "
                        "'comparative_analysis' (compare multiple tools), "
                        "'success_rate_trend' (success rate over time), "
                        "'failure_patterns' (analyze failure reasons), "
                        "'usage_patterns' (identify usage trends)"
                    ),
                    "required": True
                },
                "tool_name": {
                    "type": "string",
                    "description": "Tool name to analyze (required for single-tool analyses)",
                    "required": False
                },
                "tool_names": {
                    "type": "array",
                    "description": "List of tool names (for comparative analysis)",
                    "required": False
                },
                "threshold": {
                    "type": "number",
                    "description": "Threshold for health/performance checks (0-100, default: 70)",
                    "required": False
                }
            }
        }
    
    def execute(self, analysis_type: str, tool_name: Optional[str] = None,
                tool_names: Optional[List[str]] = None, threshold: float = 70.0) -> Dict[str, Any]:
        """
        Execute a performance analysis.
        
        Args:
            analysis_type: Type of analysis to perform
            tool_name: Single tool name to analyze
            tool_names: Multiple tool names for comparative analysis
            threshold: Performance threshold (0-100)
            
        Returns:
            Analysis results with insights and recommendations
        """
        # Validate analysis type
        if analysis_type not in self.analysis_handlers:
            return {
                "success": False,
                "error": f"Unknown analysis type: {analysis_type}",
                "available_analyses": list(self.analysis_handlers.keys())
            }
        
        # Execute analysis via handler
        try:
            handler = self.analysis_handlers[analysis_type]
            results = handler(
                tool_name=tool_name,
                tool_names=tool_names,
                threshold=threshold
            )
            
            return {
                "success": True,
                "analysis_type": analysis_type,
                "results": results,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "analysis_type": analysis_type,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _analyze_health_check(self, tool_name: Optional[str], threshold: float, **kwargs) -> Dict[str, Any]:
        """Perform health check on a tool."""
        if not tool_name:
            raise ValueError("tool_name is required for 'health_check' analysis")
        
        stats = self.execution_store.get_tool_statistics(tool_name)
        
        if stats is None:
            return {
                "tool_name": tool_name,
                "health_status": "unknown",
                "message": "No execution data available"
            }
        
        # Calculate health score (0-100)
        total = stats.get('total_executions', 0)
        successes = stats.get('successful_executions', 0)
        
        if total == 0:
            health_score = 0
            status = "no_data"
        else:
            success_rate = successes / total
            
            # Health formula: success_rate weighted by experience
            import math
            usage_factor = min(math.log10(total + 1) * 10, 30)  # Max 30 points
            health_score = min(100, success_rate * 70 + usage_factor)
            
            # Categorize health
            if health_score >= 80:
                status = "excellent"
            elif health_score >= threshold:
                status = "good"
            elif health_score >= 50:
                status = "struggling"
            else:
                status = "failing"
        
        return {
            "tool_name": tool_name,
            "health_score": round(health_score, 1),
            "health_status": status,
            "statistics": stats,
            "recommendations": self._generate_health_recommendations(stats, health_score)
        }
    
    def _analyze_performance_degradation(self, tool_name: Optional[str], **kwargs) -> Dict[str, Any]:
        """Detect performance degradation over time."""
        if not tool_name:
            raise ValueError("tool_name is required for 'performance_degradation' analysis")
        
        stats = self.execution_store.get_tool_statistics(tool_name)
        
        if stats is None:
            return {
                "tool_name": tool_name,
                "degradation_detected": False,
                "message": "No execution data available"
            }
        
        # Get recent executions to analyze trends
        # TODO: Implement time-series analysis when available
        total = stats.get('total_executions', 0)
        success_rate = (stats.get('successful_executions', 0) / total) if total > 0 else 0
        
        # Simple degradation heuristics
        degradation_detected = False
        degradation_indicators = []
        
        if success_rate < 0.5:
            degradation_detected = True
            degradation_indicators.append("Low success rate (< 50%)")
        
        if stats.get('failed_executions', 0) > stats.get('successful_executions', 0):
            degradation_detected = True
            degradation_indicators.append("More failures than successes")
        
        return {
            "tool_name": tool_name,
            "degradation_detected": degradation_detected,
            "current_success_rate": round(success_rate * 100, 1),
            "indicators": degradation_indicators,
            "statistics": stats,
            "recommendations": self._generate_degradation_recommendations(stats, degradation_detected)
        }
    
    def _analyze_comparative(self, tool_names: Optional[List[str]], threshold: float, **kwargs) -> Dict[str, Any]:
        """Compare performance across multiple tools."""
        if not tool_names:
            # Compare all tools
            top_tools = self.execution_store.get_top_tools(limit=100, min_executions=1)
            tool_names = [tool['tool_name'] for tool in top_tools]
        
        comparisons = []
        for tool_name in tool_names:
            stats = self.execution_store.get_tool_statistics(tool_name)
            if stats:
                total = stats.get('total_executions', 0)
                successes = stats.get('successful_executions', 0)
                success_rate = (successes / total) if total > 0 else 0
                
                comparisons.append({
                    "tool_name": tool_name,
                    "success_rate": round(success_rate * 100, 1),
                    "total_executions": total,
                    "avg_duration_ms": stats.get('avg_duration_ms')
                })
        
        # Sort by success rate
        comparisons.sort(key=lambda x: x['success_rate'], reverse=True)
        
        # Categorize
        excellent = [t for t in comparisons if t['success_rate'] >= 90]
        good = [t for t in comparisons if 70 <= t['success_rate'] < 90]
        struggling = [t for t in comparisons if 50 <= t['success_rate'] < 70]
        failing = [t for t in comparisons if t['success_rate'] < 50]
        
        return {
            "total_tools_analyzed": len(comparisons),
            "categories": {
                "excellent": {"count": len(excellent), "tools": excellent},
                "good": {"count": len(good), "tools": good},
                "struggling": {"count": len(struggling), "tools": struggling},
                "failing": {"count": len(failing), "tools": failing}
            },
            "best_performer": comparisons[0] if comparisons else None,
            "worst_performer": comparisons[-1] if comparisons else None,
            "recommendations": self._generate_comparative_recommendations(comparisons)
        }
    
    def _analyze_success_rate_trend(self, tool_name: Optional[str], **kwargs) -> Dict[str, Any]:
        """Analyze success rate trend over time."""
        if not tool_name:
            raise ValueError("tool_name is required for 'success_rate_trend' analysis")
        
        stats = self.execution_store.get_tool_statistics(tool_name)
        
        if stats is None:
            return {
                "tool_name": tool_name,
                "trend": "unknown",
                "message": "No execution data available"
            }
        
        # Current success rate
        total = stats.get('total_executions', 0)
        successes = stats.get('successful_executions', 0)
        current_rate = (successes / total) if total > 0 else 0
        
        # TODO: Calculate historical rates when time-series data available
        # For now, return current rate
        
        return {
            "tool_name": tool_name,
            "current_success_rate": round(current_rate * 100, 1),
            "trend": "stable",  # Placeholder
            "statistics": stats,
            "note": "Time-series trend analysis coming soon"
        }
    
    def _analyze_failure_patterns(self, tool_name: Optional[str], **kwargs) -> Dict[str, Any]:
        """Analyze patterns in tool failures."""
        if tool_name:
            # Analyze specific tool
            stats = self.execution_store.get_tool_statistics(tool_name)
            if not stats:
                return {
                    "tool_name": tool_name,
                    "message": "No execution data available"
                }
            
            failures = stats.get('failed_executions', 0)
            total = stats.get('total_executions', 0)
            
            return {
                "tool_name": tool_name,
                "total_failures": failures,
                "failure_rate": round((failures / total * 100) if total > 0 else 0, 1),
                "statistics": stats
            }
        else:
            # Analyze all tools
            top_tools = self.execution_store.get_top_tools(limit=100, min_executions=1)
            
            failing_tools = []
            for tool in top_tools:
                tool_name = tool['tool_name']
                stats = self.execution_store.get_tool_statistics(tool_name)
                if stats:
                    failures = stats.get('failed_executions', 0)
                    if failures > 0:
                        total = stats.get('total_executions', 0)
                        failing_tools.append({
                            "tool_name": tool_name,
                            "failures": failures,
                            "failure_rate": round((failures / total * 100) if total > 0 else 0, 1)
                        })
            
            # Sort by failure count
            failing_tools.sort(key=lambda x: x['failures'], reverse=True)
            
            return {
                "total_failing_tools": len(failing_tools),
                "top_failing_tools": failing_tools[:10],
                "recommendations": "Investigate top failing tools for common patterns"
            }
    
    def _analyze_usage_patterns(self, tool_name: Optional[str], **kwargs) -> Dict[str, Any]:
        """Analyze tool usage patterns."""
        if tool_name:
            stats = self.execution_store.get_tool_statistics(tool_name)
            if not stats:
                return {
                    "tool_name": tool_name,
                    "message": "No usage data available"
                }
            
            return {
                "tool_name": tool_name,
                "usage_stats": stats,
                "last_used": stats.get('last_used')
            }
        else:
            # Get overall usage patterns
            top_tools = self.execution_store.get_top_tools(limit=10, min_executions=1)
            
            return {
                "most_used_tools": top_tools,
                "total_tools_with_usage": len(top_tools)
            }
    
    def _generate_health_recommendations(self, stats: Dict, health_score: float) -> List[str]:
        """Generate recommendations based on health score."""
        recommendations = []
        
        if health_score < 50:
            recommendations.append("CRITICAL: Tool needs immediate attention")
            recommendations.append("Consider rewriting or deprecating this tool")
        elif health_score < 70:
            recommendations.append("Tool needs optimization")
            recommendations.append("Review recent failures for common patterns")
        elif health_score < 90:
            recommendations.append("Tool is functioning well but has room for improvement")
        else:
            recommendations.append("Tool is performing excellently")
        
        total = stats.get('total_executions', 0)
        if total < 10:
            recommendations.append("Limited data - more executions needed for accurate assessment")
        
        return recommendations
    
    def _generate_degradation_recommendations(self, stats: Dict, degraded: bool) -> List[str]:
        """Generate recommendations for degradation analysis."""
        recommendations = []
        
        if degraded:
            recommendations.append("Performance degradation detected")
            recommendations.append("Review recent code changes")
            recommendations.append("Check for external dependency issues")
            recommendations.append("Increase error logging for debugging")
        else:
            recommendations.append("No significant degradation detected")
            recommendations.append("Continue monitoring performance")
        
        return recommendations
    
    def _generate_comparative_recommendations(self, comparisons: List[Dict]) -> List[str]:
        """Generate recommendations from comparative analysis."""
        recommendations = []
        
        if not comparisons:
            return ["No tools to compare"]
        
        failing_count = sum(1 for t in comparisons if t['success_rate'] < 50)
        if failing_count > 0:
            recommendations.append(f"{failing_count} tools are failing (success rate < 50%)")
            recommendations.append("Prioritize fixing failing tools")
        
        if len(comparisons) > 0:
            avg_success = sum(t['success_rate'] for t in comparisons) / len(comparisons)
            recommendations.append(f"Average success rate across all tools: {avg_success:.1f}%")
        
        return recommendations
    
    def close(self):
        """Close ExecutionStore connection if we own it."""
        if self._owns_store and self.execution_store:
            self.execution_store.close()
