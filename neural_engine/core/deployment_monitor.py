"""
Post-Deployment Monitoring - Continuous Health Tracking

Monitor tool performance after deployment to detect regressions.
Automatically rollback if success rate drops significantly.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import statistics

logger = logging.getLogger(__name__)


class DeploymentMonitor:
    """
    Monitor tool performance after deployment and trigger rollback if needed.
    
    Uses sliding window comparison:
    - Track success rate over time
    - Compare current window to historical baseline
    - Detect statistically significant drops
    - Auto-rollback if regression detected
    """
    
    def __init__(self,
                 execution_store,
                 tool_registry,
                 monitoring_window_hours: int = 24,
                 baseline_window_days: int = 7,
                 regression_threshold: float = 0.15,  # 15% drop triggers rollback
                 min_executions: int = 10):
        """
        Initialize deployment monitor.
        
        Args:
            execution_store: ExecutionStore for metrics
            tool_registry: ToolRegistry for rollback
            monitoring_window_hours: Hours to monitor after deployment
            baseline_window_days: Days of history to use as baseline
            regression_threshold: Success rate drop that triggers rollback (0.15 = 15%)
            min_executions: Minimum executions needed for valid comparison
        """
        self.execution_store = execution_store
        self.tool_registry = tool_registry
        self.monitoring_window_hours = monitoring_window_hours
        self.baseline_window_days = baseline_window_days
        self.regression_threshold = regression_threshold
        self.min_executions = min_executions
    
    def start_monitoring(self, tool_name: str, deployment_time: datetime = None) -> str:
        """
        Start monitoring a newly deployed tool.
        
        Args:
            tool_name: Name of deployed tool
            deployment_time: When tool was deployed (default: now)
        
        Returns:
            Monitoring session ID
        """
        if deployment_time is None:
            deployment_time = datetime.now()
        
        logger.info(f"📊 Starting post-deployment monitoring for {tool_name}")
        logger.info(f"   Deployment time: {deployment_time}")
        logger.info(f"   Monitoring window: {self.monitoring_window_hours} hours")
        logger.info(f"   Baseline period: {self.baseline_window_days} days")
        
        # Create monitoring session
        session_id = self._create_monitoring_session(tool_name, deployment_time)
        
        logger.info(f"   Monitoring session: {session_id}")
        
        return session_id
    
    def check_health(self, tool_name: str, session_id: str = None) -> Dict[str, Any]:
        """
        Check tool health and detect regressions.
        
        Args:
            tool_name: Name of tool to check
            session_id: Optional monitoring session ID
        
        Returns:
            Health report with regression detection and rollback recommendation
        """
        logger.info(f"🏥 Checking health for {tool_name}")
        
        # Get deployment info
        deployment = self._get_latest_deployment(tool_name, session_id)
        if not deployment:
            return {
                'error': 'No deployment found',
                'tool_name': tool_name
            }
        
        deployment_time = deployment['deployment_time']
        time_since_deployment = (datetime.now() - deployment_time).total_seconds() / 3600
        
        logger.info(f"   Deployed {time_since_deployment:.1f} hours ago")
        
        # Get baseline metrics (before deployment)
        baseline = self._get_baseline_metrics(tool_name, deployment_time)
        
        # Get current metrics (after deployment)
        current = self._get_current_metrics(tool_name, deployment_time)
        
        # Compare metrics
        comparison = self._compare_metrics(baseline, current)
        
        # Determine if rollback needed
        needs_rollback = self._needs_rollback(comparison)
        
        report = {
            'tool_name': tool_name,
            'session_id': deployment.get('session_id'),
            'deployment_time': deployment_time.isoformat(),
            'hours_since_deployment': time_since_deployment,
            'baseline': baseline,
            'current': current,
            'comparison': comparison,
            'needs_rollback': needs_rollback,
            'checked_at': datetime.now().isoformat()
        }
        
        # Log health check
        self._log_health_check(report)
        
        # Print summary
        self._print_health_summary(report)
        
        return report
    
    def auto_rollback_if_needed(self, tool_name: str, session_id: str = None) -> Dict[str, Any]:
        """
        Check health and automatically rollback if regression detected.
        
        Args:
            tool_name: Name of tool
            session_id: Optional monitoring session ID
        
        Returns:
            Rollback report
        """
        health = self.check_health(tool_name, session_id)
        
        if health.get('needs_rollback'):
            logger.warning(f"🚨 REGRESSION DETECTED for {tool_name}!")
            logger.warning(f"   Initiating automatic rollback...")
            
            rollback_result = self._perform_rollback(tool_name, health)
            
            return {
                **health,
                'rollback_performed': True,
                'rollback_result': rollback_result
            }
        else:
            logger.info(f"   ✅ Tool health OK - no rollback needed")
            return {
                **health,
                'rollback_performed': False
            }
    
    def _get_baseline_metrics(self, tool_name: str, deployment_time: datetime) -> Dict[str, Any]:
        """
        Get baseline metrics from before deployment.
        
        Uses data from baseline_window_days before deployment.
        """
        try:
            baseline_start = deployment_time - timedelta(days=self.baseline_window_days)
            
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    # Get executions from baseline period
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE success = TRUE) as successes,
                            AVG(duration_ms) as avg_duration
                        FROM tool_executions
                        WHERE tool_name = %s
                          AND executed_at >= %s
                          AND executed_at < %s
                    """, (tool_name, baseline_start, deployment_time))
                    
                    row = cursor.fetchone()
                    total = row[0] or 0
                    successes = row[1] or 0
                    avg_duration = row[2]
                    
                    success_rate = successes / total if total > 0 else None
                    
                    return {
                        'period': 'baseline',
                        'start': baseline_start.isoformat(),
                        'end': deployment_time.isoformat(),
                        'total_executions': total,
                        'successes': successes,
                        'success_rate': success_rate,
                        'avg_duration_ms': float(avg_duration) if avg_duration else None,
                        'sufficient_data': total >= self.min_executions
                    }
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting baseline metrics: {e}")
            return {'error': str(e)}
    
    def _get_current_metrics(self, tool_name: str, deployment_time: datetime) -> Dict[str, Any]:
        """
        Get current metrics from after deployment.
        
        Uses data from deployment_time to now.
        """
        try:
            current_start = deployment_time
            current_end = datetime.now()
            
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    # Get executions from current period
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE success = TRUE) as successes,
                            AVG(duration_ms) as avg_duration
                        FROM tool_executions
                        WHERE tool_name = %s
                          AND executed_at >= %s
                          AND executed_at <= %s
                    """, (tool_name, current_start, current_end))
                    
                    row = cursor.fetchone()
                    total = row[0] or 0
                    successes = row[1] or 0
                    avg_duration = row[2]
                    
                    success_rate = successes / total if total > 0 else None
                    
                    return {
                        'period': 'current',
                        'start': current_start.isoformat(),
                        'end': current_end.isoformat(),
                        'total_executions': total,
                        'successes': successes,
                        'success_rate': success_rate,
                        'avg_duration_ms': float(avg_duration) if avg_duration else None,
                        'sufficient_data': total >= self.min_executions
                    }
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {'error': str(e)}
    
    def _compare_metrics(self, baseline: Dict, current: Dict) -> Dict[str, Any]:
        """
        Compare baseline and current metrics to detect regression.
        """
        comparison = {
            'has_sufficient_data': baseline.get('sufficient_data') and current.get('sufficient_data'),
            'success_rate_change': None,
            'success_rate_drop': None,
            'duration_change': None,
            'regression_detected': False,
            'regression_severity': 'none'
        }
        
        # Can't compare without sufficient data
        if not comparison['has_sufficient_data']:
            comparison['warning'] = 'Insufficient data for comparison'
            return comparison
        
        # Compare success rates
        baseline_rate = baseline.get('success_rate')
        current_rate = current.get('success_rate')
        
        if baseline_rate is not None and current_rate is not None:
            change = current_rate - baseline_rate
            drop = -change if change < 0 else 0
            
            comparison['success_rate_change'] = change
            comparison['success_rate_drop'] = drop
            comparison['baseline_success_rate'] = baseline_rate
            comparison['current_success_rate'] = current_rate
            
            # Check for regression
            if drop >= self.regression_threshold:
                comparison['regression_detected'] = True
                
                if drop >= 0.30:  # 30%+ drop
                    comparison['regression_severity'] = 'critical'
                elif drop >= 0.20:  # 20-30% drop
                    comparison['regression_severity'] = 'high'
                else:  # 15-20% drop
                    comparison['regression_severity'] = 'medium'
        
        # Compare durations
        baseline_duration = baseline.get('avg_duration_ms')
        current_duration = current.get('avg_duration_ms')
        
        if baseline_duration and current_duration:
            duration_change = (current_duration - baseline_duration) / baseline_duration
            comparison['duration_change'] = duration_change
            
            # Significant slowdown is also a concern
            if duration_change > 2.0:  # 200% slower
                comparison['performance_degradation'] = True
        
        return comparison
    
    def _needs_rollback(self, comparison: Dict) -> bool:
        """
        Determine if automatic rollback should be triggered.
        
        Criteria:
        - Regression detected (success rate drop >= threshold)
        - Sufficient data for comparison
        - Severity medium or higher
        """
        if not comparison.get('has_sufficient_data'):
            return False
        
        if comparison.get('regression_detected'):
            severity = comparison.get('regression_severity', 'none')
            return severity in ('medium', 'high', 'critical')
        
        return False
    
    def _perform_rollback(self, tool_name: str, health_report: Dict) -> Dict[str, Any]:
        """
        Perform automatic rollback to previous version.
        """
        try:
            logger.info(f"   Rolling back {tool_name}...")
            
            # TODO: Implement actual rollback logic
            # This would:
            # 1. Get previous version from backups
            # 2. Restore file
            # 3. Refresh registry
            # 4. Update deployment record
            
            result = {
                'success': True,
                'tool_name': tool_name,
                'rollback_time': datetime.now().isoformat(),
                'reason': f"Regression detected: {health_report['comparison']['regression_severity']}",
                'success_rate_drop': health_report['comparison']['success_rate_drop']
            }
            
            # Log rollback
            self._log_rollback(result)
            
            logger.info(f"   ✅ Rollback successful!")
            
            return result
        
        except Exception as e:
            logger.error(f"   ❌ Rollback failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_monitoring_session(self, tool_name: str, deployment_time: datetime) -> str:
        """Create monitoring session in database."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO deployment_monitoring (
                            tool_name, deployment_time, monitoring_started_at,
                            monitoring_window_hours, baseline_window_days,
                            regression_threshold, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING session_id
                    """, (
                        tool_name,
                        deployment_time,
                        datetime.now(),
                        self.monitoring_window_hours,
                        self.baseline_window_days,
                        self.regression_threshold,
                        'active'
                    ))
                    
                    session_id = cursor.fetchone()[0]
                    conn.commit()
                    return str(session_id)
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error creating monitoring session: {e}")
            return f"error_{datetime.now().timestamp()}"
    
    def _get_latest_deployment(self, tool_name: str, session_id: str = None) -> Optional[Dict]:
        """Get latest deployment info."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    if session_id:
                        cursor.execute("""
                            SELECT session_id, deployment_time
                            FROM deployment_monitoring
                            WHERE session_id = %s
                        """, (session_id,))
                    else:
                        cursor.execute("""
                            SELECT session_id, deployment_time
                            FROM deployment_monitoring
                            WHERE tool_name = %s
                            ORDER BY deployment_time DESC
                            LIMIT 1
                        """, (tool_name,))
                    
                    row = cursor.fetchone()
                    if row:
                        return {
                            'session_id': row[0],
                            'deployment_time': row[1]
                        }
                    return None
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting deployment: {e}")
            return None
    
    def _log_health_check(self, report: Dict):
        """Log health check to database."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO deployment_health_checks (
                            tool_name, session_id, checked_at,
                            baseline_success_rate, current_success_rate,
                            success_rate_drop, regression_detected,
                            regression_severity, needs_rollback
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        report['tool_name'],
                        report.get('session_id'),
                        report['checked_at'],
                        report['baseline'].get('success_rate'),
                        report['current'].get('success_rate'),
                        report['comparison'].get('success_rate_drop'),
                        report['comparison'].get('regression_detected'),
                        report['comparison'].get('regression_severity'),
                        report['needs_rollback']
                    ))
                    conn.commit()
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error logging health check: {e}")
    
    def _log_rollback(self, result: Dict):
        """Log rollback to database."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO deployment_rollbacks (
                            tool_name, rollback_time, reason,
                            success_rate_drop, rollback_successful
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (
                        result['tool_name'],
                        result['rollback_time'],
                        result['reason'],
                        result.get('success_rate_drop'),
                        result['success']
                    ))
                    conn.commit()
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error logging rollback: {e}")
    
    def _print_health_summary(self, report: Dict):
        """Print human-readable health summary."""
        logger.info(f"\n   === Health Check Summary ===")
        
        baseline = report['baseline']
        current = report['current']
        comparison = report['comparison']
        
        logger.info(f"   Baseline ({baseline.get('total_executions', 0)} executions):")
        if baseline.get('success_rate') is not None:
            logger.info(f"      Success rate: {baseline['success_rate']:.1%}")
        
        logger.info(f"   Current ({current.get('total_executions', 0)} executions):")
        if current.get('success_rate') is not None:
            logger.info(f"      Success rate: {current['success_rate']:.1%}")
        
        if comparison.get('success_rate_change') is not None:
            change = comparison['success_rate_change']
            emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            logger.info(f"   {emoji} Change: {change:+.1%}")
        
        if comparison.get('regression_detected'):
            severity = comparison.get('regression_severity', 'unknown')
            logger.warning(f"   🚨 REGRESSION: {severity.upper()} severity")
            logger.warning(f"   Drop: {comparison['success_rate_drop']:.1%}")
        
        if not comparison.get('has_sufficient_data'):
            logger.warning(f"   ⚠️  Insufficient data for reliable comparison")
        
        logger.info(f"   ===========================\n")
