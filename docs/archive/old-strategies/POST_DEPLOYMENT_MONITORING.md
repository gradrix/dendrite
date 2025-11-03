# Phase 9e: Post-Deployment Monitoring

## Overview

Post-deployment monitoring provides **continuous health tracking** after tool improvements are deployed. It automatically detects regressions by comparing baseline (pre-deployment) metrics with current (post-deployment) metrics, and triggers **automatic rollback** if performance degrades significantly.

## Purpose

Even with thorough testing (shadow and replay), some issues only appear in production:
- Edge cases not covered by test data
- Performance issues under real load
- Interaction effects with other system changes
- Data distribution shifts

Post-deployment monitoring provides a **safety net** that catches regressions early and automatically reverts problematic changes.

## Architecture

### Components

1. **DeploymentMonitor** (`deployment_monitor.py`)
   - Tracks tool health after deployment
   - Compares baseline vs current metrics
   - Detects regressions automatically
   - Triggers rollback when needed

2. **Database Schema** (`011_deployment_monitoring.sql`)
   - `deployment_monitoring`: Monitoring sessions
   - `deployment_health_checks`: Periodic health checks
   - `deployment_rollbacks`: Rollback events
   - Views: `active_monitoring`, `tool_health_history`, `deployment_stability`

3. **Autonomous Loop Integration**
   - Starts monitoring after deployment
   - Checks health periodically
   - Auto-rollback on regression
   - Marks sessions as completed/rolled_back

## How It Works

### 1. Start Monitoring

When a tool is deployed, the autonomous loop starts monitoring:

```python
# After successful deployment
session_id = deployment_monitor.start_monitoring(
    tool_name='my_tool',
    deployment_time=datetime.now()
)
```

This creates a monitoring session in the database.

### 2. Baseline Metrics

The monitor calculates baseline metrics from **before deployment**:

```sql
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE success = TRUE) as successes,
    AVG(duration_ms) as avg_duration
FROM tool_executions
WHERE tool_name = 'my_tool'
  AND executed_at >= deployment_time - INTERVAL '7 days'
  AND executed_at < deployment_time
```

**Baseline Window**: Last 7 days before deployment (configurable)

### 3. Current Metrics

The monitor tracks current metrics **after deployment**:

```sql
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE success = TRUE) as successes,
    AVG(duration_ms) as avg_duration
FROM tool_executions
WHERE tool_name = 'my_tool'
  AND executed_at >= deployment_time
  AND executed_at <= NOW()
```

**Monitoring Window**: 24 hours after deployment (configurable)

### 4. Comparison & Regression Detection

The monitor compares metrics:

```python
comparison = {
    'success_rate_change': current_rate - baseline_rate,
    'success_rate_drop': max(0, baseline_rate - current_rate),
    'regression_detected': drop >= threshold,
    'regression_severity': 'none' | 'medium' | 'high' | 'critical'
}
```

**Regression Thresholds**:
- **15-20% drop**: Medium severity → Auto-rollback
- **20-30% drop**: High severity → Auto-rollback
- **30%+ drop**: Critical severity → Auto-rollback

### 5. Auto-Rollback

If regression detected:

```python
rollback_result = deployment_monitor.auto_rollback_if_needed(
    tool_name='my_tool',
    session_id='session_123'
)

if rollback_result['rollback_performed']:
    print(f"🚨 Auto-rollback triggered!")
    print(f"   Reason: {rollback_result['reason']}")
    print(f"   Drop: {rollback_result['success_rate_drop']:.1%}")
```

The rollback:
1. Restores previous version from backup
2. Refreshes tool registry
3. Logs rollback event
4. Updates monitoring session status

## Configuration

```python
deployment_monitor = DeploymentMonitor(
    execution_store=store,
    tool_registry=registry,
    
    # How long to monitor after deployment
    monitoring_window_hours=24,
    
    # Historical baseline period
    baseline_window_days=7,
    
    # Threshold for triggering rollback (15% = 0.15)
    regression_threshold=0.15,
    
    # Minimum executions for valid comparison
    min_executions=10
)
```

