"""
Tests for Phase 10a: Goal Decomposition Learning

Tests GoalDecompositionLearner's ability to:
- Store goal decomposition patterns
- Find similar patterns via embeddings
- Suggest decompositions for new goals
- Track pattern effectiveness
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from neural_engine.core.goal_decomposition_learner import GoalDecompositionLearner


class TestGoalDecompositionLearner(unittest.TestCase):
    """Test suite for goal decomposition learning"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock execution store
        self.mock_store = Mock()
        self.mock_conn = Mock()
        self.mock_cursor = Mock()
        
        # Setup mock connection pool
        self.mock_store.pool = Mock()
        self.mock_store.pool.getconn = Mock(return_value=self.mock_conn)
        self.mock_store.pool.putconn = Mock()
        
        # Setup cursor context manager
        self.mock_conn.cursor = Mock(return_value=self.mock_cursor)
        self.mock_cursor.__enter__ = Mock(return_value=self.mock_cursor)
        self.mock_cursor.__exit__ = Mock(return_value=False)
        self.mock_conn.commit = Mock()
        
        # Create learner with mocked Chroma
        with patch('chromadb.PersistentClient'):
            self.learner = GoalDecompositionLearner(
                execution_store=self.mock_store,
                chroma_path="/tmp/test_chroma"
            )
            
            # Mock the Chroma collection
            self.learner.collection = Mock()
    
    def test_store_pattern_success(self):
        """Test storing a successful pattern"""
        # Mock database insert
        self.mock_cursor.fetchone = Mock(return_value=(123,))
        
        pattern_id = self.learner.store_pattern(
            goal_text="Get my Strava activities",
            subgoals=["Select tool", "Execute get_activities", "Return results"],
            success=True,
            execution_time_ms=1500,
            tools_used=["strava_get_my_activities"],
            goal_type="data_retrieval"
        )
        
        # Verify pattern was stored
        self.assertEqual(pattern_id, 123)
        self.mock_cursor.execute.assert_called_once()
        self.mock_conn.commit.assert_called_once()
        
        # Verify embedding was stored in Chroma
        self.learner.collection.add.assert_called_once()
    
    def test_store_pattern_failure(self):
        """Test storing a failed pattern"""
        self.mock_cursor.fetchone = Mock(return_value=(124,))
        
        pattern_id = self.learner.store_pattern(
            goal_text="Delete nonexistent user",
            subgoals=["Select delete tool", "Execute delete"],
            success=False,
            execution_time_ms=500,
            tools_used=["delete_user"]
        )
        
        self.assertEqual(pattern_id, 124)
        # Should still store failed patterns for learning
        self.mock_cursor.execute.assert_called_once()
    
    def test_find_similar_patterns_high_similarity(self):
        """Test finding patterns with high similarity"""
        # Mock Chroma query
        self.learner.collection.query = Mock(return_value={
            'ids': [['pattern_1', 'pattern_2']],
            'metadatas': [[
                {'pattern_id': 1, 'goal_type': 'data_retrieval', 'subgoal_count': 3, 'success': True},
                {'pattern_id': 2, 'goal_type': 'data_retrieval', 'subgoal_count': 2, 'success': True}
            ]],
            'distances': [[0.05, 0.15]]  # 95%, 85% similar
        })
        self.learner.collection.count = Mock(return_value=2)
        
        # Mock database queries for full patterns
        self.mock_cursor.fetchone = Mock(side_effect=[
            (1, 'Get activities', 'data_retrieval', ['subgoal1', 'subgoal2'], 2, True, 1000, ['tool1'], 0.85, 5, None, None),
            (2, 'Fetch activities', 'data_retrieval', ['subgoal1'], 1, True, 800, ['tool2'], 0.90, 3, None, None)
        ])
        
        similar = self.learner.find_similar_patterns(
            goal_text="Retrieve my activities",
            similarity_threshold=0.8,
            only_successful=True,
            limit=5
        )
        
        # Should find both patterns
        self.assertEqual(len(similar), 2)
        self.assertEqual(similar[0]['similarity'], 0.95)
        self.assertEqual(similar[1]['similarity'], 0.85)
    
    def test_find_similar_patterns_filters_unsuccessful(self):
        """Test that unsuccessful patterns are filtered when requested"""
        self.learner.collection.query = Mock(return_value={
            'ids': [['pattern_1', 'pattern_2']],
            'metadatas': [[
                {'pattern_id': 1, 'success': True},
                {'pattern_id': 2, 'success': False}  # Failed pattern
            ]],
            'distances': [[0.05, 0.05]]  # Both 95% similar
        })
        self.learner.collection.count = Mock(return_value=2)
        
        # Only return successful pattern
        self.mock_cursor.fetchone = Mock(return_value=(
            1, 'Goal', 'type', ['subgoal'], 1, True, 1000, ['tool'], 0.85, 1, None, None
        ))
        
        similar = self.learner.find_similar_patterns(
            goal_text="Test goal",
            only_successful=True
        )
        
        # Should only find successful pattern
        self.assertEqual(len(similar), 1)
        self.assertTrue(similar[0]['success'])
    
    def test_suggest_decomposition_high_confidence(self):
        """Test suggesting decomposition with high confidence"""
        # Mock find_similar_patterns
        self.learner.find_similar_patterns = Mock(return_value=[
            {
                'pattern_id': 1,
                'goal_text': 'Get my Strava activities from last week',
                'subgoal_sequence': ['Select tool', 'Execute', 'Format results'],
                'similarity': 0.92,
                'usage_count': 10,
                'efficiency_score': 0.88
            }
        ])
        
        suggestion = self.learner.suggest_decomposition("Get my activities from yesterday")
        
        self.assertIsNotNone(suggestion)
        self.assertEqual(len(suggestion['suggested_subgoals']), 3)
        self.assertEqual(suggestion['confidence'], 0.92)
        self.assertEqual(suggestion['based_on_pattern'], 1)
    
    def test_suggest_decomposition_low_confidence(self):
        """Test that low similarity doesn't suggest decomposition"""
        # Mock find_similar_patterns with low similarity
        self.learner.find_similar_patterns = Mock(return_value=[
            {
                'pattern_id': 1,
                'goal_text': 'Completely different goal',
                'subgoal_sequence': ['subgoal1'],
                'similarity': 0.70,  # Below 85% threshold
                'usage_count': 1,
                'efficiency_score': 0.5
            }
        ])
        
        suggestion = self.learner.suggest_decomposition("My goal")
        
        # Should not suggest with low confidence
        self.assertIsNone(suggestion)
    
    def test_suggest_decomposition_no_patterns(self):
        """Test suggestion when no similar patterns exist"""
        self.learner.find_similar_patterns = Mock(return_value=[])
        
        suggestion = self.learner.suggest_decomposition("Brand new goal type")
        
        self.assertIsNone(suggestion)
    
    def test_update_pattern_usage(self):
        """Test updating pattern usage statistics"""
        self.learner.update_pattern_usage(pattern_id=123)
        
        # Verify UPDATE query was executed
        self.mock_cursor.execute.assert_called_once()
        self.mock_conn.commit.assert_called_once()
        
        # Check query updates usage_count and last_used
        query = self.mock_cursor.execute.call_args[0][0]
        self.assertIn('usage_count', query.lower())
        self.assertIn('last_used', query.lower())
    
    def test_classify_goal_type_retrieval(self):
        """Test classification of data retrieval goals"""
        goal_type = self.learner.classify_goal_type(
            "Get my Strava activities",
            ["Select tool", "Execute"]
        )
        
        self.assertEqual(goal_type, 'data_retrieval')
    
    def test_classify_goal_type_analysis(self):
        """Test classification of data analysis goals"""
        goal_type = self.learner.classify_goal_type(
            "Analyze my running performance",
            ["Get data", "Calculate metrics"]
        )
        
        self.assertEqual(goal_type, 'data_analysis')
    
    def test_classify_goal_type_modification(self):
        """Test classification of data modification goals"""
        goal_type = self.learner.classify_goal_type(
            "Update my activity name",
            ["Select tool", "Execute update"]
        )
        
        self.assertEqual(goal_type, 'data_modification')
    
    def test_classify_goal_type_multi_step(self):
        """Test classification of multi-step tasks"""
        goal_type = self.learner.classify_goal_type(
            "Complex task",
            ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]
        )
        
        self.assertEqual(goal_type, 'multi_step_task')
    
    def test_calculate_efficiency_score_fast_simple_success(self):
        """Test efficiency score for fast, simple, successful execution"""
        score = self.learner._calculate_efficiency_score(
            execution_time_ms=1000,  # 1 second (fast)
            subgoal_count=2,  # Simple
            success=True
        )
        
        # Should have high efficiency score
        self.assertGreater(score, 0.7)
    
    def test_calculate_efficiency_score_slow_complex_failure(self):
        """Test efficiency score for slow, complex, failed execution"""
        score = self.learner._calculate_efficiency_score(
            execution_time_ms=30000,  # 30 seconds (slow)
            subgoal_count=10,  # Complex
            success=False
        )
        
        # Should have low efficiency score
        self.assertLess(score, 0.3)
    
    def test_get_pattern_statistics(self):
        """Test getting pattern statistics"""
        # Mock database query
        self.mock_cursor.fetchone = Mock(return_value=(
            50,  # total_patterns
            45,  # successful_patterns
            0.900,  # success_rate
            3.5,  # avg_subgoals
            2500,  # avg_execution_ms
            150,  # total_usage
            5  # unique_goal_types
        ))
        
        stats = self.learner.get_pattern_statistics(days=30)
        
        self.assertEqual(stats['total_patterns'], 50)
        self.assertEqual(stats['successful_patterns'], 45)
        self.assertEqual(stats['success_rate'], 0.900)
        self.assertEqual(stats['avg_subgoals'], 3.5)
        self.assertEqual(stats['total_usage'], 150)


if __name__ == '__main__':
    unittest.main()
