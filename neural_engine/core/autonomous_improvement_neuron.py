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
import os
import re
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING
from datetime import datetime, timedelta
from neural_engine.core.neuron import BaseNeuron
from neural_engine.core.self_investigation_neuron import SelfInvestigationNeuron
from neural_engine.tools.query_execution_store_tool import QueryExecutionStoreTool
from neural_engine.tools.analyze_tool_performance_tool import AnalyzeToolPerformanceTool
from neural_engine.core.execution_store import ExecutionStore

if TYPE_CHECKING:
    from neural_engine.core.tool_forge_neuron import ToolForgeNeuron
    from neural_engine.core.tool_registry import ToolRegistry


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
        tool_forge: Optional['ToolForgeNeuron'] = None,  # For real code generation
        tool_registry: Optional['ToolRegistry'] = None,  # For tool management
        version_manager = None,  # For version tracking (Phase 9f)
        enable_auto_improvement: bool = False,  # Safety: disabled by default
        enable_real_improvements: bool = False,  # Enable real code generation (vs placeholders)
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
            tool_forge: Optional ToolForgeNeuron for real code generation
            tool_registry: Optional ToolRegistry for tool management
            enable_auto_improvement: Enable automatic deployment
            enable_real_improvements: Enable real code generation (default: False for safety)
            enable_auto_improvement: Enable automatic deployment (default: False for safety)
            improvement_threshold: Success rate threshold for improvement consideration
            confidence_threshold: Confidence threshold for auto-deployment
            min_sample_size: Minimum executions needed before improvement
        """
        super().__init__(message_bus, ollama_client)
        
        # Configuration
        self.enable_auto_improvement = enable_auto_improvement
        self.enable_real_improvements = enable_real_improvements
        self.improvement_threshold = improvement_threshold
        self.confidence_threshold = confidence_threshold
        self.min_sample_size = min_sample_size
        
        # Dependencies
        self._owns_store = execution_store is None
        self.execution_store = execution_store or ExecutionStore()
        self.tool_forge = tool_forge  # For real code generation
        self.tool_registry = tool_registry  # For tool management
        self.version_manager = version_manager  # For version tracking (Phase 9f)
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
        
        Two modes:
        1. Real improvements (enable_real_improvements=True): Uses ToolForgeNeuron to generate actual code
        2. Placeholder improvements (default): Returns simulated improvements for testing
        
        Real improvement process:
        1. Read tool's current source code
        2. Analyze failure patterns from ExecutionStore
        3. Generate improvement prompt with context
        4. Use ToolForgeNeuron to generate improved code
        5. Validate generated code
        
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
        
        # MODE 1: Real improvements using ToolForgeNeuron
        if self.enable_real_improvements and self.tool_forge and self.tool_registry:
            return self._generate_real_improvement(tool_name, stats['results'], tool_failures)
        
        # MODE 2: Placeholder improvements (for testing)
        return self._generate_placeholder_improvement(tool_name, stats['results'], tool_failures)
    
    def _generate_real_improvement(
        self, 
        tool_name: str, 
        stats: Dict[str, Any],
        failures: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a real improved tool using ToolForgeNeuron.
        
        Steps:
        1. Read current tool source code
        2. Analyze failure patterns
        3. Create improvement prompt with context
        4. Generate improved code
        5. Validate and return
        """
        try:
            # Step 1: Read current tool source code
            tool_file = self._find_tool_file(tool_name)
            if not tool_file:
                return {
                    'success': False,
                    'error': f'Could not find source file for tool: {tool_name}'
                }
            
            with open(tool_file, 'r') as f:
                current_code = f.read()
            
            # Step 2: Analyze failure patterns
            failure_analysis = self._analyze_failures(failures)
            
            # Step 3: Create improvement prompt
            improvement_prompt = self._create_improvement_prompt(
                tool_name=tool_name,
                current_code=current_code,
                stats=stats,
                failure_analysis=failure_analysis
            )
            
            # Step 4: Generate improved code using ToolForgeNeuron
            forge_result = self.tool_forge.process(
                goal_id=f"improve_{tool_name}_{int(time.time())}",
                data={"goal": improvement_prompt},
                depth=0
            )
            
            if not forge_result['success']:
                return {
                    'success': False,
                    'error': f'ToolForge failed to generate improvement: {forge_result.get("error")}',
                    'validation_errors': forge_result.get('validation_errors', [])
                }
            
            # Step 5: Return generated improvement
            improvement = {
                'tool_name': tool_name,
                'version': 'v2_improved',
                'mode': 'real',
                'generated_code': forge_result['code'],
                'tool_class': forge_result['tool_class'],
                'improvements': [
                    'Fixed failure patterns identified in execution history',
                    'Added comprehensive error handling',
                    'Improved input validation',
                    'Added retry logic where appropriate'
                ],
                'expected_benefits': {
                    'success_rate_improvement': 0.20,
                    'reliability': 'high'
                },
                'generated_at': datetime.now().isoformat(),
                'status': 'generated',
                'failure_patterns_addressed': len(failures),
                'forge_result': forge_result
            }
            
            self.improvements_generated.append(improvement)
            
            return {
                'success': True,
                'tool_name': tool_name,
                'improvement': improvement,
                'failure_patterns_analyzed': len(failures),
                'current_success_rate': stats['success_rate'],
                'message': f'Generated real improved version of {tool_name} using ToolForge'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to generate real improvement: {str(e)}'
            }
    
    def _generate_placeholder_improvement(
        self,
        tool_name: str,
        stats: Dict[str, Any],
        failures: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a placeholder improvement (for testing without real code generation).
        """
        improvement = {
            'tool_name': tool_name,
            'version': 'v2',
            'mode': 'placeholder',
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
            'failure_patterns_analyzed': len(failures),
            'current_success_rate': stats['success_rate'],
            'message': f'Generated placeholder improvement for {tool_name} (enable_real_improvements=False)'
        }
    
    def _find_tool_file(self, tool_name: str) -> Optional[str]:
        """Find the source file for a tool."""
        # Convert tool_name to potential file patterns
        # e.g., "strava_get_activities" -> "strava_get_activities_tool.py"
        tools_dir = "neural_engine/tools"
        
        # Try exact match first
        exact_file = os.path.join(tools_dir, f"{tool_name}_tool.py")
        if os.path.exists(exact_file):
            return exact_file
        
        # Try without extra _tool suffix (in case tool_name already has it)
        if tool_name.endswith('_tool'):
            alt_file = os.path.join(tools_dir, f"{tool_name}.py")
            if os.path.exists(alt_file):
                return alt_file
        
        # Search all tool files
        if os.path.exists(tools_dir):
            for filename in os.listdir(tools_dir):
                if filename.endswith('_tool.py'):
                    # Check if filename matches tool_name pattern
                    if tool_name in filename or filename.replace('_tool.py', '') == tool_name:
                        return os.path.join(tools_dir, filename)
        
        return None
    
    def _analyze_failures(self, failures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze failure patterns to identify common issues."""
        if not failures:
            return {
                'common_errors': [],
                'error_categories': {},
                'insights': ['No recent failures to analyze']
            }
        
        # Group errors by type
        error_types = {}
        for failure in failures:
            error = failure.get('error', 'Unknown error')
            # Extract error type (first line or first 100 chars)
            error_key = error.split('\n')[0][:100]
            error_types[error_key] = error_types.get(error_key, 0) + 1
        
        # Sort by frequency
        sorted_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'common_errors': [{'error': err, 'count': count} for err, count in sorted_errors[:5]],
            'error_categories': error_types,
            'total_failures': len(failures),
            'insights': [
                f"Most common error: {sorted_errors[0][0]}" if sorted_errors else "No errors",
                f"Total unique error types: {len(error_types)}",
                f"Failure concentration: {'High' if sorted_errors and sorted_errors[0][1] > len(failures) * 0.5 else 'Distributed'}"
            ]
        }
    
    def _create_improvement_prompt(
        self,
        tool_name: str,
        current_code: str,
        stats: Dict[str, Any],
        failure_analysis: Dict[str, Any]
    ) -> str:
        """Create a detailed prompt for generating an improved tool."""
        prompt = f"""Create an improved version of the {tool_name} tool that fixes the identified issues.

CURRENT TOOL CODE:
```python
{current_code}
```

PERFORMANCE STATISTICS:
- Success Rate: {stats.get('success_rate', 0) * 100:.1f}%
- Total Executions: {stats.get('total_executions', 0)}
- Average Duration: {stats.get('avg_duration_ms', 0):.0f}ms

FAILURE ANALYSIS:
{json.dumps(failure_analysis, indent=2)}

REQUIREMENTS FOR IMPROVED VERSION:
1. Fix the most common failure patterns identified above
2. Add comprehensive error handling with specific try-except blocks
3. Add input validation to catch bad inputs early
4. Add retry logic for transient failures (network, timeouts)
5. Improve error messages to be more actionable
6. Maintain backward compatibility with the existing tool interface
7. Keep the same tool name and method signatures
8. Add docstrings explaining the improvements

The improved tool should:
- Increase success rate significantly
- Provide better error messages
- Handle edge cases that caused failures
- Be production-ready and robust

Generate the complete improved tool code following the BaseTool pattern."""

        return prompt
    
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
    
    def deploy_improvement(self, tool_name: str, improvement_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Deploy an approved improvement.
        
        Two modes:
        1. Real deployment (enable_real_improvements=True): Actually writes improved code to disk
        2. Simulated deployment (default): Returns deployment metadata for testing
        
        Real deployment process:
        1. Find the latest generated improvement for this tool
        2. Backup current tool version
        3. Write improved code to file
        4. Refresh tool registry
        5. Verify tool is loadable
        
        Args:
            tool_name: Name of tool to deploy
            improvement_data: Optional improvement data (if not provided, uses latest from improvements_generated)
            
        Returns:
            Dict with deployment status
        """
        self.deployment_count += 1
        
        # Get improvement data
        if not improvement_data:
            # Find latest improvement for this tool
            tool_improvements = [
                imp for imp in self.improvements_generated
                if imp['tool_name'] == tool_name
            ]
            if not tool_improvements:
                return {
                    'success': False,
                    'error': f'No improvement found for {tool_name}. Generate improvement first.'
                }
            improvement_data = tool_improvements[-1]  # Most recent
        
        # MODE 1: Real deployment
        if self.enable_real_improvements and improvement_data.get('mode') == 'real':
            return self._deploy_real_improvement(tool_name, improvement_data)
        
        # MODE 2: Simulated deployment (for testing)
        return self._deploy_simulated_improvement(tool_name, improvement_data)
    
    def _deploy_real_improvement(self, tool_name: str, improvement_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actually deploy the improved tool to the file system.
        
        Steps:
        1. Backup current version
        2. Write improved code to file
        3. Refresh tool registry
        4. Verify tool loads correctly
        """
        try:
            # Step 1: Find current tool file
            current_file = self._find_tool_file(tool_name)
            if not current_file:
                return {
                    'success': False,
                    'error': f'Could not find tool file for {tool_name}'
                }
            
            # Step 2: Create backup
            backup_result = self._create_tool_backup(current_file, tool_name)
            if not backup_result['success']:
                return backup_result
            
            # Step 3: Write improved code to file
            generated_code = improvement_data.get('generated_code')
            if not generated_code:
                return {
                    'success': False,
                    'error': 'No generated code found in improvement data'
                }
            
            # Write to file
            try:
                with open(current_file, 'w') as f:
                    f.write(generated_code)
            except Exception as e:
                # Restore backup if write fails
                self._restore_backup(backup_result['backup_path'], current_file)
                return {
                    'success': False,
                    'error': f'Failed to write improved code: {str(e)}'
                }
            
            # Step 4: Refresh tool registry
            if self.tool_registry:
                try:
                    self.tool_registry.refresh()
                except Exception as e:
                    # Restore backup if registry refresh fails
                    self._restore_backup(backup_result['backup_path'], current_file)
                    return {
                        'success': False,
                        'error': f'Tool registry refresh failed: {str(e)}'
                    }
            
            # Step 5: Verify tool loads correctly
            verification = self._verify_tool_deployment(tool_name)
            if not verification['success']:
                # Restore backup if verification fails
                self._restore_backup(backup_result['backup_path'], current_file)
                if self.tool_registry:
                    self.tool_registry.refresh()
                return {
                    'success': False,
                    'error': f'Deployment verification failed: {verification["error"]}',
                    'backup_restored': True
                }
            
            # Success!
            deployment = {
                'tool_name': tool_name,
                'deployed_at': datetime.now().isoformat(),
                'deployment_strategy': 'direct_replacement',
                'mode': 'real',
                'status': 'deployed',
                'backup_created': True,
                'backup_path': backup_result['backup_path'],
                'rollback_available': True,
                'file_path': current_file,
                'verification': verification
            }
            
            # Step 6: Track version (Phase 9f)
            if self.version_manager:
                try:
                    investigation_report = improvement_data.get('investigation_report', {})
                    improvement_reason = investigation_report.get('root_cause', 'Autonomous improvement')
                    
                    version_id = self.version_manager.create_version(
                        tool_name=tool_name,
                        code=generated_code,
                        created_by='autonomous',
                        improvement_type='autonomous_improvement',
                        improvement_reason=improvement_reason,
                        previous_version_id=None  # Will link to previous automatically
                    )
                    deployment['version_id'] = version_id
                    print(f"   Version {version_id} created and tracked")
                except Exception as e:
                    print(f"   Warning: Failed to track version: {e}")
                    # Don't fail deployment if version tracking fails
            
            self.improvements_deployed.append(deployment)
            
            return {
                'success': True,
                'tool_name': tool_name,
                'deployment': deployment,
                'message': f'Successfully deployed improved version of {tool_name}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Deployment failed: {str(e)}'
            }
    
    def _deploy_simulated_improvement(self, tool_name: str, improvement_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate deployment (for testing without actually modifying files).
        """
        deployment = {
            'tool_name': tool_name,
            'deployed_at': datetime.now().isoformat(),
            'deployment_strategy': 'simulated',
            'mode': 'placeholder',
            'status': 'deployed',
            'backup_created': True,
            'rollback_available': True
        }
        
        self.improvements_deployed.append(deployment)
        
        return {
            'success': True,
            'tool_name': tool_name,
            'deployment': deployment,
            'message': f'Simulated deployment of {tool_name} (enable_real_improvements=False)'
        }
    
    def _create_tool_backup(self, tool_file: str, tool_name: str) -> Dict[str, Any]:
        """
        Create a backup of the current tool version.
        
        Args:
            tool_file: Path to current tool file
            tool_name: Name of the tool
            
        Returns:
            Dict with backup info or error
        """
        try:
            import shutil
            
            # Create backups directory
            backups_dir = "neural_engine/tools/backups"
            os.makedirs(backups_dir, exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{tool_name}_backup_{timestamp}.py"
            backup_path = os.path.join(backups_dir, backup_filename)
            
            # Copy file
            shutil.copy2(tool_file, backup_path)
            
            # Create metadata file
            metadata = {
                'tool_name': tool_name,
                'original_file': tool_file,
                'backup_created_at': datetime.now().isoformat(),
                'backup_reason': 'autonomous_improvement'
            }
            metadata_path = backup_path.replace('.py', '_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return {
                'success': True,
                'backup_path': backup_path,
                'metadata_path': metadata_path
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to create backup: {str(e)}'
            }
    
    def _restore_backup(self, backup_path: str, target_file: str) -> bool:
        """
        Restore a tool from backup.
        
        Args:
            backup_path: Path to backup file
            target_file: Path to restore to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import shutil
            shutil.copy2(backup_path, target_file)
            return True
        except Exception as e:
            print(f"Failed to restore backup: {e}")
            return False
    
    def _verify_tool_deployment(self, tool_name: str) -> Dict[str, Any]:
        """
        Verify that a deployed tool loads correctly.
        
        Args:
            tool_name: Name of tool to verify
            
        Returns:
            Dict with verification results
        """
        if not self.tool_registry:
            return {
                'success': True,
                'message': 'No tool registry available for verification'
            }
        
        try:
            # Check if tool is in registry
            all_tools = self.tool_registry.get_all_tool_definitions()
            
            if tool_name not in all_tools:
                return {
                    'success': False,
                    'error': f'Tool {tool_name} not found in registry after deployment'
                }
            
            # Try to get the tool instance
            tool_instance = self.tool_registry.get_tool(tool_name)
            if not tool_instance:
                return {
                    'success': False,
                    'error': f'Failed to instantiate tool {tool_name}'
                }
            
            # Verify it has required methods
            if not hasattr(tool_instance, 'execute'):
                return {
                    'success': False,
                    'error': f'Tool {tool_name} missing execute() method'
                }
            
            if not hasattr(tool_instance, 'get_tool_definition'):
                return {
                    'success': False,
                    'error': f'Tool {tool_name} missing get_tool_definition() method'
                }
            
            return {
                'success': True,
                'tool_loaded': True,
                'methods_verified': ['execute', 'get_tool_definition']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Verification failed: {str(e)}'
            }
    
    def rollback_improvement(self, tool_name: str, reason: str) -> Dict[str, Any]:
        """
        Rollback a deployed improvement.
        
        Two modes:
        1. Real rollback (enable_real_improvements=True): Restores from backup
        2. Simulated rollback (default): Returns rollback metadata
        
        Real rollback process:
        1. Find the most recent backup for this tool
        2. Restore backup file to original location
        3. Refresh tool registry
        4. Verify restoration worked
        
        Args:
            tool_name: Name of tool to rollback
            reason: Reason for rollback
            
        Returns:
            Dict with rollback status
        """
        self.rollback_count += 1
        
        # MODE 1: Real rollback
        if self.enable_real_improvements:
            return self._rollback_real_improvement(tool_name, reason)
        
        # MODE 2: Simulated rollback
        return self._rollback_simulated_improvement(tool_name, reason)
    
    def _rollback_real_improvement(self, tool_name: str, reason: str) -> Dict[str, Any]:
        """
        Actually rollback the tool by restoring from backup.
        """
        try:
            # Find the most recent deployment for this tool
            tool_deployments = [
                dep for dep in self.improvements_deployed
                if dep['tool_name'] == tool_name and dep.get('mode') == 'real'
            ]
            
            if not tool_deployments:
                return {
                    'success': False,
                    'error': f'No real deployment found for {tool_name}'
                }
            
            latest_deployment = tool_deployments[-1]
            backup_path = latest_deployment.get('backup_path')
            
            if not backup_path or not os.path.exists(backup_path):
                return {
                    'success': False,
                    'error': f'Backup file not found: {backup_path}'
                }
            
            # Get target file path
            target_file = latest_deployment.get('file_path')
            if not target_file:
                target_file = self._find_tool_file(tool_name)
            
            if not target_file:
                return {
                    'success': False,
                    'error': f'Could not find target file for {tool_name}'
                }
            
            # Restore from backup
            if not self._restore_backup(backup_path, target_file):
                return {
                    'success': False,
                    'error': 'Failed to restore backup file'
                }
            
            # Refresh tool registry
            if self.tool_registry:
                try:
                    self.tool_registry.refresh()
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Tool registry refresh failed after rollback: {str(e)}'
                    }
            
            # Verify rollback
            verification = self._verify_tool_deployment(tool_name)
            if not verification['success']:
                return {
                    'success': False,
                    'error': f'Rollback verification failed: {verification["error"]}'
                }
            
            rollback = {
                'tool_name': tool_name,
                'rolled_back_at': datetime.now().isoformat(),
                'reason': reason,
                'mode': 'real',
                'status': 'rolled_back',
                'backup_restored': backup_path,
                'target_file': target_file,
                'verification': verification
            }
            
            self.improvements_rejected.append(rollback)
            
            return {
                'success': True,
                'tool_name': tool_name,
                'rollback': rollback,
                'message': f'Successfully rolled back {tool_name} from backup'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Rollback failed: {str(e)}'
            }
    
    def _rollback_simulated_improvement(self, tool_name: str, reason: str) -> Dict[str, Any]:
        """
        Simulate rollback (for testing).
        """
        rollback = {
            'tool_name': tool_name,
            'rolled_back_at': datetime.now().isoformat(),
            'reason': reason,
            'mode': 'simulated',
            'status': 'rolled_back'
        }
        
        self.improvements_rejected.append(rollback)
        
        return {
            'success': True,
            'tool_name': tool_name,
            'rollback': rollback,
            'message': f'Simulated rollback of {tool_name}: {reason}'
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
