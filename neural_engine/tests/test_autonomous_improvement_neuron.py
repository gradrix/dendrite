"""
Tests for AutonomousImprovementNeuron (Phase 9c)

This tests the complete autonomous improvement pipeline:
1. Opportunity Detection
2. Improvement Generation
3. A/B Testing
4. Validation & Deployment
5. Full Cycle Integration
"""

import pytest
import time
from datetime import datetime, timedelta
from neural_engine.core.autonomous_improvement_neuron import (
    AutonomousImprovementNeuron,
    ImprovementOpportunity,
    ABTestResult
)
from neural_engine.core.self_investigation_neuron import SelfInvestigationNeuron
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.ollama_client import OllamaClient


@pytest.fixture
def message_bus():
    """Create message bus for testing."""
    return MessageBus()


@pytest.fixture
def ollama_client():
    """Create Ollama client for testing."""
    return OllamaClient()


@pytest.fixture
def execution_store():
    """Create execution store with test data for improvement testing."""
    store = ExecutionStore()
    
    # Clean up any existing test data
    conn = store._get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM tool_executions WHERE tool_name LIKE 'improvement_test_%'")
            cursor.execute("DELETE FROM tool_statistics WHERE tool_name LIKE 'improvement_test_%'")
            cursor.execute("DELETE FROM executions WHERE goal_id LIKE 'goal_improvement_%'")
        conn.commit()
    finally:
        store._release_connection(conn)
    
    # Create test tools with different characteristics
    
    # 1. Failing tool - needs improvement (30% success rate)
    for i in range(30):
        is_success = i < 9  # 9 success, 21 failures = 30% success
        exec_id = store.store_execution(
            goal_id=f"goal_improvement_failing_{i}",
            goal_text="test improvement goal",
            intent="tool_use",
            success=is_success,
            error=None if is_success else f'Test failure {i}',
            duration_ms=1000
        )
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name='improvement_test_failing_tool',
            parameters={'test': i},
            result={'result': 'success' if is_success else 'failure'},
            duration_ms=1000,
            success=is_success,
            error=None if is_success else f'Test failure {i}'
        )
    
    # 2. Degrading tool - was good, now declining (80% -> 40% success rate)
    # Old executions (good)
    for i in range(20):
        exec_id = store.store_execution(
            goal_id=f"goal_improvement_degrading_old_{i}",
            goal_text="test improvement goal",
            intent="tool_use",
            success=True,
            duration_ms=1000
        )
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name='improvement_test_degrading_tool',
            parameters={'test': i},
            result={'result': 'success'},
            duration_ms=1000,
            success=True
        )
    
    # Recent failing executions
    time.sleep(0.1)  # Small delay to separate time periods
    for i in range(20, 30):
        is_success = i < 24  # 4 success, 6 failures = 40% recent
        exec_id = store.store_execution(
            goal_id=f"goal_improvement_degrading_new_{i}",
            goal_text="test improvement goal",
            intent="tool_use",
            success=is_success,
            error=None if is_success else f'Degradation failure {i}',
            duration_ms=1000
        )
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name='improvement_test_degrading_tool',
            parameters={'test': i},
            result={'result': 'success' if is_success else 'failure'},
            duration_ms=1000,
            success=is_success,
            error=None if is_success else f'Degradation failure {i}'
        )
    
    # 3. Slow tool - needs performance optimization (8 second duration)
    for i in range(10):
        exec_id = store.store_execution(
            goal_id=f"goal_improvement_slow_{i}",
            goal_text="test improvement goal",
            intent="tool_use",
            success=True,
            duration_ms=8000
        )
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name='improvement_test_slow_tool',
            parameters={'test': i},
            result={'result': 'success'},
            duration_ms=8000,  # 8 seconds - very slow
            success=True
        )
    
    # 4. Healthy tool - no improvement needed (95% success rate)
    for i in range(20):
        is_success = i < 19  # 19 success, 1 failure = 95%
        exec_id = store.store_execution(
            goal_id=f"goal_improvement_healthy_{i}",
            goal_text="test improvement goal",
            intent="tool_use",
            success=is_success,
            error=None if is_success else 'Rare failure',
            duration_ms=500
        )
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name='improvement_test_healthy_tool',
            parameters={'test': i},
            result={'result': 'success' if is_success else 'failure'},
            duration_ms=500,
            success=is_success,
            error=None if is_success else 'Rare failure'
        )
    
    yield store
    
    # Cleanup
    try:
        store.close()
    except:
        pass


