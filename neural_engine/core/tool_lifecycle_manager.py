"""
Tool Lifecycle Manager

Handles autonomous synchronization between filesystem and database.
Provides smart alerts and auto-cleanup for tool management.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ToolLifecycleManager:
    """
    Manages tool lifecycle with autonomous sync between filesystem and database.
    
    Responsibilities:
    - Detect when tools are deleted from filesystem
    - Update database status accordingly
    - Alert if useful tools are deleted (accident prevention)
    - Auto-cleanup old deleted tools
    - Reconcile filesystem and database state
    """
    
    def __init__(self, tool_registry, execution_store, tools_dir: str = "neural_engine/tools"):
        """
        Initialize lifecycle manager.
        
        Args:
            tool_registry: ToolRegistry instance
            execution_store: ExecutionStore instance
            tools_dir: Directory where tools are stored
        """
        self.registry = tool_registry
        self.store = execution_store
        self.tools_dir = Path(tools_dir)
    
    def sync_and_reconcile(self) -> Dict[str, Any]:
        """
        Synchronize filesystem and database state.
        
        Returns:
            Report with newly_deleted, restored, and new_manual_tools
        """
        logger.info("Starting tool lifecycle sync...")
        
        fs_tools = self._scan_filesystem()
        db_tools = self._get_database_tools()
        
        report = {
            'newly_deleted': [],
            'restored': [],
            'new_manual_tools': [],
            'alerts': []
        }
        
        # Find deleted tools (in DB as active, not in filesystem)
        for tool_name in db_tools:
            if tool_name not in fs_tools and db_tools[tool_name]['status'] == 'active':
                logger.info(f"Tool deleted from filesystem: {tool_name}")
                
                # Check if this was a useful tool
                alert = self._analyze_deleted_tool(tool_name)
                if alert['alert']:
                    report['alerts'].append(alert)
                
                # Mark as deleted in database
                self.store.mark_tool_status(
                    tool_name=tool_name,
                    status='deleted',
                    reason=alert.get('reason', 'file_not_found')
                )
                report['newly_deleted'].append(tool_name)
        
        # Find restored tools (in DB as deleted, now back in filesystem)
        for tool_name in db_tools:
            if tool_name in fs_tools and db_tools[tool_name]['status'] == 'deleted':
                logger.info(f"Tool restored to filesystem: {tool_name}")
                self.store.mark_tool_status(
                    tool_name=tool_name,
                    status='active',
                    reason='file_restored'
                )
                report['restored'].append(tool_name)
        
        # Find new manual tools (in filesystem, not in DB)
        for tool_name in fs_tools:
            if tool_name not in db_tools:
                logger.info(f"New manual tool detected: {tool_name}")
                report['new_manual_tools'].append(tool_name)
                # Note: We don't auto-create DB records for manual tools
                # They'll be recorded when first executed
        
        logger.info(f"Sync complete. Deleted: {len(report['newly_deleted'])}, "
                   f"Restored: {len(report['restored'])}, "
                   f"New manual: {len(report['new_manual_tools'])}")
        
        return report
    
    def _scan_filesystem(self) -> Set[str]:
        """
        Scan filesystem for tool files.
        
        Returns:
            Set of tool names (without .py extension)
        """
        if not self.tools_dir.exists():
            logger.warning(f"Tools directory not found: {self.tools_dir}")
            return set()
        
        tools = set()
        for file_path in self.tools_dir.glob("*.py"):
            # Skip __init__.py and base_tool.py
            if file_path.name in ('__init__.py', 'base_tool.py'):
                continue
            
            # Extract tool name (remove _tool.py suffix if present)
            tool_name = file_path.stem
            if tool_name.endswith('_tool'):
                tool_name = tool_name[:-5]  # Remove '_tool' suffix
            
            tools.add(tool_name)
        
        return tools
    
    def _get_database_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tools from database with their status.
        
        Returns:
            Dict mapping tool_name to {status, created_at, ...}
        """
        try:
            # Query tool_creation_events for all tools
            result = self.store.conn.execute("""
                SELECT tool_name, status, created_at, status_changed_at
                FROM tool_creation_events
                WHERE status IN ('active', 'deleted')
                ORDER BY created_at DESC
            """)
            
            tools = {}
            for row in result:
                tool_name = row[0]
                # Only keep most recent entry per tool
                if tool_name not in tools:
                    tools[tool_name] = {
                        'status': row[1] or 'active',  # Default to active if NULL
                        'created_at': row[2],
                        'status_changed_at': row[3]
                    }
            
            return tools
        except Exception as e:
            logger.error(f"Error querying database tools: {e}")
            return {}
    
    def _analyze_deleted_tool(self, tool_name: str) -> Dict[str, Any]:
        """
        Analyze if a deleted tool was valuable (accident prevention).
        
        Args:
            tool_name: Name of the deleted tool
        
        Returns:
            Alert dict with severity, reason, and suggestion
        """
        try:
            stats = self.store.get_tool_statistics(tool_name)
            
            if not stats or stats.get('total_executions', 0) == 0:
                return {
                    'alert': False,
                    'tool_name': tool_name,
                    'reason': 'never_used'
                }
            
            total_uses = stats.get('total_executions', 0)
            success_rate = stats.get('success_rate', 0)
            last_used = stats.get('last_used')
            
            # High success rate + many uses = valuable tool
            if success_rate > 0.85 and total_uses > 20:
                return {
                    'alert': True,
                    'tool_name': tool_name,
                    'severity': 'warning',
                    'reason': 'useful_tool_deleted',
                    'stats': {
                        'total_uses': total_uses,
                        'success_rate': success_rate,
                        'last_used': str(last_used) if last_used else None
                    },
                    'suggestion': 'Consider restoring from backup. This tool had high success rate.',
                    'backup_location': str(self.tools_dir / 'backups' / f'{tool_name}_tool.py')
                }
            
            # Recently used = might be accident
            if last_used:
                days_since_use = (datetime.now() - last_used).days
                if days_since_use < 7:
                    return {
                        'alert': True,
                        'tool_name': tool_name,
                        'severity': 'info',
                        'reason': 'recently_used',
                        'stats': {
                            'total_uses': total_uses,
                            'days_since_use': days_since_use
                        },
                        'suggestion': f'Tool was used {days_since_use} days ago. Was deletion intentional?'
                    }
            
            # Low usage or low success = safe to delete
            return {
                'alert': False,
                'tool_name': tool_name,
                'reason': 'cleanup_ok',
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"Error analyzing deleted tool {tool_name}: {e}")
            return {
                'alert': False,
                'tool_name': tool_name,
                'reason': 'analysis_failed',
                'error': str(e)
            }
    
    def maintenance(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run periodic maintenance tasks.
        
        Tasks:
        - Sync filesystem and database
        - Auto-cleanup old deleted tools
        - Detect duplicate tools
        
        Args:
            dry_run: If True, only report what would be done without making changes
        
        Returns:
            Maintenance report
        """
        logger.info("Starting tool lifecycle maintenance...")
        
        report = {
            'sync_report': None,
            'cleanup_report': None,
            'duplicate_report': None,
            'timestamp': datetime.now().isoformat()
        }
        
        # 1. Sync filesystem and database
        report['sync_report'] = self.sync_and_reconcile()
        
        # 2. Auto-cleanup old deleted tools
        if not dry_run:
            report['cleanup_report'] = self._auto_cleanup_old_tools()
        else:
            report['cleanup_report'] = self._preview_cleanup()
        
        # 3. TODO: Detect duplicate tools (Phase 9e - needs embeddings)
        report['duplicate_report'] = {'status': 'not_implemented'}
        
        logger.info("Maintenance complete.")
        return report
    
    def _auto_cleanup_old_tools(self, days_threshold: int = 90) -> Dict[str, Any]:
        """
        Auto-archive old deleted tools based on usage patterns.
        
        Policy:
        - Deleted >90 days + <10 uses → Archive metadata
        - Deleted >90 days + ≥10 uses → Keep metadata (learning value)
        - Deleted <90 days → Keep everything
        
        Args:
            days_threshold: Days before considering tool for cleanup
        
        Returns:
            Cleanup report
        """
        try:
            # Find all deleted tools
            result = self.store.conn.execute("""
                SELECT tool_name, status_changed_at
                FROM tool_creation_events
                WHERE status = 'deleted'
            """)
            
            archived = []
            kept = []
            
            for row in result:
                tool_name = row[0]
                status_changed_at = row[1]
                
                if not status_changed_at:
                    continue  # Skip if no deletion date
                
                # Handle both datetime and string types
                if isinstance(status_changed_at, str):
                    status_changed_at = datetime.fromisoformat(status_changed_at)
                
                days_deleted = (datetime.now() - status_changed_at).days
                
                if days_deleted < days_threshold:
                    kept.append({
                        'tool_name': tool_name,
                        'reason': f'deleted_recently ({days_deleted} days)',
                        'days_deleted': days_deleted
                    })
                    continue
                
                # Check usage stats
                stats = self.store.get_tool_statistics(tool_name)
                total_uses = stats.get('total_executions', 0) if stats else 0
                
                if total_uses < 10:
                    # Low usage, safe to archive
                    self.store.mark_tool_status(
                        tool_name=tool_name,
                        status='archived',
                        reason=f'auto_cleanup: {days_deleted} days old, {total_uses} uses'
                    )
                    archived.append({
                        'tool_name': tool_name,
                        'days_deleted': days_deleted,
                        'total_uses': total_uses,
                        'reason': 'low_usage'
                    })
                else:
                    # Keep for learning value
                    kept.append({
                        'tool_name': tool_name,
                        'reason': f'high_usage ({total_uses} uses)',
                        'total_uses': total_uses
                    })
            
            return {
                'archived': archived,
                'kept': kept,
                'total_archived': len(archived),
                'total_kept': len(kept)
            }
            
        except Exception as e:
            logger.error(f"Error during auto-cleanup: {e}")
            return {
                'error': str(e),
                'archived': [],
                'kept': []
            }
    
    def _preview_cleanup(self, days_threshold: int = 90) -> Dict[str, Any]:
        """
        Preview what would be cleaned up (dry run).
        
        Args:
            days_threshold: Days before considering tool for cleanup
        
        Returns:
            Preview report
        """
        try:
            result = self.store.conn.execute("""
                SELECT tool_name, status_changed_at
                FROM tool_creation_events
                WHERE status = 'deleted'
            """)
            
            would_archive = []
            would_keep = []
            
            for row in result:
                tool_name = row[0]
                status_changed_at = row[1]
                
                if not status_changed_at:
                    continue
                
                # Handle both datetime and string types
                if isinstance(status_changed_at, str):
                    status_changed_at = datetime.fromisoformat(status_changed_at)
                
                days_deleted = (datetime.now() - status_changed_at).days
                
                if days_deleted < days_threshold:
                    would_keep.append({
                        'tool_name': tool_name,
                        'reason': f'deleted_recently ({days_deleted} days)'
                    })
                    continue
                
                stats = self.store.get_tool_statistics(tool_name)
                total_uses = stats.get('total_executions', 0) if stats else 0
                
                if total_uses < 10:
                    would_archive.append({
                        'tool_name': tool_name,
                        'days_deleted': days_deleted,
                        'total_uses': total_uses
                    })
                else:
                    would_keep.append({
                        'tool_name': tool_name,
                        'reason': f'high_usage ({total_uses} uses)'
                    })
            
            return {
                'preview': True,
                'would_archive': would_archive,
                'would_keep': would_keep,
                'total_would_archive': len(would_archive),
                'total_would_keep': len(would_keep)
            }
            
        except Exception as e:
            logger.error(f"Error during cleanup preview: {e}")
            return {
                'error': str(e),
                'would_archive': [],
                'would_keep': []
            }
    
    def restore_tool(self, tool_name: str, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Restore a deleted tool from backup.
        
        Args:
            tool_name: Name of tool to restore
            backup_dir: Directory containing backups (default: neural_engine/tools/backups)
        
        Returns:
            Restoration report
        """
        if backup_dir is None:
            backup_dir = str(self.tools_dir / 'backups')
        
        backup_path = Path(backup_dir) / f'{tool_name}_tool.py'
        target_path = self.tools_dir / f'{tool_name}_tool.py'
        
        if not backup_path.exists():
            return {
                'success': False,
                'error': f'Backup not found: {backup_path}'
            }
        
        try:
            # Copy from backup
            import shutil
            shutil.copy2(backup_path, target_path)
            
            # Update database status
            self.store.mark_tool_status(
                tool_name=tool_name,
                status='active',
                reason='restored_from_backup'
            )
            
            # Refresh registry
            self.registry.refresh()
            
            return {
                'success': True,
                'tool_name': tool_name,
                'restored_from': str(backup_path),
                'restored_to': str(target_path)
            }
            
        except Exception as e:
            logger.error(f"Error restoring tool {tool_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