## Database Schema

### deployment_monitoring

Tracks each monitoring session:

```sql
CREATE TABLE deployment_monitoring (
    session_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    deployment_time TIMESTAMP NOT NULL,
    monitoring_started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    monitoring_window_hours INT NOT NULL DEFAULT 24,
    baseline_window_days INT NOT NULL DEFAULT 7,
    regression_threshold FLOAT NOT NULL DEFAULT 0.15,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    completed_at TIMESTAMP,
    notes TEXT
);
```

**Status Values**:
- `active`: Currently monitoring
- `completed`: Monitoring finished successfully (no regressions)
- `rolled_back`: Regression detected and rollback performed

### deployment_health_checks

Periodic health checks during monitoring:

```sql
CREATE TABLE deployment_health_checks (
    check_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    session_id INT REFERENCES deployment_monitoring(session_id),
    checked_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Baseline metrics
    baseline_success_rate FLOAT,
    baseline_total_executions INT,
    
    -- Current metrics
    current_success_rate FLOAT,
    current_total_executions INT,
    
    -- Comparison
    success_rate_drop FLOAT,
    regression_detected BOOLEAN NOT NULL DEFAULT FALSE,
    regression_severity VARCHAR(20),
    needs_rollback BOOLEAN NOT NULL DEFAULT FALSE
);
```

### deployment_rollbacks

Records rollback events:

```sql
CREATE TABLE deployment_rollbacks (
    rollback_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    session_id INT REFERENCES deployment_monitoring(session_id),
    rollback_time TIMESTAMP NOT NULL DEFAULT NOW(),
    reason TEXT NOT NULL,
    success_rate_drop FLOAT,
    regression_severity VARCHAR(20),
    rollback_successful BOOLEAN NOT NULL
);
```

## Views

### active_monitoring

Shows currently monitored tools:

```sql
SELECT * FROM active_monitoring;
```

| session_id | tool_name | hours_elapsed | regression_detected | latest_success_rate_drop |
|------------|-----------|---------------|---------------------|-------------------------|
| 123 | my_tool | 6.5 | FALSE | 0.02 |
| 124 | other_tool | 12.3 | TRUE | 0.18 |

### tool_health_history

Shows health trend over time:

```sql
SELECT * FROM tool_health_history 
WHERE tool_name = 'my_tool' 
ORDER BY checked_at DESC 
LIMIT 10;
```

| tool_name | checked_at | baseline_success_rate | current_success_rate | success_rate_drop | regression_detected |
|-----------|------------|----------------------|---------------------|-------------------|---------------------|
| my_tool | 2024-01-15 14:30 | 0.90 | 0.88 | 0.02 | FALSE |
| my_tool | 2024-01-15 14:00 | 0.90 | 0.85 | 0.05 | FALSE |

### deployment_stability

Shows overall stability across all tools:

```sql
SELECT * FROM deployment_stability 
ORDER BY rollback_rate DESC;
```

| tool_name | total_deployments | rollback_rate | avg_hours_to_rollback | avg_post_deployment_success_rate |
|-----------|-------------------|---------------|----------------------|--------------------------------|
| problematic_tool | 5 | 0.60 | 8.5 | 0.65 |
| stable_tool | 10 | 0.00 | NULL | 0.92 |

## Integration with Autonomous Loop

The autonomous loop checks deployment health periodically:

```python
async def _check_deployment_health(self):
    """Check health of recently deployed tools."""
    
    # Get active monitoring sessions
    sessions = get_active_sessions()
    
    for session in sessions:
        # Check health and auto-rollback if needed
        result = deployment_monitor.auto_rollback_if_needed(
            tool_name=session.tool_name,
            session_id=session.session_id
        )
        
        if result['rollback_performed']:
            logger.warning(f"🚨 AUTO-ROLLBACK: {session.tool_name}")
            stats['rollbacks_triggered'] += 1
```

