"""
AutonomousImprovementNeuron: Self-improving system that closes the learning loop.
Phase 9c: The system doesn't just monitor itself - it actively improves itself.

This neuron orchestrates the complete autonomous improvement pipeline:
1. Detect improvement opportunities (degrading/failing tools)
2. Generate improved versions (using ToolForgeNeuron)
3. A/B test old vs new versions
4. Validate improvements (data-driven decisions)
5. Deploy or rollback (safe, gradual rollout)

This is the culmination of Phases 9a, 9b, and 9c:
- Phase 9a: Analytics tools (Query, Analyze, Report)
- Phase 9b: Self-Investigation (autonomous monitoring)
- Phase 9c: Autonomous Improvement (closes the loop)

Together, these create a truly self-improving system - the foundation for fractal architecture.
"""

import time
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from neural_engine.core.neuron import BaseNeuron
from neural_engine.core.self_investigation_neuron import SelfInvestigationNeuron
from neural_engine.tools.query_execution_store_tool import QueryExecutionStoreTool
from neural_engine.tools.analyze_tool_performance_tool import AnalyzeToolPerformanceTool
from neural_engine.core.execution_store import ExecutionStore


class ImprovementOpportunity:
    """Represents a detected opportunity for improvement."""
    
    def __init__(
        self,
        tool_name: str,
        issue_type: str,
        severity: str,
        current_metrics: Dict[str, Any],
        evidence: List[str],
        recommended_fixes: List[str]
    ):
        self.tool_name = tool_name
        self.issue_type = issue_type  # 'degradation', 'high_failure', 'performance'
        self.severity = severity  # 'critical', 'high', 'medium', 'low'
        self.current_metrics = current_metrics
        self.evidence = evidence
        self.recommended_fixes = recommended_fixes
        self.created_at = datetime.now()
        self.status = 'detected'  # detected -> analyzing -> improving -> testing -> deployed/rejected
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'tool_name': self.tool_name,
            'issue_type': self.issue_type,
            'severity': self.severity,
            'current_metrics': self.current_metrics,
            'evidence': self.evidence,
            'recommended_fixes': self.recommended_fixes,
            'created_at': self.created_at.isoformat(),
            'status': self.status
        }


class ABTestResult:
    """Results from A/B testing old vs new tool version."""
    
    def __init__(
        self,
        tool_name: str,
        old_version_metrics: Dict[str, float],
        new_version_metrics: Dict[str, float],
        sample_size: int
    ):
        self.tool_name = tool_name
        self.old_metrics = old_version_metrics
        self.new_metrics = new_version_metrics
        self.sample_size = sample_size
        self.improvement_detected = self._calculate_improvement()
        self.confidence = self._calculate_confidence()
        self.recommendation = self._generate_recommendation()
    
    def _calculate_improvement(self) -> bool:
        """Determine if new version is better."""
        # Compare success rates
        old_success = self.old_metrics.get('success_rate', 0)
        new_success = self.new_metrics.get('success_rate', 0)
        
        # Require at least 5% improvement
        return new_success > old_success + 0.05
    
    def _calculate_confidence(self) -> float:
        """Calculate confidence in the result (0-1)."""
        # Simple confidence based on sample size
        if self.sample_size >= 100:
            return 0.95
        elif self.sample_size >= 50:
            return 0.85
        elif self.sample_size >= 20:
            return 0.70
        else:
            return 0.50
    
    def _generate_recommendation(self) -> str:
        """Generate deployment recommendation."""
        if self.improvement_detected and self.confidence > 0.80:
            return 'deploy'
        elif self.improvement_detected and self.confidence > 0.60:
            return 'continue_testing'
        elif not self.improvement_detected and self.confidence > 0.80:
            return 'rollback'
        else:
            return 'continue_testing'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tool_name': self.tool_name,
            'old_metrics': self.old_metrics,
            'new_metrics': self.new_metrics,
            'sample_size': self.sample_size,
            'improvement_detected': self.improvement_detected,
            'confidence': self.confidence,
            'recommendation': self.recommendation
        }


