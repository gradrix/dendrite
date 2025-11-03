# Tool Registry & Sync Analysis

## Current State

### What We Have
```python
class ToolRegistry:
    def __init__(self, tool_directory="neural_engine/tools"):
        self.tools = {}
        self.refresh()  # ✅ Scans filesystem and loads all tools
    
    def refresh(self):
        """
        SYNC FROM FILESYSTEM → MEMORY
        - Clears in-memory registry
        - Scans neural_engine/tools/ directory
        - Loads all *_tool.py files
        - Instantiates tool classes
        - Stores in self.tools dict
        """
```

### What We DON'T Have
❌ **Sync TO Filesystem**: No method to write tools from memory to disk
❌ **Version Management**: No tracking of tool versions
❌ **Diff Detection**: No way to detect changes between filesystem and memory
❌ **Conflict Resolution**: No handling of concurrent modifications
❌ **Metadata Persistence**: No database of tool metadata

## Current Sync Pattern

```
FILESYSTEM (Source of Truth)
    ↓
[refresh()] → Scans files, loads Python modules
    ↓
MEMORY (ToolRegistry.tools dict)
    ↓
[Tool Execution] → Uses in-memory instances
```

**One-Way Sync**: Filesystem → Memory (on refresh)

## How Autonomous Improvement Works

```python
# Current Flow:
1. Read tool from filesystem (_find_tool_file)
2. Generate improved code (AI)
3. Write directly to filesystem (deploy_improvement)
4. Call tool_registry.refresh() ← This syncs!
5. Verify new tool loads correctly
```

**Key Insight**: We already have sync! It's just:
- **Write to filesystem**: Direct file write in `_deploy_real_improvement()`
- **Sync to memory**: `tool_registry.refresh()`

## Missing Pieces for Production

### 1. Conflict Detection
**Problem**: What if file changed on disk while we were generating improvement?

```python
class ToolRegistry:
    def detect_changes(self, tool_name: str) -> Dict[str, Any]:
        """
        Detect if tool file changed since last load.
        """
        current_tool = self.tools.get(tool_name)
        if not current_tool:
            return {'changed': False, 'reason': 'not_loaded'}
        
        # Read current file
        file_path = self._find_tool_file(tool_name)
        with open(file_path, 'r') as f:
            current_code = f.read()
        
        # Compare with loaded version
        # (Need to store original code when loading)
        loaded_code = getattr(current_tool, '_original_code', None)
        if not loaded_code:
            return {'changed': 'unknown', 'reason': 'no_baseline'}
        
        if current_code != loaded_code:
            return {
                'changed': True,
                'reason': 'file_modified',
                'diff': self._compute_diff(loaded_code, current_code)
            }
        
        return {'changed': False}
```

### 2. Version Tracking
**Problem**: No history of tool versions

```python
class ToolVersionManager:
    """
    Track tool versions in database.
    """
    def __init__(self, execution_store):
        self.store = execution_store
        self._create_versions_table()
    
    def _create_versions_table(self):
        """
        CREATE TABLE tool_versions (
            version_id SERIAL PRIMARY KEY,
            tool_name VARCHAR(255) NOT NULL,
            version_number INT NOT NULL,
            code_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            created_by VARCHAR(50), -- 'human' or 'ai'
            reason TEXT, -- 'initial', 'bug_fix', 'performance', 'rollback'
            metadata JSONB
        );
        """
    
    def record_version(self, tool_name: str, code: str, reason: str):
        """Record new tool version."""
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        version_number = self._get_next_version(tool_name)
        
        self.store.execute("""
            INSERT INTO tool_versions 
            (tool_name, version_number, code_hash, created_by, reason)
            VALUES (%s, %s, %s, 'ai', %s)
        """, (tool_name, version_number, code_hash, reason))
    
    def get_version_history(self, tool_name: str):
        """Get all versions of a tool."""
        return self.store.query("""
            SELECT version_number, created_at, reason 
            FROM tool_versions 
            WHERE tool_name = %s 
            ORDER BY version_number DESC
        """, (tool_name,))
    
    def rollback_to_version(self, tool_name: str, version_number: int):
        """Rollback to specific version."""
        # Get code from backups
        # Restore file
        # Record rollback in versions table
```

### 3. Diff Management
**Problem**: Need to show what changed between versions

```python
import difflib

class ToolDiffManager:
    def compute_diff(self, old_code: str, new_code: str) -> Dict[str, Any]:
        """
        Compute diff between two versions.
        """
        diff = list(difflib.unified_diff(
            old_code.splitlines(keepends=True),
            new_code.splitlines(keepends=True),
            fromfile='old_version',
            tofile='new_version'
        ))
        
        stats = {
            'lines_added': sum(1 for line in diff if line.startswith('+')),
            'lines_removed': sum(1 for line in diff if line.startswith('-')),
            'lines_changed': len([l for l in diff if l.startswith('!') or l.startswith('?')])
        }
        
        return {
            'diff': ''.join(diff),
            'stats': stats,
            'significant': stats['lines_added'] + stats['lines_removed'] > 10
        }
    
    def show_diff(self, tool_name: str, version1: int, version2: int):
        """Show diff between two versions."""
        code1 = self._get_version_code(tool_name, version1)
        code2 = self._get_version_code(tool_name, version2)
        return self.compute_diff(code1, code2)
```

## Recommended Enhancement: Two-Phase Sync

