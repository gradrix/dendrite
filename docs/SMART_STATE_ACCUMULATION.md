# Smart State Accumulation Strategy

## Problem Statement

When querying time-windowed data repeatedly:
1. **Duplicates**: Running "last 24h kudos" twice saves same data twice
2. **Drift**: Time window moves, old data becomes stale
3. **Waste**: Re-fetching data we already have
4. **Opportunity**: Could answer future queries from accumulated state!

## Example Scenario

```
10:00 AM - "Get kudos from last 24 hours"
  API → [Alice@09:30, Bob@08:00, Charlie@yesterday-11:00]
  Save to state
  
11:00 AM - "Get kudos from last 24 hours" (same query!)
  API → [Alice@09:30, Bob@08:00, Charlie@yesterday-11:00, Diana@10:30]
  Problem: Alice/Bob/Charlie already in state!
  Solution: Merge by unique ID + timestamp, keep newest
  
Next day - "Get kudos from last 2 days"
  Check state first: Do we have this range?
  If yes → Return from state (no API call!)
  If partial → Fetch gaps only
```

## Proposed Architecture

### 1. State Key Format: `<entity>_<type>_timeseries`

**Examples:**
- `kudos_givers_timeseries` - All kudos givers accumulated over time
- `activities_timeseries` - All activities accumulated over time
- `comments_timeseries` - All comments accumulated over time

**Why "timeseries" not "2025"?**
- Single accumulating store (not per-year buckets)
- Auto-deduplicates by unique ID
- Supports range queries
- Can implement auto-cleanup for old data

---

### 2. State Data Structure

```json
{
  "entity": "kudos_givers",
  "accumulated_since": "2025-10-01T00:00:00Z",
  "last_updated": "2025-10-25T11:00:00Z",
  "count": 156,
  "entries": [
    {
      "id": "kudos_activity123_athlete456",
      "athlete_id": "456",
      "athlete_name": "Alice",
      "activity_id": "123",
      "timestamp": "2025-10-25T09:30:00Z",
      "first_seen": "2025-10-25T10:00:00Z"
    },
    {
      "id": "kudos_activity124_athlete789",
      "athlete_id": "789",
      "athlete_name": "Bob",
      "activity_id": "124",
      "timestamp": "2025-10-25T08:00:00Z",
      "first_seen": "2025-10-25T10:00:00Z"
    }
    // ... more entries
  ],
  "metadata": {
    "total_api_calls": 5,
    "total_fetched": 200,
    "duplicates_avoided": 44
  }
}
```

**Key fields:**
- `id`: Unique identifier for deduplication (composite key)
- `timestamp`: When event occurred (for range filtering)
- `first_seen`: When we first saved it (for debugging)
- `metadata`: Statistics for optimization tracking

---

### 3. Smart Merge Function

```python
def merge_timeseries_state(
    state_key: str,
    new_entries: List[Dict],
    id_field: str = "id",
    timestamp_field: str = "timestamp"
) -> Dict[str, Any]:
    """
    Merge new entries into existing timeseries state.
    Deduplicates by ID, keeps newest version.
    
    Args:
        state_key: State key (e.g., "kudos_givers_timeseries")
        new_entries: New data to merge
        id_field: Field name for unique ID
        timestamp_field: Field name for timestamp
        
    Returns:
        Updated state dict with deduplication stats
    """
    # 1. Load existing state
    existing = loadState(state_key, default={
        "entity": state_key.replace("_timeseries", ""),
        "accumulated_since": None,
        "last_updated": None,
        "count": 0,
        "entries": [],
        "metadata": {
            "total_api_calls": 0,
            "total_fetched": 0,
            "duplicates_avoided": 0
        }
    })
    
    # 2. Build lookup by ID
    entries_by_id = {e[id_field]: e for e in existing["entries"]}
    
    # 3. Merge new entries (keep newest)
    duplicates = 0
    for new_entry in new_entries:
        entry_id = new_entry[id_field]
        if entry_id in entries_by_id:
            # Duplicate - keep newest timestamp
            old_ts = entries_by_id[entry_id][timestamp_field]
            new_ts = new_entry[timestamp_field]
            if new_ts > old_ts:
                entries_by_id[entry_id] = new_entry
            duplicates += 1
        else:
            # New entry
            entries_by_id[entry_id] = new_entry
    
    # 4. Update metadata
    now = datetime.now(timezone.utc).isoformat()
    merged = {
        "entity": existing["entity"],
        "accumulated_since": existing["accumulated_since"] or now,
        "last_updated": now,
        "count": len(entries_by_id),
        "entries": sorted(
            entries_by_id.values(),
            key=lambda e: e[timestamp_field],
            reverse=True
        ),
        "metadata": {
            "total_api_calls": existing["metadata"]["total_api_calls"] + 1,
            "total_fetched": existing["metadata"]["total_fetched"] + len(new_entries),
            "duplicates_avoided": existing["metadata"]["duplicates_avoided"] + duplicates
        }
    }
    
    # 5. Save back
    saveState(state_key, merged)
    
    return {
        "success": True,
        "added": len(new_entries) - duplicates,
        "duplicates": duplicates,
        "total_count": len(entries_by_id)
    }
```