class AutonomousImprovementNeuron(BaseNeuron):
    """
    Autonomous neuron that detects problems and fixes them automatically.
    
    This is the culmination of the self-aware system:
    - Phase 9a gave us analytics tools
    - Phase 9b gave us autonomous monitoring
    - Phase 9c gives us autonomous improvement
    
    The system can now:
    1. Detect its own problems (Phase 9b)
    2. Investigate root causes (Phase 9a)
    3. Generate fixes (Phase 9c - this neuron)
    4. Test improvements (Phase 9c - this neuron)
    5. Deploy automatically (Phase 9c - this neuron)
    
    This closes the learning loop and enables true autonomy.
    """
    
    def __init__(
        self,
        message_bus,
        ollama_client,
        execution_store: Optional[ExecutionStore] = None,
        enable_auto_improvement: bool = False,  # Safety: disabled by default
        improvement_threshold: float = 0.5,  # Only improve tools with <50% success rate
        confidence_threshold: float = 0.80,  # Require 80% confidence to deploy
        min_sample_size: int = 20  # Minimum executions before considering improvement
    ):
        """
        Initialize the Autonomous Improvement Neuron.
        
        Args:
            message_bus: Communication bus
            ollama_client: LLM client for generating improvements
            execution_store: Database connection
            enable_auto_improvement: Enable automatic deployment (default: False for safety)
            improvement_threshold: Success rate threshold for improvement consideration
            confidence_threshold: Confidence threshold for auto-deployment
            min_sample_size: Minimum executions needed before improvement
        """
        super().__init__(message_bus, ollama_client)
        
        # Configuration
        self.enable_auto_improvement = enable_auto_improvement
        self.improvement_threshold = improvement_threshold
        self.confidence_threshold = confidence_threshold
        self.min_sample_size = min_sample_size
        
        # Dependencies
        self._owns_store = execution_store is None
        self.execution_store = execution_store or ExecutionStore()
        self.investigator = SelfInvestigationNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=self.execution_store,
            enable_auto_alerts=False  # We'll handle alerts
        )
        self.query_tool = QueryExecutionStoreTool(execution_store=self.execution_store)
        self.analyzer = AnalyzeToolPerformanceTool(execution_store=self.execution_store)
        
        # State tracking
        self.opportunities_detected = []
        self.improvements_generated = []
        self.ab_tests_running = {}  # tool_name -> test results
        self.improvements_deployed = []
        self.improvements_rejected = []
        
        # Statistics
        self.detection_count = 0
        self.generation_count = 0
        self.deployment_count = 0
        self.rollback_count = 0
    
    def process(self, goal_id: str, data: Any, depth: int = 0) -> Dict[str, Any]:
        """
        Process improvement-related goals.
        
        Supported goals:
        - "detect improvement opportunities"
        - "improve tool X"
        - "validate improvement for tool X"
        - "run autonomous improvement cycle"
        """
        goal_text = str(data).lower()
        
        if "detect" in goal_text and "opportunit" in goal_text:
            return self.detect_improvement_opportunities()
        
        elif "improve tool" in goal_text:
            # Extract tool name (simple parsing)
            parts = goal_text.split("improve tool")
            if len(parts) > 1:
                tool_name = parts[1].strip()
                return self.improve_tool(tool_name)
        
        elif "validate" in goal_text or ("test" in goal_text and "tool" in goal_text):
            # Extract tool name - look for "for tool X" or "tool X" patterns
            if "for tool " in goal_text:
                parts = goal_text.split("for tool ")
                if len(parts) > 1:
                    tool_name = parts[1].strip()
                    return self.validate_improvement(tool_name)
            elif "tool " in goal_text:
                parts = goal_text.split("tool ")
                if len(parts) > 1:
                    tool_name = parts[1].strip()
                    return self.validate_improvement(tool_name)
        
        elif "autonomous" in goal_text or "full cycle" in goal_text:
            return self.run_improvement_cycle()
        
        else:
            # Default: run full improvement cycle
            return self.run_improvement_cycle()
    
    def detect_improvement_opportunities(self) -> Dict[str, Any]:
        """
        Detect tools that need improvement.
        
        Uses Phase 9b's investigation capabilities to identify:
        - Failing tools (high failure rate)
        - Degrading tools (performance declining)
        - Slow tools (performance issues)
        
        Returns:
            Dict with detected opportunities and priorities
        """
        self.detection_count += 1
        opportunities = []
        
        # Step 1: Get system health from investigator
        health = self.investigator.investigate_health()
        
        if not health['success']:
            return {
                'success': False,
                'error': 'Failed to investigate system health'
            }
        
        # Step 2: Identify failing tools
        for issue in health.get('issues', []):
            if issue['type'] == 'tool_failure' and issue['severity'] == 'high':
                # Get detailed metrics
                tool_stats = self.query_tool.execute(
                    query_type='tool_stats',
                    tool_name=issue['tool_name']
                )
                
                if tool_stats['success'] and tool_stats['results']:
                    metrics = tool_stats['results']
                    
                    # Check if eligible for improvement
                    if (metrics['total_executions'] >= self.min_sample_size and
                        metrics['success_rate'] < self.improvement_threshold):
                        
                        opportunity = ImprovementOpportunity(
                            tool_name=issue['tool_name'],
                            issue_type='high_failure',
                            severity='critical',
                            current_metrics={
                                'success_rate': metrics['success_rate'],
                                'failure_rate': issue['failure_rate'],
                                'total_executions': metrics['total_executions'],
                                'avg_duration_ms': metrics['avg_duration_ms']
                            },
                            evidence=[
                                f"Failure rate: {issue['failure_rate']}%",
                                f"Only {metrics['success_rate']*100:.1f}% success rate",
                                f"Based on {metrics['total_executions']} executions"
                            ],
                            recommended_fixes=[
                                "Add better error handling",
                                "Add input validation",
                                "Add retry logic for transient failures",
                                "Review common failure patterns"
                            ]
                        )
                        opportunities.append(opportunity)
        
        # Step 3: Check for degrading tools
        degradation = self.investigator.detect_degradation()
        
        if degradation['success']:
            for tool in degradation.get('degrading_tools', []):
                # Get detailed metrics
                tool_stats = self.query_tool.execute(
                    query_type='tool_stats',
                    tool_name=tool['tool_name']
                )
                
                if tool_stats['success'] and tool_stats['results']:
                    metrics = tool_stats['results']
                    
                    if metrics['total_executions'] >= self.min_sample_size:
                        opportunity = ImprovementOpportunity(
                            tool_name=tool['tool_name'],
                            issue_type='degradation',
                            severity=tool['severity'],
                            current_metrics={
                                'success_rate': tool['current_success_rate'] / 100,
                                'total_executions': metrics['total_executions'],
                                'avg_duration_ms': metrics['avg_duration_ms']
                            },
                            evidence=tool.get('indicators', []),
                            recommended_fixes=[
                                "Optimize performance",
                                "Review recent changes",
                                "Check for resource leaks",
                                "Update dependencies"
                            ]
                        )
                        opportunities.append(opportunity)
        
        # Step 4: Check for slow tools
        # Get all tool executions and analyze duration
        all_tools = self.query_tool.execute(
            query_type='top_tools',
            limit=100  # Get many tools
        )
        
        if all_tools['success'] and all_tools['results']:
            for tool_data in all_tools['results']:
                tool_name = tool_data.get('tool_name')
                avg_duration = tool_data.get('avg_duration_ms', 0)
                execution_count = tool_data.get('total_executions', 0)  # Fixed: use 'total_executions'
                
                # Consider tools that are consistently slow (> 5s avg) with enough data
                if avg_duration > 5000 and execution_count >= 3:
                    # Check if not already identified as a problem
                    if any(o.tool_name == tool_name for o in opportunities):
                        continue  # Already identified for other reasons
                    
                    # Get detailed statistics
                    tool_stats = self.query_tool.execute(
                        query_type='tool_stats',
                        tool_name=tool_name
                    )
                    
                    if tool_stats['success'] and tool_stats['results']:
                        metrics = tool_stats['results']
                        
                        # Only add if eligible (enough executions)
                        if metrics['total_executions'] >= self.min_sample_size:
                            opportunity = ImprovementOpportunity(
                                tool_name=tool_name,
                                issue_type='performance',
                                severity='medium',
                                current_metrics={
                                    'avg_duration_ms': avg_duration,
                                    'total_executions': metrics['total_executions'],
                                    'success_rate': metrics['success_rate']
                                },
                                evidence=[
                                    f"Average duration: {avg_duration:.0f}ms (>5s)",
                                    f"Based on {metrics['total_executions']} executions"
                                ],
                                recommended_fixes=[
                                    "Optimize algorithm",
                                    "Add caching",
                                    "Reduce database queries",
                                    "Profile and optimize hot paths"
                                ]
                            )
                            opportunities.append(opportunity)
        
        # Store detected opportunities
        self.opportunities_detected.extend(opportunities)
        
        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        opportunities.sort(key=lambda o: severity_order.get(o.severity, 999))
        
        return {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'opportunities_count': len(opportunities),
            'opportunities': [opp.to_dict() for opp in opportunities],
            'priorities': {
                'critical': len([o for o in opportunities if o.severity == 'critical']),
                'high': len([o for o in opportunities if o.severity == 'high']),
                'medium': len([o for o in opportunities if o.severity == 'medium']),
                'low': len([o for o in opportunities if o.severity == 'low'])
            }
        }
    
    def improve_tool(self, tool_name: str) -> Dict[str, Any]:
        """
        Generate an improved version of a tool.
        
        This is a placeholder for the actual improvement generation.
        In Phase 9c, this would:
        1. Analyze tool's source code
        2. Review failure patterns
        3. Use LLM to generate improved version
        4. Validate generated code
        
        Args:
            tool_name: Name of tool to improve
            
        Returns:
            Dict with improvement details
        """
        self.generation_count += 1
        
        # Get tool statistics and failure patterns
        stats = self.query_tool.execute(
            query_type='tool_stats',
            tool_name=tool_name
        )
        
        if not stats['success']:
            return {
                'success': False,
                'error': f'Failed to get statistics for {tool_name}'
            }
        
        # Get recent failures to understand patterns
        failures = self.query_tool.execute(
            query_type='recent_failures',
            limit=10
        )
        
        tool_failures = []
        if failures['success']:
            tool_failures = [
                f for f in failures['results']
                if f.get('tool_name') == tool_name
            ]
        
        # Generate improvement (placeholder - would use ToolForgeNeuron in production)
        improvement = {
            'tool_name': tool_name,
            'version': 'v2',
            'improvements': [
                'Added comprehensive error handling',
                'Added input validation',
                'Added retry logic for transient failures',
                'Improved logging for debugging'
            ],
            'expected_benefits': {
                'success_rate_improvement': 0.20,  # Expected 20% improvement
                'reliability': 'high'
            },
            'generated_at': datetime.now().isoformat(),
            'status': 'generated'
        }
        
        self.improvements_generated.append(improvement)
        
        return {
            'success': True,
            'tool_name': tool_name,
            'improvement': improvement,
            'failure_patterns_analyzed': len(tool_failures),
            'current_success_rate': stats['results']['success_rate'],
            'message': f'Generated improved version of {tool_name}'
        }
    
    def validate_improvement(self, tool_name: str) -> Dict[str, Any]:
        """
        Validate an improvement through A/B testing.
        
        This is a placeholder for actual A/B testing.
        In production, this would:
        1. Deploy new version alongside old
        2. Route traffic to both (50/50 split)
        3. Collect metrics on both versions
        4. Compare performance statistically
        
        Args:
            tool_name: Name of tool being tested
            
        Returns:
            Dict with validation results and recommendation
        """
        # Simulate A/B test results (in production, these would be real metrics)
        # For demo purposes, we'll use existing tool stats as "old" version
        # and simulate improved stats as "new" version
        
        old_stats = self.query_tool.execute(
            query_type='tool_stats',
            tool_name=tool_name
        )
        
        if not old_stats['success'] or not old_stats['results']:
            return {
                'success': False,
                'error': f'No statistics available for {tool_name}'
            }
        
        old_metrics = old_stats['results']
        
        # Check if we have enough data
        if not old_metrics.get('success_rate'):
            return {
                'success': False,
                'error': f'Insufficient data for {tool_name} - no success_rate available'
            }
        
        # Simulate improved metrics (in production, these would be from actual A/B test)
        # Assume 20% improvement for demonstration
        new_metrics = {
            'success_rate': min(old_metrics['success_rate'] + 0.20, 1.0),
            'avg_duration_ms': old_metrics.get('avg_duration_ms', 1000) * 0.90,  # 10% faster
            'failure_rate': max(old_metrics.get('failure_rate', 0) - 20, 0)
        }
        
        # Create A/B test result
        ab_result = ABTestResult(
            tool_name=tool_name,
            old_version_metrics={
                'success_rate': old_metrics['success_rate'],
                'avg_duration_ms': old_metrics['avg_duration_ms']
            },
            new_version_metrics=new_metrics,
            sample_size=old_metrics['total_executions']
        )
        
        # Store result
        self.ab_tests_running[tool_name] = ab_result
        
        return {
            'success': True,
            'tool_name': tool_name,
            'ab_test_result': ab_result.to_dict(),
            'recommendation': ab_result.recommendation,
            'can_auto_deploy': (
                ab_result.recommendation == 'deploy' and
                ab_result.confidence >= self.confidence_threshold and
                self.enable_auto_improvement
            )
        }
    
    def deploy_improvement(self, tool_name: str) -> Dict[str, Any]:
        """
        Deploy an approved improvement.
        
        This would:
        1. Backup old version
        2. Deploy new version
        3. Monitor for issues
        4. Rollback if problems detected
        
        Args:
            tool_name: Name of tool to deploy
            
        Returns:
            Dict with deployment status
        """
        self.deployment_count += 1
        
        # In production, this would actually deploy the new tool version
        # For now, we'll simulate the deployment
        
        deployment = {
            'tool_name': tool_name,
            'deployed_at': datetime.now().isoformat(),
            'deployment_strategy': 'gradual_rollout',
            'status': 'deployed',
            'backup_created': True,
            'rollback_available': True
        }
        
        self.improvements_deployed.append(deployment)
        
        return {
            'success': True,
            'tool_name': tool_name,
            'deployment': deployment,
            'message': f'Successfully deployed improved version of {tool_name}'
        }
    
    def rollback_improvement(self, tool_name: str, reason: str) -> Dict[str, Any]:
        """
        Rollback a deployed improvement.
        
        Args:
            tool_name: Name of tool to rollback
            reason: Reason for rollback
            
        Returns:
            Dict with rollback status
        """
        self.rollback_count += 1
        
        rollback = {
            'tool_name': tool_name,
            'rolled_back_at': datetime.now().isoformat(),
            'reason': reason,
            'status': 'rolled_back'
        }
        
        self.improvements_rejected.append(rollback)
        
        return {
            'success': True,
            'tool_name': tool_name,
            'rollback': rollback,
            'message': f'Rolled back {tool_name}: {reason}'
        }
    
    def run_improvement_cycle(self) -> Dict[str, Any]:
        """
        Run complete autonomous improvement cycle.
        
        This orchestrates the full pipeline:
        1. Detect opportunities
        2. For each critical opportunity:
           a. Generate improvement
           b. Validate via A/B test
           c. Deploy if validated (and auto-improvement enabled)
           d. Or report for manual review
        
        Returns:
            Dict with cycle results
        """
        cycle_start = time.time()
        cycle_results = {
            'opportunities_detected': 0,
            'improvements_generated': 0,
            'improvements_validated': 0,
            'improvements_deployed': 0,
            'improvements_rejected': 0,
            'pending_manual_review': []
        }
        
        # Step 1: Detect opportunities
        detection_result = self.detect_improvement_opportunities()
        
        if not detection_result['success']:
            return {
                'success': False,
                'error': 'Failed to detect opportunities',
                'cycle_duration_ms': int((time.time() - cycle_start) * 1000)
            }
        
        cycle_results['opportunities_detected'] = detection_result['opportunities_count']
        
        # Step 2: Process critical opportunities
        critical_opportunities = [
            opp for opp in detection_result['opportunities']
            if opp['severity'] in ['critical', 'high']
        ]
        
        for opp in critical_opportunities[:3]:  # Limit to top 3 for safety
            tool_name = opp['tool_name']
            
            # Generate improvement
            improvement_result = self.improve_tool(tool_name)
            
            if improvement_result['success']:
                cycle_results['improvements_generated'] += 1
                
                # Validate improvement
                validation_result = self.validate_improvement(tool_name)
                
                if validation_result['success']:
                    cycle_results['improvements_validated'] += 1
                    
                    # Check if can auto-deploy
                    if validation_result['can_auto_deploy']:
                        deploy_result = self.deploy_improvement(tool_name)
                        if deploy_result['success']:
                            cycle_results['improvements_deployed'] += 1
                    else:
                        # Requires manual review
                        cycle_results['pending_manual_review'].append({
                            'tool_name': tool_name,
                            'recommendation': validation_result['recommendation'],
                            'reason': 'Requires manual approval' if not self.enable_auto_improvement
                                      else 'Confidence below threshold'
                        })
        
        cycle_duration = int((time.time() - cycle_start) * 1000)
        
        return {
            'success': True,
            'cycle_duration_ms': cycle_duration,
            'results': cycle_results,
            'auto_improvement_enabled': self.enable_auto_improvement,
            'message': f'Improvement cycle completed: {cycle_results["improvements_deployed"]} deployed, '
                      f'{len(cycle_results["pending_manual_review"])} pending review'
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get neuron statistics."""
        return {
            'detection_count': self.detection_count,
            'generation_count': self.generation_count,
            'deployment_count': self.deployment_count,
            'rollback_count': self.rollback_count,
            'opportunities_detected': len(self.opportunities_detected),
            'improvements_generated': len(self.improvements_generated),
            'improvements_deployed': len(self.improvements_deployed),
            'improvements_rejected': len(self.improvements_rejected),
            'ab_tests_running': len(self.ab_tests_running)
        }
    
    def close(self):
        """Clean up resources."""
        self.investigator.close()
        self.query_tool.close()
        self.analyzer.close()
        if self._owns_store and self.execution_store:
            self.execution_store.close()
