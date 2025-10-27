"""
Analytics Engine: Scheduled jobs for continuous learning and improvement.
Phase 8c: Analyze execution history, detect patterns, optimize performance.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from neural_engine.core.execution_store import ExecutionStore


class AnalyticsEngine:
    """Analyzes execution history and provides insights for optimization."""
    
    def __init__(self, execution_store: Optional[ExecutionStore] = None):
        """
        Initialize AnalyticsEngine.
        
        Args:
            execution_store: ExecutionStore instance (creates new one if None)
        """
        self.store = execution_store or ExecutionStore()
    
    # ==================== HOURLY JOBS ====================
    
    def hourly_statistics_update(self):
        """
        Update aggregated tool statistics.
        Run every hour to keep metrics fresh.
        """
        print(f"[{datetime.now()}] Running hourly statistics update...")
        start = time.time()
        
        self.store.update_statistics()
        
        duration = time.time() - start
        print(f"✓ Statistics updated in {duration:.2f}s")
        
        return {
            "job": "hourly_statistics_update",
            "status": "success",
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat()
        }
    
    # ==================== DAILY JOBS ====================
    
    def daily_tool_analysis(self) -> Dict:
        """
        Analyze tool performance and identify issues.
        Run daily to detect failing or underperforming tools.
        
        Returns:
            Dictionary with analysis results and recommendations
        """
        print(f"[{datetime.now()}] Running daily tool analysis...")
        start = time.time()
        
        # Update statistics first
        self.store.update_statistics()
        
        # Get all tools with sufficient data (min 10 executions)
        all_tools = self.store.get_top_tools(limit=1000, min_executions=10)
        
        # Categorize tools
        excellent_tools = []  # >90% success
        good_tools = []       # 70-90% success
        struggling_tools = [] # 50-70% success
        failing_tools = []    # <50% success
        
        for tool in all_tools:
            rate = tool['success_rate']
            if rate >= 0.9:
                excellent_tools.append(tool)
            elif rate >= 0.7:
                good_tools.append(tool)
            elif rate >= 0.5:
                struggling_tools.append(tool)
            else:
                failing_tools.append(tool)
        
        # Generate report
        report = {
            "job": "daily_tool_analysis",
            "status": "success",
            "duration_seconds": time.time() - start,
            "timestamp": datetime.now().isoformat(),
            "total_tools_analyzed": len(all_tools),
            "categories": {
                "excellent": len(excellent_tools),
                "good": len(good_tools),
                "struggling": len(struggling_tools),
                "failing": len(failing_tools)
            },
            "excellent_tools": [t['tool_name'] for t in excellent_tools],
            "failing_tools": [
                {
                    "name": t['tool_name'],
                    "success_rate": float(t['success_rate']),
                    "executions": t['total_executions']
                }
                for t in failing_tools
            ],
            "recommendations": []
        }
        
        # Generate recommendations
        if failing_tools:
            report["recommendations"].append({
                "priority": "high",
                "action": "investigate_failing_tools",
                "message": f"{len(failing_tools)} tool(s) with <50% success rate need investigation",
                "tools": [t['tool_name'] for t in failing_tools]
            })
        
        if struggling_tools:
            report["recommendations"].append({
                "priority": "medium",
                "action": "review_struggling_tools",
                "message": f"{len(struggling_tools)} tool(s) with 50-70% success rate could be improved",
                "tools": [t['tool_name'] for t in struggling_tools]
            })
        
        # Print summary
        print(f"  Total tools analyzed: {len(all_tools)}")
        print(f"  ✓ Excellent (>90%): {len(excellent_tools)}")
        print(f"  ✓ Good (70-90%): {len(good_tools)}")
        print(f"  ⚠ Struggling (50-70%): {len(struggling_tools)}")
        print(f"  ✗ Failing (<50%): {len(failing_tools)}")
        
        if failing_tools:
            print(f"\n  ⚠️  ALERT: {len(failing_tools)} failing tool(s):")
            for tool in failing_tools[:5]:  # Show top 5
                print(f"    - {tool['tool_name']}: {tool['success_rate']:.1%} success "
                      f"({tool['total_executions']} runs)")
        
        return report
    
    def daily_performance_analysis(self) -> Dict:
        """
        Analyze execution performance and identify bottlenecks.
        Run daily to track performance trends.
        
        Returns:
            Dictionary with performance metrics and insights
        """
        print(f"[{datetime.now()}] Running daily performance analysis...")
        start = time.time()
        
        # Get recent executions (last 24 hours worth)
        recent = self.store.get_recent_executions(limit=1000)
        
        if not recent:
            return {
                "job": "daily_performance_analysis",
                "status": "no_data",
                "message": "No executions in the last 24 hours"
            }
        
        # Calculate metrics
        durations = [e['duration_ms'] for e in recent if e['duration_ms']]
        successes = [e for e in recent if e.get('success')]
        failures = [e for e in recent if not e.get('success')]
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        p50_duration = sorted(durations)[len(durations) // 2] if durations else 0
        p95_duration = sorted(durations)[int(len(durations) * 0.95)] if durations else 0
        p99_duration = sorted(durations)[int(len(durations) * 0.99)] if durations else 0
        
        success_rate = len(successes) / len(recent) if recent else 0
        
        # Intent breakdown
        intent_counts = {}
        for exec in recent:
            intent = exec.get('intent', 'unknown')
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # Identify slow executions (>5 seconds)
        slow_executions = [e for e in recent if (e.get('duration_ms') or 0) > 5000]
        
        report = {
            "job": "daily_performance_analysis",
            "status": "success",
            "duration_seconds": time.time() - start,
            "timestamp": datetime.now().isoformat(),
            "executions_analyzed": len(recent),
            "performance_metrics": {
                "avg_duration_ms": round(avg_duration, 2),
                "p50_duration_ms": p50_duration,
                "p95_duration_ms": p95_duration,
                "p99_duration_ms": p99_duration,
                "success_rate": round(success_rate, 4)
            },
            "intent_breakdown": intent_counts,
            "slow_executions_count": len(slow_executions),
            "recommendations": []
        }
        
        # Generate recommendations
        if avg_duration > 3000:
            report["recommendations"].append({
                "priority": "high",
                "action": "optimize_performance",
                "message": f"Average execution time is high: {avg_duration:.0f}ms"
            })
        
        if p95_duration > 10000:
            report["recommendations"].append({
                "priority": "high",
                "action": "investigate_outliers",
                "message": f"95th percentile is very high: {p95_duration}ms"
            })
        
        if success_rate < 0.7:
            report["recommendations"].append({
                "priority": "high",
                "action": "improve_reliability",
                "message": f"Success rate is low: {success_rate:.1%}"
            })
        
        if slow_executions:
            report["recommendations"].append({
                "priority": "medium",
                "action": "optimize_slow_queries",
                "message": f"{len(slow_executions)} execution(s) took >5 seconds"
            })
        
        # Print summary
        print(f"  Executions analyzed: {len(recent)}")
        print(f"  Avg duration: {avg_duration:.0f}ms")
        print(f"  P95 duration: {p95_duration}ms")
        print(f"  Success rate: {success_rate:.1%}")
        print(f"  Intent breakdown: {intent_counts}")
        
        if slow_executions:
            print(f"\n  ⚠️  {len(slow_executions)} slow execution(s) detected (>5s)")
        
        return report
    
    # ==================== WEEKLY JOBS ====================
    
    def weekly_tool_lifecycle_management(self) -> Dict:
        """
        Manage tool lifecycle: promote successful tools, deprecate failing ones.
        Run weekly to maintain tool quality.
        
        Returns:
            Dictionary with lifecycle actions taken
        """
        print(f"[{datetime.now()}] Running weekly tool lifecycle management...")
        start = time.time()
        
        self.store.update_statistics()
        
        # Get tools with significant usage (min 50 executions)
        all_tools = self.store.get_top_tools(limit=1000, min_executions=50)
        
        # Identify candidates for promotion/deprecation
        promote_candidates = []   # AI tools with >85% success, 100+ runs
        deprecate_candidates = []  # Tools with <30% success, 50+ runs
        archive_candidates = []    # Tools not used in 30+ days
        
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        for tool in all_tools:
            rate = tool['success_rate']
            runs = tool['total_executions']
            last_used = tool.get('last_used')
            
            # Check for promotion (successful AI-generated tools)
            if rate >= 0.85 and runs >= 100:
                promote_candidates.append(tool)
            
            # Check for deprecation (consistently failing)
            if rate < 0.30 and runs >= 50:
                deprecate_candidates.append(tool)
            
            # Check for archiving (not used recently)
            if last_used and datetime.fromisoformat(str(last_used)) < thirty_days_ago:
                archive_candidates.append(tool)
        
        report = {
            "job": "weekly_tool_lifecycle_management",
            "status": "success",
            "duration_seconds": time.time() - start,
            "timestamp": datetime.now().isoformat(),
            "tools_reviewed": len(all_tools),
            "actions": {
                "promote": [
                    {
                        "tool": t['tool_name'],
                        "success_rate": float(t['success_rate']),
                        "executions": t['total_executions']
                    }
                    for t in promote_candidates
                ],
                "deprecate": [
                    {
                        "tool": t['tool_name'],
                        "success_rate": float(t['success_rate']),
                        "executions": t['total_executions'],
                        "reason": "low_success_rate"
                    }
                    for t in deprecate_candidates
                ],
                "archive": [
                    {
                        "tool": t['tool_name'],
                        "last_used": str(t.get('last_used')),
                        "reason": "inactive_30_days"
                    }
                    for t in archive_candidates
                ]
            },
            "recommendations": []
        }
        
        # Generate recommendations
        if promote_candidates:
            report["recommendations"].append({
                "priority": "low",
                "action": "promote_ai_tools",
                "message": f"{len(promote_candidates)} AI-generated tool(s) ready for promotion to admin tools",
                "tools": [t['tool_name'] for t in promote_candidates]
            })
        
        if deprecate_candidates:
            report["recommendations"].append({
                "priority": "high",
                "action": "deprecate_failing_tools",
                "message": f"{len(deprecate_candidates)} tool(s) with <30% success should be deprecated",
                "tools": [t['tool_name'] for t in deprecate_candidates]
            })
        
        if archive_candidates:
            report["recommendations"].append({
                "priority": "low",
                "action": "archive_unused_tools",
                "message": f"{len(archive_candidates)} tool(s) not used in 30+ days can be archived",
                "tools": [t['tool_name'] for t in archive_candidates]
            })
        
        # Print summary
        print(f"  Tools reviewed: {len(all_tools)}")
        print(f"  ↑ Promotion candidates: {len(promote_candidates)}")
        print(f"  ↓ Deprecation candidates: {len(deprecate_candidates)}")
        print(f"  📦 Archive candidates: {len(archive_candidates)}")
        
        if deprecate_candidates:
            print(f"\n  ⚠️  ALERT: {len(deprecate_candidates)} tool(s) should be deprecated:")
            for tool in deprecate_candidates[:3]:
                print(f"    - {tool['tool_name']}: {tool['success_rate']:.1%} success")
        
        return report
    
    # ==================== ON-DEMAND ANALYSIS ====================
    
    def analyze_goal_patterns(self, limit: int = 100) -> Dict:
        """
        Analyze patterns in user goals to identify common requests.
        
        Args:
            limit: Number of recent executions to analyze
        
        Returns:
            Dictionary with pattern analysis
        """
        print(f"[{datetime.now()}] Analyzing goal patterns...")
        
        recent = self.store.get_recent_executions(limit=limit)
        
        if not recent:
            return {"status": "no_data", "message": "No executions to analyze"}
        
        # Extract keywords from goals
        word_frequency = {}
        for exec in recent:
            goal = exec.get('goal_text', '').lower()
            words = [w.strip('.,!?;:()[]{}') for w in goal.split() if len(w) > 3]
            for word in words:
                word_frequency[word] = word_frequency.get(word, 0) + 1
        
        # Sort by frequency
        top_keywords = sorted(word_frequency.items(), key=lambda x: x[1], reverse=True)[:20]
        
        # Intent distribution
        intent_dist = {}
        for exec in recent:
            intent = exec.get('intent', 'unknown')
            intent_dist[intent] = intent_dist.get(intent, 0) + 1
        
        print(f"  Analyzed {len(recent)} executions")
        print(f"  Top keywords: {', '.join([w for w, _ in top_keywords[:5]])}")
        print(f"  Intent distribution: {intent_dist}")
        
        return {
            "status": "success",
            "executions_analyzed": len(recent),
            "top_keywords": [{"word": w, "count": c} for w, c in top_keywords],
            "intent_distribution": intent_dist,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_tool_insights(self, tool_name: str) -> Dict:
        """
        Get detailed insights for a specific tool.
        
        Args:
            tool_name: Name of tool to analyze
        
        Returns:
            Dictionary with tool insights
        """
        print(f"[{datetime.now()}] Getting insights for tool: {tool_name}")
        
        stats = self.store.get_tool_statistics(tool_name)
        
        if not stats:
            return {
                "status": "not_found",
                "message": f"No statistics found for tool: {tool_name}"
            }
        
        # Calculate health score (0-100)
        success_weight = 0.6
        usage_weight = 0.3
        recency_weight = 0.1
        
        success_score = stats['success_rate'] * 100
        usage_score = min(stats['total_executions'] / 100, 1.0) * 100
        
        # Recency score (higher if used recently)
        last_used = stats.get('last_used')
        if last_used:
            days_since_use = (datetime.now() - datetime.fromisoformat(str(last_used))).days
            recency_score = max(0, 100 - (days_since_use * 5))
        else:
            recency_score = 0
        
        health_score = (
            success_score * success_weight +
            usage_score * usage_weight +
            recency_score * recency_weight
        )
        
        # Determine status
        if health_score >= 80:
            status = "excellent"
        elif health_score >= 60:
            status = "good"
        elif health_score >= 40:
            status = "needs_improvement"
        else:
            status = "poor"
        
        insights = {
            "tool_name": tool_name,
            "status": status,
            "health_score": round(health_score, 2),
            "statistics": {
                "total_executions": stats['total_executions'],
                "successful_executions": stats['successful_executions'],
                "failed_executions": stats['failed_executions'],
                "success_rate": float(stats['success_rate']),
                "avg_duration_ms": float(stats['avg_duration_ms']) if stats['avg_duration_ms'] else None,
                "last_used": str(stats.get('last_used')),
                "first_used": str(stats.get('first_used'))
            },
            "recommendations": []
        }
        
        # Generate recommendations
        if stats['success_rate'] < 0.5:
            insights["recommendations"].append({
                "priority": "high",
                "message": "Low success rate - investigate tool implementation"
            })
        
        if stats['total_executions'] < 10:
            insights["recommendations"].append({
                "priority": "low",
                "message": "Limited usage data - need more executions for accurate analysis"
            })
        
        if stats['avg_duration_ms'] and stats['avg_duration_ms'] > 5000:
            insights["recommendations"].append({
                "priority": "medium",
                "message": f"High average duration ({stats['avg_duration_ms']:.0f}ms) - consider optimization"
            })
        
        print(f"  Tool: {tool_name}")
        print(f"  Status: {status} (health score: {health_score:.1f}/100)")
        print(f"  Success rate: {stats['success_rate']:.1%}")
        print(f"  Total executions: {stats['total_executions']}")
        
        return insights
    
    def generate_dashboard_data(self) -> Dict:
        """
        Generate data for analytics dashboard.
        
        Returns:
            Dictionary with dashboard metrics
        """
        print(f"[{datetime.now()}] Generating dashboard data...")
        
        # Update statistics
        self.store.update_statistics()
        
        # Get key metrics
        recent_executions = self.store.get_recent_executions(limit=100)
        top_tools = self.store.get_top_tools(limit=10, min_executions=5)
        tool_performance = self.store.get_tool_performance_view()
        overall_success = self.store.get_success_rate()
        
        # Calculate trends
        total_executions = len(recent_executions)
        successful = len([e for e in recent_executions if e.get('success')])
        failed = total_executions - successful
        
        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "overview": {
                "total_executions_today": total_executions,
                "successful_executions": successful,
                "failed_executions": failed,
                "overall_success_rate": round(overall_success, 4),
                "total_tools": len(tool_performance)
            },
            "top_tools": [
                {
                    "name": t['tool_name'],
                    "executions": t['total_executions'],
                    "success_rate": float(t['success_rate'])
                }
                for t in top_tools
            ],
            "recent_activity": [
                {
                    "goal_id": e['goal_id'],
                    "goal_text": e['goal_text'][:50] + "..." if len(e['goal_text']) > 50 else e['goal_text'],
                    "intent": e.get('intent'),
                    "success": e.get('success'),
                    "duration_ms": e.get('duration_ms'),
                    "created_at": str(e.get('created_at'))
                }
                for e in recent_executions[:10]
            ]
        }
        
        print(f"  ✓ Dashboard data generated")
        print(f"  Total executions: {total_executions}")
        print(f"  Success rate: {overall_success:.1%}")
        print(f"  Top tools: {len(top_tools)}")
        
        return dashboard
    
    def close(self):
        """Close ExecutionStore connection."""
        if self.store:
            self.store.close()
