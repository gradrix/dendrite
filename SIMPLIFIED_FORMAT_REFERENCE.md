# Simplified Task List Format - Quick Reference

## Overview

The simplified format lets you write instructions in natural language with minimal syntax. The system automatically handles time ranges, loops, state management, and error recovery.

## Format Comparison

### ❌ Old Way (V2 - 130 lines)
```yaml
steps:
  - id: "get_24h_ago"
    description: "Calculate timestamp for 24 hours ago"
    tool: "getDateTimeHoursAgo"
    params:
      hours: 24
    save_as: "time_24h_ago"
  
  - id: "fetch_activities"
    description: "Get my activities from last 24 hours"
    tool: "getMyActivities"
    params_template:
      after_unix: "{{time_24h_ago.datetime.unix_timestamp}}"
      before_unix: "{{current_time.datetime.unix_timestamp}}"
      per_page: 100
    depends_on: ["get_current_time", "get_24h_ago"]
    save_as: "my_activities"
```

### ✅ New Way (Simplified - 3 lines)
```yaml
tasks:
  - Get my activities from last 24 hours
```

**Result**: System automatically:
- Calculates time range
- Calls the right tool
- Handles parameters
- Saves results

---

## Three Levels of Simplicity

### Level 1: Ultra-Simple (V3-style)

**When to use**: Quick one-off tasks, testing, exploration

```yaml
name: "Quick Check"
goal: "Show me my last 5 activities"
schedule: once
```

**Features**:
- Single goal in natural language
- No explicit tasks
- Fully automatic execution
- Routes to V3 engine

### Level 2: Simple Task List

**When to use**: Most common use cases (80% of instructions)

```yaml
name: "Daily Activity Update"
goal: "Update visibility and maps for recent activities"

tasks:
  - Get my activities from yesterday
  - Make public any rides over 10km
  - Enable 3D maps for public activities

schedule: daily
```

**Features**:
- Natural language tasks
- Automatic time ranges
- Automatic loops ("for each activity" is implied)
- Automatic state management
- Self-correcting on errors

### Level 3: Advanced Task List

**When to use**: Complex workflows, explicit control needed

```yaml
name: "Activity Cleanup"
goal: "Clean up and organize activities"

settings:
  time_range: 7d
  retry_on_error: true
  max_retries: 3

tasks:
  - id: fetch
    do: Get all my activities from last 7 days
    save_as: activities
    
  - id: analyze
    do: Identify activities needing updates
    when: activities
    rules:
      - Private training rides → make public
      - No description → add default
    save_as: updates_needed
    
  - id: apply
    do: Apply updates
    when: updates_needed
    for_each: updates_needed
    retry_on_error: true

schedule: weekly
```

**Features**:
- All simple features PLUS:
- Explicit task IDs
- Explicit dependencies (`when:`)
- Explicit loops (`for_each:`)
- Detailed rules
- Per-task settings

---

## Syntax Guide

### Basic Structure

```yaml
name: "Instruction Name"              # Required
goal: "High-level description"        # Required
tasks: [...]                          # Required (or just 'goal' for Level 1)
schedule: once|hourly|daily|weekly    # Optional (default: once)
permissions: {...}                    # Optional
```

### Simple Task (Level 2)

```yaml
tasks:
  - Task description in natural language
```

**Auto-detection**:
- `"last 24 hours"` → time range calculation
- `"for each"` / `"all activities"` → loop
- `"if/when"` → conditional
- Result auto-saved for next task

### Advanced Task (Level 3)

```yaml
tasks:
  - id: unique_id           # Optional, for dependencies
    do: Task description    # Natural language
    save_as: result_name    # Store result for later use
    when: dependency_id     # Wait for this task
    for_each: array_name    # Loop over array
    rules:                  # Detailed criteria (list or dict)
      - Rule 1
      - Rule 2
    optional: true          # Don't fail if this fails
    retry_on_error: true    # Retry with self-correction
    max_retries: 3          # Retry limit
```

### Settings (Global)