```python
class EnhancedToolRegistry(ToolRegistry):
    """
    Enhanced registry with better sync and version control.
    """
    
    def __init__(self, tool_directory="neural_engine/tools", execution_store=None):
        super().__init__(tool_directory)
        self.version_manager = ToolVersionManager(execution_store) if execution_store else None
        self._store_original_code()
    
    def _store_original_code(self):
        """Store original code for each tool after loading."""
        for tool_name, tool_instance in self.tools.items():
            file_path = self._find_tool_file(tool_name)
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    tool_instance._original_code = f.read()
                    tool_instance._code_hash = hashlib.sha256(
                        tool_instance._original_code.encode()
                    ).hexdigest()
    
    def check_sync_status(self) -> Dict[str, Any]:
        """
        Check if memory and filesystem are in sync.
        """
        status = {
            'in_sync': True,
            'issues': []
        }
        
        # Check for files not in memory
        file_tools = self._scan_filesystem()
        memory_tools = set(self.tools.keys())
        
        orphaned_files = file_tools - memory_tools
        if orphaned_files:
            status['in_sync'] = False
            status['issues'].append({
                'type': 'orphaned_files',
                'tools': list(orphaned_files),
                'message': 'Files on disk not loaded in memory'
            })
        
        # Check for modified files
        for tool_name, tool_instance in self.tools.items():
            change_status = self.detect_changes(tool_name)
            if change_status.get('changed'):
                status['in_sync'] = False
                status['issues'].append({
                    'type': 'file_modified',
                    'tool': tool_name,
                    'message': 'File changed on disk since load'
                })
        
        return status
    
    def safe_deploy(self, tool_name: str, new_code: str, reason: str):
        """
        Deploy with conflict detection.
        """
        # 1. Check for conflicts
        sync_status = self.check_sync_status()
        conflicts = [i for i in sync_status['issues'] 
                    if i.get('tool') == tool_name and i['type'] == 'file_modified']
        
        if conflicts:
            return {
                'success': False,
                'error': 'Conflict detected',
                'conflicts': conflicts,
                'suggestion': 'Refresh and regenerate improvement'
            }
        
        # 2. Create backup
        backup_path = self._create_backup(tool_name)
        
        # 3. Record version
        if self.version_manager:
            self.version_manager.record_version(tool_name, new_code, reason)
        
        # 4. Write file
        file_path = self._find_tool_file(tool_name)
        with open(file_path, 'w') as f:
            f.write(new_code)
        
        # 5. Refresh
        self.refresh()
        
        # 6. Verify
        if tool_name not in self.tools:
            # Rollback
            self._restore_backup(backup_path, file_path)
            self.refresh()
            return {'success': False, 'error': 'Tool failed to load after deployment'}
        
        return {'success': True, 'backup': backup_path}
```

## Answer to Your Questions

### Q1: "Do we have endpoints to sync tools from filesystem and vice versa?"

**Current State**:
- ✅ **Filesystem → Memory**: `tool_registry.refresh()` - works perfectly
- ❌ **Memory → Filesystem**: No explicit API, but autonomous improvement writes directly

**What We Need**:
```python
# Explicit sync API
tool_registry.sync_from_filesystem()  # What we have (refresh)
tool_registry.sync_to_filesystem(tool_name, code)  # What we need (currently in autonomous_improvement)
tool_registry.check_sync_status()  # NEW - detect differences
```

### Q2: "How would we manage differences?"

**Current Approach**: Last-write-wins (no conflict detection)
```python
# Autonomous improvement just overwrites:
with open(tool_file, 'w') as f:
    f.write(improved_code)
```

**Better Approach**: Three-way merge strategy
```python
class ConflictResolver:
    def handle_conflict(self, tool_name, memory_version, disk_version):
        """
        Handle conflicts between memory and disk.
        
        Strategies:
        1. If disk_version == original → safe to overwrite (we have latest)
        2. If disk_version != original → conflict! (someone else modified)
        3. If memory_version == disk_version → already in sync
        """
        
        if disk_version == memory_version:
            return {'action': 'no_op', 'reason': 'already_in_sync'}
        
        if disk_version == tool_instance._original_code:
            return {'action': 'safe_overwrite', 'reason': 'no_concurrent_changes'}
        
        # Conflict!
        return {
            'action': 'conflict',
            'reason': 'concurrent_modification',
            'resolution_options': [
                'abort_and_refresh',  # Safest
                'overwrite_anyway',   # Risky
                'manual_merge'        # Expert mode
            ]
        }
```

## Recommendation

### For Current Demo: NO CHANGES NEEDED ✅
Your current sync is fine for demo:
- Write to disk → `refresh()` → verify
- Simple, works, good enough

### For Production (Phase 9d+):
1. **Add version tracking** (tool_versions table in PostgreSQL)
2. **Add conflict detection** (check file hash before deploy)
3. **Add diff visualization** (show what changed)
4. **Add sync status API** (check_sync_status())

### Priority: Testing Strategy First! 🎯
The sync issues are edge cases. What's MORE important:
- Tool classification (safe vs side-effects)
- Shadow testing (run both versions)
- Regression monitoring (detect failures after deployment)

Your instinct is right: **Go ahead with testing strategy!**

## Code Structure Assessment

Your code is **well-structured and manageable**:
- Clear separation of concerns
- Each neuron has single responsibility  
- Tool system is modular
- Tests are comprehensive

✅ **NOT too complicated for you or AI to handle**
✅ **Good foundation for adding testing strategy**

Let's implement the testing strategy now!
