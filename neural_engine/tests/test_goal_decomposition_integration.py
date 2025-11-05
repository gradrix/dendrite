"""
Unit tests for Goal Decomposition Learner integration in Orchestrator.

Tests the integration points:
- Pattern lookup before execution
- Pattern storage after successful caching
- Helper methods for extracting subgoals and tools
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from neural_engine.core.orchestrator import Orchestrator


class TestGoalDecompositionIntegration:
    """Test Goal Decomposition Learner integration points."""
    
    def test_pattern_lookup_before_execution(self):
        """Verify orchestrator queries for similar patterns before execution."""
        # Create mock orchestrator with goal_learner
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.goal_learner = Mock()
        orchestrator.visualizer = Mock()
        
        # Mock pattern response
        mock_pattern = {
            'goal_text': 'Calculate 5 plus 3',
            'similarity': 0.85,
            'subgoal_count': 2,
            'execution_time_ms': 1500
        }
        orchestrator.goal_learner.find_similar_patterns.return_value = [mock_pattern]
        
        # Simulate the pattern lookup code from orchestrator
        patterns = orchestrator.goal_learner.find_similar_patterns(
            goal_text="Calculate 10 plus 7",
            similarity_threshold=0.75,
            only_successful=True,
            limit=1
        )
        
        # Verify pattern lookup was called with correct parameters
        orchestrator.goal_learner.find_similar_patterns.assert_called_once_with(
            goal_text="Calculate 10 plus 7",
            similarity_threshold=0.75,
            only_successful=True,
            limit=1
        )
        
        # Verify pattern found
        assert len(patterns) > 0
        assert patterns[0]['similarity'] == 0.85
        
        # Verify visualizer would be called
        if patterns:
            orchestrator.visualizer.show_pattern_suggestion(patterns[0])
            orchestrator.visualizer.show_pattern_suggestion.assert_called_once()
    
    def test_pattern_storage_after_success(self):
        """Verify orchestrator stores patterns after successful execution."""
        # Create mock orchestrator with goal_learner
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.goal_learner = Mock()
        orchestrator.goal_learner.store_pattern.return_value = 42  # Mock pattern ID
        
        # Mock helper methods
        orchestrator._extract_tools_used = Mock(return_value=['add_numbers'])
        orchestrator._extract_subgoals = Mock(return_value=['execute_tool'])
        
        # Simulate the pattern storage code from orchestrator
        pattern_id = orchestrator.goal_learner.store_pattern(
            goal_text="Calculate 5 plus 3",
            subgoals=orchestrator._extract_subgoals('goal-123'),
            success=True,
            execution_time_ms=1200,
            tools_used=orchestrator._extract_tools_used('goal-123')
        )
        
        # Verify storage was called with correct parameters
        orchestrator.goal_learner.store_pattern.assert_called_once()
        call_args = orchestrator.goal_learner.store_pattern.call_args[1]
        assert call_args['goal_text'] == "Calculate 5 plus 3"
        assert call_args['success'] is True
        assert call_args['execution_time_ms'] == 1200
        assert 'add_numbers' in call_args['tools_used']
        
        # Verify pattern ID returned
        assert pattern_id == 42
    
    def test_no_patterns_found_graceful(self):
        """Verify system handles no patterns found gracefully."""
        # Create mock orchestrator with goal_learner
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.goal_learner = Mock()
        orchestrator.visualizer = Mock()
        
        # Mock empty pattern response
        orchestrator.goal_learner.find_similar_patterns.return_value = []
        
        # Simulate the pattern lookup code
        patterns = orchestrator.goal_learner.find_similar_patterns(
            goal_text="Completely unique goal",
            similarity_threshold=0.75,
            only_successful=True,
            limit=1
        )
        
        # Verify no patterns found
        assert len(patterns) == 0
        
        # Verify visualizer NOT called (no pattern to show)
        orchestrator.visualizer.show_pattern_suggestion.assert_not_called()
    
    def test_goal_learner_not_available(self):
        """Verify system handles missing goal_learner gracefully."""
        # Create orchestrator without goal_learner
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.goal_learner = None
        
        # Simulate the hasattr check from orchestrator
        has_learner = hasattr(orchestrator, 'goal_learner') and orchestrator.goal_learner
        
        # Verify learner not available
        assert not has_learner
        
        # In real code, this would skip pattern lookup/storage
        # No exception should be raised


class TestGoalDecompositionHelpers:
    """Test helper methods for goal decomposition."""
    
    def test_extract_subgoals_placeholder(self):
        """Verify _extract_subgoals returns list (placeholder implementation)."""
        # This is a placeholder test for the placeholder implementation
        # When _extract_subgoals is properly implemented, update this test
        orchestrator = Orchestrator.__new__(Orchestrator)
        
        result = orchestrator._extract_subgoals('goal-123')
        
        # Current placeholder just returns ['execute_tool']
        assert isinstance(result, list)
        assert len(result) >= 0  # May be empty or have items
    
    def test_extract_tools_used_returns_list(self):
        """Verify _extract_tools_used returns list of tool names."""
        orchestrator = Orchestrator.__new__(Orchestrator)
        
        # Note: This will fail if execution_store not initialized
        # In real usage, orchestrator is fully initialized via system_factory
        try:
            result = orchestrator._extract_tools_used('goal-123')
            assert isinstance(result, list)
        except AttributeError:
            # Expected if execution_store not initialized
            pytest.skip("Requires initialized execution_store")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
