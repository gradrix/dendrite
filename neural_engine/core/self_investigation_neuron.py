"""
SelfInvestigationNeuron: Autonomous system health monitoring and investigation.
Phase 9b: The system becomes self-aware and proactively monitors itself.

This neuron runs continuously in the background, using Phase 9a analytics tools
to investigate system health without human prompting. It detects anomalies,
identifies degrading tools, and generates actionable insights.

Key Capabilities:
- Automatic health checks (configurable interval)
- Anomaly detection (statistical methods)
- Degradation detection (performance trends)
- Smart alerting (only on real issues)
- Insight generation (actionable recommendations)
"""

import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from neural_engine.core.neuron import BaseNeuron
from neural_engine.tools.query_execution_store_tool import QueryExecutionStoreTool
from neural_engine.tools.analyze_tool_performance_tool import AnalyzeToolPerformanceTool
from neural_engine.tools.generate_report_tool import GenerateReportTool
from neural_engine.core.execution_store import ExecutionStore


class SelfInvestigationNeuron(BaseNeuron):
    """
    Autonomous neuron that continuously monitors and investigates system health.
    
    Unlike reactive neurons that respond to user queries, this neuron proactively
    investigates the system, detects issues, and generates insights without
    human intervention.
    """
    
    def __init__(
        self,
        message_bus,
        ollama_client,
        execution_store: Optional[ExecutionStore] = None,
        check_interval_seconds: int = 300,  # Default: 5 minutes
        alert_threshold: float = 0.6,  # Alert if health score < 60%
        enable_auto_alerts: bool = True
    ):
        """
        Initialize the Self-Investigation Neuron.
        
        Args:
            message_bus: Communication bus for publishing findings
            ollama_client: LLM client for generating insights
            execution_store: Database connection for analytics
            check_interval_seconds: How often to check system health
            alert_threshold: Health score threshold for alerts (0-1)
            enable_auto_alerts: Whether to automatically publish alerts
        """
        super().__init__(message_bus, ollama_client)
        
        # Configuration
        self.check_interval = check_interval_seconds
        self.alert_threshold = alert_threshold
        self.enable_auto_alerts = enable_auto_alerts
        
        # Analytics tools
        self._owns_store = execution_store is None  # Track if we created the store
        self.execution_store = execution_store or ExecutionStore()
        self.query_tool = QueryExecutionStoreTool(execution_store=self.execution_store)
        self.analyzer = AnalyzeToolPerformanceTool(execution_store=self.execution_store)
        self.reporter = GenerateReportTool()
        
        # State tracking
        self.last_check_time = None
        self.investigation_count = 0
        self.alerts_generated = []
        self.running = False
        self._thread = None
        
        # Baseline metrics (learned over time)
        self.baseline_health = None
        self.known_issues = set()  # Track known issues to avoid duplicate alerts
    
    def process(self, goal_id: str, data: Any, depth: int = 0) -> Dict[str, Any]:
        """
        Process investigative goals.
        
        This neuron can respond to direct queries like:
        - "Investigate system health"
        - "What issues need attention?"
        - "Generate health report"
        
        But it also runs autonomously in the background.
        """
        goal_text = str(data).lower()
        
        # Check for report first (since it contains "health")
        if "report" in goal_text:
            health_data = self.investigate_health()
            return self._generate_health_report(health_data)
        
        elif "investigate" in goal_text or "health" in goal_text:
            return self.investigate_health()
        
        elif "anomal" in goal_text or "detect" in goal_text:
            return self.detect_anomalies()
        
        elif "degrad" in goal_text:
            return self.detect_degradation()
        
        elif "insight" in goal_text or "recommendation" in goal_text:
            return self.generate_insights()
        
        else:
            # Default: Full investigation
            return self.investigate_health()
    
    def investigate_health(self) -> Dict[str, Any]:
        """
        Comprehensive system health investigation.
        
        This is the core investigation method that:
        1. Queries system statistics
        2. Analyzes tool performance
        3. Detects issues
        4. Generates insights
        
        Returns:
            Dict with health_score, issues, insights, and recommendations
        """
        self.investigation_count += 1
        investigation_start = time.time()
        
        # Step 1: Get comparative analysis (all tools)
        comparison_result = self.analyzer.execute(
            analysis_type="comparative_analysis"
        )
        
        if not comparison_result["success"]:
            return {
                "success": False,
                "error": "Failed to retrieve comparative analysis",
                "investigation_id": f"inv-{self.investigation_count}"
            }
        
        analysis = comparison_result["results"]
        
        # Step 2: Calculate overall system health
        total_tools = analysis["total_tools_analyzed"]
        if total_tools == 0:
            return {
                "success": True,
                "health_score": 1.0,
                "status": "no_data",
                "message": "No tools have been executed yet",
                "investigation_id": f"inv-{self.investigation_count}"
            }
        
        categories = analysis["categories"]
        excellent = categories.get("excellent", {}).get("count", 0)
        good = categories.get("good", {}).get("count", 0)
        struggling = categories.get("struggling", {}).get("count", 0)
        failing = categories.get("failing", {}).get("count", 0)
        
        # Calculate weighted health score
        # Excellent: 1.0, Good: 0.75, Struggling: 0.5, Failing: 0.0
        health_score = (
            (excellent * 1.0) +
            (good * 0.75) +
            (struggling * 0.5) +
            (failing * 0.0)
        ) / total_tools if total_tools > 0 else 0.0
        
        # Step 3: Identify specific issues
        issues = []
        
        # Check for failing tools
        if failing > 0:
            failure_result = self.analyzer.execute(analysis_type="failure_patterns")
            if failure_result["success"]:
                top_failing = failure_result["results"].get("top_failing_tools", [])
                for tool in top_failing[:3]:  # Top 3 failing tools
                    issues.append({
                        "severity": "high",
                        "type": "tool_failure",
                        "tool_name": tool["tool_name"],
                        "failure_rate": tool["failure_rate"],
                        "description": f"{tool['tool_name']} has {tool['failure_rate']}% failure rate"
                    })
        
        # Check for struggling tools
        if struggling > 0:
            struggling_tools = categories.get("struggling", {}).get("tools", [])
            for tool in struggling_tools[:2]:  # Top 2 struggling tools
                issues.append({
                    "severity": "medium",
                    "type": "tool_struggling",
                    "tool_name": tool["tool_name"],
                    "success_rate": tool["success_rate"],
                    "description": f"{tool['tool_name']} is struggling with {tool['success_rate']}% success rate"
                })
        
        # Step 4: Check for recent failures
        recent_failures = self.query_tool.execute(
            query_type="recent_failures",
            limit=10
        )
        
        if recent_failures["success"] and recent_failures["count"] > 5:
            issues.append({
                "severity": "medium",
                "type": "high_failure_volume",
                "count": recent_failures["count"],
                "description": f"{recent_failures['count']} failures in recent history"
            })
        
        # Step 5: Check for slow executions
        slow_executions = self.query_tool.execute(
            query_type="slow_executions",
            threshold_ms=5000,  # 5 seconds
            limit=5
        )
        
        if slow_executions["success"] and slow_executions["count"] > 0:
            issues.append({
                "severity": "low",
                "type": "performance_issue",
                "count": slow_executions["count"],
                "description": f"{slow_executions['count']} executions took >5 seconds"
            })
        
        # Step 6: Generate insights
        insights = self._generate_insights_from_issues(issues, health_score)
        
        # Step 7: Determine status
        if health_score >= 0.8:
            status = "healthy"
        elif health_score >= 0.6:
            status = "warning"
        else:
            status = "critical"
        
        investigation_duration = time.time() - investigation_start
        
        result = {
            "success": True,
            "investigation_id": f"inv-{self.investigation_count}",
            "timestamp": datetime.now().isoformat(),
            "duration_ms": int(investigation_duration * 1000),
            "health_score": health_score,
            "status": status,
            "total_tools": total_tools,
            "tool_categories": {
                "excellent": excellent,
                "good": good,
                "struggling": struggling,
                "failing": failing
            },
            "issues": issues,
            "insights": insights,
            "best_performer": analysis.get("best_performer"),
            "worst_performer": analysis.get("worst_performer")
        }
        
        # Update baseline
        if self.baseline_health is None:
            self.baseline_health = health_score
        
        # Publish alert if needed
        if self.enable_auto_alerts and self._should_alert(result):
            self._publish_alert(result)
        
        self.last_check_time = datetime.now()
        
        return result
    
    def detect_anomalies(self) -> Dict[str, Any]:
        """
        Detect statistical anomalies in system behavior.
        
        Compares current metrics to baseline and identifies deviations.
        
        Returns:
            Dict with detected anomalies and severity levels
        """
        anomalies = []
        
        # Get current health
        current_health = self.investigate_health()
        
        if not current_health["success"]:
            return {
                "success": False,
                "error": "Failed to get current health metrics"
            }
        
        current_score = current_health["health_score"]
        
        # Check for health score anomaly
        if self.baseline_health is not None:
            health_delta = self.baseline_health - current_score
            
            if health_delta > 0.2:  # 20% drop
                anomalies.append({
                    "type": "health_degradation",
                    "severity": "high",
                    "baseline": self.baseline_health,
                    "current": current_score,
                    "delta": health_delta,
                    "description": f"System health dropped {health_delta*100:.1f}% from baseline"
                })
            elif health_delta > 0.1:  # 10% drop
                anomalies.append({
                    "type": "health_degradation",
                    "severity": "medium",
                    "baseline": self.baseline_health,
                    "current": current_score,
                    "delta": health_delta,
                    "description": f"System health dropped {health_delta*100:.1f}% from baseline"
                })
        
        # Check for sudden spike in failures
        recent_failures = self.query_tool.execute(
            query_type="recent_failures",
            limit=20
        )
        
        if recent_failures["success"] and recent_failures["count"] > 10:
            anomalies.append({
                "type": "failure_spike",
                "severity": "high",
                "count": recent_failures["count"],
                "description": f"Unusual spike in failures: {recent_failures['count']} recent failures"
            })
        
        # Check for new tool failures (not in known_issues)
        for issue in current_health.get("issues", []):
            if issue["type"] == "tool_failure":
                issue_key = f"fail_{issue['tool_name']}"
                if issue_key not in self.known_issues:
                    anomalies.append({
                        "type": "new_failure",
                        "severity": "high",
                        "tool_name": issue["tool_name"],
                        "description": f"New tool failure detected: {issue['tool_name']}"
                    })
                    self.known_issues.add(issue_key)
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "anomalies_detected": len(anomalies),
            "anomalies": anomalies,
            "baseline_health": self.baseline_health,
            "current_health": current_score
        }
    
    def detect_degradation(self) -> Dict[str, Any]:
        """
        Detect tools with degrading performance over time.
        
        Returns:
            Dict with list of degrading tools and recommendations
        """
        degrading_tools = []
        
        # Get top tools by usage
        top_tools_result = self.query_tool.execute(
            query_type="top_tools",
            limit=10
        )
        
        if not top_tools_result["success"]:
            return {
                "success": False,
                "error": "Failed to retrieve top tools"
            }
        
        # Check each tool for degradation
        for tool in top_tools_result["results"]:
            tool_name = tool["tool_name"]
            
            degradation_result = self.analyzer.execute(
                analysis_type="performance_degradation",
                tool_name=tool_name
            )
            
            if degradation_result["success"]:
                if degradation_result["results"].get("degradation_detected", False):
                    degrading_tools.append({
                        "tool_name": tool_name,
                        "current_success_rate": degradation_result["results"].get("current_success_rate", 0),
                        "indicators": degradation_result["results"].get("indicators", []),
                        "severity": "high" if degradation_result["results"].get("current_success_rate", 100) < 50 else "medium"
                    })
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "degrading_tools_count": len(degrading_tools),
            "degrading_tools": degrading_tools,
            "recommendations": self._generate_degradation_recommendations(degrading_tools)
        }
    
    def generate_insights(self) -> Dict[str, Any]:
        """
        Generate high-level insights about system behavior.
        
        Uses LLM to analyze patterns and generate natural language insights.
        
        Returns:
            Dict with insights and strategic recommendations
        """
        # Get comprehensive system state
        health = self.investigate_health()
        anomalies = self.detect_anomalies()
        degradation = self.detect_degradation()
        
        # Prepare data for LLM
        context = {
            "health_score": health.get("health_score", 0),
            "status": health.get("status", "unknown"),
            "issues": health.get("issues", []),
            "anomalies": anomalies.get("anomalies", []),
            "degrading_tools": degradation.get("degrading_tools", [])
        }
        
        # Generate insights (placeholder for now, would use LLM)
        insights = []
        
        # Insight 1: Overall trend
        if health["health_score"] >= 0.8:
            insights.append({
                "type": "positive",
                "category": "overall_health",
                "message": "System is performing well with high reliability"
            })
        elif health["health_score"] < 0.6:
            insights.append({
                "type": "negative",
                "category": "overall_health",
                "message": "System health is below acceptable thresholds"
            })
        
        # Insight 2: Tool quality distribution
        failing_count = health["tool_categories"].get("failing", 0)
        excellent_count = health["tool_categories"].get("excellent", 0)
        total_count = health["total_tools"]
        
        if failing_count > total_count * 0.2:
            insights.append({
                "type": "negative",
                "category": "tool_quality",
                "message": f"{failing_count}/{total_count} tools are failing - urgent attention needed"
            })
        elif excellent_count > total_count * 0.7:
            insights.append({
                "type": "positive",
                "category": "tool_quality",
                "message": f"{excellent_count}/{total_count} tools performing excellently"
            })
        
        # Insight 3: Degradation trend
        if len(degradation.get("degrading_tools", [])) > 0:
            insights.append({
                "type": "warning",
                "category": "performance_trend",
                "message": f"{len(degradation['degrading_tools'])} tools showing performance degradation"
            })
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "insights": insights,
            "context": context,
            "recommendations": self._generate_strategic_recommendations(context, insights)
        }
    
    def start_monitoring(self):
        """
        Start the background monitoring loop.
        
        This runs the investigation on a periodic basis without blocking.
        """
        if self.running:
            return {"success": False, "error": "Already running"}
        
        self.running = True
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        
        return {
            "success": True,
            "message": f"Monitoring started with {self.check_interval}s interval"
        }
    
    def stop_monitoring(self):
        """Stop the background monitoring loop."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        
        return {
            "success": True,
            "message": "Monitoring stopped",
            "investigations_completed": self.investigation_count
        }
    
    def _monitoring_loop(self):
        """
        Internal monitoring loop that runs continuously.
        
        This is the autonomous component that makes the system self-aware.
        """
        while self.running:
            try:
                # Perform investigation
                result = self.investigate_health()
                
                # Log investigation
                self._log_investigation(result)
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                # Don't crash the monitoring loop on errors
                self._log_error(f"Monitoring loop error: {e}")
                time.sleep(self.check_interval)
    
    def _should_alert(self, investigation_result: Dict[str, Any]) -> bool:
        """
        Determine if an alert should be published.
        
        Smart alerting logic to avoid noise:
        - Alert on status change
        - Alert on new critical issues
        - Don't spam on known issues
        """
        status = investigation_result["status"]
        health_score = investigation_result["health_score"]
        
        # Always alert on critical status
        if status == "critical" and health_score < self.alert_threshold:
            return True
        
        # Alert on new high-severity issues
        high_severity_issues = [
            issue for issue in investigation_result.get("issues", [])
            if issue["severity"] == "high"
        ]
        
        if len(high_severity_issues) > 0:
            # Check if these are new issues
            for issue in high_severity_issues:
                issue_key = f"{issue['type']}_{issue.get('tool_name', 'system')}"
                if issue_key not in self.known_issues:
                    return True
        
        return False
    
    def _publish_alert(self, investigation_result: Dict[str, Any]):
        """
        Publish alert to message bus for other neurons to handle.
        
        This creates a feedback loop where investigation results
        can trigger corrective actions by other neurons.
        """
        alert = {
            "type": "system_health_alert",
            "timestamp": datetime.now().isoformat(),
            "investigation_id": investigation_result["investigation_id"],
            "health_score": investigation_result["health_score"],
            "status": investigation_result["status"],
            "issues": investigation_result["issues"],
            "insights": investigation_result["insights"]
        }
        
        self.alerts_generated.append(alert)
        
        # Publish to message bus
        alert_id = f"alert-{len(self.alerts_generated)}"
        self.message_bus.add_message(alert_id, "alert", alert)
    
    def _generate_health_report(self, health_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a formatted health report."""
        report_result = self.reporter.execute(
            report_type="executive_summary",
            data={
                "total_tools_analyzed": health_data["total_tools"],
                "categories": {
                    "excellent": {"count": health_data["tool_categories"]["excellent"]},
                    "good": {"count": health_data["tool_categories"]["good"]},
                    "struggling": {"count": health_data["tool_categories"]["struggling"]},
                    "failing": {"count": health_data["tool_categories"]["failing"]}
                },
                "best_performer": health_data.get("best_performer"),
                "worst_performer": health_data.get("worst_performer")
            },
            title="System Health Report"
        )
        
        return {
            "success": True,
            "health_data": health_data,
            "report": report_result.get("report", "Failed to generate report")
        }
    
    def _generate_insights_from_issues(
        self,
        issues: List[Dict[str, Any]],
        health_score: float
    ) -> List[str]:
        """Generate actionable insights from detected issues."""
        insights = []
        
        if health_score >= 0.9:
            insights.append("System is performing excellently")
        elif health_score >= 0.7:
            insights.append("System is healthy with minor issues to address")
        elif health_score >= 0.5:
            insights.append("System health requires attention")
        else:
            insights.append("System health is critical - immediate action required")
        
        # Generate specific insights from issues
        high_severity = [i for i in issues if i["severity"] == "high"]
        if len(high_severity) > 0:
            insights.append(f"{len(high_severity)} high-severity issues detected")
        
        failing_tools = [i for i in issues if i["type"] == "tool_failure"]
        if len(failing_tools) > 0:
            insights.append(f"{len(failing_tools)} tools are failing and need immediate fix")
        
        return insights
    
    def _generate_degradation_recommendations(
        self,
        degrading_tools: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations for degrading tools."""
        recommendations = []
        
        if len(degrading_tools) == 0:
            recommendations.append("No degrading tools detected - system is stable")
        else:
            recommendations.append(f"Investigate {len(degrading_tools)} degrading tools")
            
            for tool in degrading_tools[:3]:  # Top 3
                recommendations.append(
                    f"Review {tool['tool_name']} - success rate at {tool['current_success_rate']}%"
                )
        
        return recommendations
    
    def _generate_strategic_recommendations(
        self,
        context: Dict[str, Any],
        insights: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate high-level strategic recommendations."""
        recommendations = []
        
        health_score = context.get("health_score", 0)
        
        if health_score < 0.6:
            recommendations.append("URGENT: Focus on fixing failing tools immediately")
            recommendations.append("Consider temporarily disabling unreliable tools")
        elif health_score < 0.8:
            recommendations.append("Prioritize addressing struggling tools")
            recommendations.append("Review recent changes that may have impacted reliability")
        else:
            recommendations.append("Maintain current monitoring cadence")
            recommendations.append("Consider optimizing high-usage tools for better performance")
        
        # Check for anomalies
        if len(context.get("anomalies", [])) > 0:
            recommendations.append("Investigate detected anomalies for root cause")
        
        # Check for degradation
        if len(context.get("degrading_tools", [])) > 0:
            recommendations.append("Address performance degradation before it becomes critical")
        
        return recommendations
    
    def _log_investigation(self, result: Dict[str, Any]):
        """Log investigation results (placeholder for actual logging)."""
        # In production, this would write to logs or metrics system
        pass
    
    def _log_error(self, error: str):
        """Log errors from monitoring loop."""
        # In production, this would write to error logging system
        print(f"[SelfInvestigationNeuron] ERROR: {error}")
    
    def close(self):
        """Clean up resources."""
        self.stop_monitoring()
        self.query_tool.close()
        self.analyzer.close()
        self.reporter.close()
        # Only close execution_store if we created it
        if self._owns_store and self.execution_store:
            self.execution_store.close()
