"""
Tool Version Manager - Complete Version History and Rollback

Tracks all versions of every tool with:
- Complete version history
- Performance metrics per version
- Deployment tracking
- Rollback to any version
- Version comparison and diffs
- Fast rollback triggers for critical issues
"""

import logging
import hashlib
import difflib
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


class ToolVersionManager:
    """
    Manage complete version history for all tools.
    
    Features:
    - Track every version with metadata
    - Enable rollback to any previous version
    - Compare versions and generate diffs
    - Detect breaking changes
    - Fast rollback triggers (don't wait for statistics)
    """
    
    def __init__(self, execution_store, tool_registry=None):
        """
        Initialize version manager.
        
        Args:
            execution_store: ExecutionStore for database operations
            tool_registry: ToolRegistry for tool operations (optional)
        """
        self.execution_store = execution_store
        self.tool_registry = tool_registry
    
    def create_version(self,
                      tool_name: str,
                      code: str,
                      created_by: str = 'human',
                      improvement_type: str = 'initial',
                      improvement_reason: str = None,
                      previous_version_id: int = None,
                      set_as_current: bool = True) -> int:
        """
        Create a new version of a tool.
        
        Args:
            tool_name: Name of the tool
            code: Tool source code
            created_by: 'human' or 'autonomous'
            improvement_type: 'initial', 'bugfix', 'enhancement', 'rollback'
            improvement_reason: Why this version was created
            previous_version_id: Previous version ID (for tracking lineage)
            set_as_current: Whether to set this as the current version
        
        Returns:
            version_id: ID of created version
        """
        try:
            logger.info(f"Creating new version for {tool_name}")
            
            # Calculate code hash for deduplication
            code_hash = self._calculate_hash(code)
            
            # Check if identical version already exists
            existing = self._find_version_by_hash(tool_name, code_hash)
            if existing:
                logger.info(f"   Identical version already exists: v{existing['version_number']}")
                if set_as_current:
                    self._set_current_version(existing['version_id'])
                return existing['version_id']
            
            # Get next version number
            version_number = self._get_next_version_number(tool_name)
            
            # If no previous version specified, get current version
            if previous_version_id is None and version_number > 1:
                current = self._get_current_version(tool_name)
                if current:
                    previous_version_id = current['version_id']
            
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    # Insert new version
                    cursor.execute("""
                        INSERT INTO tool_versions (
                            tool_name, version_number, code, code_hash,
                            created_by, improvement_type, improvement_reason,
                            previous_version_id, is_current
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING version_id
                    """, (
                        tool_name,
                        version_number,
                        code,
                        code_hash,
                        created_by,
                        improvement_type,
                        improvement_reason,
                        previous_version_id,
                        False  # Will be set later if needed
                    ))
                    
                    version_id = cursor.fetchone()[0]
                    
                    # Set as current if requested
                    if set_as_current:
                        self._set_current_version_internal(tool_name, version_id, cursor)
                    
                    # Create deployment record
                    cursor.execute("""
                        INSERT INTO version_deployments (
                            version_id, tool_name, deployed_by, deployment_type, reason
                        ) VALUES (%s, %s, %s, %s, %s)
                        RETURNING deployment_id
                    """, (
                        version_id,
                        tool_name,
                        created_by,
                        improvement_type,
                        improvement_reason
                    ))
                    
                    deployment_id = cursor.fetchone()[0]
                    
                    # Update version with deployment time
                    cursor.execute("""
                        UPDATE tool_versions
                        SET first_deployed_at = NOW(),
                            last_deployed_at = NOW(),
                            deployment_count = 1
                        WHERE version_id = %s
                    """, (version_id,))
                    
                    conn.commit()
                    
                    logger.info(f"   Created version {version_number} (ID: {version_id})")
                    logger.info(f"   Deployment ID: {deployment_id}")
                    
                    # Generate diff if there's a previous version
                    if previous_version_id:
                        self._generate_diff(previous_version_id, version_id)
                    
                    return version_id
                    
            finally:
                self.execution_store._release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error creating version: {e}")
            raise
    
    def rollback_to_version(self,
                           tool_name: str,
                           version_id: int,
                           reason: str = None,
                           deployed_by: str = 'autonomous') -> bool:
        """
        Rollback tool to a specific version.
        
        Args:
            tool_name: Name of the tool
            version_id: Version to rollback to
            reason: Reason for rollback
            deployed_by: Who initiated the rollback
        
        Returns:
            success: Whether rollback succeeded
        """
        try:
            logger.info(f"🔄 Rolling back {tool_name} to version {version_id}")
            logger.info(f"   Reason: {reason}")
            
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    # Get target version
                    cursor.execute("""
                        SELECT version_id, version_number, code
                        FROM tool_versions
                        WHERE version_id = %s AND tool_name = %s
                    """, (version_id, tool_name))
                    
                    target = cursor.fetchone()
                    if not target:
                        logger.error(f"   Version {version_id} not found")
                        return False
                    
                    target_version_id, target_version_number, target_code = target
                    
                    # Get current version to mark as rolled back
                    cursor.execute("""
                        SELECT version_id, version_number
                        FROM tool_versions
                        WHERE tool_name = %s AND is_current = TRUE
                    """, (tool_name,))
                    
                    current = cursor.fetchone()
                    if current:
                        current_version_id, current_version_number = current
                        
                        # Mark current version as rolled back
                        cursor.execute("""
                            UPDATE tool_versions
                            SET was_rolled_back = TRUE,
                                rolled_back_at = NOW(),
                                rollback_reason = %s,
                                replaced_by_version_id = %s
                            WHERE version_id = %s
                        """, (reason, target_version_id, current_version_id))
                        
                        # Close current deployment
                        cursor.execute("""
                            UPDATE version_deployments
                            SET undeployed_at = NOW(),
                                was_successful = FALSE
                            WHERE version_id = %s AND undeployed_at IS NULL
                        """, (current_version_id,))
                    
                    # Set target version as current
                    self._set_current_version_internal(tool_name, target_version_id, cursor)
                    
                    # Create new deployment record
                    cursor.execute("""
                        INSERT INTO version_deployments (
                            version_id, tool_name, deployed_by, 
                            deployment_type, reason
                        ) VALUES (%s, %s, %s, 'rollback', %s)
                    """, (target_version_id, tool_name, deployed_by, reason))
                    
                    # Update deployment count and time
                    cursor.execute("""
                        UPDATE tool_versions
                        SET deployment_count = deployment_count + 1,
                            last_deployed_at = NOW()
                        WHERE version_id = %s
                    """, (target_version_id,))
                    
                    conn.commit()
                    
                    logger.info(f"   ✅ Rolled back to version {target_version_number}")
                    
                    # Write code to filesystem if tool_registry available
                    if self.tool_registry:
                        self._write_version_to_filesystem(tool_name, target_code)
                        self.tool_registry.refresh()
                    
                    return True
                    
            finally:
                self.execution_store._release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error rolling back: {e}")
            return False
    
    def check_immediate_rollback_needed(self, tool_name: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check if immediate rollback is needed (don't wait for statistics).
        
        This detects critical patterns that indicate a broken deployment:
        - 3+ consecutive failures within 5 minutes
        - TypeError or AttributeError (signature change)
        - 100% failure rate with 5+ attempts
        
        Args:
            tool_name: Name of tool to check
        
        Returns:
            (needs_rollback, reason, details)
        """
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    # Get last 10 executions in last 5 minutes
                    cursor.execute("""
                        SELECT 
                            executed_at,
                            success,
                            error
                        FROM tool_executions
                        WHERE tool_name = %s
                          AND executed_at > NOW() - INTERVAL '5 minutes'
                        ORDER BY executed_at DESC
                        LIMIT 10
                    """, (tool_name,))
                    
                    recent_execs = cursor.fetchall()
                    
                    if len(recent_execs) < 3:
                        return False, None, None
                    
                    # Check for consecutive failures
                    consecutive_failures = 0
                    failure_errors = []
                    
                    for exec_time, success, error in recent_execs:
                        if not success:
                            consecutive_failures += 1
                            failure_errors.append(error)
                        else:
                            break  # Not consecutive anymore
                    
                    # Pattern 1: 3+ consecutive failures
                    if consecutive_failures >= 3:
                        # Check error types
                        signature_errors = [e for e in failure_errors 
                                          if e and ('TypeError' in e or 'AttributeError' in e)]
                        
                        if signature_errors:
                            return True, 'signature_change', {
                                'consecutive_failures': consecutive_failures,
                                'sample_error': signature_errors[0],
                                'pattern': 'Parameter signature changed - incompatible with existing code'
                            }
                        
                        # Complete breakage
                        return True, 'consecutive_failures', {
                            'consecutive_failures': consecutive_failures,
                            'sample_error': failure_errors[0] if failure_errors else None,
                            'pattern': f'{consecutive_failures} consecutive failures indicates broken deployment'
                        }
                    
                    # Pattern 2: 100% failure rate with 5+ attempts
                    if len(recent_execs) >= 5:
                        all_failed = all(not success for _, success, _ in recent_execs)
                        if all_failed:
                            return True, 'complete_failure', {
                                'total_attempts': len(recent_execs),
                                'pattern': '100% failure rate - tool completely broken'
                            }
                    
                    return False, None, None
                    
            finally:
                self.execution_store._release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error checking immediate rollback: {e}")
            return False, None, None
    
    def get_version_history(self, tool_name: str, limit: int = 20) -> List[Dict]:
        """
        Get version history for a tool.
        
        Args:
            tool_name: Name of tool
            limit: Maximum versions to return
        
        Returns:
            List of version dictionaries
        """
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT * FROM tool_version_history
                        WHERE tool_name = %s
                        ORDER BY version_number DESC
                        LIMIT %s
                    """, (tool_name, limit))
                    
                    columns = [desc[0] for desc in cursor.description]
                    versions = []
                    
                    for row in cursor.fetchall():
                        version = dict(zip(columns, row))
                        versions.append(version)
                    
                    return versions
                    
            finally:
                self.execution_store._release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error getting version history: {e}")
            return []
    
    def compare_versions(self, tool_name: str, from_version_id: int, to_version_id: int) -> Dict:
        """
        Compare two versions of a tool.
        
        Args:
            tool_name: Name of tool
            from_version_id: Source version
            to_version_id: Target version
        
        Returns:
            Comparison dictionary with diff, metrics, etc.
        """
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    # Get both versions
                    cursor.execute("""
                        SELECT version_id, version_number, code, success_rate, 
                               total_executions, created_at, created_by
                        FROM tool_versions
                        WHERE version_id IN (%s, %s) AND tool_name = %s
                    """, (from_version_id, to_version_id, tool_name))
                    
                    versions = {}
                    for row in cursor.fetchall():
                        vid, vnum, code, sr, te, ca, cb = row
                        versions[vid] = {
                            'version_id': vid,
                            'version_number': vnum,
                            'code': code,
                            'success_rate': sr,
                            'total_executions': te,
                            'created_at': ca,
                            'created_by': cb
                        }
                    
                    if len(versions) != 2:
                        return {'error': 'One or both versions not found'}
                    
                    from_ver = versions[from_version_id]
                    to_ver = versions[to_version_id]
                    
                    # Check if diff already exists
                    cursor.execute("""
                        SELECT unified_diff, lines_added, lines_removed, 
                               breaking_changes, breaking_change_details
                        FROM version_diffs
                        WHERE from_version_id = %s AND to_version_id = %s
                    """, (from_version_id, to_version_id))
                    
                    existing_diff = cursor.fetchone()
                    if existing_diff:
                        unified_diff, lines_added, lines_removed, breaking, breaking_details = existing_diff
                    else:
                        # Generate diff
                        unified_diff, lines_added, lines_removed = self._compute_diff(
                            from_ver['code'], 
                            to_ver['code']
                        )
                        
                        # Detect breaking changes
                        breaking, breaking_details = self._detect_breaking_changes(
                            from_ver['code'],
                            to_ver['code']
                        )
                        
                        # Store diff
                        cursor.execute("""
                            INSERT INTO version_diffs (
                                tool_name, from_version_id, to_version_id,
                                unified_diff, lines_added, lines_removed,
                                breaking_changes, breaking_change_details
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            tool_name, from_version_id, to_version_id,
                            unified_diff, lines_added, lines_removed,
                            breaking, breaking_details
                        ))
                        conn.commit()
                    
                    return {
                        'tool_name': tool_name,
                        'from_version': from_ver,
                        'to_version': to_ver,
                        'diff': {
                            'unified_diff': unified_diff,
                            'lines_added': lines_added,
                            'lines_removed': lines_removed,
                            'breaking_changes': breaking,
                            'breaking_change_details': breaking_details
                        },
                        'metrics_comparison': {
                            'success_rate_change': (to_ver['success_rate'] or 0) - (from_ver['success_rate'] or 0),
                            'execution_count_change': (to_ver['total_executions'] or 0) - (from_ver['total_executions'] or 0)
                        }
                    }
                    
            finally:
                self.execution_store._release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            return {'error': str(e)}
    
    def update_version_metrics(self, tool_name: str):
        """
        Update performance metrics for current version from execution history.
        
        Args:
            tool_name: Name of tool
        """
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    # Get current version
                    cursor.execute("""
                        SELECT version_id, last_deployed_at
                        FROM tool_versions
                        WHERE tool_name = %s AND is_current = TRUE
                    """, (tool_name,))
                    
                    result = cursor.fetchone()
                    if not result:
                        return
                    
                    version_id, deployed_at = result
                    
                    # Get metrics since deployment
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE success = TRUE) as successes,
                            AVG(duration_ms) as avg_duration
                        FROM tool_executions
                        WHERE tool_name = %s
                          AND executed_at >= %s
                    """, (tool_name, deployed_at))
                    
                    metrics = cursor.fetchone()
                    total, successes, avg_duration = metrics
                    
                    if total > 0:
                        success_rate = successes / total
                        
                        # Update version
                        cursor.execute("""
                            UPDATE tool_versions
                            SET success_rate = %s,
                                total_executions = %s,
                                successful_executions = %s,
                                failed_executions = %s,
                                avg_duration_ms = %s
                            WHERE version_id = %s
                        """, (
                            success_rate,
                            total,
                            successes,
                            total - successes,
                            avg_duration,
                            version_id
                        ))
                        
                        conn.commit()
                        
            finally:
                self.execution_store._release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error updating version metrics: {e}")
    
    def _calculate_hash(self, code: str) -> str:
        """Calculate SHA-256 hash of code."""
        return hashlib.sha256(code.encode('utf-8')).hexdigest()
    
    def _find_version_by_hash(self, tool_name: str, code_hash: str) -> Optional[Dict]:
        """Find existing version with same code hash."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT version_id, version_number
                        FROM tool_versions
                        WHERE tool_name = %s AND code_hash = %s
                        ORDER BY version_number DESC
                        LIMIT 1
                    """, (tool_name, code_hash))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'version_id': result[0],
                            'version_number': result[1]
                        }
                    return None
                    
            finally:
                self.execution_store._release_connection(conn)
        except:
            return None
    
    def _get_next_version_number(self, tool_name: str) -> int:
        """Get next version number for tool."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT COALESCE(MAX(version_number), 0) + 1
                        FROM tool_versions
                        WHERE tool_name = %s
                    """, (tool_name,))
                    
                    return cursor.fetchone()[0]
                    
            finally:
                self.execution_store._release_connection(conn)
        except:
            return 1
    
    def _get_current_version(self, tool_name: str) -> Optional[Dict]:
        """Get current version info."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT version_id, version_number, code
                        FROM tool_versions
                        WHERE tool_name = %s AND is_current = TRUE
                    """, (tool_name,))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'version_id': result[0],
                            'version_number': result[1],
                            'code': result[2]
                        }
                    return None
                    
            finally:
                self.execution_store._release_connection(conn)
        except:
            return None
    
    def _set_current_version(self, version_id: int):
        """Set a version as current (standalone)."""
        conn = self.execution_store._get_connection()
        try:
            with conn.cursor() as cursor:
                # Get tool name
                cursor.execute("""
                    SELECT tool_name FROM tool_versions WHERE version_id = %s
                """, (version_id,))
                
                tool_name = cursor.fetchone()[0]
                self._set_current_version_internal(tool_name, version_id, cursor)
                conn.commit()
        finally:
            self.execution_store._release_connection(conn)
    
    def _set_current_version_internal(self, tool_name: str, version_id: int, cursor):
        """Set a version as current (within transaction)."""
        # Unset all versions
        cursor.execute("""
            UPDATE tool_versions
            SET is_current = FALSE
            WHERE tool_name = %s
        """, (tool_name,))
        
        # Set this version
        cursor.execute("""
            UPDATE tool_versions
            SET is_current = TRUE
            WHERE version_id = %s
        """, (version_id,))
    
    def _generate_diff(self, from_version_id: int, to_version_id: int):
        """Generate and store diff between versions."""
        try:
            # This will be called by compare_versions which handles the full logic
            pass
        except Exception as e:
            logger.error(f"Error generating diff: {e}")
    
    def _compute_diff(self, from_code: str, to_code: str) -> Tuple[str, int, int]:
        """Compute unified diff between two code strings."""
        from_lines = from_code.splitlines(keepends=True)
        to_lines = to_code.splitlines(keepends=True)
        
        diff = difflib.unified_diff(from_lines, to_lines, lineterm='')
        unified_diff = '\n'.join(diff)
        
        # Count lines
        lines_added = unified_diff.count('\n+') - unified_diff.count('\n+++')
        lines_removed = unified_diff.count('\n-') - unified_diff.count('\n---')
        
        return unified_diff, lines_added, lines_removed
    
    def _detect_breaking_changes(self, from_code: str, to_code: str) -> Tuple[bool, List[str]]:
        """Detect breaking changes in code."""
        breaking = False
        details = []
        
        # Extract function signatures
        from_sigs = self._extract_signatures(from_code)
        to_sigs = self._extract_signatures(to_code)
        
        # Check for removed functions
        removed = from_sigs - to_sigs
        if removed:
            breaking = True
            details.append(f"Removed methods/functions: {', '.join(removed)}")
        
        # Check for parameter changes (basic check)
        if 'def execute(' in from_code and 'def execute(' in to_code:
            from_params = self._extract_params(from_code, 'execute')
            to_params = self._extract_params(to_code, 'execute')
            
            if from_params != to_params:
                breaking = True
                details.append(f"execute() signature changed: {from_params} → {to_params}")
        
        return breaking, details
    
    def _extract_signatures(self, code: str) -> set:
        """Extract method/function signatures from code."""
        pattern = r'def\s+(\w+)\s*\('
        return set(re.findall(pattern, code))
    
    def _extract_params(self, code: str, func_name: str) -> str:
        """Extract parameters for a specific function."""
        pattern = f'def\\s+{func_name}\\s*\\(([^)]*)\\)'
        match = re.search(pattern, code)
        return match.group(1).strip() if match else ''
    
    def _write_version_to_filesystem(self, tool_name: str, code: str):
        """Write version code to filesystem."""
        try:
            import os
            tool_path = os.path.join('neural_engine', 'tools', f'{tool_name}.py')
            with open(tool_path, 'w') as f:
                f.write(code)
            logger.info(f"   Wrote version to {tool_path}")
        except Exception as e:
            logger.error(f"Error writing to filesystem: {e}")