```yaml
settings:
  time_range: 24h|7d|30d        # Auto-calculate time ranges
  state_tracking: true          # Auto save/load state
  retry_on_error: true          # Global retry setting
  max_retries: 3                # Global retry limit
  batch_size: 50                # For batch operations
```

### Permissions

```yaml
permissions:
  allow_write: true             # Allow write operations
  require_approval: false       # Human-in-the-loop
```

---

## Common Patterns

### 1. Fetch and Filter

```yaml
tasks:
  - Get my activities from last week
  - Filter for rides over 20km
  - Show summary
```

### 2. Fetch, Analyze, Act

```yaml
tasks:
  - id: fetch
    do: Get all my private activities
    save_as: activities
    
  - id: analyze
    do: Identify which should be public
    when: activities
    rules:
      - Type is Ride or Run
      - Distance > 10km
    save_as: to_update
    
  - id: update
    do: Make activities public
    when: to_update
    for_each: to_update
```

### 3. Data Collection and Storage

```yaml
tasks:
  - Fetch kudos for all recent activities
  - Merge with existing kudos database
  - Save to kudos_givers state
```

### 4. Scheduled Monitoring

```yaml
name: "Hourly Activity Monitor"
goal: "Check for new activities and process them"

tasks:
  - Get new activities since last check
  - Update visibility based on rules
  - Track kudos
  - Update statistics

schedule: hourly
```

### 5. Conditional Actions

```yaml
tasks:
  - id: check
    do: Get activities from yesterday
    save_as: activities
    
  - do: Process activities if any found
    when: activities
    rules:
      - Only if count > 0
```

---

## Natural Language Hints

### Time Ranges
- `"last 24 hours"` → `after: now - 24h`
- `"yesterday"` → `after: yesterday_start, before: yesterday_end`
- `"last week"` → `after: now - 7d`
- `"since last check"` → auto-loads from state

### Loops
- `"for each activity"` → auto-loop
- `"all activities"` → auto-loop
- `"each kudos giver"` → auto-loop

### Conditions
- `"if/when"` → conditional execution
- `"only if"` → conditional execution
- `"unless"` → negative conditional

### Actions
- `"get/fetch"` → read operation
- `"update/change/set"` → write operation
- `"save/store"` → state operation
- `"calculate/count/summarize"` → analysis

---

## Migration from V2

### Pattern 1: Time Calculations

**V2 (5 steps)**:
```yaml
steps:
  - id: "get_current_time"
    tool: "getCurrentDateTime"
    save_as: "current_time"
  - id: "get_24h_ago"
    tool: "getDateTimeHoursAgo"
    params: {hours: 24}
    save_as: "time_24h_ago"
  - id: "fetch"
    tool: "getMyActivities"
    params_template:
      after_unix: "{{time_24h_ago.datetime.unix_timestamp}}"
```

**Simplified (1 task)**:
```yaml
tasks:
  - Get my activities from last 24 hours
```

### Pattern 2: Loops with Templates

**V2**:
```yaml
steps:
  - id: "update_visibility"
    tool: "updateActivity"
    loop: "{{activities}}"
    params_template:
      activity_id: "{{loop.item.id}}"
      visibility: "everyone"
    depends_on: ["fetch_activities"]
```

**Simplified**:
```yaml
tasks:
  - Make activities public
```
*(loop and activity IDs auto-detected)*

### Pattern 3: LLM Analysis Steps

**V2**:
```yaml
steps:
  - id: "analyze"
    tool: "llm_analyze"
    context: |
      Analyze activities and determine which need updates.
      RULES: ...
    input: "{{activities}}"
    output_format:
      activities_to_update: [...]
```

**Simplified**:
```yaml
tasks:
  - do: Identify activities needing updates
    rules:
      - Rule 1
      - Rule 2
```
*(LLM analysis automatic)*

### Pattern 4: State Management

