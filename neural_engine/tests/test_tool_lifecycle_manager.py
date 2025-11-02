"""
Tests for Tool Lifecycle Manager
Phase 9d: Verify autonomous sync between filesystem and database
"""

import os
import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from neural_engine.core.tool_lifecycle_manager import ToolLifecycleManager


class TestToolLifecycleManager:
    """Test tool lifecycle management functionality."""
    
    @pytest.fixture
    def mock_tool_registry(self):
        """Create mock tool registry."""
        registry = Mock()
        registry.refresh = Mock()
        return registry
    
    @pytest.fixture
    def mock_execution_store(self):
        """Create mock execution store."""
        store = Mock()
        store.mark_tool_status = Mock()
        store.get_tool_statistics = Mock()
        
        # Mock connection pool pattern
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor = Mock(return_value=mock_cursor)
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[])
        
        store._get_connection = Mock(return_value=mock_conn)
        store._release_connection = Mock()
        
        # Store references for test access
        store._mock_conn = mock_conn
        store._mock_cursor = mock_cursor
        
        return store
    
    @pytest.fixture
    def temp_tools_dir(self):
        """Create temporary tools directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def lifecycle_manager(self, mock_tool_registry, mock_execution_store, temp_tools_dir):
        """Create ToolLifecycleManager with mocks."""
        return ToolLifecycleManager(
            tool_registry=mock_tool_registry,
            execution_store=mock_execution_store,
            tools_dir=temp_tools_dir
        )
    
    def test_scan_filesystem_empty_directory(self, lifecycle_manager):
        """Test scanning empty tools directory."""
        tools = lifecycle_manager._scan_filesystem()
        assert tools == set()
    
    def test_scan_filesystem_with_tools(self, lifecycle_manager, temp_tools_dir):
        """Test scanning directory with tool files."""
        # Create some tool files
        tool_files = ['hello_world_tool.py', 'calculator_tool.py', 'weather_tool.py']
        for filename in tool_files:
            (Path(temp_tools_dir) / filename).write_text("# Tool code")
        
        # Also create files to ignore
        (Path(temp_tools_dir) / '__init__.py').write_text("")
        (Path(temp_tools_dir) / 'base_tool.py').write_text("# Base")
        
        tools = lifecycle_manager._scan_filesystem()
        
        # Should find 3 tools, ignoring __init__ and base_tool
        assert len(tools) == 3
        assert 'hello_world' in tools  # _tool suffix removed
        assert 'calculator' in tools
        assert 'weather' in tools
    
    def test_get_database_tools(self, lifecycle_manager, mock_execution_store):
        """Test getting tools from database."""
        # Mock database query result
        mock_result = [
            ('hello_world', 'active', datetime.now(), None),
            ('calculator', 'deleted', datetime.now(), datetime.now()),
            ('weather', 'active', datetime.now(), None)
        ]
        mock_execution_store._mock_cursor.fetchall.return_value = mock_result
        
        db_tools = lifecycle_manager._get_database_tools()
        
        assert len(db_tools) == 3
        assert 'hello_world' in db_tools
        assert db_tools['hello_world']['status'] == 'active'
        assert db_tools['calculator']['status'] == 'deleted'
    
    def test_detect_newly_deleted_tool(self, lifecycle_manager, mock_execution_store, temp_tools_dir):
        """Test detection of tool deleted from filesystem."""
        # Setup: Tool in DB but not in filesystem
        mock_result = [
            ('deleted_tool', 'active', datetime.now(), None)
        ]
        mock_execution_store._mock_cursor.fetchall.return_value = mock_result
        mock_execution_store.get_tool_statistics.return_value = {
            'total_executions': 5,
            'success_rate': 0.6
        }
        
        # Run sync
        report = lifecycle_manager.sync_and_reconcile()
        
        # Should detect deleted tool
        assert len(report['newly_deleted']) == 1
        assert 'deleted_tool' in report['newly_deleted']
        
        # Should mark as deleted in DB
        mock_execution_store.mark_tool_status.assert_called()
        call_args = mock_execution_store.mark_tool_status.call_args
        assert call_args[1]['tool_name'] == 'deleted_tool'
        assert call_args[1]['status'] == 'deleted'
    
    def test_detect_restored_tool(self, lifecycle_manager, mock_execution_store, temp_tools_dir):
        """Test detection of tool restored to filesystem."""
        # Create tool file
        (Path(temp_tools_dir) / 'restored_tool.py').write_text("# Restored")
        
        # Setup: Tool marked as deleted in DB but exists in filesystem
        mock_result = [
            ('restored', 'deleted', datetime.now() - timedelta(days=1), datetime.now())
        ]
        mock_execution_store._mock_cursor.fetchall.return_value = mock_result
        
        # Run sync
        report = lifecycle_manager.sync_and_reconcile()
        
        # Should detect restored tool
        assert len(report['restored']) == 1
        assert 'restored' in report['restored']
        
        # Should mark as active in DB
        mock_execution_store.mark_tool_status.assert_called()
        call_args = mock_execution_store.mark_tool_status.call_args
        assert call_args[1]['tool_name'] == 'restored'
        assert call_args[1]['status'] == 'active'
    
    def test_detect_new_manual_tool(self, lifecycle_manager, mock_execution_store, temp_tools_dir):
        """Test detection of manually created tool file."""
        # Create tool file
        (Path(temp_tools_dir) / 'manual_tool.py').write_text("# Manual")
        
        # Setup: No tools in DB
        mock_execution_store._mock_cursor.fetchall.return_value = []
        
        # Run sync
        report = lifecycle_manager.sync_and_reconcile()
        
        # Should detect new manual tool
        assert len(report['new_manual_tools']) == 1
        assert 'manual' in report['new_manual_tools']
    
    def test_analyze_deleted_tool_never_used(self, lifecycle_manager, mock_execution_store):
        """Test analysis of deleted tool that was never used."""
        mock_execution_store.get_tool_statistics.return_value = None
        
        alert = lifecycle_manager._analyze_deleted_tool('unused_tool')
        
        assert alert['alert'] is False
        assert alert['reason'] == 'never_used'
    
    def test_analyze_deleted_tool_useful(self, lifecycle_manager, mock_execution_store):
        """Test analysis of deleted tool with high success rate."""
        mock_execution_store.get_tool_statistics.return_value = {
            'total_executions': 50,
            'success_rate': 0.90,
            'last_used': datetime.now()
        }
        
        alert = lifecycle_manager._analyze_deleted_tool('useful_tool')
        
        assert alert['alert'] is True
        assert alert['severity'] == 'warning'
        assert alert['reason'] == 'useful_tool_deleted'
        assert 'backup_location' in alert
    
    def test_analyze_deleted_tool_recently_used(self, lifecycle_manager, mock_execution_store):
        """Test analysis of deleted tool used recently."""
        mock_execution_store.get_tool_statistics.return_value = {
            'total_executions': 10,
            'success_rate': 0.70,
            'last_used': datetime.now() - timedelta(days=3)
        }
        
        alert = lifecycle_manager._analyze_deleted_tool('recent_tool')
        
        assert alert['alert'] is True
        assert alert['severity'] == 'info'
        assert alert['reason'] == 'recently_used'
        assert alert['stats']['days_since_use'] == 3
    
    def test_analyze_deleted_tool_low_usage(self, lifecycle_manager, mock_execution_store):
        """Test analysis of deleted tool with low usage - safe to delete."""
        mock_execution_store.get_tool_statistics.return_value = {
            'total_executions': 3,
            'success_rate': 0.33,
            'last_used': datetime.now() - timedelta(days=30)
        }
        
        alert = lifecycle_manager._analyze_deleted_tool('junk_tool')
        
        assert alert['alert'] is False
        assert alert['reason'] == 'cleanup_ok'
    
    def test_auto_cleanup_old_tools(self, lifecycle_manager, mock_execution_store):
        """Test automatic cleanup of old deleted tools."""
        # Setup: Mix of old/new, high/low usage deleted tools
        old_date = datetime.now() - timedelta(days=100)
        recent_date = datetime.now() - timedelta(days=10)
        
        mock_result = [
            ('old_junk', old_date),  # Should archive
            ('old_useful', old_date),  # Should keep
            ('recent_junk', recent_date)  # Should keep (too recent)
        ]
        mock_execution_store._mock_cursor.fetchall.return_value = mock_result
        
        # Mock statistics
        def get_stats(tool_name):
            stats = {
                'old_junk': {'total_executions': 2},
                'old_useful': {'total_executions': 100},
                'recent_junk': {'total_executions': 1}
            }
            return stats.get(tool_name, {})
        
        mock_execution_store.get_tool_statistics.side_effect = get_stats
        
        # Run cleanup
        report = lifecycle_manager._auto_cleanup_old_tools(days_threshold=90)
        
        # Should archive old_junk only
        assert len(report['archived']) == 1
        assert report['archived'][0]['tool_name'] == 'old_junk'
        
        # Should keep old_useful and recent_junk
        assert len(report['kept']) == 2
    
    def test_preview_cleanup_dry_run(self, lifecycle_manager, mock_execution_store):
        """Test cleanup preview without making changes."""
        old_date = datetime.now() - timedelta(days=100)
        
        mock_result = [
            ('would_archive', old_date)
        ]
        mock_execution_store._mock_cursor.fetchall.return_value = mock_result
        mock_execution_store.get_tool_statistics.return_value = {'total_executions': 2}
        
        report = lifecycle_manager._preview_cleanup(days_threshold=90)
        
        # Should preview without archiving
        assert report['preview'] is True
        assert len(report['would_archive']) == 1
        assert report['would_archive'][0]['tool_name'] == 'would_archive'
        
        # Should not actually mark as archived
        mock_execution_store.mark_tool_status.assert_not_called()
    
    def test_maintenance_workflow(self, lifecycle_manager, mock_execution_store, temp_tools_dir):
        """Test full maintenance workflow."""
        # Create some tool files
        (Path(temp_tools_dir) / 'active_tool.py').write_text("# Active")
        
        # Setup DB state - mock needs to return different results for different queries
        # First call: sync_and_reconcile calls _get_database_tools (tool_name, status, created_at, status_changed_at)
        # Second call: _preview_cleanup queries deleted tools (tool_name, status_changed_at)
        mock_sync_result = [
            ('active', 'active', datetime.now(), None),
            ('deleted', 'deleted', datetime.now() - timedelta(days=100), datetime.now() - timedelta(days=100))
        ]
        mock_cleanup_result = [
            ('deleted', datetime.now() - timedelta(days=100))
        ]
        mock_execution_store._mock_cursor.fetchall.side_effect = [mock_sync_result, mock_cleanup_result]
        mock_execution_store.get_tool_statistics.return_value = {'total_executions': 2}
        
        # Run maintenance
        report = lifecycle_manager.maintenance(dry_run=True)
        
        # Should include all sections
        assert 'sync_report' in report
        assert 'cleanup_report' in report
        assert 'duplicate_report' in report
        assert 'timestamp' in report
        
        # Cleanup should be preview only
        assert report['cleanup_report']['preview'] is True
    
    def test_restore_tool_from_backup(self, lifecycle_manager, mock_execution_store, mock_tool_registry, temp_tools_dir):
        """Test restoring deleted tool from backup."""
        # Create backup directory with tool
        backup_dir = Path(temp_tools_dir) / 'backups'
        backup_dir.mkdir()
        backup_file = backup_dir / 'restored_tool.py'
        backup_file.write_text("# Backed up code")
        
        # Restore tool
        result = lifecycle_manager.restore_tool('restored', backup_dir=str(backup_dir))
        
        assert result['success'] is True
        assert result['tool_name'] == 'restored'
        
        # Should update DB status
        mock_execution_store.mark_tool_status.assert_called_with(
            tool_name='restored',
            status='active',
            reason='restored_from_backup'
        )
        
        # Should refresh registry
        mock_tool_registry.refresh.assert_called_once()
        
        # Should copy file
        restored_file = Path(temp_tools_dir) / 'restored_tool.py'
        assert restored_file.exists()
        assert restored_file.read_text() == "# Backed up code"
    
    def test_restore_tool_backup_not_found(self, lifecycle_manager, temp_tools_dir):
        """Test restore when backup doesn't exist."""
        backup_dir = Path(temp_tools_dir) / 'backups'
        backup_dir.mkdir()
        
        result = lifecycle_manager.restore_tool('missing', backup_dir=str(backup_dir))
        
        assert result['success'] is False
        assert 'Backup not found' in result['error']
    
    def test_sync_with_alerts(self, lifecycle_manager, mock_execution_store, temp_tools_dir):
        """Test sync generates alerts for useful deleted tools."""
        # Setup: Useful tool deleted from filesystem
        mock_result = [
            ('useful_tool', 'active', datetime.now(), None)
        ]
        mock_execution_store._mock_cursor.fetchall.return_value = mock_result
        mock_execution_store.get_tool_statistics.return_value = {
            'total_executions': 100,
            'success_rate': 0.95,
            'last_used': datetime.now()
        }
        
        report = lifecycle_manager.sync_and_reconcile()
        
        # Should generate alert
        assert len(report['alerts']) == 1
        alert = report['alerts'][0]
        assert alert['alert'] is True
        assert alert['severity'] == 'warning'
        assert alert['tool_name'] == 'useful_tool'


class TestToolLifecycleIntegration:
    """Integration tests requiring real database."""
    
    @pytest.mark.integration
    def test_full_lifecycle_with_database(self):
        """Test complete lifecycle with real ExecutionStore."""
        # This would require real database connection
        # Placeholder for integration test
        pass
    
    @pytest.mark.integration  
    def test_concurrent_sync_operations(self):
        """Test multiple sync operations don't conflict."""
        # Test thread safety of sync operations
        pass