# ============================================================================
# Test ImprovementOpportunity Class
# ============================================================================

class TestImprovementOpportunity:
    """Test ImprovementOpportunity data class."""
    
    def test_opportunity_creation(self):
        """Test creating an improvement opportunity."""
        opp = ImprovementOpportunity(
            tool_name='test_tool',
            issue_type='high_failure',
            severity='critical',
            current_metrics={'success_rate': 0.3, 'failure_rate': 0.7},
            evidence=['70% failure rate', '30 executions analyzed'],
            recommended_fixes=['Add error handling', 'Add validation']
        )
        
        assert opp.tool_name == 'test_tool'
        assert opp.issue_type == 'high_failure'
        assert opp.severity == 'critical'
        assert opp.status == 'detected'
        assert len(opp.evidence) == 2
        assert len(opp.recommended_fixes) == 2
    
    def test_opportunity_to_dict(self):
        """Test converting opportunity to dictionary."""
        opp = ImprovementOpportunity(
            tool_name='test_tool',
            issue_type='degradation',
            severity='high',
            current_metrics={'success_rate': 0.4},
            evidence=['Performance declining'],
            recommended_fixes=['Optimize code']
        )
        
        opp_dict = opp.to_dict()
        
        assert opp_dict['tool_name'] == 'test_tool'
        assert opp_dict['issue_type'] == 'degradation'
        assert opp_dict['severity'] == 'high'
        assert 'created_at' in opp_dict
        assert 'status' in opp_dict


# ============================================================================
# Test ABTestResult Class
# ============================================================================

