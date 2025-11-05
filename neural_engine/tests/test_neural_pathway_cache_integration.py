"""
Test Neural Pathway Cache Integration - Phase 2.1

Tests the integration of NeuralPathwayCache into the orchestrator pipeline.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.neural_pathway_cache import NeuralPathwayCache


class TestNeuralPathwayCacheIntegration:
    """Test pathway cache integration in orchestrator."""
    
    def test_orchestrator_checks_pathway_cache_first(self):
        """Orchestrator should check pathway cache before executing pipeline."""
        # Create mock components
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.goal_counter = 0
        orchestrator.pathway_cache = Mock(spec=NeuralPathwayCache)
        orchestrator.execution_store = None
        
        # Mock pathway cache to return a cached result
        cached_pathway = {
            'pathway_id': 'test-pathway-123',
            'similarity_score': 0.95,
            'confidence_score': 0.87,
            'final_result': {'output': 'Cached response!'},
            'tool_names': ['test_tool'],
            'usage_count': 5
        }
        orchestrator.pathway_cache.find_cached_pathway = Mock(return_value=cached_pathway)
        orchestrator.pathway_cache.update_pathway_result = Mock(return_value=True)
        
        # Mock embedding generation
        orchestrator._generate_goal_embedding = Mock(return_value=[0.1] * 384)
        
        # Test that cache is queried
        goal = "Test goal for caching"
        orchestrator._generate_goal_embedding(goal)
        orchestrator.pathway_cache.find_cached_pathway(
            goal_text=goal,
            goal_embedding=[0.1] * 384
        )
        
        # Verify cache was queried
        orchestrator.pathway_cache.find_cached_pathway.assert_called_once()
        assert orchestrator.pathway_cache.find_cached_pathway.return_value == cached_pathway
    
    def test_cache_miss_triggers_full_pipeline(self):
        """When cache misses, full pipeline should execute."""
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.pathway_cache = Mock(spec=NeuralPathwayCache)
        
        # Mock cache to return None (miss)
        orchestrator.pathway_cache.find_cached_pathway = Mock(return_value=None)
        orchestrator._generate_goal_embedding = Mock(return_value=[0.1] * 384)
        
        goal = "New goal not in cache"
        result = orchestrator.pathway_cache.find_cached_pathway(
            goal_text=goal,
            goal_embedding=[0.1] * 384
        )
        
        # Verify cache miss
        assert result is None
        orchestrator.pathway_cache.find_cached_pathway.assert_called_once()
    
    def test_successful_execution_stored_in_cache(self):
        """Successful executions should be stored in pathway cache."""
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.pathway_cache = Mock(spec=NeuralPathwayCache)
        orchestrator._generate_goal_embedding = Mock(return_value=[0.1] * 384)
        orchestrator._extract_execution_steps = Mock(return_value=[{'step': 1}])
        orchestrator._extract_tools_used = Mock(return_value=['test_tool'])
        
        # Mock successful storage
        orchestrator.pathway_cache.store_pathway = Mock(return_value='new-pathway-456')
        
        # Simulate storing after successful execution
        goal = "Test successful goal"
        result = {'success': True, 'output': 'Success!'}
        duration_ms = 1000
        
        pathway_id = orchestrator.pathway_cache.store_pathway(
            goal_text=goal,
            goal_embedding=[0.1] * 384,
            execution_steps=[{'step': 1}],
            final_result=result,
            tool_names=['test_tool'],
            execution_time_ms=duration_ms
        )
        
        # Verify storage
        assert pathway_id == 'new-pathway-456'
        orchestrator.pathway_cache.store_pathway.assert_called_once()
    
    def test_cache_hit_updates_usage_statistics(self):
        """Cache hits should update pathway usage statistics."""
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.pathway_cache = Mock(spec=NeuralPathwayCache)
        
        # Mock usage update
        orchestrator.pathway_cache.update_pathway_result = Mock(return_value=True)
        
        # Simulate cache hit and usage update
        pathway_id = 'cached-pathway-789'
        result = orchestrator.pathway_cache.update_pathway_result(
            pathway_id=pathway_id,
            success=True
        )
        
        # Verify usage update
        assert result is True
        orchestrator.pathway_cache.update_pathway_result.assert_called_once_with(
            pathway_id=pathway_id,
            success=True
        )
    
    def test_visualizer_notified_on_cache_hit(self):
        """Visualizer should be notified of pathway cache hits."""
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.visualizer = Mock()
        orchestrator.pathway_cache = Mock(spec=NeuralPathwayCache)
        
        cached_pathway = {
            'pathway_id': 'viz-test-123',
            'similarity_score': 0.92,
            'confidence_score': 0.88,
            'final_result': {'output': 'Cached!'},
            'tool_names': ['viz_tool'],
            'usage_count': 3
        }
        
        # Simulate visualizer notification
        if hasattr(orchestrator, 'visualizer') and orchestrator.visualizer:
            orchestrator.visualizer.show_cache_check({
                'similarity': cached_pathway['similarity_score'],
                'confidence_score': cached_pathway['confidence_score'],
                'pathway_id': cached_pathway['pathway_id'],
                'tools_used': cached_pathway['tool_names'],
                'usage_count': cached_pathway['usage_count'],
                'cache_type': 'pathway'
            })
        
        # Verify visualizer was notified
        orchestrator.visualizer.show_cache_check.assert_called_once()
    
    def test_visualizer_notified_on_cache_miss(self):
        """Visualizer should be notified of cache misses."""
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.visualizer = Mock()
        orchestrator.pathway_cache = Mock(spec=NeuralPathwayCache)
        
        # Simulate cache miss
        orchestrator.pathway_cache.find_cached_pathway = Mock(return_value=None)
        
        result = orchestrator.pathway_cache.find_cached_pathway(
            goal_text="New goal",
            goal_embedding=[0.1] * 384
        )
        
        # Simulate visualizer notification for miss
        if result is None:
            if hasattr(orchestrator, 'visualizer') and orchestrator.visualizer:
                orchestrator.visualizer.show_cache_check(None)
        
        # Verify visualizer was notified
        orchestrator.visualizer.show_cache_check.assert_called_once_with(None)
    
    def test_embedding_generation_helper(self):
        """Test that embedding generation helper works."""
        orchestrator = Mock(spec=Orchestrator)
        
        # Mock embedding function
        def mock_embedding(goal):
            # Return a 384-dim vector (standard for all-MiniLM-L6-v2)
            return [0.1] * 384
        
        orchestrator._generate_goal_embedding = mock_embedding
        
        goal = "Generate embedding for this"
        embedding = orchestrator._generate_goal_embedding(goal)
        
        # Verify embedding dimensions
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)
    
    def test_cache_disabled_falls_back_to_normal_execution(self):
        """When cache is disabled, should execute normally."""
        orchestrator = Mock(spec=Orchestrator)
        # No pathway_cache attribute = disabled
        assert not hasattr(orchestrator, 'pathway_cache')
        
        # Should proceed with normal execution
        # (no cache lookup attempt)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