---

### 4. Smart Query Function

```python
def query_timeseries_state(
    state_key: str,
    start_time: str,
    end_time: str,
    timestamp_field: str = "timestamp"
) -> Dict[str, Any]:
    """
    Query timeseries state for a time range.
    Returns entries within range + coverage info.
    
    Args:
        state_key: State key to query
        start_time: ISO timestamp (e.g., "2025-10-24T10:00:00Z")
        end_time: ISO timestamp
        timestamp_field: Field name for timestamp filtering
        
    Returns:
        Filtered entries + coverage analysis
    """
    # 1. Load state
    state = loadState(state_key, default={"entries": []})
    
    if not state.get("entries"):
        return {
            "success": True,
            "entries": [],
            "coverage": "none",
            "needs_api_call": True,
            "reason": "No data in state"
        }
    
    # 2. Filter by time range
    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    
    filtered = [
        e for e in state["entries"]
        if start <= datetime.fromisoformat(e[timestamp_field].replace('Z', '+00:00')) <= end
    ]
    
    # 3. Analyze coverage
    if not filtered:
        coverage = "none"
        needs_api = True
        reason = "No entries in requested range"
    else:
        # Check if we have continuous coverage
        oldest_in_state = min(
            datetime.fromisoformat(e[timestamp_field].replace('Z', '+00:00'))
            for e in state["entries"]
        )
        
        if oldest_in_state <= start:
            coverage = "full"
            needs_api = False
            reason = "Complete coverage from state"
        else:
            coverage = "partial"
            needs_api = True
            reason = f"State only goes back to {oldest_in_state}, need API for older data"
    
    return {
        "success": True,
        "entries": filtered,
        "count": len(filtered),
        "coverage": coverage,
        "needs_api_call": needs_api,
        "reason": reason,
        "state_range": {
            "oldest": min(e[timestamp_field] for e in state["entries"]) if state["entries"] else None,
            "newest": max(e[timestamp_field] for e in state["entries"]) if state["entries"] else None
        }
    }
```

---

### 5. Automatic Cleanup (Optional)

```python
def cleanup_old_timeseries(
    state_key: str,
    keep_days: int = 90,
    timestamp_field: str = "timestamp"
) -> Dict[str, Any]:
    """
    Remove entries older than keep_days to prevent state bloat.
    
    Args:
        state_key: State key to clean
        keep_days: Keep entries from last N days
        timestamp_field: Field for timestamp comparison
        
    Returns:
        Cleanup stats
    """
    state = loadState(state_key, default={"entries": []})
    
    if not state.get("entries"):
        return {"success": True, "removed": 0, "kept": 0}
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    
    old_count = len(state["entries"])
    state["entries"] = [
        e for e in state["entries"]
        if datetime.fromisoformat(e[timestamp_field].replace('Z', '+00:00')) >= cutoff
    ]
    new_count = len(state["entries"])
    
    state["count"] = new_count
    saveState(state_key, state)
    
    return {
        "success": True,
        "removed": old_count - new_count,
        "kept": new_count,
        "cutoff_date": cutoff.isoformat()
    }
```