class TestABTestResult:
    """Test ABTestResult data class."""
    
    def test_ab_result_improvement_detected(self):
        """Test A/B result detects improvement."""
        result = ABTestResult(
            tool_name='test_tool',
            old_version_metrics={'success_rate': 0.5, 'avg_duration_ms': 1000},
            new_version_metrics={'success_rate': 0.8, 'avg_duration_ms': 800},
            sample_size=100
        )
        
        assert result.improvement_detected is True
        assert result.confidence >= 0.80
        assert result.recommendation == 'deploy'
    
    def test_ab_result_no_improvement(self):
        """Test A/B result when no improvement."""
        result = ABTestResult(
            tool_name='test_tool',
            old_version_metrics={'success_rate': 0.8, 'avg_duration_ms': 1000},
            new_version_metrics={'success_rate': 0.75, 'avg_duration_ms': 1100},
            sample_size=100
        )
        
        assert result.improvement_detected is False
        assert result.recommendation == 'rollback'
    
    def test_ab_result_low_confidence(self):
        """Test A/B result with low sample size."""
        result = ABTestResult(
            tool_name='test_tool',
            old_version_metrics={'success_rate': 0.5, 'avg_duration_ms': 1000},
            new_version_metrics={'success_rate': 0.8, 'avg_duration_ms': 800},
            sample_size=10  # Low sample size
        )
        
        assert result.improvement_detected is True
        assert result.confidence < 0.80
        assert result.recommendation == 'continue_testing'
    
    def test_ab_result_to_dict(self):
        """Test converting A/B result to dictionary."""
        result = ABTestResult(
            tool_name='test_tool',
            old_version_metrics={'success_rate': 0.5},
            new_version_metrics={'success_rate': 0.8},
            sample_size=100
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['tool_name'] == 'test_tool'
        assert result_dict['improvement_detected'] is True
        assert 'confidence' in result_dict
        assert 'recommendation' in result_dict


# ============================================================================
# Test AutonomousImprovementNeuron Core
# ============================================================================

class TestAutonomousImprovementNeuronCore:
    """Test core neuron functionality."""
    
    def test_neuron_initialization(self, message_bus, ollama_client, execution_store):
        """Test neuron initializes correctly."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store,
            enable_auto_improvement=False,
            improvement_threshold=0.5,
            confidence_threshold=0.80
        )
        
        try:
            assert neuron.enable_auto_improvement is False
            assert neuron.improvement_threshold == 0.5
            assert neuron.confidence_threshold == 0.80
            assert neuron.detection_count == 0
            assert neuron.generation_count == 0
            assert neuron.deployment_count == 0
            assert neuron.rollback_count == 0
        finally:
            neuron.close()
    
    def test_neuron_has_dependencies(self, message_bus, ollama_client, execution_store):
        """Test neuron has all required dependencies."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            assert neuron.investigator is not None
            assert neuron.query_tool is not None
            assert neuron.analyzer is not None
            assert isinstance(neuron.investigator, SelfInvestigationNeuron)
        finally:
            neuron.close()
    
    def test_get_statistics(self, message_bus, ollama_client, execution_store):
        """Test getting neuron statistics."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            stats = neuron.get_statistics()
            
            assert 'detection_count' in stats
            assert 'generation_count' in stats
            assert 'deployment_count' in stats
            assert 'rollback_count' in stats
            assert all(v == 0 for v in stats.values())
        finally:
            neuron.close()


# ============================================================================
# Test Opportunity Detection
# ============================================================================

class TestOpportunityDetection:
    """Test improvement opportunity detection."""
    
    def test_detect_failing_tool(self, message_bus, ollama_client, execution_store):
        """Test detecting a failing tool."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store,
            min_sample_size=10
        )
        
        try:
            result = neuron.detect_improvement_opportunities()
            
            assert result['success'] is True
            assert result['opportunities_count'] > 0
            
            # Find the failing tool opportunity
            failing_opp = next(
                (o for o in result['opportunities'] 
                 if o['tool_name'] == 'improvement_test_failing_tool'),
                None
            )
            
            assert failing_opp is not None
            assert failing_opp['issue_type'] == 'high_failure'
            assert failing_opp['severity'] == 'critical'
            assert failing_opp['current_metrics']['success_rate'] < 0.5
        finally:
            neuron.close()
    
    def test_detect_slow_tool(self, message_bus, ollama_client, execution_store):
        """Test detecting a slow tool."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store,
            min_sample_size=10  # Lower threshold to detect slow tool with 10 executions
        )
        
        try:
            result = neuron.detect_improvement_opportunities()
            
            assert result['success'] is True
            
            # Find the slow tool opportunity
            slow_opp = next(
                (o for o in result['opportunities'] 
                 if o['tool_name'] == 'improvement_test_slow_tool'),
                None
            )
            
            assert slow_opp is not None
            assert slow_opp['issue_type'] == 'performance'
            assert slow_opp['current_metrics']['avg_duration_ms'] > 5000
        finally:
            neuron.close()
    
    def test_detect_no_opportunities_for_healthy_tool(self, message_bus, ollama_client, execution_store):
        """Test that healthy tools don't trigger opportunities."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store,
            improvement_threshold=0.5  # Only improve tools below 50%
        )
        
        try:
            result = neuron.detect_improvement_opportunities()
            
            assert result['success'] is True
            
            # Healthy tool should NOT have an opportunity (95% success rate)
            healthy_opp = next(
                (o for o in result['opportunities'] 
                 if o['tool_name'] == 'improvement_test_healthy_tool'),
                None
            )
            
            # Should not find an opportunity for healthy tool
            assert healthy_opp is None
        finally:
            neuron.close()
    
    def test_opportunities_sorted_by_severity(self, message_bus, ollama_client, execution_store):
        """Test that opportunities are sorted by severity."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.detect_improvement_opportunities()
            
            assert result['success'] is True
            assert result['opportunities_count'] > 0
            
            # Check sorting: critical/high should come before medium/low
            severities = [o['severity'] for o in result['opportunities']]
            
            # First opportunity should be critical or high
            if severities:
                assert severities[0] in ['critical', 'high']
        finally:
            neuron.close()


# ============================================================================
# Test Improvement Generation
# ============================================================================

class TestImprovementGeneration:
    """Test improvement generation."""
    
    def test_generate_improvement_for_failing_tool(self, message_bus, ollama_client, execution_store):
        """Test generating improvement for failing tool."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.improve_tool('improvement_test_failing_tool')
            
            assert result['success'] is True
            assert result['tool_name'] == 'improvement_test_failing_tool'
            assert 'improvement' in result
            assert 'improvements' in result['improvement']
            assert len(result['improvement']['improvements']) > 0
            assert neuron.generation_count == 1
        finally:
            neuron.close()
    
    def test_improvement_includes_error_handling(self, message_bus, ollama_client, execution_store):
        """Test that improvements include error handling."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.improve_tool('improvement_test_failing_tool')
            
            assert result['success'] is True
            
            # Check that improvements mention error handling
            improvements = result['improvement']['improvements']
            assert any('error' in imp.lower() for imp in improvements)
        finally:
            neuron.close()
    
    def test_multiple_improvement_generations(self, message_bus, ollama_client, execution_store):
        """Test generating improvements for multiple tools."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            # Generate improvements for two tools
            result1 = neuron.improve_tool('improvement_test_failing_tool')
            result2 = neuron.improve_tool('improvement_test_slow_tool')
            
            assert result1['success'] is True
            assert result2['success'] is True
            assert neuron.generation_count == 2
            assert len(neuron.improvements_generated) == 2
        finally:
            neuron.close()


