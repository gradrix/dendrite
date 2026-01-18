"""
StorageClient: PostgreSQL-backed persistent key-value storage for tools.

Provides namespaced storage with JSON values, TTL support, and connection pooling.
Replaces Redis for credentials, accumulated knowledge, and other persistent data.
"""

import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool
import logging

logger = logging.getLogger(__name__)


class StorageClient:
    """
    PostgreSQL-backed key-value storage for tools.
    
    Usage:
        storage = StorageClient()
        
        # Store credentials
        storage.set("strava", "credentials", {"access_token": "...", "refresh_token": "..."})
        
        # Get credentials
        creds = storage.get("strava", "credentials")
        
        # Store with TTL (expires in 1 hour)
        storage.set("weather", "cache", {"temp": 5}, ttl_seconds=3600)
        
        # Delete
        storage.delete("strava", "credentials")
        
        # List all keys in namespace
        keys = storage.keys("strava")
    """
    
    _pool: Optional[SimpleConnectionPool] = None
    
    def __init__(self,
                 host: Optional[str] = None,
                 database: Optional[str] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 min_connections: int = 1,
                 max_connections: int = 5):
        """Initialize with PostgreSQL connection."""
        self.host = host or os.getenv('POSTGRES_HOST', 'postgres')
        self.database = database or os.getenv('POSTGRES_DB', 'dendrite')
        self.user = user or os.getenv('POSTGRES_USER', 'dendrite')
        self.password = password or os.getenv('POSTGRES_PASSWORD', 'dendrite_pass')
        self.min_connections = min_connections
        self.max_connections = max_connections
        
        self._ensure_pool()
    
    def _ensure_pool(self):
        """Ensure connection pool exists (shared across instances)."""
        if StorageClient._pool is None:
            try:
                StorageClient._pool = SimpleConnectionPool(
                    self.min_connections,
                    self.max_connections,
                    host=self.host,
                    database=self.database,
                    user=self.user,
                    password=self.password
                )
                logger.debug(f"StorageClient pool created: {self.host}/{self.database}")
            except Exception as e:
                logger.error(f"Failed to create connection pool: {e}")
                raise
    
    def _get_connection(self):
        """Get connection from pool."""
        self._ensure_pool()
        return StorageClient._pool.getconn()
    
    def _release_connection(self, conn):
        """Return connection to pool."""
        if StorageClient._pool and conn:
            StorageClient._pool.putconn(conn)
    
    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        """
        Get value from storage.
        
        Args:
            namespace: Tool/domain namespace
            key: Key within namespace
            default: Default value if not found or expired
            
        Returns:
            Stored value (dict/list/primitive) or default
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT value FROM tool_storage
                    WHERE namespace = %s AND key = %s
                    AND (expires_at IS NULL OR expires_at > NOW())
                """, (namespace, key))
                
                row = cur.fetchone()
                if row:
                    return row['value']
                return default
                
        except Exception as e:
            logger.error(f"StorageClient.get error: {e}")
            return default
        finally:
            self._release_connection(conn)
    
    def set(self, namespace: str, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Set value in storage.
        
        Args:
            namespace: Tool/domain namespace
            key: Key within namespace
            value: Value to store (dict, list, or primitive - will be JSON serialized)
            ttl_seconds: Optional TTL in seconds
            
        Returns:
            True if successful
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                expires_at = None
                if ttl_seconds:
                    expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
                
                cur.execute("""
                    INSERT INTO tool_storage (namespace, key, value, expires_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (namespace, key)
                    DO UPDATE SET value = EXCLUDED.value, expires_at = EXCLUDED.expires_at
                """, (namespace, key, Json(value), expires_at))
                
                conn.commit()
                logger.debug(f"StorageClient.set: {namespace}:{key}")
                return True
                
        except Exception as e:
            logger.error(f"StorageClient.set error: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            self._release_connection(conn)
    
    def delete(self, namespace: str, key: str) -> bool:
        """
        Delete value from storage.
        
        Args:
            namespace: Tool/domain namespace
            key: Key within namespace
            
        Returns:
            True if deleted, False if not found
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM tool_storage
                    WHERE namespace = %s AND key = %s
                """, (namespace, key))
                
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
                
        except Exception as e:
            logger.error(f"StorageClient.delete error: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            self._release_connection(conn)
    
    def keys(self, namespace: str) -> List[str]:
        """
        List all keys in a namespace.
        
        Args:
            namespace: Tool/domain namespace
            
        Returns:
            List of keys (excluding expired)
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT key FROM tool_storage
                    WHERE namespace = %s
                    AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY key
                """, (namespace,))
                
                return [row[0] for row in cur.fetchall()]
                
        except Exception as e:
            logger.error(f"StorageClient.keys error: {e}")
            return []
        finally:
            self._release_connection(conn)
    
    def get_all(self, namespace: str) -> Dict[str, Any]:
        """
        Get all key-value pairs in a namespace.
        
        Args:
            namespace: Tool/domain namespace
            
        Returns:
            Dict of key -> value
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT key, value FROM tool_storage
                    WHERE namespace = %s
                    AND (expires_at IS NULL OR expires_at > NOW())
                """, (namespace,))
                
                return {row['key']: row['value'] for row in cur.fetchall()}
                
        except Exception as e:
            logger.error(f"StorageClient.get_all error: {e}")
            return {}
        finally:
            self._release_connection(conn)
    
    def update_nested(self, namespace: str, key: str, path: str, value: Any) -> bool:
        """
        Update a nested value using JSONB path.
        
        Useful for accumulating data like kudos_givers[athlete_id] = {...}
        
        Args:
            namespace: Tool/domain namespace
            key: Key within namespace
            path: JSON path (e.g., "12345" for top-level key, or "data.count")
            value: Value to set at path
            
        Returns:
            True if successful
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                # Build path array for jsonb_set
                path_parts = path.split('.')
                path_array = '{' + ','.join(path_parts) + '}'
                
                cur.execute("""
                    INSERT INTO tool_storage (namespace, key, value)
                    VALUES (%s, %s, jsonb_build_object(%s, %s::jsonb))
                    ON CONFLICT (namespace, key)
                    DO UPDATE SET value = jsonb_set(
                        COALESCE(tool_storage.value, '{}'::jsonb),
                        %s::text[],
                        %s::jsonb,
                        true
                    )
                """, (namespace, key, path_parts[0], Json(value), path_array, Json(value)))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"StorageClient.update_nested error: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            self._release_connection(conn)
    
    def cleanup_expired(self) -> int:
        """
        Delete all expired entries.
        
        Returns:
            Number of entries deleted
        """
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM tool_storage
                    WHERE expires_at IS NOT NULL AND expires_at < NOW()
                """)
                
                deleted = cur.rowcount
                conn.commit()
                logger.info(f"StorageClient: cleaned up {deleted} expired entries")
                return deleted
                
        except Exception as e:
            logger.error(f"StorageClient.cleanup_expired error: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            self._release_connection(conn)
    
    def close(self):
        """Close the connection pool."""
        if StorageClient._pool:
            StorageClient._pool.closeall()
            StorageClient._pool = None
            logger.debug("StorageClient pool closed")
