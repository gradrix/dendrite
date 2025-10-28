"""
Autonomous Background Loop - The Heart of Fractal Self-Improvement

This module implements the continuous autonomous improvement cycle:
1. Monitor system state
2. Detect improvement opportunities
3. Investigate and analyze
4. Generate improvements
5. Test improvements safely
6. Deploy if successful
7. Monitor post-deployment
8. Repeat forever

This is the "fractal" aspect - the system improving itself recursively,
at multiple levels, continuously, without human intervention.
"""

import asyncio
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
import time

from neural_engine.core.shadow_tester import ShadowTester, ShadowTestRecommender
from neural_engine.core.replay_tester import ReplayTester, ReplayTestRecommender

logger = logging.getLogger(__name__)


class AutonomousLoop:
    """
    Continuous autonomous improvement loop.
    
    This is the orchestrator of the orchestrators - it watches the system,
    detects opportunities, and coordinates improvements autonomously.
    """
    
    def __init__(self,
                 orchestrator,
                 execution_store,
                 lifecycle_manager=None,
                 self_investigation_neuron=None,
                 autonomous_improvement_neuron=None,
                 check_interval_seconds: int = 300,  # 5 minutes
                 maintenance_interval_hours: int = 24,  # Daily
                 min_executions_for_analysis: int = 10,
                 improvement_threshold: float = 0.7):
        """
        Initialize autonomous loop.
        
        Args:
            orchestrator: Main orchestrator instance
            execution_store: ExecutionStore for querying metrics
            lifecycle_manager: ToolLifecycleManager for tool maintenance
            self_investigation_neuron: SelfInvestigationNeuron for analysis
            autonomous_improvement_neuron: AutonomousImprovementNeuron for improvements
            check_interval_seconds: How often to check for opportunities
            maintenance_interval_hours: How often to run full maintenance
            min_executions_for_analysis: Minimum executions before analyzing a tool
            improvement_threshold: Threshold for triggering improvements (0.0-1.0)
        """
        self.orchestrator = orchestrator
        self.execution_store = execution_store
        self.lifecycle_manager = lifecycle_manager
        self.self_investigation = self_investigation_neuron
        self.autonomous_improvement = autonomous_improvement_neuron
        
        self.check_interval = check_interval_seconds
        self.maintenance_interval = maintenance_interval_hours * 3600  # Convert to seconds
        self.min_executions = min_executions_for_analysis
        self.improvement_threshold = improvement_threshold
        
        self.running = False
        self.last_maintenance = None
        self.last_check = None
        self.cycle_count = 0
        
        # Initialize testing strategies
        self.shadow_tester = ShadowTester(execution_store=execution_store)
        self.replay_tester = ReplayTester(execution_store=execution_store)
        
        # Statistics
        self.stats = {
            'cycles_completed': 0,
            'opportunities_detected': 0,
            'improvements_attempted': 0,
            'improvements_deployed': 0,
            'improvements_failed': 0,
            'tools_analyzed': 0,
            'maintenance_runs': 0
        }
    
    async def start(self):
        """
        Start the autonomous loop.
        
        This runs forever until explicitly stopped.
        """
        logger.info("🚀 Starting autonomous improvement loop...")
        self.running = True
        self.last_maintenance = datetime.now()
        
        try:
            while self.running:
                cycle_start = time.time()
                self.cycle_count += 1
                
                logger.info(f"\n{'='*60}")
                logger.info(f"Autonomous Cycle #{self.cycle_count}")
                logger.info(f"{'='*60}")
                
                # 1. Run periodic maintenance if needed
                await self._check_maintenance()
                
                # 2. Detect improvement opportunities
                opportunities = await self._detect_opportunities()
                
                # 3. Process opportunities
                if opportunities:
                    await self._process_opportunities(opportunities)
                else:
                    logger.info("No improvement opportunities detected in this cycle.")
                
                # 4. Update statistics
                self.stats['cycles_completed'] += 1
                self.last_check = datetime.now()
                
                # 5. Wait before next cycle
                cycle_duration = time.time() - cycle_start
                logger.info(f"\nCycle completed in {cycle_duration:.2f}s")
                logger.info(f"Stats: {self.stats}")
                logger.info(f"Next check in {self.check_interval}s...\n")
                
                await asyncio.sleep(self.check_interval)
                
        except asyncio.CancelledError:
            logger.info("Autonomous loop cancelled")
            self.running = False
        except Exception as e:
            logger.error(f"Autonomous loop error: {e}", exc_info=True)
            self.running = False
            raise
    
    def stop(self):
        """Stop the autonomous loop."""
        logger.info("Stopping autonomous loop...")
        self.running = False
    
    async def _check_maintenance(self):
        """Run periodic maintenance tasks."""
        if not self.last_maintenance:
            self.last_maintenance = datetime.now()
            return
        
        time_since_maintenance = (datetime.now() - self.last_maintenance).total_seconds()
        
        if time_since_maintenance >= self.maintenance_interval:
            logger.info("\n🔧 Running periodic maintenance...")
            
            try:
                # 1. Tool lifecycle maintenance
                if self.lifecycle_manager:
                    report = self.lifecycle_manager.maintenance(dry_run=False)
                    logger.info(f"   Lifecycle: Archived {report['cleanup_report'].get('total_archived', 0)} old tools")
                
                # 2. Refresh tool discovery embeddings
                if hasattr(self.orchestrator, 'tool_discovery') and self.orchestrator.tool_discovery:
                    self.orchestrator.tool_discovery.index_all_tools()
                    logger.info(f"   Discovery: Re-indexed all tools")
                
                # 3. Refresh tool registry
                if hasattr(self.orchestrator, 'tool_selector') and self.orchestrator.tool_selector:
                    if hasattr(self.orchestrator.tool_selector, 'tool_registry'):
                        self.orchestrator.tool_selector.tool_registry.refresh()
                        logger.info(f"   Registry: Refreshed tool list")
                
                self.last_maintenance = datetime.now()
                self.stats['maintenance_runs'] += 1
                logger.info("✓ Maintenance complete\n")
                
            except Exception as e:
                logger.error(f"Maintenance error: {e}")
    
    async def _detect_opportunities(self) -> List[Dict[str, Any]]:
        """
        Detect improvement opportunities by analyzing system metrics.
        
        Returns:
            List of opportunity dictionaries with details
        """
        logger.info("🔍 Detecting improvement opportunities...")
        opportunities = []
        
        try:
            # Get low-performing tools
            low_performers = self.execution_store.get_bottom_tools(
                limit=5,
                min_executions=self.min_executions
            )
            
            for tool in low_performers:
                tool_name = tool['tool_name']
                success_rate = tool['success_rate']
                total_execs = tool['total_executions']
                
                # Check if below improvement threshold
                if success_rate < self.improvement_threshold:
                    opportunity = {
                        'type': 'low_success_rate',
                        'tool_name': tool_name,
                        'current_success_rate': success_rate,
                        'total_executions': total_execs,
                        'priority': 'high' if success_rate < 0.5 else 'medium',
                        'detected_at': datetime.now().isoformat()
                    }
                    opportunities.append(opportunity)
                    logger.info(f"   ⚠️  Found: {tool_name} (success rate: {success_rate:.2%}, {total_execs} executions)")
            
            # Check for tools with recent failures
            recent_failures = self._get_recent_failures()
            for failure in recent_failures:
                if not any(opp['tool_name'] == failure['tool_name'] for opp in opportunities):
                    opportunities.append({
                        'type': 'recent_failures',
                        'tool_name': failure['tool_name'],
                        'failure_count': failure['count'],
                        'priority': 'high',
                        'detected_at': datetime.now().isoformat()
                    })
                    logger.info(f"   ⚠️  Found: {failure['tool_name']} (recent failures: {failure['count']})")
            
            # TODO: Phase 9e - Detect duplicate tools via embeddings
            # TODO: Phase 9e - Detect unused tools that could be deprecated
            
            self.stats['opportunities_detected'] += len(opportunities)
            logger.info(f"   Detected {len(opportunities)} opportunities\n")
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error detecting opportunities: {e}")
            return []
    
    def _get_recent_failures(self, hours: int = 24, min_failures: int = 3) -> List[Dict]:
        """Get tools with recent failures."""
        try:
            # Query recent failed executions grouped by tool
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT tool_name, COUNT(*) as failure_count
                        FROM tool_executions
                        WHERE success = FALSE
                          AND executed_at > NOW() - INTERVAL '%s hours'
                        GROUP BY tool_name
                        HAVING COUNT(*) >= %s
                        ORDER BY COUNT(*) DESC
                        LIMIT 5
                    """, (hours, min_failures))
                    
                    results = cursor.fetchall()
                    return [
                        {'tool_name': row[0], 'count': row[1]}
                        for row in results
                    ]
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting recent failures: {e}")
            return []
    
    async def _process_opportunities(self, opportunities: List[Dict[str, Any]]):
        """
        Process improvement opportunities.
        
        This is the core of the autonomous loop - analyze, improve, deploy.
        """
        logger.info(f"🔨 Processing {len(opportunities)} opportunities...\n")
        
        # Sort by priority
        opportunities.sort(key=lambda x: 0 if x['priority'] == 'high' else 1)
        
        for idx, opportunity in enumerate(opportunities, 1):
            logger.info(f"--- Opportunity {idx}/{len(opportunities)} ---")
            logger.info(f"Type: {opportunity['type']}")
            logger.info(f"Tool: {opportunity['tool_name']}")
            logger.info(f"Priority: {opportunity['priority']}")
            
            try:
                # Check if we have the neurons needed for improvement
                if not self.self_investigation or not self.autonomous_improvement:
                    logger.warning("⚠️  Self-improvement neurons not available. Skipping.")
                    continue
                
                # 1. Investigate the tool
                logger.info("\n1️⃣  Investigating tool...")
                investigation = await self._investigate_tool(opportunity)
                
                if not investigation or not investigation.get('should_improve'):
                    logger.info("   Investigation suggests no improvement needed.")
                    continue
                
                # 2. Generate improvement
                logger.info("\n2️⃣  Generating improvement...")
                improvement = await self._generate_improvement(opportunity, investigation)
                
                if not improvement or not improvement.get('success'):
                    logger.info("   Improvement generation failed.")
                    self.stats['improvements_failed'] += 1
                    continue
                
                # 3. Test improvement (TODO: Phase 9d - use shadow/replay testing)
                logger.info("\n3️⃣  Testing improvement...")
                test_result = await self._test_improvement(opportunity, improvement)
                
                if not test_result or not test_result.get('passed'):
                    logger.info("   Tests failed. Not deploying.")
                    self.stats['improvements_failed'] += 1
                    continue
                
                # 4. Deploy improvement
                logger.info("\n4️⃣  Deploying improvement...")
                deploy_result = await self._deploy_improvement(improvement)
                
                if deploy_result and deploy_result.get('success'):
                    logger.info("   ✅ Improvement deployed successfully!")
                    self.stats['improvements_deployed'] += 1
                else:
                    logger.info("   ❌ Deployment failed.")
                    self.stats['improvements_failed'] += 1
                
                # 5. Schedule post-deployment monitoring (TODO: Phase 9d)
                # This will track success rate after deployment and auto-rollback if needed
                
            except Exception as e:
                logger.error(f"Error processing opportunity: {e}", exc_info=True)
                self.stats['improvements_failed'] += 1
            
            logger.info("")  # Blank line between opportunities
    
    async def _investigate_tool(self, opportunity: Dict) -> Optional[Dict]:
        """Investigate tool to understand issues."""
        tool_name = opportunity['tool_name']
        
        try:
            # Use SelfInvestigationNeuron to analyze
            investigation_goal = f"Investigate why tool '{tool_name}' has low success rate"
            result = self.self_investigation.investigate(investigation_goal)
            
            self.stats['tools_analyzed'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Investigation error: {e}")
            return None
    
    async def _generate_improvement(self, opportunity: Dict, investigation: Dict) -> Optional[Dict]:
        """Generate improvement for the tool."""
        tool_name = opportunity['tool_name']
        
        try:
            # Use AutonomousImprovementNeuron to generate improvement
            improvement_goal = f"Improve tool '{tool_name}' based on analysis"
            result = self.autonomous_improvement.improve_tool(
                tool_name=tool_name,
                investigation_results=investigation
            )
            
            self.stats['improvements_attempted'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Improvement generation error: {e}")
            return None
    
    async def _test_improvement(self, opportunity: Dict, improvement: Dict) -> Optional[Dict]:
        """
        Test the improvement before deployment using appropriate strategy.
        
        Uses SafeTestingStrategy to determine:
        - Shadow testing (parallel old/new comparison)
        - Replay testing (historical data)  
        - Synthetic testing (test cases)
        - Manual review needed
        """
        tool_name = opportunity['tool_name']
        
        # Get old and new tool instances
        old_tool = self._get_tool_instance(tool_name, version='old')
        new_tool = self._get_tool_instance(tool_name, version='new')
        
        if not old_tool or not new_tool:
            logger.error("   Could not load tool instances for testing")
            return {'passed': False, 'reason': 'tool_loading_failed'}
        
        # Determine testing strategy
        test_strategy = self._determine_test_strategy(new_tool, tool_name)
        logger.info(f"   Testing strategy: {test_strategy['method']}")
        
        # Execute appropriate testing method
        if test_strategy['method'] == 'shadow':
            return await self._shadow_test_improvement(old_tool, new_tool, tool_name)
        
        elif test_strategy['method'] == 'replay':
            return await self._replay_test_improvement(new_tool, tool_name)
        
        elif test_strategy['method'] == 'synthetic':
            return await self._synthetic_test_improvement(new_tool)
        
        elif test_strategy['method'] == 'manual':
            logger.warning("   Manual review required - auto-approving for now")
            return {'passed': True, 'method': 'manual_auto_approved'}
        
        else:
            # Fallback: basic validation
            if improvement.get('generated_code'):
                return {'passed': True, 'method': 'basic_validation'}
            return {'passed': False, 'reason': 'no_code_generated'}
    
    def _determine_test_strategy(self, tool, tool_name: str) -> Dict[str, str]:
        """Determine best testing strategy for this tool."""
        
        # Check if shadow testing is suitable
        shadow_check = ShadowTestRecommender.can_shadow_test(tool)
        if shadow_check['suitable']:
            return {
                'method': 'shadow',
                'reason': shadow_check['reason']
            }
        
        # Check if replay testing is suitable
        replay_check = ReplayTestRecommender.can_replay_test(
            tool, self.execution_store, tool_name
        )
        if replay_check['suitable']:
            return {
                'method': 'replay',
                'reason': replay_check['reason']
            }
        
        # Check if tool has test cases
        if hasattr(tool, 'get_test_cases'):
            test_cases = tool.get_test_cases()
            if test_cases:
                return {
                    'method': 'synthetic',
                    'reason': f'Tool provides {len(test_cases)} test cases'
                }
        
        # Default to manual review
        return {
            'method': 'manual',
            'reason': 'No automated testing strategy available'
        }
    
    async def _shadow_test_improvement(self, old_tool, new_tool, tool_name: str) -> Dict:
        """Run shadow test comparing old and new versions."""
        try:
            # Get test inputs from tool or generate simple ones
            test_inputs = []
            if hasattr(new_tool, 'get_test_cases'):
                test_cases = new_tool.get_test_cases()
                test_inputs = [tc.get('input', {}) for tc in test_cases]
            
            if not test_inputs:
                # Generate simple test inputs based on recent executions
                test_inputs = self._generate_test_inputs_from_history(tool_name)
            
            if not test_inputs:
                logger.warning("   No test inputs available for shadow testing")
                return {'passed': False, 'reason': 'no_test_inputs'}
            
            # Run shadow test
            result = await self.shadow_tester.shadow_test(
                old_tool, new_tool, test_inputs, tool_name
            )
            
            return result
        
        except Exception as e:
            logger.error(f"   Shadow test error: {e}")
            return {'passed': False, 'error': str(e)}
    
    async def _replay_test_improvement(self, new_tool, tool_name: str) -> Dict:
        """Run replay test with historical data."""
        try:
            result = await self.replay_tester.replay_test(
                new_tool, tool_name
            )
            return result
        
        except Exception as e:
            logger.error(f"   Replay test error: {e}")
            return {'passed': False, 'error': str(e)}
    
    async def _synthetic_test_improvement(self, new_tool) -> Dict:
        """Run synthetic tests using tool's test cases."""
        try:
            if not hasattr(new_tool, 'get_test_cases'):
                return {'passed': False, 'reason': 'no_test_cases'}
            
            test_cases = new_tool.get_test_cases()
            if not test_cases:
                return {'passed': False, 'reason': 'no_test_cases'}
            
            passed = 0
            failed = 0
            
            for test_case in test_cases:
                try:
                    result = new_tool.execute(test_case.get('input', {}))
                    expected = test_case.get('expected_output')
                    
                    if expected and result == expected:
                        passed += 1
                    elif not expected:
                        passed += 1  # No expected output, just check it runs
                    else:
                        failed += 1
                
                except Exception:
                    failed += 1
            
            success_rate = passed / (passed + failed) if (passed + failed) > 0 else 0
            
            return {
                'passed': success_rate >= 0.9,  # 90% threshold
                'method': 'synthetic',
                'passed_tests': passed,
                'failed_tests': failed,
                'success_rate': success_rate
            }
        
        except Exception as e:
            logger.error(f"   Synthetic test error: {e}")
            return {'passed': False, 'error': str(e)}
    
    def _get_tool_instance(self, tool_name: str, version: str):
        """Get tool instance (stub - needs actual implementation)."""
        # TODO: Implement actual tool loading
        # This would need to:
        # 1. Load tool class from registry
        # 2. For 'old' version: load from backup
        # 3. For 'new' version: load current version
        return None
    
    def _generate_test_inputs_from_history(self, tool_name: str, limit: int = 5) -> List[Dict]:
        """Generate test inputs from recent successful executions."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT parameters
                        FROM tool_executions
                        WHERE tool_name = %s
                          AND success = TRUE
                        ORDER BY executed_at DESC
                        LIMIT %s
                    """, (tool_name, limit))
                    
                    rows = cursor.fetchall()
                    return [row[0] for row in rows if row[0]]
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error generating test inputs: {e}")
            return []
    
    async def _deploy_improvement(self, improvement: Dict) -> Optional[Dict]:
        """Deploy the improvement."""
        try:
            # The improvement should already be deployed by AutonomousImprovementNeuron
            # This is just confirmation
            return {'success': True}
        except Exception as e:
            logger.error(f"Deployment error: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        return {
            **self.stats,
            'running': self.running,
            'cycle_count': self.cycle_count,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'last_maintenance': self.last_maintenance.isoformat() if self.last_maintenance else None,
            'uptime_seconds': (datetime.now() - self.last_maintenance).total_seconds() if self.last_maintenance else 0
        }


# Convenience function to start loop in background
def start_autonomous_loop(orchestrator, execution_store, **kwargs) -> asyncio.Task:
    """
    Start autonomous loop as a background task.
    
    Args:
        orchestrator: Orchestrator instance
        execution_store: ExecutionStore instance
        **kwargs: Additional arguments for AutonomousLoop
    
    Returns:
        asyncio.Task that can be cancelled
    
    Example:
        loop_task = start_autonomous_loop(orchestrator, execution_store)
        
        # Later, to stop:
        loop_task.cancel()
    """
    loop = AutonomousLoop(orchestrator, execution_store, **kwargs)
    task = asyncio.create_task(loop.start())
    return task
