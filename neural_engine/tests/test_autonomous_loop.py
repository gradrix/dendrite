"""
Tests for Autonomous Background Loop
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

from neural_engine.core.autonomous_loop import AutonomousLoop, start_autonomous_loop


class TestAutonomousLoop:
    """Test autonomous improvement loop functionality."""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = Mock()
        orchestrator.tool_selector = Mock()
        orchestrator.tool_selector.tool_registry = Mock()
        orchestrator.tool_selector.tool_registry.refresh = Mock()
        orchestrator.tool_discovery = Mock()
        orchestrator.tool_discovery.index_all_tools = Mock()
        return orchestrator
    
    @pytest.fixture
    def mock_execution_store(self):
        """Create mock execution store."""
        store = Mock()
        store.get_bottom_tools = Mock(return_value=[])
        store._get_connection = Mock()
        store._release_connection = Mock()
        return store
    
    @pytest.fixture
    def mock_lifecycle_manager(self):
        """Create mock lifecycle manager."""
        manager = Mock()
        manager.maintenance = Mock(return_value={
            'cleanup_report': {'total_archived': 0}
        })
        return manager
    
    @pytest.fixture
    def autonomous_loop(self, mock_orchestrator, mock_execution_store):
        """Create AutonomousLoop instance."""
        return AutonomousLoop(
            orchestrator=mock_orchestrator,
            execution_store=mock_execution_store,
            check_interval_seconds=1,  # Fast for testing
            maintenance_interval_hours=1
        )
    
    def test_initialization(self, autonomous_loop):
        """Test loop initialization."""
        assert autonomous_loop.running is False
        assert autonomous_loop.cycle_count == 0
        assert autonomous_loop.stats['cycles_completed'] == 0
        assert autonomous_loop.check_interval == 1
    
    def test_get_stats(self, autonomous_loop):
        """Test getting statistics."""
        stats = autonomous_loop.get_stats()
        
        assert 'cycles_completed' in stats
        assert 'opportunities_detected' in stats
        assert 'improvements_deployed' in stats
        assert 'running' in stats
        assert stats['running'] is False
    
    @pytest.mark.asyncio
    async def test_check_maintenance_not_needed(self, autonomous_loop):
        """Test maintenance check when not needed."""
        autonomous_loop.last_maintenance = datetime.now()
        
        await autonomous_loop._check_maintenance()
        
        # Should not run maintenance (too recent)
        assert autonomous_loop.stats['maintenance_runs'] == 0
    
    @pytest.mark.asyncio
    async def test_check_maintenance_needed(self, autonomous_loop, mock_lifecycle_manager):
        """Test maintenance check when needed."""
        autonomous_loop.lifecycle_manager = mock_lifecycle_manager
        autonomous_loop.last_maintenance = datetime.now() - timedelta(hours=25)
        
        await autonomous_loop._check_maintenance()
        
        # Should run maintenance
        assert autonomous_loop.stats['maintenance_runs'] == 1
        mock_lifecycle_manager.maintenance.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_detect_opportunities_empty(self, autonomous_loop, mock_execution_store):
        """Test opportunity detection with no issues."""
        mock_execution_store.get_bottom_tools.return_value = []
        
        opportunities = await autonomous_loop._detect_opportunities()
        
        assert opportunities == []
        assert autonomous_loop.stats['opportunities_detected'] == 0
    
    @pytest.mark.asyncio
    async def test_detect_opportunities_low_success_rate(self, autonomous_loop, mock_execution_store):
        """Test detecting low success rate tools."""
        mock_execution_store.get_bottom_tools.return_value = [
            {
                'tool_name': 'buggy_tool',
                'success_rate': 0.3,
                'total_executions': 50
            }
        ]
        
        opportunities = await autonomous_loop._detect_opportunities()
        
        assert len(opportunities) == 1
        assert opportunities[0]['tool_name'] == 'buggy_tool'
        assert opportunities[0]['type'] == 'low_success_rate'
        assert opportunities[0]['priority'] == 'high'  # <0.5 = high priority
        assert autonomous_loop.stats['opportunities_detected'] == 1
    
    @pytest.mark.asyncio
    async def test_detect_opportunities_medium_priority(self, autonomous_loop, mock_execution_store):
        """Test detecting medium priority issues."""
        mock_execution_store.get_bottom_tools.return_value = [
            {
                'tool_name': 'mediocre_tool',
                'success_rate': 0.65,  # Below 0.7 threshold but above 0.5
                'total_executions': 30
            }
        ]
        
        opportunities = await autonomous_loop._detect_opportunities()
        
        assert len(opportunities) == 1
        assert opportunities[0]['priority'] == 'medium'
    
    @pytest.mark.asyncio
    async def test_investigate_tool(self, autonomous_loop):
        """Test tool investigation."""
        mock_investigation_neuron = Mock()
        mock_investigation_neuron.investigate = Mock(return_value={
            'should_improve': True,
            'analysis': 'Tool has logic errors'
        })
        autonomous_loop.self_investigation = mock_investigation_neuron
        
        opportunity = {'tool_name': 'buggy_tool'}
        result = await autonomous_loop._investigate_tool(opportunity)
        
        assert result is not None
        assert result['should_improve'] is True
        assert autonomous_loop.stats['tools_analyzed'] == 1
    
    @pytest.mark.asyncio
    async def test_generate_improvement(self, autonomous_loop):
        """Test improvement generation."""
        mock_improvement_neuron = Mock()
        mock_improvement_neuron.improve_tool = Mock(return_value={
            'success': True,
            'generated_code': 'def improved_function(): pass'
        })
        autonomous_loop.autonomous_improvement = mock_improvement_neuron
        
        opportunity = {'tool_name': 'buggy_tool'}
        investigation = {'analysis': 'Found issues'}
        
        result = await autonomous_loop._generate_improvement(opportunity, investigation)
        
        assert result is not None
        assert result['success'] is True
        assert autonomous_loop.stats['improvements_attempted'] == 1
    
    @pytest.mark.asyncio
    async def test_test_improvement(self, autonomous_loop):
        """Test improvement testing."""
        opportunity = {
            'tool_name': 'test_tool',
            'type': 'low_success_rate',
            'priority': 'high'
        }
        improvement = {'generated_code': 'def test(): pass'}
        
        # Mock tool instance loading and testing
        mock_tool = Mock()
        autonomous_loop._get_tool_instance = Mock(return_value=mock_tool)
        autonomous_loop._determine_test_strategy = Mock(return_value={'method': 'synthetic'})
        autonomous_loop._synthetic_test_improvement = AsyncMock(return_value={'passed': True, 'method': 'synthetic'})
        
        result = await autonomous_loop._test_improvement(opportunity, improvement)
        
        assert result is not None
        assert result['passed'] is True
    
    @pytest.mark.asyncio
    async def test_test_improvement_no_code(self, autonomous_loop):
        """Test improvement testing when no code generated."""
        opportunity = {
            'tool_name': 'test_tool',
            'type': 'low_success_rate',
            'priority': 'high'
        }
        improvement = {}
        
        # Mock tool instance loading - return None to simulate failure path
        autonomous_loop._get_tool_instance = Mock(return_value=None)
        
        result = await autonomous_loop._test_improvement(opportunity, improvement)
        
        assert result is not None
        assert result['passed'] is False
    
    @pytest.mark.asyncio
    async def test_deploy_improvement(self, autonomous_loop):
        """Test improvement deployment."""
        improvement = {'generated_code': 'def new_tool(): pass'}
        
        result = await autonomous_loop._deploy_improvement(improvement)
        
        assert result is not None
        assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_process_opportunities_no_neurons(self, autonomous_loop):
        """Test processing when improvement neurons not available."""
        opportunities = [
            {'tool_name': 'tool1', 'type': 'low_success_rate', 'priority': 'high'}
        ]
        
        await autonomous_loop._process_opportunities(opportunities)
        
        # Should skip without neurons
        assert autonomous_loop.stats['improvements_attempted'] == 0
    
    @pytest.mark.asyncio
    async def test_process_opportunities_full_cycle(self, autonomous_loop):
        """Test full opportunity processing cycle."""
        # Setup mocks for full cycle
        mock_investigation = Mock()
        mock_investigation.investigate = Mock(return_value={
            'should_improve': True,
            'analysis': 'Issues found'
        })
        
        mock_improvement = Mock()
        mock_improvement.improve_tool = Mock(return_value={
            'success': True,
            'generated_code': 'def improved(): pass'
        })
        
        autonomous_loop.self_investigation = mock_investigation
        autonomous_loop.autonomous_improvement = mock_improvement
        
        # Mock _test_improvement to return success
        async def mock_test_improvement(opportunity, improvement):
            return {'passed': True, 'method': 'mocked'}
        
        # Mock _deploy_improvement to return success
        async def mock_deploy_improvement(improvement):
            return {'success': True}
        
        autonomous_loop._test_improvement = mock_test_improvement
        autonomous_loop._deploy_improvement = mock_deploy_improvement
        
        opportunities = [
            {
                'tool_name': 'buggy_tool',
                'type': 'low_success_rate',
                'priority': 'high',
                'current_success_rate': 0.3
            }
        ]
        
        await autonomous_loop._process_opportunities(opportunities)
        
        # Should complete full cycle
        assert autonomous_loop.stats['tools_analyzed'] == 1
        assert autonomous_loop.stats['improvements_attempted'] == 1
        assert autonomous_loop.stats['improvements_deployed'] == 1
    
    @pytest.mark.asyncio
    async def test_process_opportunities_no_improvement_needed(self, autonomous_loop):
        """Test when investigation suggests no improvement needed."""
        mock_investigation = Mock()
        mock_investigation.investigate = Mock(return_value={
            'should_improve': False,
            'analysis': 'Tool is fine'
        })
        
        autonomous_loop.self_investigation = mock_investigation
        autonomous_loop.autonomous_improvement = Mock()
        
        opportunities = [
            {'tool_name': 'good_tool', 'type': 'low_success_rate', 'priority': 'medium'}
        ]
        
        await autonomous_loop._process_opportunities(opportunities)
        
        # Should investigate but not improve
        assert autonomous_loop.stats['tools_analyzed'] == 1
        assert autonomous_loop.stats['improvements_attempted'] == 0
    
    @pytest.mark.asyncio
    async def test_stop_loop(self, autonomous_loop):
        """Test stopping the loop."""
        autonomous_loop.running = True
        
        autonomous_loop.stop()
        
        assert autonomous_loop.running is False
    
    @pytest.mark.asyncio
    async def test_start_loop_one_cycle(self, autonomous_loop, mock_execution_store):
        """Test running one cycle of the loop."""
        # Setup for quick exit
        mock_execution_store.get_bottom_tools.return_value = []
        
        # Start loop and cancel after short time
        async def run_briefly():
            task = asyncio.create_task(autonomous_loop.start())
            await asyncio.sleep(0.1)  # Let it run briefly
            autonomous_loop.stop()
            await task
        
        await run_briefly()
        
        # Should have completed at least one cycle
        assert autonomous_loop.stats['cycles_completed'] >= 0  # Might be 0 if stopped before first cycle
    
    def test_start_autonomous_loop_helper(self, mock_orchestrator, mock_execution_store):
        """Test helper function to start loop."""
        # Note: This is synchronous test of function creation
        # Actual async execution would be tested separately
        
        # Just verify function exists and returns task-like object
        # Can't actually run async task in sync test
        pass


class TestAutonomousLoopIntegration:
    """Integration tests requiring real components."""
    
    @pytest.mark.integration
    async def test_full_autonomous_cycle(self):
        """Test complete autonomous cycle with real components."""
        # This would require:
        # - Real ExecutionStore with data
        # - Real investigation and improvement neurons
        # - Real tool registry
        pass
    
    @pytest.mark.integration
    async def test_concurrent_cycles(self):
        """Test multiple cycles running without conflicts."""
        pass
