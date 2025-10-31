# Phase 9f: Tool Version Management - Complete! ✅

## Overview

Tool Version Management provides **complete version history tracking** with fast rollback capabilities. Every change to a tool is tracked, compared, and can be rolled back instantly when issues are detected.

## Purpose

Phase 9e provided statistical rollback (waiting for 10+ executions), but some issues need **immediate response**:
- **Signature changes** (TypeError) → rollback in <5 minutes
- **Complete breakage** (100% failure) → rollback in <10 minutes
- **Consecutive failures** (3+ in a row) → rollback immediately

Version management enables:
1. **Track every version** with full metadata
2. **Fast rollback** on critical patterns (don't wait for statistics)
3. **Compare versions** to see what changed
4. **Rollback to any version** in history (not just previous)
5. **Breaking change detection** (removed methods, signature changes)

## Components

### 1. ToolVersionManager

**File**: `neural_engine/core/tool_version_manager.py` (741 lines)

**Key Features**:
- Create and track versions automatically
- Get current version and full history
- Rollback to any previous version
- Compare versions with unified diffs
- Detect breaking changes
- Fast rollback triggers
- Update version metrics

**Core Methods**:

```python
class ToolVersionManager:
    def create_version(tool_name, code, created_by='human', 
                      improvement_type='initial', improvement_reason=None):
        """Create new version and track in database."""
    
    def get_current_version(tool_name):
        """Get currently active version."""
    
    def get_version_history(tool_name, limit=50):
        """Get complete version history."""
    
    def rollback_to_version(tool_name, version_id, reason):
        """Rollback to specific version."""
    
    def compare_versions(tool_name, from_version_id, to_version_id):
        """Compare two versions with diff."""
    
    def check_immediate_rollback_needed(tool_name):
        """Check for fast rollback triggers."""
        # Returns: (needs_rollback: bool, reason: str, details: Dict)
```

### 2. Database Schema

**File**: `neural_engine/scripts/012_tool_versions.sql`

**Main Tables**:

#### tool_versions
```sql
CREATE TABLE tool_versions (
    version_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    version_number INT NOT NULL,
    code TEXT NOT NULL,
    code_hash VARCHAR(64) NOT NULL,  -- SHA256 for deduplication
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),  -- 'human' or 'autonomous'
    
    -- Performance metrics
    success_rate FLOAT,
    total_executions INT DEFAULT 0,
    deployment_count INT DEFAULT 0,
    
    -- Status
    is_current BOOLEAN DEFAULT FALSE,
    is_breaking_change BOOLEAN DEFAULT FALSE,
    
    -- Improvement context
    improvement_type VARCHAR(50),
    improvement_reason TEXT,
    previous_version_id INT REFERENCES tool_versions(version_id),
    
    UNIQUE(tool_name, version_number)
);
```

**Views**:

#### version_history_with_metrics
Shows complete history with performance comparison:
```sql
SELECT 
    tool_name,
    version_number,
    created_at,
    created_by,
    success_rate,
    improvement_type,
    success_rate - LAG(success_rate) OVER (
        PARTITION BY tool_name 
        ORDER BY version_number
    ) AS success_rate_change
FROM tool_versions
ORDER BY tool_name, version_number DESC;
```

#### version_stability
Shows tools with unstable versions (frequent rollbacks):
```sql
SELECT 
    tool_name,
    COUNT(*) as total_versions,
    COUNT(*) FILTER (WHERE is_breaking_change) as breaking_changes,
    MAX(version_number) as current_version
FROM tool_versions
GROUP BY tool_name
ORDER BY breaking_changes DESC;
```

### 3. Fast Rollback Triggers

**Integration**: `neural_engine/core/deployment_monitor.py` (enhanced)

**Three Speed Tiers**:

#### Immediate Rollback (<5 minutes)
Triggers on critical patterns that indicate broken deployment:

```python
def check_immediate_rollback_needed(tool_name):
    """
    Fast rollback triggers:
    1. 3+ consecutive failures within 5 minutes
    2. TypeError or AttributeError (signature change)
    3. 100% failure rate with 5+ attempts
    """
    
    recent_execs = get_last_n_executions(tool_name, n=10, minutes=5)
    
    # Check 1: Consecutive failures
    if len(recent_execs) >= 3:
        consecutive_failures = count_consecutive_failures(recent_execs)
        if consecutive_failures >= 3:
            return True, 'consecutive_failures', {...}
    
    # Check 2: Signature change (TypeError/AttributeError)
    errors = [e['error'] for e in recent_execs if not e['success']]
    signature_errors = [e for e in errors if 'TypeError' in e or 'AttributeError' in e]
    if len(signature_errors) >= 2:
        return True, 'signature_change', {...}
    
    # Check 3: Complete failure
    if len(recent_execs) >= 5 and all(not e['success'] for e in recent_execs):
        return True, 'complete_failure', {...}
    
    return False, None, {}
```

#### Fast Rollback (10-30 minutes)
Statistical patterns indicating severe regression:

```python
# In DeploymentMonitor
if failure_rate > 0.8 and total_attempts >= 5:
    # 80%+ failure in first 5 attempts
    trigger_fast_rollback()
```

#### Standard Rollback (hours)
Phase 9e implementation - waits for statistical significance:

```python
# Sliding window comparison
if success_rate_drop >= 0.15 and total_executions >= 10:
    # 15%+ drop over 10+ executions
    trigger_standard_rollback()
```

### 4. Breaking Change Detection

Automatically detects incompatible changes:

```python
def _detect_breaking_changes(old_code, new_code):
    """
    Detect breaking changes between versions.
    
    Checks:
    - Removed methods/functions
    - execute() signature changes
    - Parameter additions/removals
    """
    
    breaking = False
    details = []
    
    # Extract signatures
    old_sigs = extract_signatures(old_code)
    new_sigs = extract_signatures(new_code)
    
    # Check for removed functions
    removed = old_sigs - new_sigs
    if removed:
        breaking = True
        details.append(f"Removed: {', '.join(removed)}")
    
    # Check execute() signature
    if 'def execute(' in old_code and 'def execute(' in new_code:
        old_params = extract_params(old_code, 'execute')
        new_params = extract_params(new_code, 'execute')
        
        if old_params != new_params:
            breaking = True
            details.append(f"Signature changed: {old_params} → {new_params}")
    
    return breaking, details
```

### 5. Integration Points

#### Autonomous Improvement Neuron
Tracks versions on deployment:

```python
# In _deploy_real_improvement()
if self.version_manager:
    version_id = self.version_manager.create_version(
        tool_name=tool_name,
        code=generated_code,
        created_by='autonomous',
        improvement_type='autonomous_improvement',
        improvement_reason=investigation_report.get('root_cause'),
        previous_version_id=None  # Auto-links
    )
    deployment['version_id'] = version_id
```

#### Autonomous Loop
Initializes and uses version manager:

```python
# In __init__()
self.version_manager = ToolVersionManager(
    execution_store=execution_store,
    tool_registry=orchestrator.tool_registry
)

# Inject into deployment monitor
self.deployment_monitor = DeploymentMonitor(
    execution_store=execution_store,
    tool_registry=tool_registry,
    version_manager=self.version_manager  # NEW
)

# Inject into improvement neuron
if self.autonomous_improvement:
    self.autonomous_improvement.version_manager = self.version_manager
```

#### Deployment Monitor
Uses version manager for fast rollback:

```python
def auto_rollback_if_needed(tool_name, session_id, check_fast_rollback=True):
    # Check fast rollback first
    if check_fast_rollback and self.version_manager:
        needs_fast, reason, details = self.version_manager.check_immediate_rollback_needed(tool_name)
        
        if needs_fast:
            rollback_result = self._perform_fast_rollback(tool_name, reason, details)
            return {'rollback_performed': True, 'type': 'fast', ...}
    
    # Then check statistical rollback
    health = self.check_health(tool_name, session_id)
    if health['needs_rollback']:
        rollback_result = self._perform_rollback(tool_name, health)
        return {'rollback_performed': True, 'type': 'standard', ...}
```

## Usage Examples

### Create Version Manually

```python
from neural_engine.core.tool_version_manager import ToolVersionManager

version_manager = ToolVersionManager(execution_store)

# Create new version
version_id = version_manager.create_version(
    tool_name='my_tool',
    code=tool_code,
    created_by='human',
    improvement_type='bug_fix',
    improvement_reason='Fixed timeout issue'
)
```

### Get Version History

```python
# Get all versions
history = version_manager.get_version_history('my_tool')

for version in history:
    print(f"Version {version['version_number']}:")
    print(f"  Created: {version['created_at']}")
    print(f"  By: {version['created_by']}")
    print(f"  Success rate: {version['success_rate']:.1%}")
    print(f"  Executions: {version['total_executions']}")
```

### Compare Versions

```python
# Compare two versions
comparison = version_manager.compare_versions('my_tool', 1, 2)

print("Code differences:")
print(comparison['code_diff'])

print("\nMetrics comparison:")
print(f"  Version 1: {comparison['from_metrics']['success_rate']:.1%}")
print(f"  Version 2: {comparison['to_metrics']['success_rate']:.1%}")
print(f"  Change: {comparison['metrics_comparison']['success_rate_change']:+.1%}")

if comparison['is_breaking_change']:
    print("\n⚠️  Breaking change detected:")
    for detail in comparison['breaking_changes']:
        print(f"  - {detail}")
```

### Rollback to Version

```python
# Rollback to previous version
result = version_manager.rollback_to_version(
    tool_name='my_tool',
    version_id=2,
    reason='Regression detected in version 3'
)

if result['success']:
    print(f"✅ Rolled back to version {result['rolled_back_to_version']}")
    print(f"   Tool reloaded and registry refreshed")
else:
    print(f"❌ Rollback failed: {result['error']}")
```

### Check Fast Rollback Triggers

```python
# Check if immediate rollback needed
needs_rollback, reason, details = version_manager.check_immediate_rollback_needed('my_tool')

if needs_rollback:
    print(f"🚨 Immediate rollback needed!")
    print(f"   Reason: {reason}")
    print(f"   Details: {details}")
    
    # Get current version
    current = version_manager.get_current_version('my_tool')
    
    # Rollback to previous
    if current['previous_version_id']:
        version_manager.rollback_to_version(
            tool_name='my_tool',
            version_id=current['previous_version_id'],
            reason=reason
        )
```

## Fast Rollback Scenarios

### Scenario 1: Signature Change Detected

```
Time 0:00 - Tool improved and deployed (version 3)
Time 0:01 - First execution: TypeError("unexpected keyword argument 'limit'")
Time 0:02 - Second execution: TypeError("unexpected keyword argument 'limit'")
Time 0:03 - Third execution: TypeError("unexpected keyword argument 'limit'")
Time 0:04 - Health check detects signature change pattern
         → Immediate rollback triggered!
         → Rolled back to version 2
         → Tool registry refreshed
Time 0:05 - Fourth execution: ✅ Success with version 2
```

**Why fast?** Signature errors are unambiguous - the tool is broken, not just experiencing issues.

### Scenario 2: Consecutive Failures

```
Time 0:00 - Tool improved and deployed (version 4)
Time 0:01 - Execution 1: Failed (500 Internal Server Error)
Time 0:02 - Execution 2: Failed (500 Internal Server Error)
Time 0:03 - Execution 3: Failed (500 Internal Server Error)
Time 0:04 - Execution 4: Failed (500 Internal Server Error)
Time 0:05 - Health check detects 4 consecutive failures
         → Fast rollback triggered!
         → Rolled back to version 3
```

**Why fast?** 4 consecutive failures in 5 minutes indicates deployment issue, not bad luck.

### Scenario 3: Complete Breakage

```
Time 0:00 - Tool improved and deployed (version 5)
Time 0:05 - 5 attempts, 0 successes (100% failure)
Time 0:10 - 2 more attempts, still 0 successes
Time 0:15 - Health check detects 100% failure rate over 7 attempts
         → Fast rollback triggered!
```

**Why fast?** 100% failure with multiple attempts = broken deployment.

### Scenario 4: No Fast Rollback (Wait for Statistics)

```
Time 0:00 - Tool improved and deployed (version 6)
Time 0:10 - 3 successes, 1 failure (75% success rate)
Time 0:20 - 5 successes, 2 failures (71% success rate)
Time 0:30 - 8 successes, 4 failures (67% success rate)
...
Time 2:00 - 18 successes, 12 failures (60% success rate over 30 attempts)
         → Standard rollback triggered (15% drop from 75% baseline)
```

**Why slow?** Mixed results need statistical confidence. Could be temporary issues.

## Database Queries

### Get current versions of all tools
```sql
SELECT 
    tool_name,
    version_number,
    created_at,
    created_by,
    success_rate,
    total_executions
FROM tool_versions
WHERE is_current = TRUE
ORDER BY tool_name;
```

### Find tools with breaking changes
```sql
SELECT 
    tool_name,
    version_number,
    created_at,
    improvement_reason
FROM tool_versions
WHERE is_breaking_change = TRUE
ORDER BY created_at DESC;
```

### Version comparison query
```sql
SELECT 
    v1.tool_name,
    v1.version_number as from_version,
    v2.version_number as to_version,
    v1.success_rate as old_success_rate,
    v2.success_rate as new_success_rate,
    v2.success_rate - v1.success_rate as improvement
FROM tool_versions v1
JOIN tool_versions v2 ON v1.tool_name = v2.tool_name 
                     AND v2.previous_version_id = v1.version_id
WHERE v2.created_by = 'autonomous'
ORDER BY improvement DESC;
```

### Tools needing immediate rollback
```sql
-- Query recent executions for fast rollback check
SELECT 
    tool_name,
    executed_at,
    success,
    error
FROM tool_executions
WHERE tool_name = 'my_tool'
  AND executed_at > NOW() - INTERVAL '5 minutes'
ORDER BY executed_at DESC
LIMIT 10;
```

## Tests

**File**: `neural_engine/tests/test_tool_version_manager.py` (17 tests)

**Coverage**:
- ✅ Create version
- ✅ Get current version
- ✅ Get version history
- ✅ Rollback to version
- ✅ Compare versions
- ✅ Immediate rollback: consecutive failures
- ✅ Immediate rollback: signature change
- ✅ Immediate rollback: complete failure
- ✅ No rollback trigger (mixed results)
- ✅ Breaking change detection
- ✅ No breaking change (same signature)
- ✅ Update version metrics

## Benefits

### Before Phase 9f
❌ No version history - can't see what changed  
❌ Only rollback to previous version  
❌ Wait hours for statistics (10+ executions)  
❌ Signature changes cause prolonged failures  
❌ Can't compare versions  

### After Phase 9f
✅ Complete version history with metadata  
✅ Rollback to **any** version, not just previous  
✅ **Fast rollback** in <5 minutes on critical patterns  
✅ Automatic breaking change detection  
✅ Version comparison with diffs  
✅ Metrics tracking per version  

## Summary

Phase 9f completes the safety layer of the autonomous improvement system:

**Phase 9e**: Post-deployment monitoring (statistical, hours)  
**Phase 9f**: Version management + fast rollback (pattern-based, minutes)

Together, they provide **defense in depth**:
1. **Immediate** (<5 min): Critical patterns (signature errors, consecutive failures)
2. **Fast** (10-30 min): Severe patterns (100% failure, high error rate)
3. **Standard** (hours): Subtle regressions (15%+ success rate drop)

**The system can now safely improve itself with multiple safety nets at different time scales.** 🛡️

## Next: Phase 9g - Duplicate Detection

Use tool embeddings to find similar/duplicate tools and recommend consolidation.