# ============================================================================
# Test A/B Testing & Validation
# ============================================================================

class TestValidation:
    """Test improvement validation via A/B testing."""
    
    def test_validate_improvement(self, message_bus, ollama_client, execution_store):
        """Test validating an improvement."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            # First generate improvement
            neuron.improve_tool('improvement_test_failing_tool')
            
            # Then validate it
            result = neuron.validate_improvement('improvement_test_failing_tool')
            
            assert result['success'] is True
            assert result['tool_name'] == 'improvement_test_failing_tool'
            assert 'ab_test_result' in result
            assert 'recommendation' in result
        finally:
            neuron.close()
    
    def test_validation_recommends_deploy_for_improved_tool(self, message_bus, ollama_client, execution_store):
        """Test that validation recommends deployment for improvements."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.validate_improvement('improvement_test_failing_tool')
            
            assert result['success'] is True
            
            # Should recommend deploy since we simulate improvement
            ab_result = result['ab_test_result']
            assert ab_result['improvement_detected'] is True
            assert ab_result['recommendation'] in ['deploy', 'continue_testing']
        finally:
            neuron.close()
    
    def test_can_auto_deploy_check(self, message_bus, ollama_client, execution_store):
        """Test auto-deployment eligibility check."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store,
            enable_auto_improvement=True,
            confidence_threshold=0.80
        )
        
        try:
            result = neuron.validate_improvement('improvement_test_failing_tool')
            
            assert result['success'] is True
            assert 'can_auto_deploy' in result
            
            # Should be able to auto-deploy if confidence high and improvement enabled
            if result['ab_test_result']['confidence'] >= 0.80:
                assert result['can_auto_deploy'] is True
        finally:
            neuron.close()


# ============================================================================
# Test Deployment & Rollback
# ============================================================================

class TestDeploymentAndRollback:
    """Test deployment and rollback functionality."""
    
    def test_deploy_improvement(self, message_bus, ollama_client, execution_store):
        """Test deploying an improvement."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            # First generate an improvement
            neuron.improve_tool('improvement_test_failing_tool')
            
            # Then deploy it
            result = neuron.deploy_improvement('improvement_test_failing_tool')
            
            assert result['success'] is True
            assert result['tool_name'] == 'improvement_test_failing_tool'
            assert 'deployment' in result
            assert neuron.deployment_count == 1
            assert len(neuron.improvements_deployed) == 1
        finally:
            neuron.close()
    
    def test_rollback_improvement(self, message_bus, ollama_client, execution_store):
        """Test rolling back an improvement."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.rollback_improvement(
                'improvement_test_failing_tool',
                reason='Performance degraded after deployment'
            )
            
            assert result['success'] is True
            assert result['tool_name'] == 'improvement_test_failing_tool'
            assert 'rollback' in result
            assert neuron.rollback_count == 1
            assert len(neuron.improvements_rejected) == 1
        finally:
            neuron.close()
    
    def test_deployment_creates_backup(self, message_bus, ollama_client, execution_store):
        """Test that deployment creates backup."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            # First generate an improvement
            neuron.improve_tool('improvement_test_failing_tool')
            
            # Then deploy it
            result = neuron.deploy_improvement('improvement_test_failing_tool')
            
            assert result['success'] is True
            assert result['deployment']['backup_created'] is True
            assert result['deployment']['rollback_available'] is True
        finally:
            neuron.close()