**Workflow**:
1. Autonomous loop deploys improvement
2. Starts monitoring session
3. Periodically checks health (every 5 minutes)
4. If regression detected → auto-rollback
5. If monitoring window passes with no issues → mark completed

## Example Scenarios

### Scenario 1: Successful Deployment

```
1. Tool deployed at 10:00 AM
2. Baseline: 90% success rate (100 executions over 7 days)
3. Current: 88% success rate (20 executions in 6 hours)
4. Drop: 2% → Below threshold (15%)
5. Result: ✅ Monitoring continues
6. After 24 hours: ✅ Marked as completed successfully
```

### Scenario 2: Medium Regression → Rollback

```
1. Tool deployed at 10:00 AM
2. Baseline: 90% success rate
3. Current: 72% success rate (6 hours later)
4. Drop: 18% → Above threshold (15%)
5. Severity: Medium
6. Result: 🚨 Auto-rollback triggered
7. Previous version restored
8. Monitoring marked as 'rolled_back'
```

### Scenario 3: Critical Regression → Immediate Rollback

```
1. Tool deployed at 10:00 AM
2. Baseline: 85% success rate
3. Current: 50% success rate (2 hours later)
4. Drop: 35% → Critical
5. Result: 🚨 Immediate auto-rollback
6. Alert triggered
7. Investigation logged
```

### Scenario 4: Insufficient Data

```
1. Tool deployed at 10:00 AM
2. Baseline: 90% success rate (20 executions)
3. Current: 60% success rate (only 5 executions in 2 hours)
4. Result: ⚠️  Insufficient data - no rollback
5. Continue monitoring
6. Wait for more executions (min_executions=10)
```

## Safety Features

1. **Minimum Executions**: Requires at least 10 executions for valid comparison
2. **Sufficient Data Check**: Both baseline and current must have enough data
3. **Severity Levels**: Only medium+ severity triggers rollback
4. **Time Windows**: Separate baseline (7 days) and monitoring (24 hours) windows
5. **Performance Degradation**: Also detects significant slowdowns (200%+ slower)

## Monitoring Best Practices

1. **Set Appropriate Thresholds**
   - 15% is reasonable for most tools
   - Lower threshold (10%) for critical tools
   - Higher threshold (20%) for experimental tools

2. **Monitor Window Duration**
   - 24 hours is typical
   - Longer for low-traffic tools (48 hours)
   - Shorter for high-traffic tools (12 hours)

3. **Baseline Period**
   - 7 days provides good historical context
   - Longer (14 days) for seasonal patterns
   - Shorter (3 days) for rapidly evolving tools

4. **Review Rollbacks**
   - Investigate why rollback happened
   - Improve testing to catch issue earlier
   - Adjust thresholds if too sensitive

## Queries

### Find tools with active regressions
```sql
SELECT * FROM active_monitoring 
WHERE regression_detected = TRUE;
```

### Recent rollbacks
```sql
SELECT 
    tool_name,
    rollback_time,
    reason,
    success_rate_drop,
    regression_severity
FROM deployment_rollbacks
WHERE rollback_time > NOW() - INTERVAL '7 days'
ORDER BY rollback_time DESC;
```

### Tools needing attention
```sql
SELECT * FROM active_monitoring
WHERE regression_detected = TRUE
   OR (hours_elapsed > monitoring_window_hours AND check_count < 5)
ORDER BY latest_success_rate_drop DESC;
```

### Deployment stability report
```sql
SELECT * FROM deployment_stability
WHERE rollback_rate > 0.2  -- 20%+ rollback rate
ORDER BY total_deployments DESC;
```

## Next Steps

Phase 9e is complete! The autonomous system now has:
- ✅ Opportunity detection
- ✅ Self-investigation
- ✅ Autonomous improvement
- ✅ Safe testing (shadow + replay)
- ✅ Automatic deployment
- ✅ **Post-deployment monitoring**
- ✅ **Auto-rollback on regression**

**Next: Phase 9f - Tool Version Management**
- Track all versions with metadata
- Enable rollback to any version
- Show version history with diffs
- Version comparison tools