---

## Usage Examples

### Example 1: Accumulate Kudos Over Time

```yaml
# First run - 10:00 AM
goal: "Get kudos from last 24 hours and save to memory"

# Agent does:
1. Fetch kudos from API (last 24h)
2. Transform to entries with IDs:
   - id: "kudos_{activity_id}_{athlete_id}"
   - timestamp: kudos.created_at
   - athlete info...
3. merge_timeseries_state("kudos_givers_timeseries", entries)
   → Added: 15, Duplicates: 0, Total: 15

# Second run - 11:00 AM (same instruction!)
goal: "Get kudos from last 24 hours and save to memory"

# Agent does:
1. Fetch kudos from API (last 24h)
2. Transform to entries
3. merge_timeseries_state("kudos_givers_timeseries", entries)
   → Added: 2, Duplicates: 13, Total: 17
   # Only 2 new kudos, avoided re-saving 13!
```

### Example 2: Query from State First

```yaml
goal: "Who gave me kudos in the last 2 days?"

# Agent does (with memory overseer):
1. Memory overseer detects "kudos" → checks state
2. query_timeseries_state("kudos_givers_timeseries", start="2 days ago", end="now")
   → Coverage: "full", Needs API: false
   → Returns: 47 kudos from state
3. Agent formats and returns (NO API CALL!)

# Saved time: No Strava API call needed
# Saved money: No LLM call to fetch (data already in memory)
```

### Example 3: Partial Coverage - Fill Gaps

```yaml
goal: "Show me kudos from last 7 days"

# Agent does:
1. query_timeseries_state("kudos_givers_timeseries", start="7 days ago", end="now")
   → Coverage: "partial"
   → Reason: "State only goes back to 3 days ago"
   → Returns: 30 kudos from last 3 days
   
2. Agent decides: "Need to fetch missing 4 days"
3. Fetch from API: Last 7 days (or smart: only days 4-7)
4. merge_timeseries_state() → Merge with existing
5. Return combined result: 62 kudos total
```

---

## Integration with Memory Overseer

### Pre-Query Check (Enhanced)

```python
def _check_memory_relevance(self, goal: str) -> Dict[str, Any]:
    """Enhanced to support timeseries queries."""
    
    # 1. List state keys
    keys = self.tool_registry.call_tool('listStateKeys', {})
    if not keys.get('keys'):
        return {}
    
    # 2. Check if timeseries-related query
    if any(word in goal.lower() for word in ['last', 'recent', 'past', 'days', 'hours', 'week']):
        # Extract time range from goal
        time_range = self._extract_time_range(goal)  # "24 hours", "2 days", etc.
        
        # 3. Ask LLM which timeseries keys are relevant
        prompt = f"""Goal: "{goal}"
Time range detected: {time_range}

Available timeseries data: {', '.join([k for k in keys['keys'] if 'timeseries' in k])}

Which timeseries should be checked? Output JSON:
{{"relevant_keys": ["key1"], "time_range": "{time_range}"}}"""
        
        response = self.ollama.generate(prompt, temperature=0)
        decision = json.loads(response)
        
        # 4. Query each relevant timeseries
        memory_context = {}
        for key in decision.get('relevant_keys', []):
            result = query_timeseries_state(key, start=time_range['start'], end=time_range['end'])
            memory_context[key] = result
            
            if result['coverage'] == 'full':
                logger.info(f"✅ Full coverage from state: {key} ({result['count']} entries)")
            elif result['coverage'] == 'partial':
                logger.info(f"⚠️ Partial coverage: {key} ({result['count']} entries, needs API for gaps)")
        
        return memory_context
    
    # Fall back to simple key matching (for non-timeseries)
    return self._simple_key_match(goal, keys['keys'])
```

---

## New Tools to Add

### 1. `mergeTimeseriesState` Tool