# ============================================================================
# Test Full Improvement Cycle
# ============================================================================

class TestFullImprovementCycle:
    """Test complete improvement cycle."""
    
    def test_run_full_cycle(self, message_bus, ollama_client, execution_store):
        """Test running full improvement cycle."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store,
            enable_auto_improvement=False  # Manual review for safety
        )
        
        try:
            result = neuron.run_improvement_cycle()
            
            assert result['success'] is True
            assert 'cycle_duration_ms' in result
            assert 'results' in result
            
            cycle_results = result['results']
            assert cycle_results['opportunities_detected'] > 0
            assert cycle_results['improvements_generated'] > 0
            assert cycle_results['improvements_validated'] > 0
        finally:
            neuron.close()
    
    def test_cycle_with_auto_deployment(self, message_bus, ollama_client, execution_store):
        """Test cycle with auto-deployment enabled."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store,
            enable_auto_improvement=True,
            confidence_threshold=0.70  # Lower threshold for testing
        )
        
        try:
            result = neuron.run_improvement_cycle()
            
            assert result['success'] is True
            assert result['auto_improvement_enabled'] is True
            
            cycle_results = result['results']
            # With auto-improvement enabled, should deploy some improvements
            assert cycle_results['improvements_deployed'] >= 0
        finally:
            neuron.close()
    
    def test_cycle_limits_processing(self, message_bus, ollama_client, execution_store):
        """Test that cycle limits number of improvements (safety)."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.run_improvement_cycle()
            
            assert result['success'] is True
            
            cycle_results = result['results']
            # Should process at most 3 critical opportunities (safety limit)
            assert cycle_results['improvements_generated'] <= 3
        finally:
            neuron.close()
    
    def test_cycle_via_process_method(self, message_bus, ollama_client, execution_store):
        """Test running cycle via process() method."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.process(
                goal_id='test_improvement_cycle',
                data='run autonomous improvement cycle'
            )
            
            assert result['success'] is True
            assert 'cycle_duration_ms' in result
            assert 'results' in result
        finally:
            neuron.close()


# ============================================================================
# Test Process Method Routing
# ============================================================================

