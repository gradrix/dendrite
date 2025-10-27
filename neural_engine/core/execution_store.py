"""
ExecutionStore: PostgreSQL-backed execution history and learning foundation.
Phase 8a: Stores all executions for analytics and continuous improvement.
"""

import os
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool


class ExecutionStore:
    """Stores execution history in PostgreSQL for learning and analytics."""
    
    def __init__(self, 
                 host: str = None,
                 database: str = None, 
                 user: str = None,
                 password: str = None,
                 min_connections: int = 1,
                 max_connections: int = 10):
        """
        Initialize ExecutionStore with PostgreSQL connection.
        
        Args:
            host: PostgreSQL host (default: from POSTGRES_HOST env)
            database: Database name (default: from POSTGRES_DB env)
            user: Database user (default: from POSTGRES_USER env)
            password: Database password (default: from POSTGRES_PASSWORD env)
            min_connections: Minimum pool connections
            max_connections: Maximum pool connections
        """
        self.host = host or os.getenv('POSTGRES_HOST', 'postgres')
        self.database = database or os.getenv('POSTGRES_DB', 'dendrite')
        self.user = user or os.getenv('POSTGRES_USER', 'dendrite')
        self.password = password or os.getenv('POSTGRES_PASSWORD', 'dendrite_pass')
        
        # Create connection pool
        self.pool = SimpleConnectionPool(
            min_connections,
            max_connections,
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password
        )
    
    def _get_connection(self):
        """Get connection from pool."""
        return self.pool.getconn()
    
    def _release_connection(self, conn):
        """Return connection to pool."""
        self.pool.putconn(conn)
    
    def store_execution(self, 
                       goal_id: str,
                       goal_text: str,
                       intent: Optional[str] = None,
                       success: bool = False,
                       error: Optional[str] = None,
                       duration_ms: Optional[int] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store a goal execution.
        
        Args:
            goal_id: Unique goal identifier (e.g., "goal_1")
            goal_text: Original user goal text
            intent: Classified intent (tool_use, generative, unknown)
            success: Whether execution succeeded
            error: Error message if failed
            duration_ms: Execution duration in milliseconds
            metadata: Additional metadata (pipeline data, neuron outputs, etc.)
        
        Returns:
            execution_id: UUID of stored execution
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO executions (
                        goal_id, goal_text, intent, success, error, 
                        duration_ms, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING execution_id
                """, (
                    goal_id,
                    goal_text,
                    intent,
                    success,
                    error,
                    duration_ms,
                    Json(metadata or {})
                ))
                execution_id = cursor.fetchone()[0]
                conn.commit()
                return str(execution_id)
        finally:
            self._release_connection(conn)
    
    def store_tool_execution(self,
                            execution_id: str,
                            tool_name: str,
                            parameters: Optional[Dict] = None,
                            result: Optional[Any] = None,
                            success: bool = False,
                            error: Optional[str] = None,
                            duration_ms: Optional[int] = None):
        """
        Store a tool execution within a goal execution.
        
        Args:
            execution_id: Parent execution UUID
            tool_name: Name of tool executed
            parameters: Tool input parameters
            result: Tool execution result
            success: Whether tool succeeded
            error: Error message if failed
            duration_ms: Tool execution duration
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO tool_executions (
                        execution_id, tool_name, parameters, result,
                        success, error, duration_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    execution_id,
                    tool_name,
                    Json(parameters or {}),
                    Json(result) if result is not None else None,
                    success,
                    error,
                    duration_ms
                ))
                conn.commit()
        finally:
            self._release_connection(conn)
    
    def store_feedback(self,
                      execution_id: str,
                      rating: int,
                      feedback_text: Optional[str] = None):
        """
        Store user feedback for an execution.
        
        Args:
            execution_id: Execution UUID
            rating: User rating (1-5)
            feedback_text: Optional feedback text
        """
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO execution_feedback (
                        execution_id, rating, feedback_text
                    ) VALUES (%s, %s, %s)
                """, (execution_id, rating, feedback_text))
                conn.commit()
        finally:
            self._release_connection(conn)
    
    def store_tool_creation(self,
                           tool_name: str,
                           tool_class: str,
                           goal_text: str,
                           generated_code: str,
                           validation_passed: bool,
                           validation_errors: Optional[List[str]] = None,
                           created_by: str = 'ai'):
        """
        Store a tool creation event.
        
        Args:
            tool_name: Name of created tool
            tool_class: Class name in code
            goal_text: Original request that created the tool
            generated_code: Complete tool code
            validation_passed: Whether validation succeeded
            validation_errors: List of validation errors if any
            created_by: 'ai' or 'admin'
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO tool_creation_events (
                        tool_name, tool_class, goal_text, generated_code,
                        validation_passed, validation_errors, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    tool_name,
                    tool_class,
                    goal_text,
                    generated_code,
                    validation_passed,
                    Json(validation_errors or []),
                    created_by
                ))
                conn.commit()
        finally:
            self._release_connection(conn)
    
    def get_tool_statistics(self, tool_name: str) -> Optional[Dict]:
        """
        Get statistics for a specific tool.
        
        Args:
            tool_name: Name of tool
        
        Returns:
            Dictionary with statistics or None if not found
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM tool_statistics WHERE tool_name = %s
                """, (tool_name,))
                result = cursor.fetchone()
                return dict(result) if result else None
        finally:
            self._release_connection(conn)
    
    def get_top_tools(self, limit: int = 20, min_executions: int = 3) -> List[Dict]:
        """
        Get top performing tools by success rate.
        
        Args:
            limit: Maximum number of tools to return
            min_executions: Minimum executions required for ranking
        
        Returns:
            List of tool statistics sorted by success rate
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM tool_statistics
                    WHERE total_executions >= %s
                    ORDER BY success_rate DESC, total_executions DESC
                    LIMIT %s
                """, (min_executions, limit))
                return [dict(row) for row in cursor.fetchall()]
        finally:
            self._release_connection(conn)
    
    def get_recent_executions(self, limit: int = 50) -> List[Dict]:
        """
        Get recent executions.
        
        Args:
            limit: Maximum number of executions
        
        Returns:
            List of execution records
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        execution_id::text,
                        goal_id,
                        goal_text,
                        intent,
                        success,
                        duration_ms,
                        created_at
                    FROM executions
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        finally:
            self._release_connection(conn)
    
    def get_tool_performance_view(self) -> List[Dict]:
        """
        Get aggregated tool performance from view.
        
        Returns:
            List of tool performance records
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM tool_performance
                    ORDER BY execution_count DESC
                """)
                return [dict(row) for row in cursor.fetchall()]
        finally:
            self._release_connection(conn)
    
    def update_statistics(self):
        """
        Update aggregated tool statistics.
        Should be called periodically (hourly/daily).
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT update_tool_statistics()")
                conn.commit()
        finally:
            self._release_connection(conn)
    
    def get_success_rate(self, intent: Optional[str] = None) -> float:
        """
        Get overall system success rate.
        
        Args:
            intent: Filter by intent (tool_use, generative, etc.)
        
        Returns:
            Success rate as float (0.0 to 1.0)
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                if intent:
                    cursor.execute("""
                        SELECT 
                            COALESCE(
                                SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / 
                                NULLIF(COUNT(*), 0),
                                0
                            ) as success_rate
                        FROM executions
                        WHERE intent = %s
                    """, (intent,))
                else:
                    cursor.execute("""
                        SELECT 
                            COALESCE(
                                SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / 
                                NULLIF(COUNT(*), 0),
                                0
                            ) as success_rate
                        FROM executions
                    """)
                result = cursor.fetchone()
                return result[0] if result else 0.0
        finally:
            self._release_connection(conn)
    
    def close(self):
        """Close all connections in pool."""
        self.pool.closeall()
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connections on exit."""
        self.close()