```python
@tool(
    description="Merge time-stamped entries into state with automatic deduplication",
    parameters=[
        {"name": "key", "type": "string", "description": "State key (e.g., 'kudos_givers_timeseries')", "required": True},
        {"name": "entries", "type": "array", "description": "List of entries to merge (must have id and timestamp)", "required": True},
        {"name": "id_field", "type": "string", "description": "Field name for unique ID (default: 'id')", "required": False},
        {"name": "timestamp_field", "type": "string", "description": "Field name for timestamp (default: 'timestamp')", "required": False}
    ],
    returns="Merge stats (added, duplicates, total)",
    permissions="write"
)
def mergeTimeseriesState(key: str, entries: List[Dict], id_field: str = "id", timestamp_field: str = "timestamp") -> Dict[str, Any]:
    """See implementation above"""
    pass
```

### 2. `queryTimeseriesState` Tool

```python
@tool(
    description="Query time-ranged data from state, check coverage",
    parameters=[
        {"name": "key", "type": "string", "description": "State key to query", "required": True},
        {"name": "start_time", "type": "string", "description": "Start timestamp (ISO format)", "required": True},
        {"name": "end_time", "type": "string", "description": "End timestamp (ISO format)", "required": True}
    ],
    returns="Filtered entries + coverage analysis",
    permissions="read"
)
def queryTimeseriesState(key: str, start_time: str, end_time: str) -> Dict[str, Any]:
    """See implementation above"""
    pass
```

---

## Benefits

1. **No Duplicates**: Automatic deduplication by unique ID
2. **Incremental Updates**: Each run adds only new data
3. **API Savings**: Avoid re-fetching data we already have
4. **Fast Queries**: Answer from state without API calls
5. **Coverage Awareness**: Agent knows if it needs to fetch more
6. **Generic Pattern**: Works for any time-series data (kudos, activities, comments, etc.)

---

## Rollout Plan

### Phase 1: Core Functions (PRIORITY)
- ✅ Implement `merge_timeseries_state()` in `tools/utility_tools.py`
- ✅ Implement `query_timeseries_state()` in `tools/utility_tools.py`
- ✅ Add as tools: `mergeTimeseriesState`, `queryTimeseriesState`

### Phase 2: Integration with Overseer
- ✅ Enhance `_check_memory_relevance()` to detect time-range queries
- ✅ Add `_extract_time_range()` helper to parse "last 24 hours", "2 days ago", etc.
- ✅ Inject coverage info into goal context

### Phase 3: Auto-Cleanup (OPTIONAL)
- Add `cleanup_old_timeseries()` as scheduled task or manual tool
- Default: Keep 90 days of data

### Phase 4: Testing
```yaml
# Test 1: Initial accumulation
goal: "Get kudos from last 24 hours and save to memory"
# Expected: 15 kudos saved

# Test 2: Incremental update (1 hour later)
goal: "Get kudos from last 24 hours and save to memory"
# Expected: +2 new, 13 duplicates avoided

# Test 3: Query from state
goal: "Who gave me kudos in last 2 days?"
# Expected: Answer from state, no API call

# Test 4: Partial coverage
goal: "Show kudos from last 7 days"
# Expected: Partial from state, fetch gaps, merge
```

---

## Open Questions

1. **Key naming**: `kudos_givers_timeseries` vs `timeseries_kudos_givers` vs `kudos_ts`?
   - **Recommendation**: `<entity>_timeseries` (e.g., `kudos_timeseries`, `activities_timeseries`)
   
2. **ID format**: How to generate unique IDs for different data types?
   - Kudos: `kudos_{activity_id}_{athlete_id}`
   - Activities: `activity_{id}`
   - Comments: `comment_{id}`
   - **Recommendation**: Let LLM generate based on data type

3. **Cleanup frequency**: Auto-cleanup on every merge, or manual?
   - **Recommendation**: Manual for now (use `scripts/state.sh` or cleanup tool)

4. **State size limits**: What if timeseries grows to 10MB?
   - **Recommendation**: Implement max_entries limit (e.g., 10,000) with FIFO eviction

---

## Conclusion

This is a **smart, generic caching pattern** that makes the agent much more efficient:
- Avoids duplicate API calls
- Builds up knowledge over time
- Answers queries from memory when possible
- Works for any time-series data (not just kudos!)

**Ready to implement Phase 1 (core functions)?** Should take ~100 lines of code.