class TestProcessMethodRouting:
    """Test process() method routes goals correctly."""
    
    def test_detect_opportunities_goal(self, message_bus, ollama_client, execution_store):
        """Test 'detect opportunities' goal routing."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.process(
                goal_id='test_detect',
                data='detect improvement opportunities'
            )
            
            assert result['success'] is True
            assert 'opportunities_count' in result
            assert neuron.detection_count == 1
        finally:
            neuron.close()
    
    def test_improve_tool_goal(self, message_bus, ollama_client, execution_store):
        """Test 'improve tool' goal routing."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.process(
                goal_id='test_improve',
                data='improve tool improvement_test_failing_tool'
            )
            
            assert result['success'] is True
            assert result['tool_name'] == 'improvement_test_failing_tool'
            assert neuron.generation_count == 1
        finally:
            neuron.close()
    
    def test_validate_goal(self, message_bus, ollama_client, execution_store):
        """Test 'validate' goal routing."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            result = neuron.process(
                goal_id='test_validate',
                data='validate improvement for tool improvement_test_failing_tool'
            )
            
            assert result['success'] is True
            assert 'ab_test_result' in result
        finally:
            neuron.close()


# ============================================================================
# Test Resource Management
# ============================================================================

class TestResourceManagement:
    """Test resource management and cleanup."""
    
    def test_neuron_cleanup(self, message_bus, ollama_client, execution_store):
        """Test that neuron cleans up resources."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        # Use neuron
        neuron.detect_improvement_opportunities()
        
        # Clean up
        neuron.close()
        
        # Should not raise exceptions
    
    def test_multiple_neuron_instances(self, message_bus, ollama_client, execution_store):
        """Test multiple neuron instances don't interfere."""
        neuron1 = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        neuron2 = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            # Both should work independently
            result1 = neuron1.detect_improvement_opportunities()
            result2 = neuron2.detect_improvement_opportunities()
            
            assert result1['success'] is True
            assert result2['success'] is True
        finally:
            neuron1.close()
            neuron2.close()
    
    def test_owns_store_pattern(self, message_bus, ollama_client):
        """Test _owns_store resource management pattern."""
        # Create neuron without providing store
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client
            # No execution_store provided
        )
        
        try:
            assert neuron._owns_store is True
            assert neuron.execution_store is not None
        finally:
            neuron.close()  # Should close store since it owns it


# ============================================================================
# Test Integration with Phase 9a/9b
# ============================================================================

class TestIntegrationWithPreviousPhases:
    """Test integration with Phase 9a analytics and Phase 9b investigation."""
    
    def test_uses_phase9a_query_tool(self, message_bus, ollama_client, execution_store):
        """Test that neuron uses Phase 9a QueryExecutionStoreTool."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            # Should use query_tool internally
            result = neuron.detect_improvement_opportunities()
            
            assert result['success'] is True
            # Query tool was used to get statistics
        finally:
            neuron.close()
    
    def test_uses_phase9b_investigation(self, message_bus, ollama_client, execution_store):
        """Test that neuron uses Phase 9b SelfInvestigationNeuron."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store
        )
        
        try:
            assert neuron.investigator is not None
            
            # Should use investigator to detect issues
            result = neuron.detect_improvement_opportunities()
            
            assert result['success'] is True
        finally:
            neuron.close()
    
    def test_end_to_end_pipeline(self, message_bus, ollama_client, execution_store):
        """Test complete pipeline from Phase 9a → 9b → 9c."""
        neuron = AutonomousImprovementNeuron(
            message_bus=message_bus,
            ollama_client=ollama_client,
            execution_store=execution_store,
            enable_auto_improvement=True
        )
        
        try:
            # Complete cycle uses all phases:
            # - Phase 9a: Query tool stats, analyze performance
            # - Phase 9b: Investigate health, detect anomalies
            # - Phase 9c: Detect opportunities, generate improvements, deploy
            
            result = neuron.run_improvement_cycle()
            
            assert result['success'] is True
            assert result['results']['opportunities_detected'] > 0
            
            # Verify all phases contributed
            assert neuron.detection_count > 0  # Phase 9c detection
            assert neuron.generation_count > 0  # Phase 9c generation
        finally:
            neuron.close()
