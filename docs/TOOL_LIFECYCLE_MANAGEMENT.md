# Tool Lifecycle Management - Questions & Solutions

## Your Questions

### Q1: "AI creates tools in folder, I delete some tools - what happens?"

**Current Behavior:**
1. AI creates tool → writes to `neural_engine/tools/my_tool.py`
2. ToolRegistry scans folder → loads tool into memory
3. ExecutionStore records tool creation in database
4. **You delete file** → `rm neural_engine/tools/my_tool.py`
5. Next `tool_registry.refresh()` → tool NOT loaded (file gone)
6. **BUT**: Database still has:
   - `tool_creation_events` table: Tool creation record
   - `tool_executions` table: Historical execution data
   
**Problem:** Database and filesystem OUT OF SYNC!

### Q2: "Do I have to delete tool from DB?"

**Current Answer:** No mechanism exists to do this!

### Q3: "What SHOULD happen?"

This is the key design question. Let's explore options:

---

## Solution Options

### Option 1: Filesystem is Source of Truth (Conservative) ✅ **RECOMMENDED**

**Philosophy:** If file doesn't exist, tool doesn't exist.

**Behavior:**
```python
# After you delete tool file:
tool_registry.refresh()  # Tool not in registry anymore
tool_registry.get_tool('deleted_tool')  # Returns None

# Database still has history (for learning):
execution_store.get_tool_statistics('deleted_tool')  # Still works!
# Returns: {
#   'total_executions': 100,
#   'success_rate': 0.85,
#   'status': 'deleted'  ← NEW FLAG
# }
```

**Implementation:**
1. Add `status` column to database records: 'active' | 'deleted' | 'archived'
2. ToolRegistry marks tools as 'deleted' when file missing
3. Historical data preserved for analytics
4. Queries filter by status (show only 'active' by default)

**Pros:**
- ✅ Simple: Delete file = delete tool
- ✅ Keeps historical data for learning
- ✅ Can restore from backups if needed
- ✅ Autonomous: No manual DB cleanup needed

**Cons:**
- ⚠️ Database grows over time
- ⚠️ Need periodic cleanup of old deleted tools

---

### Option 2: Database is Source of Truth (Complex)

**Philosophy:** Database controls what exists. Filesystem just stores code.

**Behavior:**
```python
# Tool lifecycle:
tool_manager.create_tool(...)  # Writes DB + file
tool_manager.delete_tool('my_tool')  # Deletes DB + file
tool_manager.archive_tool('my_tool')  # Keeps DB, deletes file

# Manual file deletion:
os.remove('my_tool.py')  # Detected as corruption
tool_registry.sync()  # Regenerates file from DB!
```

**Pros:**
- ✅ Versioning built-in
- ✅ Can rollback any version
- ✅ Single source of truth