**V2**:
```yaml
steps:
  - id: "load_state"
    tool: "loadState"
    params: {key: "last_check"}
    save_as: "last_check"
  # ... do work ...
  - id: "save_state"
    tool: "saveState"
    params_template:
      key: "last_check"
      value: "{{current_time}}"
```

**Simplified**:
```yaml
settings:
  state_tracking: true

tasks:
  - Get activities since last check
  # state auto-saved at end
```

---

## Troubleshooting

### Issue: Task not executing
**Cause**: Dependency not satisfied
**Fix**: Check `when:` references valid task ID

### Issue: Wrong time range
**Cause**: Ambiguous natural language
**Fix**: Be explicit: `"last 24 hours"` not `"recent"`

### Issue: Loop not working
**Cause**: Array not detected
**Fix**: Use explicit `for_each: array_name`

### Issue: LLM misunderstands task
**Cause**: Task too vague
**Fix**: Add `rules:` section with details

### Issue: Need V2 features
**Cause**: Advanced template needed
**Fix**: Use advanced format or keep as V2

---

## Examples

### Example 1: Simple Monitoring
```yaml
name: "Activity Monitor"
goal: "Monitor and update recent activities"

tasks:
  - Get my activities from last 24 hours
  - Make public if conditions met
  - Enable 3D maps

schedule: hourly
```

### Example 2: Reporting
```yaml
name: "Weekly Report"
goal: "Generate weekly activity report"

tasks:
  - Get all activities from last 7 days
  - Calculate totals by type
  - Count kudos received
  - Generate summary report

schedule: weekly
```

### Example 3: Cleanup
```yaml
name: "Activity Cleanup"
goal: "Clean up test activities"

tasks:
  - id: find
    do: Get all my activities
    save_as: all_activities
    
  - id: filter
    do: Find test activities
    when: all_activities
    rules:
      - Title contains "test"
      - OR description contains "testing"
    save_as: test_activities
    
  - id: delete
    do: Delete test activities
    when: test_activities
    for_each: test_activities
    optional: true

schedule: once
```

---

## Tips & Best Practices

### ✅ DO
- Use natural language for task descriptions
- Let system auto-detect time ranges
- Trust automatic loop detection
- Keep tasks focused (one action per task)
- Use `optional: true` for non-critical tasks

### ❌ DON'T
- Over-specify (let system infer)
- Use V2 templates unless necessary
- Create explicit time steps
- Nest tasks deeply
- Mix V2 and simplified syntax

### 🎯 WHEN TO USE EACH LEVEL

**Level 1 (Ultra-Simple)**:
- Quick checks
- Testing
- One-off questions
- Exploration

**Level 2 (Simple)**:
- Regular monitoring
- Standard workflows
- 80% of use cases

**Level 3 (Advanced)**:
- Complex workflows
- Precise control needed
- State management
- Error handling critical

---

## Command Line Usage

### Run Once
```bash
# Simplified format (default)
python main.py --once --instruction strava_monitor

# V2 format (legacy)
python main.py --once --v2 --instruction strava_monitor_v2

# V3 format (goal only)
python main.py --v3 --goal "List my last 3 activities"
```

### Scheduled
```bash
# Start scheduler (uses simplified format)
python main.py

# Force V2 format in scheduler
python main.py --format v2
```

### Dry Run
```bash
# Preview without executing
python main.py --once --instruction strava_monitor
# (Set dry_run: true in config.yaml)
```

---

## Getting Help

### Documentation
- `SIMPLIFICATION_PLAN.md` - Full design document
- `MIGRATION_GUIDE.md` - V2 → Simplified conversion
- `README.md` - General usage

### Examples
- `instructions/examples/` - Sample instructions
- `instructions/strava_monitor.yaml` - Real-world example

### Debugging
- Set `logging.level: DEBUG` in `config.yaml`
- Check `logs/agent.log` for execution details
- Use dry_run mode to preview plans

---

## Version History

- **v3.0** - Simplified task list format (this document)
- **v2.0** - Step-by-step YAML format
- **v1.0** - LLM decision loop format

**Current Recommendation**: Use simplified format (v3.0) for all new instructions.
