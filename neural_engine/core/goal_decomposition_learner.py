"""
Goal Decomposition Learner: Learn efficient goal decomposition patterns.

Phase 10a: System learns from successful goal decompositions and applies
patterns to similar goals.

Key Capabilities:
1. Store successful goal → subgoals patterns
2. Find similar goals via vector embeddings
3. Apply learned patterns to new goals
4. Track pattern effectiveness
5. Refine patterns based on outcomes

Learning Process:
- After successful execution: Store goal + subgoals + outcome
- Before new execution: Check for similar goals
- If found: Suggest proven decomposition pattern
- After execution: Update pattern usage statistics
"""

import json
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import chromadb
from neural_engine.core.execution_store import ExecutionStore


class GoalDecompositionLearner:
    """
    Learn and apply efficient goal decomposition patterns.
    
    Phase 10a: Makes the system smarter over time by learning what works.
    """
    
    def __init__(self,
                 execution_store: ExecutionStore,
                 chroma_path: str = "./chroma_data"):
        """
        Initialize GoalDecompositionLearner.
        
        Args:
            execution_store: ExecutionStore for database access
            chroma_path: Path to Chroma storage for embeddings
        """
        self.execution_store = execution_store
        
        # Initialize Chroma for goal embeddings
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        
        # Get or create collection for goal patterns
        try:
            self.collection = self.chroma_client.get_collection(name="goal_patterns")
        except:
            self.collection = self.chroma_client.create_collection(
                name="goal_patterns",
                metadata={"hnsw:space": "cosine"}
            )
    
    def store_pattern(self,
                     goal_text: str,
                     subgoals: List[str],
                     success: bool,
                     execution_time_ms: int,
                     tools_used: List[str],
                     goal_type: Optional[str] = None) -> int:
        """
        Store a goal decomposition pattern for future learning.
        
        Args:
            goal_text: Original goal
            subgoals: List of subgoals in execution order
            success: Whether execution succeeded
            execution_time_ms: Total execution time
            tools_used: List of tools used
            goal_type: Optional classification (e.g., 'data_retrieval')
        
        Returns:
            pattern_id of stored pattern
        """
        # Calculate efficiency score
        efficiency_score = self._calculate_efficiency_score(
            execution_time_ms=execution_time_ms,
            subgoal_count=len(subgoals),
            success=success
        )
        
        # Store in database
        query = """
        INSERT INTO goal_decomposition_patterns 
        (goal_text, goal_type, subgoal_sequence, subgoal_count, success, 
         execution_time_ms, tools_used, efficiency_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (goal_text, subgoal_sequence) 
        DO UPDATE SET 
            usage_count = goal_decomposition_patterns.usage_count + 1,
            last_used = CURRENT_TIMESTAMP
        RETURNING pattern_id
        """
        
        conn = self.execution_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (
                    goal_text,
                    goal_type,
                    json.dumps(subgoals),
                    len(subgoals),
                    success,
                    execution_time_ms,
                    json.dumps(tools_used),
                    efficiency_score
                ))
                pattern_id = cur.fetchone()[0]
                conn.commit()
                
                # Store embedding in Chroma
                self.collection.add(
                    documents=[goal_text],
                    metadatas=[{
                        'pattern_id': pattern_id,
                        'goal_type': goal_type or 'unknown',
                        'subgoal_count': len(subgoals),
                        'success': success
                    }],
                    ids=[f"pattern_{pattern_id}"]
                )
                
                return pattern_id
        finally:
            self.execution_store.pool.putconn(conn)
    
    def find_similar_patterns(self,
                             goal_text: str,
                             similarity_threshold: float = 0.8,
                             only_successful: bool = True,
                             limit: int = 5) -> List[Dict]:
        """
        Find similar goal patterns using vector similarity.
        
        Args:
            goal_text: New goal to find patterns for
            similarity_threshold: Minimum cosine similarity (0.8 = 80%)
            only_successful: Only return successful patterns
            limit: Maximum number of patterns to return
        
        Returns:
            List of similar patterns with similarity scores
        """
        # Check if collection has any patterns
        collection_count = self.collection.count()
        if collection_count == 0:
            return []  # No patterns to search
        
        # Search Chroma for similar goals
        results = self.collection.query(
            query_texts=[goal_text],
            n_results=min(limit * 2, collection_count)  # Get extra for filtering
        )
        
        similar_patterns = []
        
        if results['ids'] and len(results['ids']) > 0:
            pattern_ids = results['ids'][0]
            metadatas = results['metadatas'][0]
            distances = results['distances'][0] if results['distances'] else [0] * len(pattern_ids)
            
            for pattern_id_str, metadata, distance in zip(pattern_ids, metadatas, distances):
                # Calculate similarity
                similarity = 1.0 - distance
                
                # Filter by threshold
                if similarity < similarity_threshold:
                    continue
                
                # Filter by success if requested
                if only_successful and not metadata.get('success', False):
                    continue
                
                # Get full pattern from database
                pattern_id = metadata.get('pattern_id')
                pattern = self._get_pattern_by_id(pattern_id)
                
                if pattern:
                    pattern['similarity'] = similarity
                    similar_patterns.append(pattern)
                
                # Stop if we have enough
                if len(similar_patterns) >= limit:
                    break
        
        # Sort by similarity (highest first)
        similar_patterns.sort(key=lambda x: x['similarity'], reverse=True)
        
        return similar_patterns
    
    def _get_pattern_by_id(self, pattern_id: int) -> Optional[Dict]:
        """Get full pattern details from database."""
        query = """
        SELECT 
            pattern_id, goal_text, goal_type, subgoal_sequence, subgoal_count,
            success, execution_time_ms, tools_used, efficiency_score,
            usage_count, last_used, created_at
        FROM goal_decomposition_patterns
        WHERE pattern_id = %s
        """
        
        conn = self.execution_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (pattern_id,))
                row = cur.fetchone()
                
                if row:
                    return {
                        'pattern_id': row[0],
                        'goal_text': row[1],
                        'goal_type': row[2],
                        'subgoal_sequence': row[3],
                        'subgoal_count': row[4],
                        'success': row[5],
                        'execution_time_ms': row[6],
                        'tools_used': row[7],
                        'efficiency_score': row[8],
                        'usage_count': row[9],
                        'last_used': row[10],
                        'created_at': row[11]
                    }
                return None
        finally:
            self.execution_store.pool.putconn(conn)
    
    def suggest_decomposition(self, goal_text: str) -> Optional[Dict]:
        """
        Suggest a decomposition based on similar successful patterns.
        
        Args:
            goal_text: New goal to decompose
        
        Returns:
            Suggested decomposition or None if no good match found
        """
        # Find similar successful patterns
        similar = self.find_similar_patterns(
            goal_text=goal_text,
            similarity_threshold=0.85,  # Higher threshold for suggestions
            only_successful=True,
            limit=3
        )
        
        if not similar:
            return None
        
        # Use the most similar pattern
        best_pattern = similar[0]
        
        # Only suggest if similarity is high enough
        if best_pattern['similarity'] < 0.85:
            return None
        
        return {
            'suggested_subgoals': best_pattern['subgoal_sequence'],
            'confidence': best_pattern['similarity'],
            'based_on_pattern': best_pattern['pattern_id'],
            'pattern_goal': best_pattern['goal_text'],
            'usage_count': best_pattern['usage_count'],
            'efficiency_score': best_pattern['efficiency_score'],
            'reasoning': f"Similar to previous goal (similarity: {best_pattern['similarity']:.0%})"
        }
    
    def update_pattern_usage(self, pattern_id: int):
        """
        Update usage statistics when a pattern is applied.
        
        Args:
            pattern_id: ID of pattern that was used
        """
        query = """
        UPDATE goal_decomposition_patterns
        SET usage_count = usage_count + 1,
            last_used = CURRENT_TIMESTAMP
        WHERE pattern_id = %s
        """
        
        conn = self.execution_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (pattern_id,))
                conn.commit()
        finally:
            self.execution_store.pool.putconn(conn)
    
    def get_pattern_statistics(self, days: int = 30) -> Dict:
        """
        Get statistics about learned patterns.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Statistics about pattern learning and usage
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = """
        SELECT 
            COUNT(*) as total_patterns,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_patterns,
            ROUND(AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END), 3) as success_rate,
            ROUND(AVG(subgoal_count), 1) as avg_subgoals,
            ROUND(AVG(execution_time_ms), 0) as avg_execution_ms,
            SUM(usage_count) as total_usage,
            COUNT(DISTINCT goal_type) as unique_goal_types
        FROM goal_decomposition_patterns
        WHERE created_at >= %s
        """
        
        conn = self.execution_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (cutoff_date,))
                row = cur.fetchone()
                
                if row:
                    return {
                        'total_patterns': row[0],
                        'successful_patterns': row[1],
                        'success_rate': float(row[2]) if row[2] else 0.0,
                        'avg_subgoals': float(row[3]) if row[3] else 0.0,
                        'avg_execution_ms': int(row[4]) if row[4] else 0,
                        'total_usage': row[5],
                        'unique_goal_types': row[6]
                    }
                return {
                    'total_patterns': 0,
                    'successful_patterns': 0,
                    'success_rate': 0.0,
                    'avg_subgoals': 0.0,
                    'avg_execution_ms': 0,
                    'total_usage': 0,
                    'unique_goal_types': 0
                }
        finally:
            self.execution_store.pool.putconn(conn)
    
    def get_patterns_by_type(self, goal_type: str) -> List[Dict]:
        """
        Get all patterns for a specific goal type.
        
        Args:
            goal_type: Type of goal (e.g., 'data_retrieval')
        
        Returns:
            List of patterns for that type
        """
        query = """
        SELECT 
            pattern_id, goal_text, subgoal_sequence, subgoal_count,
            success, execution_time_ms, efficiency_score, usage_count
        FROM goal_decomposition_patterns
        WHERE goal_type = %s
        ORDER BY usage_count DESC, efficiency_score DESC NULLS LAST
        LIMIT 20
        """
        
        conn = self.execution_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (goal_type,))
                rows = cur.fetchall()
                
                patterns = []
                for row in rows:
                    patterns.append({
                        'pattern_id': row[0],
                        'goal_text': row[1],
                        'subgoal_sequence': row[2],
                        'subgoal_count': row[3],
                        'success': row[4],
                        'execution_time_ms': row[5],
                        'efficiency_score': row[6],
                        'usage_count': row[7]
                    })
                
                return patterns
        finally:
            self.execution_store.pool.putconn(conn)
    
    def _calculate_efficiency_score(self,
                                    execution_time_ms: int,
                                    subgoal_count: int,
                                    success: bool) -> float:
        """
        Calculate efficiency score for a pattern.
        
        Formula: (time_score * 0.4) + (complexity_score * 0.3) + (success * 0.3)
        
        Where:
        - time_score: Faster is better (normalized)
        - complexity_score: Fewer subgoals is better
        - success: 1.0 if successful, 0.0 if failed
        """
        # Time score: faster is better (10 seconds baseline)
        time_score = 1.0 / (1.0 + (execution_time_ms / 10000.0))
        
        # Complexity score: fewer subgoals is better (5 subgoals baseline)
        complexity_score = 1.0 / (1.0 + (subgoal_count / 5.0))
        
        # Success bonus
        success_score = 1.0 if success else 0.0
        
        # Combined score
        return (time_score * 0.4) + (complexity_score * 0.3) + (success_score * 0.3)
    
    def classify_goal_type(self, goal_text: str, subgoals: List[str]) -> str:
        """
        Classify goal type based on content.
        
        Simple heuristic classification:
        - data_retrieval: Get, fetch, retrieve
        - data_analysis: Analyze, calculate, compute
        - data_modification: Update, create, delete
        - multi_step: Multiple distinct operations
        
        Args:
            goal_text: Goal text
            subgoals: List of subgoals
        
        Returns:
            Goal type classification
        """
        goal_lower = goal_text.lower()
        
        # Check for retrieval keywords
        retrieval_keywords = ['get', 'fetch', 'retrieve', 'find', 'search', 'list', 'show']
        if any(kw in goal_lower for kw in retrieval_keywords):
            return 'data_retrieval'
        
        # Check for analysis keywords
        analysis_keywords = ['analyze', 'calculate', 'compute', 'summarize', 'aggregate']
        if any(kw in goal_lower for kw in analysis_keywords):
            return 'data_analysis'
        
        # Check for modification keywords
        modification_keywords = ['update', 'create', 'delete', 'modify', 'change', 'set']
        if any(kw in goal_lower for kw in modification_keywords):
            return 'data_modification'
        
        # Check if multi-step
        if len(subgoals) > 3:
            return 'multi_step_task'
        
        return 'general'
    
    def get_learning_statistics(self) -> Dict:
        """
        Get overall learning statistics.
        
        Returns:
            Statistics about pattern learning effectiveness
        """
        query = """
        SELECT 
            goal_type,
            COUNT(*) as pattern_count,
            ROUND(AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END), 3) as success_rate,
            ROUND(AVG(efficiency_score), 3) as avg_efficiency,
            SUM(usage_count) as total_usage
        FROM goal_decomposition_patterns
        GROUP BY goal_type
        ORDER BY total_usage DESC
        """
        
        conn = self.execution_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                
                by_type = {}
                for row in rows:
                    by_type[row[0]] = {
                        'pattern_count': row[1],
                        'success_rate': float(row[2]) if row[2] else 0.0,
                        'avg_efficiency': float(row[3]) if row[3] else 0.0,
                        'total_usage': row[4]
                    }
                
                # Get overall stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(usage_count) as total_usage,
                        ROUND(AVG(efficiency_score), 3) as avg_efficiency
                    FROM goal_decomposition_patterns
                """)
                overall = cur.fetchone()
                
                return {
                    'total_patterns': overall[0],
                    'total_usage': overall[1],
                    'avg_efficiency': float(overall[2]) if overall[2] else 0.0,
                    'by_type': by_type
                }
        finally:
            self.execution_store.pool.putconn(conn)
    
    def close(self):
        """Close connections."""
        # Chroma client doesn't need explicit closing
        pass
