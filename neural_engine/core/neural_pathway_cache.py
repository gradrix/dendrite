"""
Neural Pathway Cache - System 1 vs System 2 Thinking

Implements fast cached execution (System 1) with fallback to full reasoning (System 2).
Automatically invalidates cached pathways when dependent tools are removed.

Key Features:
- Cache successful execution traces with vector similarity search
- Track tool dependencies for automatic invalidation
- Fast direct execution for high-confidence cached paths
- Fallback to full orchestrator reasoning on cache miss or invalidation
- Auto-invalidate pathways with high failure rates
- Decay confidence for old pathways

System 1 (Fast): Lookup cached pathway, execute directly
System 2 (Slow): Full orchestrator reasoning when cache miss/invalid
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import hashlib
import json
from uuid import UUID

logger = logging.getLogger(__name__)


class NeuralPathwayCache:
    """
    Caches successful execution traces for fast System 1 lookup.
    Automatically invalidates when tools are removed.
    """
    
    def __init__(
        self,
        execution_store,
        chroma_client,
        collection_name: str = "neural_pathways",
        similarity_threshold: float = 0.85,
        min_success_count: int = 2,
        confidence_threshold: float = 0.70
    ):
        """
        Initialize neural pathway cache.
        
        Args:
            execution_store: ExecutionStore instance for database operations
            chroma_client: Chroma client for vector similarity search
            collection_name: Chroma collection name
            similarity_threshold: Minimum similarity for pathway match (0.0-1.0)
            min_success_count: Minimum successes before pathway is trusted
            confidence_threshold: Minimum confidence for direct execution
        """
        self.execution_store = execution_store
        self.chroma_client = chroma_client
        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        self.min_success_count = min_success_count
        self.confidence_threshold = confidence_threshold
        
        # Initialize Chroma collection
        try:
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Neural pathway cache for System 1 execution"}
            )
            logger.info(f"✓ Neural pathway cache initialized (collection: {self.collection_name})")
        except Exception as e:
            logger.error(f"Failed to initialize neural pathway cache: {e}")
            raise
    
    def store_pathway(
        self,
        goal_text: str,
        goal_embedding: List[float],
        execution_steps: List[Dict[str, Any]],
        final_result: Any,
        tool_names: List[str],
        goal_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None
    ) -> Optional[str]:
        """
        Store a successful execution pathway for future reuse.
        
        Args:
            goal_text: Original goal/prompt text
            goal_embedding: Vector embedding of goal (384-dim)
            execution_steps: List of execution steps [{step, action, tool, params, result}]
            final_result: Final execution result
            tool_names: List of tool names used in execution
            goal_type: Type of goal (e.g., 'data_retrieval', 'data_analysis')
            context: Optional context dict (user prefs, constraints)
            execution_time_ms: Execution time in milliseconds
            
        Returns:
            pathway_id (UUID str) if successful, None otherwise
        """
        try:
            # Calculate context hash for cache key
            context_hash = self._calculate_context_hash(context) if context else None
            
            # Calculate complexity score based on steps
            complexity_score = self._calculate_complexity_score(execution_steps)
            
            # Store in PostgreSQL
            with self.execution_store.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO neural_pathways (
                        goal_text, goal_embedding, goal_type,
                        execution_steps, tool_names, final_result,
                        context_hash, complexity_score, execution_time_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING pathway_id
                """, (
                    goal_text,
                    goal_embedding,
                    goal_type,
                    json.dumps(execution_steps),
                    tool_names,
                    json.dumps(final_result),
                    context_hash,
                    complexity_score,
                    execution_time_ms
                ))
                
                pathway_id = cur.fetchone()[0]
                self.execution_store.conn.commit()
            
            # Store in Chroma for vector similarity search
            self.collection.add(
                ids=[str(pathway_id)],
                embeddings=[goal_embedding],
                metadatas=[{
                    "goal_text": goal_text,
                    "goal_type": goal_type or "unknown",
                    "tool_names": ",".join(tool_names),
                    "complexity_score": complexity_score,
                    "created_at": datetime.now().isoformat()
                }]
            )
            
            logger.info(f"✓ Stored neural pathway {pathway_id} (tools: {tool_names}, complexity: {complexity_score:.2f})")
            return str(pathway_id)
            
        except Exception as e:
            logger.error(f"Failed to store neural pathway: {e}")
            return None
    
    def find_cached_pathway(
        self,
        goal_text: str,
        goal_embedding: List[float],
        goal_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a cached pathway for fast System 1 execution.
        
        Args:
            goal_text: Goal/prompt text to match
            goal_embedding: Vector embedding of goal
            goal_type: Optional goal type filter
            context: Optional context for matching
            available_tools: List of currently available tool names
            
        Returns:
            Pathway dict if found with high confidence, None for cache miss
            {
                'pathway_id': UUID,
                'execution_steps': [...],
                'final_result': {...},
                'confidence_score': 0.0-1.0,
                'similarity_score': 0.0-1.0,
                'success_rate': 0.0-1.0,
                'system': 1  # System 1 (cached)
            }
        """
        try:
            # First check Chroma for similar pathways
            results = self.collection.query(
                query_embeddings=[goal_embedding],
                n_results=5,
                where={"goal_type": goal_type} if goal_type else None
            )
            
            if not results['ids'] or not results['ids'][0]:
                logger.info("⚡ Cache miss - no similar pathways found (System 2 reasoning)")
                return None
            
            # Get detailed pathway info from PostgreSQL
            pathway_ids = [UUID(pid) for pid in results['ids'][0]]
            distances = results['distances'][0]
            
            with self.execution_store.conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        pathway_id,
                        goal_text,
                        execution_steps,
                        tool_names,
                        final_result,
                        success_count,
                        failure_count,
                        execution_time_ms,
                        is_valid,
                        invalidation_reason
                    FROM neural_pathways
                    WHERE pathway_id = ANY(%s)
                    ORDER BY 
                        (success_count::float / NULLIF(success_count + failure_count, 0)) DESC,
                        success_count DESC
                """, (pathway_ids,))
                
                pathways = cur.fetchall()
            
            # Find best valid pathway
            for i, pathway in enumerate(pathways):
                (
                    pathway_id, cached_goal_text, execution_steps_json,
                    tool_names, final_result_json, success_count, failure_count,
                    execution_time_ms, is_valid, invalidation_reason
                ) = pathway
                
                # Check if pathway is valid
                if not is_valid:
                    logger.info(f"⚠️  Pathway {pathway_id} invalid: {invalidation_reason}")
                    continue
                
                # Check if all required tools are available
                if available_tools is not None:
                    missing_tools = set(tool_names) - set(available_tools)
                    if missing_tools:
                        logger.warning(f"⚠️  Pathway {pathway_id} uses missing tools: {missing_tools}")
                        # Invalidate this pathway
                        self._invalidate_pathway(
                            str(pathway_id),
                            f"Required tools no longer available: {missing_tools}"
                        )
                        continue
                
                # Calculate scores
                similarity_score = 1.0 - distances[i]
                success_rate = success_count / max(1, success_count + failure_count)
                
                # Calculate confidence using database function
                with self.execution_store.conn.cursor() as cur:
                    cur.execute(
                        "SELECT calculate_pathway_confidence(%s)",
                        (pathway_id,)
                    )
                    confidence_score = cur.fetchone()[0]
                
                # Check if confidence meets threshold
                if (
                    similarity_score >= self.similarity_threshold and
                    success_count >= self.min_success_count and
                    confidence_score >= self.confidence_threshold
                ):
                    logger.info(
                        f"⚡ Cache HIT! Pathway {pathway_id} "
                        f"(similarity: {similarity_score:.2f}, "
                        f"confidence: {confidence_score:.2f}, "
                        f"success_rate: {success_rate:.2f}) - System 1 execution"
                    )
                    
                    return {
                        'pathway_id': str(pathway_id),
                        'goal_text': cached_goal_text,
                        'execution_steps': json.loads(execution_steps_json),
                        'tool_names': tool_names,
                        'final_result': json.loads(final_result_json),
                        'confidence_score': confidence_score,
                        'similarity_score': similarity_score,
                        'success_rate': success_rate,
                        'execution_time_ms': execution_time_ms,
                        'system': 1  # System 1 (fast cached execution)
                    }
            
            # No valid high-confidence pathway found
            logger.info("⚡ Cache miss - no high-confidence pathway found (System 2 reasoning)")
            return None
            
        except Exception as e:
            logger.error(f"Error finding cached pathway: {e}")
            return None
    
    def update_pathway_result(
        self,
        pathway_id: str,
        success: bool,
        execution_time_ms: Optional[int] = None
    ) -> bool:
        """
        Update pathway usage statistics after execution.
        
        Args:
            pathway_id: UUID of pathway
            success: Whether execution was successful
            execution_time_ms: Actual execution time
            
        Returns:
            True if updated successfully
        """
        try:
            with self.execution_store.conn.cursor() as cur:
                cur.execute(
                    "SELECT update_pathway_usage(%s, %s, %s)",
                    (UUID(pathway_id), success, execution_time_ms)
                )
                updated = cur.fetchone()[0]
                self.execution_store.conn.commit()
            
            status = "✓ success" if success else "✗ failure"
            logger.info(f"Updated pathway {pathway_id} usage: {status}")
            return updated
            
        except Exception as e:
            logger.error(f"Failed to update pathway result: {e}")
            return False
    
    def invalidate_pathways_for_tool(
        self,
        tool_name: str,
        reason: Optional[str] = None
    ) -> int:
        """
        Invalidate all pathways that depend on a specific tool.
        Called when tool is removed or becomes unavailable.
        
        Args:
            tool_name: Name of tool that was removed
            reason: Optional reason for invalidation
            
        Returns:
            Number of pathways invalidated
        """
        try:
            reason = reason or f"Tool '{tool_name}' removed or unavailable"
            
            with self.execution_store.conn.cursor() as cur:
                cur.execute(
                    "SELECT invalidate_pathways_for_tool(%s, %s)",
                    (tool_name, reason)
                )
                affected_count = cur.fetchone()[0]
                self.execution_store.conn.commit()
            
            logger.warning(
                f"⚠️  Invalidated {affected_count} pathway(s) due to missing tool: {tool_name}"
            )
            return affected_count
            
        except Exception as e:
            logger.error(f"Failed to invalidate pathways for tool: {e}")
            return 0
    
    def _invalidate_pathway(
        self,
        pathway_id: str,
        reason: str
    ) -> bool:
        """
        Invalidate a specific pathway.
        
        Args:
            pathway_id: UUID of pathway to invalidate
            reason: Reason for invalidation
            
        Returns:
            True if invalidated successfully
        """
        try:
            with self.execution_store.conn.cursor() as cur:
                cur.execute("""
                    UPDATE neural_pathways
                    SET 
                        is_valid = FALSE,
                        invalidation_reason = %s,
                        invalidated_at = CURRENT_TIMESTAMP
                    WHERE pathway_id = %s
                """, (reason, UUID(pathway_id)))
                
                self.execution_store.conn.commit()
            
            logger.warning(f"⚠️  Invalidated pathway {pathway_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate pathway: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.
        
        Returns:
            Dict with cache metrics
        """
        try:
            with self.execution_store.conn.cursor() as cur:
                # Overall stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_pathways,
                        COUNT(*) FILTER (WHERE is_valid = TRUE) as valid_pathways,
                        COUNT(*) FILTER (WHERE is_valid = FALSE) as invalid_pathways,
                        AVG(success_count::float / NULLIF(success_count + failure_count, 0)) 
                            FILTER (WHERE is_valid = TRUE) as avg_success_rate,
                        AVG(execution_time_ms) FILTER (WHERE is_valid = TRUE) as avg_execution_time_ms,
                        SUM(success_count) as total_successes,
                        SUM(failure_count) as total_failures
                    FROM neural_pathways
                """)
                
                stats = cur.fetchone()
                
                # By goal type
                cur.execute("""
                    SELECT goal_type, COUNT(*) as count
                    FROM neural_pathways
                    WHERE is_valid = TRUE
                    GROUP BY goal_type
                    ORDER BY count DESC
                """)
                
                by_type = {row[0]: row[1] for row in cur.fetchall()}
            
            return {
                'total_pathways': stats[0],
                'valid_pathways': stats[1],
                'invalid_pathways': stats[2],
                'avg_success_rate': float(stats[3]) if stats[3] else 0.0,
                'avg_execution_time_ms': float(stats[4]) if stats[4] else 0.0,
                'total_successes': stats[5] or 0,
                'total_failures': stats[6] or 0,
                'pathways_by_type': by_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    def cleanup_old_pathways(self, days_old: int = 90) -> int:
        """
        Clean up old invalidated pathways.
        
        Args:
            days_old: Delete pathways invalidated more than this many days ago
            
        Returns:
            Number of pathways deleted
        """
        try:
            with self.execution_store.conn.cursor() as cur:
                cur.execute(
                    "SELECT cleanup_old_invalidated_pathways(%s)",
                    (days_old,)
                )
                deleted_count = cur.fetchone()[0]
                self.execution_store.conn.commit()
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old invalidated pathway(s)")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old pathways: {e}")
            return 0
    
    def _calculate_context_hash(self, context: Dict[str, Any]) -> str:
        """
        Calculate hash of context for cache key.
        
        Args:
            context: Context dict (user prefs, constraints, etc.)
            
        Returns:
            SHA256 hash hex string
        """
        context_json = json.dumps(context, sort_keys=True)
        return hashlib.sha256(context_json.encode()).hexdigest()
    
    def _calculate_complexity_score(self, execution_steps: List[Dict[str, Any]]) -> float:
        """
        Calculate complexity score based on execution steps.
        
        Args:
            execution_steps: List of execution step dicts
            
        Returns:
            Complexity score (0.0-1.0)
        """
        # Simple heuristic: normalize step count
        step_count = len(execution_steps)
        
        # 1 step = 0.1 complexity, 10+ steps = 1.0 complexity
        base_score = min(1.0, step_count * 0.1)
        
        # Increase complexity for nested structures or multiple tools
        unique_tools = len(set(step.get('tool', '') for step in execution_steps))
        tool_diversity_factor = min(1.0, unique_tools * 0.15)
        
        # Combine factors
        complexity = min(1.0, base_score * 0.7 + tool_diversity_factor * 0.3)
        
        return round(complexity, 2)
