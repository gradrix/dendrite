"""
Tests for Phase 9g: Duplicate Detection via Embeddings

Tests ToolDiscovery's duplicate detection capabilities:
- find_similar_tools(): Find tools similar to a reference tool
- find_all_duplicates(): Scan entire registry for duplicate pairs
- compare_tools_side_by_side(): Detailed comparison
- _generate_consolidation_recommendation(): Which tool to keep
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from neural_engine.core.tool_discovery import ToolDiscovery
from neural_engine.tools.base_tool import BaseTool


class MockSimilarTool1(BaseTool):
    """Mock tool for similarity testing"""
    name = "mock_similar_tool_1"
    description = "Get user activity data from fitness tracker"
    parameters = {
        "user_id": {"type": "string", "description": "User identifier"},
        "date_range": {"type": "string", "description": "Date range for activities"}
    }
    
    def execute(self, user_id, date_range):
        return {"activities": []}


class MockSimilarTool2(BaseTool):
    """Very similar tool (likely duplicate)"""
    name = "mock_similar_tool_2"
    description = "Retrieve user activity information from fitness tracking system"
    parameters = {
        "user_id": {"type": "string", "description": "User ID"},
        "dates": {"type": "string", "description": "Date range"}
    }
    
    def execute(self, user_id, dates):
        return {"activities": []}


class MockDifferentTool(BaseTool):
    """Completely different tool"""
    name = "mock_different_tool"
    description = "Send email notifications to users"
    parameters = {
        "recipient": {"type": "string", "description": "Email address"},
        "subject": {"type": "string", "description": "Email subject"},
        "body": {"type": "string", "description": "Email body"}
    }
    
    def execute(self, recipient, subject, body):
        return {"sent": True}


class TestDuplicateDetection(unittest.TestCase):
    """Test suite for duplicate detection functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock tool registry
        self.mock_registry = Mock()
        self.mock_registry.get_tool = Mock(side_effect=self._mock_get_tool)
        self.mock_registry.get_all_tools = Mock(return_value={
            "mock_similar_tool_1": MockSimilarTool1,
            "mock_similar_tool_2": MockSimilarTool2,
            "mock_different_tool": MockDifferentTool
        })
        
        # Mock execution store
        self.mock_store = Mock()
        self.mock_store.get_tool_statistics = Mock(side_effect=self._mock_get_statistics)
        self.mock_store.close = Mock()
        
        # Create tool discovery instance
        with patch('chromadb.PersistentClient'):
            self.discovery = ToolDiscovery(
                tool_registry=self.mock_registry,
                execution_store=self.mock_store,
                chroma_path="/tmp/test_chroma"
            )
            
            # Mock the Chroma collection
            self.discovery.collection = Mock()
    
    def _mock_get_tool(self, tool_name):
        """Mock tool registry get_tool"""
        tools = {
            "mock_similar_tool_1": MockSimilarTool1,
            "mock_similar_tool_2": MockSimilarTool2,
            "mock_different_tool": MockDifferentTool
        }
        return tools.get(tool_name)
    
    def _mock_get_statistics(self, tool_name):
        """Mock execution store statistics"""
        stats = {
            "mock_similar_tool_1": {
                "total_executions": 50,
                "success_rate": 0.95,
                "avg_duration": 1.2
            },
            "mock_similar_tool_2": {
                "total_executions": 10,
                "success_rate": 0.85,
                "avg_duration": 1.5
            },
            "mock_different_tool": {
                "total_executions": 100,
                "success_rate": 0.98,
                "avg_duration": 0.5
            }
        }
        return stats.get(tool_name)
    
    def test_find_similar_tools_high_similarity(self):
        """Test finding tools with high similarity (>0.9)"""
        # Mock Chroma query to return similar tool
        self.discovery.collection.query = Mock(return_value={
            'ids': [['mock_similar_tool_1', 'mock_similar_tool_2', 'mock_different_tool']],
            'metadatas': [[
                {'description': 'Get user activity data', 'parameter_count': 2},
                {'description': 'Retrieve user activity information', 'parameter_count': 2},
                {'description': 'Send email notifications', 'parameter_count': 3}
            ]],
            'distances': [[0.0, 0.05, 0.8]]  # 100%, 95%, 20% similar
        })
        self.discovery.collection.count = Mock(return_value=3)
        
        # Find similar tools
        similar = self.discovery.find_similar_tools(
            tool_name="mock_similar_tool_1",
            similarity_threshold=0.9
        )
        
        # Should find mock_similar_tool_2 (95% similar) but not mock_different_tool (20%)
        self.assertEqual(len(similar), 1)
        self.assertEqual(similar[0]['tool_name'], 'mock_similar_tool_2')
        self.assertEqual(similar[0]['similarity'], 0.95)
        self.assertTrue(similar[0]['is_potential_duplicate'])
    
    def test_find_similar_tools_medium_similarity(self):
        """Test finding tools with medium similarity (0.85-0.90)"""
        self.discovery.collection.query = Mock(return_value={
            'ids': [['mock_similar_tool_1', 'mock_similar_tool_2']],
            'metadatas': [[
                {'description': 'Get user activity data', 'parameter_count': 2},
                {'description': 'Similar but not identical', 'parameter_count': 2}
            ]],
            'distances': [[0.0, 0.12]]  # 100%, 88% similar
        })
        self.discovery.collection.count = Mock(return_value=2)
        
        similar = self.discovery.find_similar_tools(
            tool_name="mock_similar_tool_1",
            similarity_threshold=0.85
        )
        
        # Should find tool with 88% similarity
        self.assertEqual(len(similar), 1)
        self.assertEqual(similar[0]['similarity'], 0.88)
        self.assertFalse(similar[0]['is_potential_duplicate'])  # < 95%
    
    def test_find_similar_tools_no_matches(self):
        """Test when no similar tools found"""
        self.discovery.collection.query = Mock(return_value={
            'ids': [['mock_similar_tool_1', 'mock_different_tool']],
            'metadatas': [[
                {'description': 'Get user activity data', 'parameter_count': 2},
                {'description': 'Send email notifications', 'parameter_count': 3}
            ]],
            'distances': [[0.0, 0.8]]  # 100%, 20% similar
        })
        self.discovery.collection.count = Mock(return_value=2)
        
        similar = self.discovery.find_similar_tools(
            tool_name="mock_similar_tool_1",
            similarity_threshold=0.9
        )
        
        # Should find nothing above 90% threshold
        self.assertEqual(len(similar), 0)
    
    def test_find_similar_tools_tool_not_found(self):
        """Test handling when reference tool doesn't exist"""
        similar = self.discovery.find_similar_tools(
            tool_name="nonexistent_tool",
            similarity_threshold=0.9
        )
        
        self.assertEqual(len(similar), 0)
    
    def test_find_similar_tools_excludes_self(self):
        """Test that tool doesn't match with itself"""
        self.discovery.collection.query = Mock(return_value={
            'ids': [['mock_similar_tool_1', 'mock_similar_tool_1']],  # Duplicate of self
            'metadatas': [[
                {'description': 'Get user activity data', 'parameter_count': 2},
                {'description': 'Get user activity data', 'parameter_count': 2}
            ]],
            'distances': [[0.0, 0.0]]  # Both 100% similar
        })
        self.discovery.collection.count = Mock(return_value=2)
        
        similar = self.discovery.find_similar_tools(
            tool_name="mock_similar_tool_1",
            similarity_threshold=0.9
        )
        
        # Should exclude the tool itself
        self.assertEqual(len(similar), 0)
    
    def test_find_all_duplicates(self):
        """Test scanning entire registry for duplicates"""
        # Mock find_similar_tools to return controlled results
        def mock_find_similar(tool_name, similarity_threshold, limit):
            if tool_name == "mock_similar_tool_1":
                return [{
                    'tool_name': 'mock_similar_tool_2',
                    'description': 'Retrieve user activity information',
                    'parameter_count': 2,
                    'similarity': 0.95,
                    'is_potential_duplicate': True
                }]
            elif tool_name == "mock_similar_tool_2":
                return [{
                    'tool_name': 'mock_similar_tool_1',
                    'description': 'Get user activity data',
                    'parameter_count': 2,
                    'similarity': 0.95,
                    'is_potential_duplicate': True
                }]
            else:
                return []
        
        self.discovery.find_similar_tools = Mock(side_effect=mock_find_similar)
        
        # Find all duplicates
        duplicates = self.discovery.find_all_duplicates(similarity_threshold=0.9)
        
        # Should find one duplicate pair (not counted twice)
        self.assertEqual(len(duplicates), 1)
        pair = duplicates[0]
        
        # Check pair structure
        self.assertIn('tool_a', pair)
        self.assertIn('tool_b', pair)
        self.assertEqual(pair['similarity'], 0.95)
        self.assertTrue(pair['is_potential_duplicate'])
        self.assertIn('stats_a', pair)
        self.assertIn('stats_b', pair)
        self.assertIn('recommendation', pair)
    
    def test_generate_consolidation_recommendation_by_usage(self):
        """Test recommendation favors more-used tool"""
        stats_a = {"total_executions": 100, "success_rate": 0.90}
        stats_b = {"total_executions": 10, "success_rate": 0.90}
        
        recommendation = self.discovery._generate_consolidation_recommendation(
            "tool_a", "tool_b", stats_a, stats_b, similarity=0.95
        )
        
        self.assertEqual(recommendation['action'], 'consolidate')
        self.assertEqual(recommendation['keep'], 'tool_a')
        self.assertEqual(recommendation['deprecate'], 'tool_b')
        self.assertIn('better usage and reliability', recommendation['reason'])
        self.assertEqual(recommendation['confidence'], 'high')  # 95% similarity
    
    def test_generate_consolidation_recommendation_by_success(self):
        """Test recommendation favors more reliable tool"""
        stats_a = {"total_executions": 50, "success_rate": 0.98}
        stats_b = {"total_executions": 50, "success_rate": 0.75}
        
        recommendation = self.discovery._generate_consolidation_recommendation(
            "tool_a", "tool_b", stats_a, stats_b, similarity=0.92
        )
        
        self.assertEqual(recommendation['keep'], 'tool_a')
        self.assertEqual(recommendation['deprecate'], 'tool_b')
        self.assertIn('better usage and reliability', recommendation['reason'])
        self.assertEqual(recommendation['confidence'], 'medium')  # 92% similarity
    
    def test_generate_consolidation_recommendation_equal_stats(self):
        """Test recommendation when stats are equal (alphabetical)"""
        stats_a = {"total_executions": 50, "success_rate": 0.90}
        stats_b = {"total_executions": 50, "success_rate": 0.90}
        
        recommendation = self.discovery._generate_consolidation_recommendation(
            "zebra_tool", "aardvark_tool", stats_a, stats_b, similarity=0.95
        )
        
        # Should keep alphabetically first
        self.assertEqual(recommendation['keep'], 'aardvark_tool')
        self.assertEqual(recommendation['deprecate'], 'zebra_tool')
        self.assertIn('alphabetical', recommendation['reason'])
    
    def test_compare_tools_side_by_side(self):
        """Test detailed side-by-side comparison"""
        # Mock Chroma query for similarity calculation
        self.discovery.collection.query = Mock(return_value={
            'ids': [['mock_similar_tool_1', 'mock_similar_tool_2', 'mock_different_tool']],
            'distances': [[0.0, 0.05, 0.8]]
        })
        
        comparison = self.discovery.compare_tools_side_by_side(
            "mock_similar_tool_1",
            "mock_similar_tool_2"
        )
        
        # Check structure
        self.assertIn('tool_a', comparison)
        self.assertIn('tool_b', comparison)
        self.assertIn('comparison', comparison)
        self.assertIn('recommendation', comparison)
        
        # Check tool details
        self.assertEqual(comparison['tool_a']['name'], 'mock_similar_tool_1')
        self.assertEqual(comparison['tool_b']['name'], 'mock_similar_tool_2')
        
        # Check comparison metrics
        comp = comparison['comparison']
        self.assertEqual(comp['similarity'], 0.95)
        self.assertTrue(comp['is_likely_duplicate'])
        self.assertIn('common_parameters', comp)
        self.assertIn('unique_to_a', comp)
        self.assertIn('unique_to_b', comp)
        self.assertIn('parameter_overlap', comp)
    
    def test_compare_tools_different_params(self):
        """Test comparison of tools with different parameters"""
        self.discovery.collection.query = Mock(return_value={
            'ids': [['mock_similar_tool_1', 'mock_different_tool']],
            'distances': [[0.0, 0.8]]
        })
        
        comparison = self.discovery.compare_tools_side_by_side(
            "mock_similar_tool_1",
            "mock_different_tool"
        )
        
        comp = comparison['comparison']
        
        # Should have low similarity and no common parameters
        self.assertAlmostEqual(comp['similarity'], 0.2, places=1)
        self.assertFalse(comp['is_likely_duplicate'])
        self.assertEqual(len(comp['common_parameters']), 0)
        self.assertGreater(len(comp['unique_to_a']), 0)
        self.assertGreater(len(comp['unique_to_b']), 0)
    
    def test_compare_tools_tool_not_found(self):
        """Test comparison when tool doesn't exist"""
        comparison = self.discovery.compare_tools_side_by_side(
            "nonexistent_tool_1",
            "nonexistent_tool_2"
        )
        
        self.assertIn('error', comparison)
        self.assertIn('not found', comparison['error'])
    
    def test_find_similar_tools_respects_limit(self):
        """Test that limit parameter is respected"""
        # Return many similar tools
        self.discovery.collection.query = Mock(return_value={
            'ids': [[f'tool_{i}' for i in range(20)]],
            'metadatas': [[{'description': f'Tool {i}', 'parameter_count': 2} for i in range(20)]],
            'distances': [[0.05 for _ in range(20)]]  # All 95% similar
        })
        self.discovery.collection.count = Mock(return_value=20)
        
        similar = self.discovery.find_similar_tools(
            tool_name="mock_similar_tool_1",
            similarity_threshold=0.9,
            limit=5
        )
        
        # Should respect limit
        self.assertEqual(len(similar), 5)
    
    def test_find_similar_tools_sorted_by_similarity(self):
        """Test that results are sorted by similarity (highest first)"""
        self.discovery.collection.query = Mock(return_value={
            'ids': [['mock_similar_tool_1', 'tool_a', 'tool_b', 'tool_c']],
            'metadatas': [[
                {'description': 'Tool 1', 'parameter_count': 2},
                {'description': 'Tool A', 'parameter_count': 2},
                {'description': 'Tool B', 'parameter_count': 2},
                {'description': 'Tool C', 'parameter_count': 2}
            ]],
            'distances': [[0.0, 0.02, 0.08, 0.05]]  # 100%, 98%, 92%, 95% similar
        })
        self.discovery.collection.count = Mock(return_value=4)
        
        similar = self.discovery.find_similar_tools(
            tool_name="mock_similar_tool_1",
            similarity_threshold=0.9
        )
        
        # Should be sorted: 98%, 95%, 92%
        self.assertEqual(len(similar), 3)
        self.assertEqual(similar[0]['tool_name'], 'tool_a')
        self.assertEqual(similar[0]['similarity'], 0.98)
        self.assertEqual(similar[1]['tool_name'], 'tool_c')
        self.assertEqual(similar[1]['similarity'], 0.95)
        self.assertEqual(similar[2]['tool_name'], 'tool_b')
        self.assertEqual(similar[2]['similarity'], 0.92)


if __name__ == '__main__':
    unittest.main()