**Cons:**
- ❌ Complex: Need full CRUD API
- ❌ Database stores large code blobs
- ❌ Less transparent (can't just delete files)
- ❌ Against Unix philosophy

---

### Option 3: Hybrid with Reconciliation (Autonomous) 🌟 **BEST LONG-TERM**

**Philosophy:** Filesystem and DB sync automatically. AI fixes conflicts.

**Behavior:**
```python
class ToolLifecycleManager:
    def sync_tools(self):
        """
        Automatically reconcile filesystem and database.
        
        Cases:
        1. File exists, not in DB → Mark as 'manual_creation'
        2. File missing, in DB as 'active' → Mark as 'deleted'
        3. File exists, DB says 'deleted' → Mark as 'restored'
        4. Code changed on disk → Create new version
        """
        
    def handle_deleted_tool(self, tool_name):
        """
        When tool file deleted:
        1. Check if tool was useful (high success rate)
        2. If useful + recently deleted → Alert for review
        3. If junk (low success rate) → Mark as 'deleted', done
        4. Keep historical data for learning
        """
```

**Auto-Cleanup Policy:**
```python
class ToolGarbageCollector:
    def cleanup_old_tools(self):
        """
        Automatic cleanup based on usage:
        
        - Deleted >30 days + low usage → Archive metadata
        - Deleted >90 days + never used → Purge completely
        - Deleted but high success rate → Flag for review
        """
```

**Pros:**
- ✅ Autonomous: No manual intervention needed
- ✅ Learns from tool usage patterns
- ✅ Alerts if accidentally deleting useful tools
- ✅ Historical data retained for learning
- ✅ Auto-cleanup prevents DB bloat

**Cons:**
- ⚠️ More complex implementation
- ⚠️ Need background sync process

---

## Recommended Implementation (Phase 9d)

### **Start with Option 1 (Filesystem SOT), Evolve to Option 3**

**Phase 9d.1: Add Status Tracking**
```python
# Add to ExecutionStore:
def mark_tool_status(self, tool_name: str, status: str):
    """Mark tool as: active | deleted | archived"""

# Add to ToolRegistry:
def sync_tool_status(self):
    """
    Compare filesystem and database.
    Mark missing tools as 'deleted' in DB.
    """
```

**Phase 9d.2: Add Reconciliation**
```python
class ToolLifecycleManager:
    def __init__(self, tool_registry, execution_store):
        self.registry = tool_registry
        self.store = execution_store
    
    def sync_and_reconcile(self):
        """
        1. Scan filesystem
        2. Compare with database
        3. Update statuses
        4. Return sync report
        """
        
        fs_tools = self._scan_filesystem()
        db_tools = self._get_database_tools()
        
        report = {
            'newly_deleted': [],
            'restored': [],
            'new_manual_tools': []
        }
        
        # Find deleted tools
        for db_tool in db_tools:
            if db_tool not in fs_tools and db_tool['status'] == 'active':
                self.store.mark_tool_status(db_tool['name'], 'deleted')
                report['newly_deleted'].append(db_tool['name'])
        
        # Find restored tools
        for db_tool in db_tools:
            if db_tool in fs_tools and db_tool['status'] == 'deleted':
                self.store.mark_tool_status(db_tool['name'], 'active')
                report['restored'].append(db_tool['name'])
        
        # Find new tools
        for fs_tool in fs_tools:
            if fs_tool not in db_tools:
                report['new_manual_tools'].append(fs_tool)
        
        return report
```

**Phase 9d.3: Add Smart Alerts**
```python
def analyze_deleted_tool(self, tool_name: str):
    """
    When tool deleted, check if it was valuable.
    """
    stats = self.store.get_tool_statistics(tool_name)
    
    if not stats:
        return {'alert': False, 'reason': 'never_used'}
    
    # High success rate = might be accident
    if stats['success_rate'] > 0.85 and stats['total_executions'] > 20:
        return {
            'alert': True,
            'severity': 'warning',
            'reason': 'useful_tool_deleted',
            'stats': stats,
            'suggestion': 'Consider restoring from backup'
        }
    
    # Recent usage = might be accident
    last_used = stats.get('last_used')
    if last_used and (datetime.now() - last_used).days < 7:
        return {
            'alert': True,
            'severity': 'info',
            'reason': 'recently_used',
            'suggestion': 'Was this intentional?'
        }
    
    return {'alert': False, 'reason': 'cleanup_ok'}
```

**Phase 9d.4: Add Auto-Cleanup**
```python
class ToolGarbageCollector:
    def __init__(self, execution_store, backup_dir='neural_engine/tools/backups'):
        self.store = execution_store
        self.backup_dir = backup_dir
    
    def cleanup_old_deleted_tools(self, days_threshold=90):
        """
        Archive metadata for old deleted tools.
        
        Policy:
        - Deleted >90 days + <10 uses → Purge metadata
        - Deleted >90 days + >10 uses → Keep metadata, mark 'archived'
        - Deleted <90 days → Keep everything
        """
        deleted_tools = self.store.get_tools_by_status('deleted')
        
        for tool in deleted_tools:
            deleted_date = tool['status_changed_at']
            days_deleted = (datetime.now() - deleted_date).days
            
            if days_deleted < days_threshold:
                continue  # Too recent, keep
            
            stats = self.store.get_tool_statistics(tool['name'])
            
            if stats['total_executions'] < 10:
                # Low usage, safe to purge
                self.store.purge_tool_data(tool['name'])
            else:
                # Keep metadata for learning
                self.store.mark_tool_status(tool['name'], 'archived')
```

---

## Autonomous Behavior Design

### Scenario 1: You Delete Junk Tool
```
1. You: rm neural_engine/tools/buggy_test_tool.py
2. System: tool_registry.refresh() → tool not loaded
3. System: lifecycle_manager.sync() detects missing file
4. System: Checks stats → 2 uses, 0% success rate
5. System: Marks as 'deleted', no alert
6. After 90 days: Auto-purges metadata
```

### Scenario 2: You Delete Useful Tool (Accident)
```
1. You: rm neural_engine/tools/my_amazing_tool.py
2. System: tool_registry.refresh() → tool not loaded
3. System: lifecycle_manager.sync() detects missing file
4. System: Checks stats → 500 uses, 95% success rate
5. System: 🚨 ALERT: "Useful tool deleted! Restore from backup?"
6. You: Click restore → Copies from backups/ → tool back
```

### Scenario 3: AI Creates Duplicate Tool
```
1. AI: Creates similar_tool_v2.py (duplicates existing_tool.py)
2. System: Detects similar functionality via embedding comparison
3. System: Analyzes both tools
4. System: "Found duplicate: existing_tool (95% success, 100 uses) vs similar_tool_v2 (85% success, 5 uses)"
5. System: Suggests keeping existing_tool, archiving similar_tool_v2
6. Auto-archives after confirmation
```

### Scenario 4: Background Maintenance
```
# Runs periodically (e.g., daily)
lifecycle_manager.maintenance():
    1. Sync filesystem and database
    2. Detect deleted tools, mark in DB
    3. Alert if useful tools deleted
    4. Auto-archive old deleted tools (>90 days, low usage)
    5. Detect duplicate tools via embeddings
    6. Generate cleanup report
```

---

## Database Schema Enhancement

```sql
-- Add status tracking
ALTER TABLE tool_creation_events 
ADD COLUMN status VARCHAR(20) DEFAULT 'active'
  CHECK (status IN ('active', 'deleted', 'archived', 'deprecated'));

ALTER TABLE tool_creation_events
ADD COLUMN status_changed_at TIMESTAMP DEFAULT NOW();

ALTER TABLE tool_creation_events
ADD COLUMN status_reason TEXT;  -- Why was it deleted/archived?

-- Create tool lifecycle events table
CREATE TABLE tool_lifecycle_events (
    event_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- created | deleted | restored | archived
    event_time TIMESTAMP DEFAULT NOW(),
    reason TEXT,
    metadata JSONB,  -- {success_rate: 0.95, total_uses: 100, ...}
    triggered_by VARCHAR(50)  -- 'user' | 'ai' | 'auto_cleanup'
);

-- Index for fast queries
CREATE INDEX idx_tool_lifecycle_tool_name ON tool_lifecycle_events(tool_name);
CREATE INDEX idx_tool_lifecycle_event_type ON tool_lifecycle_events(event_type);
```

---

## Summary: Best Autonomous Solution

**Short Answer:**
- ✅ **Filesystem is source of truth** (you delete file = tool gone)
- ✅ **Database tracks status** ('active' | 'deleted' | 'archived')
- ✅ **Historical data preserved** for learning
- ✅ **Smart alerts** if you delete useful tools (accident prevention)
- ✅ **Auto-cleanup** old deleted tools (>90 days, low usage)
- ✅ **Background sync** keeps DB and filesystem aligned
- ✅ **No manual DB intervention** needed

**Your Workflow:**
```bash
# Just delete the file - system handles the rest!
rm neural_engine/tools/junk_tool.py

# System automatically:
# 1. Detects file missing on next refresh
# 2. Marks as 'deleted' in DB
# 3. Preserves historical stats for learning
# 4. Alerts if tool was useful (accident prevention)
# 5. After 90 days: Auto-archives if low usage
```

**Most Autonomous:** You just manage files. System manages database. No manual sync needed!

Ready to implement this in Phase 9d? 🚀
