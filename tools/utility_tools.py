"""
Utility Tools

General purpose tools for date/time, state management, etc.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from agent.tool_registry import tool
from agent.state_manager import StateManager

logger = logging.getLogger(__name__)


# SPECIAL: LLM Reasoning Step (not a callable tool, but a step type)
# This is documented here so it appears in tool listings for ask.sh
@tool(
    description="Use LLM to analyze, filter, format, or transform data. Example: extract specific fields, format data for display, summarize results.",
    parameters=[
        {"name": "data", "type": "any", "description": "Data to analyze (JSON, dict, list, etc.)", "required": True},
        {"name": "task", "type": "string", "description": "What to do with the data (e.g., 'extract activity IDs', 'format as readable list', 'find activities without descriptions')", "required": True},
        {"name": "format", "type": "string", "description": "Desired output format: 'json', 'list', 'text', 'table'", "required": False}
    ],
    returns="Analyzed/formatted data",
    permissions="read"
)
def llm_analyze_pseudo(data: Optional[Any] = None, task: Optional[str] = None, format: str = "json", **kwargs) -> Any:
    """
    Use LLM to analyze, filter, format, or transform data.
    
    This is a real callable tool that uses the LLM to process data.
    Useful for:
    - Extracting specific fields from complex data
    - Formatting data for human readability
    - Filtering data based on criteria
    - Summarizing or transforming data structures
    
    Args:
        data: The data to analyze (dict, list, JSON, etc.)
        task: What to do with the data
        format: Output format preference (json, list, text, table)
        **kwargs: Support legacy parameter names (input, context, output_format)
    
    Returns:
        Processed data in requested format
    """
    import json as json_module
    from agent.ollama_client import OllamaClient
    
    # Support legacy parameter names
    if data is None and 'input' in kwargs:
        data = kwargs['input']
    if task is None and 'context' in kwargs:
        task = kwargs['context']
    if 'output_format' in kwargs:
        format = 'json'  # Always use JSON if output_format specified
    
    if data is None or task is None:
        raise ValueError("Both 'data' (or 'input') and 'task' (or 'context') are required")
    
    # Get Ollama client from registry context (injected by tool_registry)
    # For now, we'll import config and create it
    import yaml
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    ollama = OllamaClient(
        base_url=config['ollama']['base_url'],
        model=config['ollama']['model'],
        timeout=config['ollama']['timeout']
    )
    
    # Convert data to string for LLM
    if isinstance(data, (dict, list)):
        data_str = json_module.dumps(data, indent=2)
    else:
        data_str = str(data)
    
    # Build prompt
    prompt = f"""Task: {task}

Data:
{data_str}

Output the result in {format} format.
Be concise and accurate."""
    
    # Call LLM
    response = ollama.generate(
        prompt,
        system=f"You analyze and transform data. Output only the requested {format} format, no explanations.",
        temperature=0.3
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    
    # Try to parse as JSON if format is json
    if format == "json":
        try:
            # Extract JSON from markdown if present
            if "```json" in response_str:
                response_str = response_str.split("```json")[1].split("```")[0].strip()
            elif "```" in response_str:
                response_str = response_str.split("```")[1].split("```")[0].strip()
            
            return json_module.loads(response_str)
        except:
            pass
    
    return response_str
def llm_analyze_pseudo():
    """
    SPECIAL STEP TYPE: LLM Reasoning
    
    This is NOT a callable tool. It's a special step type that uses the LLM
    to analyze, filter, format, or transform data.
    
    Instead of using 'tool' and 'params', use:
    - input: "{{previous_step.result}}"
    - context: "What to analyze/extract/format"
    - output_format: {expected: "structure"}
    
    Example YAML:
      - id: "format_output"
        description: "Format activities for display"
        input: "{{fetch_activities.result.activities}}"
        context: "Extract only activity name and date, format as clean list"
        output_format:
          activities:
            - name: "string"
              date: "string"
        save_as: "formatted"
    
    This tool registration exists only for documentation purposes.
    The actual execution is handled by StepExecutor._execute_llm_step().
    """
    raise NotImplementedError("llm_analyze is not a callable tool - it's a step type. Use 'input' and 'output_format' fields in your step definition.")


@tool(
    description="Get current date and time in ISO format with timezone",
    parameters=[],
    returns="Current datetime info with ISO string, unix timestamp, and timezone",
    permissions="read"
)
def getCurrentDateTime() -> Dict[str, Any]:
    """
    Get current date and time.
    
    Returns:
        dict: Current datetime information including:
            - iso: ISO 8601 formatted string (e.g., "2025-10-24T14:30:00+00:00")
            - unix_timestamp: Unix timestamp (seconds since epoch)
            - timezone: Timezone name (e.g., "UTC")
            - human_readable: Human-friendly format
    """
    now = datetime.now(timezone.utc)
    
    return {
        "success": True,
        "datetime": {
            "iso": now.isoformat(),
            "unix_timestamp": int(now.timestamp()),
            "timezone": str(now.tzinfo),
            "human_readable": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S")
        }
    }


@tool(
    description="Calculate datetime N hours ago from now",
    parameters=[
        {"name": "hours", "type": "integer", "description": "Number of hours ago (e.g., 24 for yesterday)", "required": True}
    ],
    returns="Datetime information for the calculated past time",
    permissions="read"
)
def getDateTimeHoursAgo(hours: int) -> Dict[str, Any]:
    """
    Calculate datetime N hours in the past.
    
    Args:
        hours: Number of hours ago (e.g., 24 for 1 day ago)
        
    Returns:
        dict: Datetime information for the calculated time
    """
    now = datetime.now(timezone.utc)
    past_time = now - timedelta(hours=hours)
    
    return {
        "success": True,
        "datetime": {
            "iso": past_time.isoformat(),
            "unix_timestamp": int(past_time.timestamp()),
            "hours_ago": hours,
            "human_readable": past_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        }
    }


@tool(
    description="Save data to persistent state storage (key-value store)",
    parameters=[
        {"name": "key", "type": "string", "description": "Key to store the data under (e.g., 'last_feed_check', 'kudos_givers')", "required": True},
        {"name": "value", "type": "any", "description": "Value to store (can be string, number, list, or object)", "required": True}
    ],
    returns="Success confirmation with stored key",
    permissions="write"
)
def saveState(key: str, value: Any) -> Dict[str, Any]:
    """
    Save data to persistent state storage.
    
    This data persists across agent runs and can be retrieved later.
    Use this to remember information between executions.
    
    Args:
        key: Unique key for this data (e.g., 'last_feed_check_time')
        value: Data to store (will be JSON serialized)
        
    Returns:
        dict: Success status and confirmation
        
    Examples:
        saveState(key="last_feed_check", value={"timestamp": "2025-10-24T10:00:00Z", "count": 15})
        saveState(key="kudos_givers", value=["athlete_123", "athlete_456"])
    """
    try:
        state_manager = StateManager()
        state_manager.set_state(key, value)
        
        return {
            "success": True,
            "message": f"Saved state for key: {key}",
            "key": key
        }
    except Exception as e:
        logger.error(f"Failed to save state for {key}: {e}")
        return {
            "success": False,
            "error": str(e),
            "key": key
        }


@tool(
    description="Load data from persistent state storage",
    parameters=[
        {"name": "key", "type": "string", "description": "Key to retrieve data for", "required": True},
        {"name": "default", "type": "any", "description": "Default value if key doesn't exist (optional)", "required": False}
    ],
    returns="Retrieved value or default",
    permissions="read"
)
def loadState(key: str, default: Any = None) -> Dict[str, Any]:
    """
    Load data from persistent state storage.
    
    Args:
        key: Key to retrieve
        default: Value to return if key doesn't exist (optional)
        
    Returns:
        dict: Retrieved data or default value
        
    Examples:
        loadState(key="last_feed_check")
        loadState(key="kudos_givers", default=[])
    """
    try:
        state_manager = StateManager()
        value = state_manager.get_state(key, default=default)
        
        return {
            "success": True,
            "key": key,
            "value": value,
            "found": value is not None or default is not None
        }
    except Exception as e:
        logger.error(f"Failed to load state for {key}: {e}")
        return {
            "success": False,
            "error": str(e),
            "key": key,
            "value": default
        }


@tool(
    description="List all saved state keys",
    parameters=[],
    returns="List of all state keys with their update times",
    permissions="read"
)
def listStateKeys() -> Dict[str, Any]:
    """
    List all available state keys.
    
    Useful for debugging or checking what data has been saved.
    
    Returns:
        dict: List of keys with metadata
    """
    try:
        import sqlite3
        state_manager = StateManager()
        
        conn = sqlite3.connect(state_manager.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT key, updated_at FROM state ORDER BY updated_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        keys = [{"key": row["key"], "updated_at": row["updated_at"]} for row in rows]
        
        return {
            "success": True,
            "count": len(keys),
            "keys": keys
        }
    except Exception as e:
        logger.error(f"Failed to list state keys: {e}")
        return {
            "success": False,
            "error": str(e),
            "keys": []
        }


@tool(
    description="Merge time-stamped entries into state with automatic deduplication. Perfect for accumulating kudos, activities, or any time-series data across multiple runs.",
    parameters=[
        {"name": "key", "type": "string", "description": "State key (e.g., 'kudos_timeseries', 'activities_timeseries')", "required": True},
        {"name": "entries", "type": "array", "description": "List of entries to merge. Each must have an 'id' field (for deduplication) and 'timestamp' field (ISO format)", "required": True},
        {"name": "id_field", "type": "string", "description": "Field name for unique ID (default: 'id')", "required": False},
        {"name": "timestamp_field", "type": "string", "description": "Field name for timestamp (default: 'timestamp')", "required": False}
    ],
    returns="Merge statistics: added count, duplicates avoided, total entries",
    permissions="write"
)
def mergeTimeseriesState(key: str, entries: List[Dict], id_field: str = "id", timestamp_field: str = "timestamp") -> Dict[str, Any]:
    """
    Merge new time-stamped entries into existing timeseries state.
    
    Automatically deduplicates by ID field, keeping the entry with the newest timestamp.
    Perfect for accumulating data over time without duplicates.
    
    Use cases:
    - Accumulate kudos from multiple "last 24h" queries
    - Build up activity history incrementally
    - Collect comments over time
    
    Args:
        key: State key to store under (e.g., 'kudos_timeseries')
        entries: List of dicts, each must have id_field and timestamp_field
        id_field: Name of field containing unique ID (default: 'id')
        timestamp_field: Name of field containing ISO timestamp (default: 'timestamp')
    
    Returns:
        dict: Statistics about the merge operation
        
    Example:
        # First run - save 15 kudos
        mergeTimeseriesState(
            key="kudos_timeseries",
            entries=[
                {"id": "kudos_123_456", "timestamp": "2025-10-25T10:00:00Z", "athlete": "Alice"},
                {"id": "kudos_124_789", "timestamp": "2025-10-25T09:00:00Z", "athlete": "Bob"},
                # ... 13 more
            ]
        )
        # Result: {"added": 15, "duplicates": 0, "total_count": 15}
        
        # Second run (1 hour later) - same query fetches 17 kudos (15 old + 2 new)
        mergeTimeseriesState(
            key="kudos_timeseries",
            entries=[...17 kudos including the original 15...]
        )
        # Result: {"added": 2, "duplicates": 15, "total_count": 17}
        # No duplicates stored! Only 2 new kudos added.
    """
    try:
        if not entries:
            return {
                "success": True,
                "added": 0,
                "duplicates": 0,
                "total_count": 0,
                "message": "No entries to merge"
            }
        
        # Validate entries have required fields
        for entry in entries:
            if id_field not in entry:
                return {
                    "success": False,
                    "error": f"Entry missing required field '{id_field}': {entry}"
                }
            if timestamp_field not in entry:
                return {
                    "success": False,
                    "error": f"Entry missing required field '{timestamp_field}': {entry}"
                }
        
        # 1. Load existing state
        state_result = loadState(key)
        
        if state_result.get('success') and state_result.get('found'):
            existing = state_result['value']
        else:
            # Initialize new timeseries state
            existing = {
                "entity": key.replace("_timeseries", ""),
                "accumulated_since": None,
                "last_updated": None,
                "count": 0,
                "entries": [],
                "metadata": {
                    "total_api_calls": 0,
                    "total_fetched": 0,
                    "duplicates_avoided": 0
                }
            }
        
        # 2. Build lookup by ID
        entries_by_id = {e[id_field]: e for e in existing.get("entries", [])}
        original_count = len(entries_by_id)
        
        # 3. Merge new entries (keep entry with newest timestamp)
        duplicates = 0
        added = 0
        
        for new_entry in entries:
            entry_id = new_entry[id_field]
            
            if entry_id in entries_by_id:
                # Duplicate - keep newest timestamp
                old_ts = entries_by_id[entry_id][timestamp_field]
                new_ts = new_entry[timestamp_field]
                
                # Compare timestamps (handle both ISO strings and already parsed)
                if isinstance(old_ts, str):
                    old_dt = datetime.fromisoformat(old_ts.replace('Z', '+00:00'))
                else:
                    old_dt = old_ts
                    
                if isinstance(new_ts, str):
                    new_dt = datetime.fromisoformat(new_ts.replace('Z', '+00:00'))
                else:
                    new_dt = new_ts
                
                if new_dt > old_dt:
                    entries_by_id[entry_id] = new_entry
                    
                duplicates += 1
            else:
                # New entry
                entries_by_id[entry_id] = new_entry
                added += 1
        
        # 4. Update metadata
        now = datetime.now(timezone.utc).isoformat()
        
        merged = {
            "entity": existing.get("entity", key.replace("_timeseries", "")),
            "accumulated_since": existing.get("accumulated_since") or now,
            "last_updated": now,
            "count": len(entries_by_id),
            "entries": sorted(
                entries_by_id.values(),
                key=lambda e: e[timestamp_field],
                reverse=True  # Newest first
            ),
            "metadata": {
                "total_api_calls": existing.get("metadata", {}).get("total_api_calls", 0) + 1,
                "total_fetched": existing.get("metadata", {}).get("total_fetched", 0) + len(entries),
                "duplicates_avoided": existing.get("metadata", {}).get("duplicates_avoided", 0) + duplicates
            }
        }
        
        # 5. Save back to state
        saveState(key, merged)
        
        logger.info(f"📊 Merged timeseries '{key}': +{added} new, {duplicates} duplicates avoided, {len(entries_by_id)} total")
        
        return {
            "success": True,
            "added": added,
            "duplicates": duplicates,
            "total_count": len(entries_by_id),
            "message": f"Added {added} new entries, avoided {duplicates} duplicates"
        }
        
    except Exception as e:
        logger.error(f"Failed to merge timeseries state for {key}: {e}")
        return {
            "success": False,
            "error": str(e),
            "added": 0,
            "duplicates": 0,
            "total_count": 0
        }


@tool(
    description="Query time-ranged data from timeseries state. Checks if we have data for the requested range, avoiding unnecessary API calls.",
    parameters=[
        {"name": "key", "type": "string", "description": "State key to query (e.g., 'kudos_timeseries')", "required": True},
        {"name": "start_time", "type": "string", "description": "Start of time range (ISO format, e.g., '2025-10-24T10:00:00Z')", "required": True},
        {"name": "end_time", "type": "string", "description": "End of time range (ISO format, e.g., '2025-10-25T10:00:00Z')", "required": True},
        {"name": "timestamp_field", "type": "string", "description": "Field name for timestamp comparison (default: 'timestamp')", "required": False}
    ],
    returns="Filtered entries within time range + coverage analysis (full/partial/none)",
    permissions="read"
)
def queryTimeseriesState(key: str, start_time: str, end_time: str, timestamp_field: str = "timestamp") -> Dict[str, Any]:
    """
    Query timeseries state for entries within a time range.
    
    Returns filtered entries AND coverage analysis to help decide if API call is needed.
    
    Coverage types:
    - "full": All requested data is in state, no API call needed
    - "partial": Some data in state, but missing older entries (need API for gaps)
    - "none": No data in state for this range, API call required
    
    Args:
        key: State key to query
        start_time: Start timestamp (ISO format)
        end_time: End timestamp (ISO format)
        timestamp_field: Field name containing timestamp (default: 'timestamp')
    
    Returns:
        dict: Filtered entries + coverage info
        
    Example:
        # Query last 2 days of kudos
        result = queryTimeseriesState(
            key="kudos_timeseries",
            start_time="2025-10-23T10:00:00Z",
            end_time="2025-10-25T10:00:00Z"
        )
        
        if result['coverage'] == 'full':
            # Use result['entries'] directly, no API call!
            return format_kudos(result['entries'])
        else:
            # Need to fetch from API
            api_data = fetch_kudos_from_strava(...)
            # Then merge: mergeTimeseriesState(...)
    """
    try:
        # 1. Load state
        state_result = loadState(key)
        
        if not state_result.get('success') or not state_result.get('found'):
            return {
                "success": True,
                "entries": [],
                "count": 0,
                "coverage": "none",
                "needs_api_call": True,
                "reason": "No data in state - first time query",
                "state_range": None
            }
        
        state = state_result['value']
        
        if not state.get("entries"):
            return {
                "success": True,
                "entries": [],
                "count": 0,
                "coverage": "none",
                "needs_api_call": True,
                "reason": "State exists but empty",
                "state_range": None
            }
        
        # 2. Parse time range
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # 3. Filter by time range
        filtered = []
        for entry in state["entries"]:
            entry_ts = entry.get(timestamp_field)
            if not entry_ts:
                continue
                
            if isinstance(entry_ts, str):
                entry_dt = datetime.fromisoformat(entry_ts.replace('Z', '+00:00'))
            else:
                entry_dt = entry_ts
            
            if start <= entry_dt <= end:
                filtered.append(entry)
        
        # 4. Analyze coverage
        if not filtered:
            coverage = "none"
            needs_api = True
            reason = "No entries in requested range"
        else:
            # Check if we have continuous coverage
            # Find oldest entry in entire state
            oldest_in_state = None
            newest_in_state = None
            
            for entry in state["entries"]:
                entry_ts = entry.get(timestamp_field)
                if not entry_ts:
                    continue
                    
                if isinstance(entry_ts, str):
                    entry_dt = datetime.fromisoformat(entry_ts.replace('Z', '+00:00'))
                else:
                    entry_dt = entry_ts
                
                if oldest_in_state is None or entry_dt < oldest_in_state:
                    oldest_in_state = entry_dt
                if newest_in_state is None or entry_dt > newest_in_state:
                    newest_in_state = entry_dt
            
            # Check if state covers our requested range
            if oldest_in_state and oldest_in_state <= start and newest_in_state and newest_in_state >= end:
                coverage = "full"
                needs_api = False
                reason = "Complete coverage from state - no API call needed! 🎉"
            else:
                coverage = "partial"
                needs_api = True
                if oldest_in_state and oldest_in_state > start:
                    reason = f"State only goes back to {oldest_in_state.isoformat()}, need API for older data"
                elif newest_in_state and newest_in_state < end:
                    reason = f"State only goes up to {newest_in_state.isoformat()}, need API for newer data"
                else:
                    reason = "Partial coverage - may have gaps in requested range"
        
        # 5. Build state range info
        state_range = None
        if state.get("entries"):
            timestamps = []
            for entry in state["entries"]:
                entry_ts = entry.get(timestamp_field)
                if entry_ts:
                    if isinstance(entry_ts, str):
                        timestamps.append(datetime.fromisoformat(entry_ts.replace('Z', '+00:00')))
                    else:
                        timestamps.append(entry_ts)
            
            if timestamps:
                state_range = {
                    "oldest": min(timestamps).isoformat(),
                    "newest": max(timestamps).isoformat(),
                    "total_entries": len(state["entries"])
                }
        
        logger.info(f"📊 Query '{key}': {len(filtered)} entries, coverage={coverage}")
        
        return {
            "success": True,
            "entries": filtered,
            "count": len(filtered),
            "coverage": coverage,
            "needs_api_call": needs_api,
            "reason": reason,
            "state_range": state_range,
            "requested_range": {
                "start": start_time,
                "end": end_time
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to query timeseries state for {key}: {e}")
        return {
            "success": False,
            "error": str(e),
            "entries": [],
            "count": 0,
            "coverage": "none",
            "needs_api_call": True,
            "reason": f"Error: {str(e)}"
        }


# =============================================================================
# DATE/TIME UTILITIES - Critical for preventing timestamp hallucination
# =============================================================================

@tool(
    description="Get current date and time. ALWAYS call this FIRST before calculating timestamps to avoid hallucination! Returns current Unix timestamp, ISO string, and human-readable format.",
    parameters=[
        {"name": "timezone", "type": "string", "description": "Timezone (default: UTC). Use 'UTC' for consistency.", "required": False}
    ],
    returns="Current date/time with unix_timestamp, iso_string, human_readable, year, month, day components",
    permissions="read"
)
def getCurrentDateTime(timezone: str = "UTC") -> Dict[str, Any]:
    """
    Get current date and time in multiple formats.
    
    ALWAYS call this FIRST before doing any date calculations!
    This prevents hallucinating what "today" or "now" means.
    
    Args:
        timezone: Timezone name (default: UTC)
    
    Returns:
        dict with:
        - unix_timestamp: Current Unix timestamp (seconds since 1970)
        - iso_string: ISO 8601 format (e.g., "2024-01-15T10:30:00Z")
        - human_readable: Easy to read format (e.g., "January 15, 2024 10:30 AM")
        - date: Just the date (e.g., "2024-01-15")
        - year, month, day, hour, minute, second: Individual components
    """
    try:
        from datetime import datetime, timezone as tz
        
        # Use UTC (standard library doesn't support other timezones easily)
        now = datetime.now(tz.utc)
        
        return {
            "success": True,
            "unix_timestamp": int(now.timestamp()),
            "iso_string": now.isoformat(),
            "human_readable": now.strftime("%B %d, %Y %I:%M %p UTC"),
            "date": now.strftime("%Y-%m-%d"),
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "timezone": "UTC"
        }
    except Exception as e:
        logger.error(f"Failed to get current date/time: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool(
    description="Get start AND end Unix timestamps for a month/date range. Use this when you need BOTH start and end times (e.g., 'January 2024' returns Jan 1 00:00 AND Jan 31 23:59). Perfect for filtering activities in a date range.",
    parameters=[
        {"name": "year", "type": "int", "description": "Year (e.g., 2024)", "required": True},
        {"name": "month", "type": "int", "description": "Month (1-12, e.g., 1 = January)", "required": True},
        {"name": "end_year", "type": "int", "description": "Optional: End year (if different from start)", "required": False},
        {"name": "end_month", "type": "int", "description": "Optional: End month (if different from start month). If omitted, uses same month as start.", "required": False},
        {"name": "timezone", "type": "string", "description": "Always use 'UTC'", "required": False}
    ],
    returns="Dict with after_unix (start timestamp) and before_unix (end timestamp) - ready to use with Strava API",
    permissions="read"
)
def getDateRangeTimestamps(year: int, month: int, end_year: int = None, end_month: int = None, timezone: str = "UTC") -> Dict[str, Any]:
    """
    Get both start and end Unix timestamps for a date range.
    
    Perfect for filtering activities by date range in Strava API.
    Examples:
    - "January 2024" → getDateRangeTimestamps(2024, 1) → returns start (Jan 1) and end (Jan 31 23:59:59)
    - "January to March 2024" → getDateRangeTimestamps(2024, 1, end_month=3)
    
    Args:
        year: Start year
        month: Start month (1-12)
        end_year: Optional end year (defaults to start year)
        end_month: Optional end month (defaults to start month)
        timezone: Timezone (default: UTC)
    
    Returns:
        dict with:
        - after_unix: Start timestamp (beginning of period)
        - before_unix: End timestamp (end of period)
        - start_human: Readable start date
        - end_human: Readable end date
    """
    try:
        from datetime import datetime, timezone as tz
        from calendar import monthrange
        
        # Default end to same as start if not provided
        if end_year is None:
            end_year = year
        if end_month is None:
            end_month = month
        
        # Start: First day of start month at 00:00:00
        start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=tz.utc)
        
        # End: Last day of end month at 23:59:59
        last_day = monthrange(end_year, end_month)[1]  # Get last day of month
        end_dt = datetime(end_year, end_month, last_day, 23, 59, 59, tzinfo=tz.utc)
        
        return {
            "success": True,
            "after_unix": int(start_dt.timestamp()),
            "before_unix": int(end_dt.timestamp()),
            "start_iso": start_dt.isoformat(),
            "end_iso": end_dt.isoformat(),
            "start_human": start_dt.strftime("%B %d, %Y %I:%M %p UTC"),
            "end_human": end_dt.strftime("%B %d, %Y %I:%M %p UTC"),
            "input": {
                "year": year,
                "month": month,
                "end_year": end_year,
                "end_month": end_month,
                "timezone": "UTC"
            }
        }
    except Exception as e:
        logger.error(f"Failed to get date range timestamps: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool(
    description="Convert human date to Unix timestamp WITHOUT GUESSING! Example: 'January 2024' = dateToUnixTimestamp(2024, 1, 1). Returns exact timestamp you can use with Strava API.",
    parameters=[
        {"name": "year", "type": "int", "description": "Year (e.g., 2024)", "required": True},
        {"name": "month", "type": "int", "description": "Month (1-12, e.g., 1 = January)", "required": True},
        {"name": "day", "type": "int", "description": "Day (default: 1 = start of month)", "required": False},
        {"name": "hour", "type": "int", "description": "Hour (default: 0)", "required": False},
        {"name": "minute", "type": "int", "description": "Minute (default: 0)", "required": False},
        {"name": "timezone", "type": "string", "description": "Always use 'UTC'", "required": False}
    ],
    returns="Dict with unix_timestamp (use this!), iso_string, human_readable, and input echo",
    permissions="read"
)
def dateToUnixTimestamp(year: int, month: int, day: int = 1, hour: int = 0, minute: int = 0, timezone: str = "UTC") -> Dict[str, Any]:
    """
    Convert a specific date to Unix timestamp.
    
    Use this instead of guessing timestamps! Example:
    - "January 2024" → dateToUnixTimestamp(2024, 1, 1)
    - "End of January 2024" → dateToUnixTimestamp(2024, 2, 1) - 1
    
    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)
        day: Day (default: 1 = start of month)
        hour: Hour (default: 0)
        minute: Minute (default: 0)
        timezone: Timezone (default: UTC)
    
    Returns:
        dict with:
        - unix_timestamp: The Unix timestamp
        - iso_string: ISO format
        - human_readable: Readable format
        - input: Echo of input parameters
    """
    try:
        from datetime import datetime, timezone as tz
        
        # Create datetime in UTC
        dt = datetime(year, month, day, hour, minute, 0, tzinfo=tz.utc)
        
        return {
            "success": True,
            "unix_timestamp": int(dt.timestamp()),
            "iso_string": dt.isoformat(),
            "human_readable": dt.strftime("%B %d, %Y %I:%M %p UTC"),
            "input": {
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "timezone": "UTC"
            }
        }
    except Exception as e:
        logger.error(f"Failed to convert date to timestamp: {e}")
        return {
            "success": False,
            "error": str(e),
            "input": {
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute
            }
        }


@tool(
    description="Calculate timestamp for relative time like '30 days ago' or 'last week'. Prevents hallucination by using current time as reference.",
    parameters=[
        {"name": "days_ago", "type": "int", "description": "Days in past (e.g., 30 = 30 days ago)", "required": False},
        {"name": "hours_ago", "type": "int", "description": "Hours in past", "required": False},
        {"name": "weeks_ago", "type": "int", "description": "Weeks in past (e.g., 1 = last week)", "required": False},
        {"name": "months_ago", "type": "int", "description": "Approximate months (30 days each)", "required": False}
    ],
    returns="Dict with unix_timestamp (use with Strava API), iso_string, human_readable, days_difference",
    permissions="read"
)
def getRelativeTimestamp(days_ago: int = 0, hours_ago: int = 0, weeks_ago: int = 0, months_ago: int = 0) -> Dict[str, Any]:
    """
    Calculate timestamp for relative time periods.
    
    Examples:
    - "Last 30 days" → getRelativeTimestamp(days_ago=30)
    - "Last week" → getRelativeTimestamp(weeks_ago=1)
    - "Last 3 months" → getRelativeTimestamp(months_ago=3)
    
    Args:
        days_ago: Days in the past
        hours_ago: Hours in the past
        weeks_ago: Weeks in the past
        months_ago: Months in the past (approximate, 30 days each)
    
    Returns:
        dict with:
        - unix_timestamp: The calculated timestamp
        - iso_string: ISO format
        - human_readable: Readable description
        - days_difference: Total days calculated
    """
    try:
        from datetime import datetime, timedelta
        
        # Calculate total offset
        total_days = days_ago + (weeks_ago * 7) + (months_ago * 30)
        total_hours = hours_ago
        
        # Get current time and subtract
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=total_days, hours=total_hours)
        
        return {
            "success": True,
            "unix_timestamp": int(past.timestamp()),
            "iso_string": past.isoformat(),
            "human_readable": past.strftime("%B %d, %Y %I:%M %p UTC"),
            "days_difference": total_days,
            "calculation": f"{total_days} days and {total_hours} hours ago from now"
        }
    except Exception as e:
        logger.error(f"Failed to calculate relative timestamp: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool(
    description="Validate if Unix timestamp makes sense for expected date. CRITICAL: Use this to catch hallucinated timestamps! Checks if timestamp is reasonable (not future, not too old) and matches expected description.",
    parameters=[
        {"name": "unix_timestamp", "type": "int", "description": "Unix timestamp to validate", "required": True},
        {"name": "expected_description", "type": "string", "description": "What timestamp should represent (e.g., 'January 2024', 'last 30 days')", "required": True}
    ],
    returns="Dict with is_valid (bool), warnings (list), human_readable (actual date), year, month, day. Check warnings!",
    permissions="read"
)
def validateTimestamp(unix_timestamp: int, expected_description: str) -> Dict[str, Any]:
    """
    Validate if a timestamp makes sense.
    
    Use this to catch hallucinated timestamps! Example:
    - You calculated timestamp for "January 2024"
    - Call validateTimestamp(1704067200, "January 2024")
    - Check if returned date matches what you expect
    
    Args:
        unix_timestamp: The timestamp to validate
        expected_description: Human description of what it should be
    
    Returns:
        dict with:
        - is_valid: Whether timestamp is reasonable (not in future, not too old)
        - unix_timestamp: Echo of input
        - human_readable: What the timestamp actually represents
        - year, month, day: Components
        - is_future: Whether it's in the future (BAD!)
        - years_ago: How many years in the past
        - expected: Echo of expected description
    """
    try:
        from datetime import datetime
        
        # Convert timestamp to datetime
        dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Calculate age
        diff = now - dt
        years_ago = diff.days / 365.25
        is_future = diff.days < 0
        
        # Sanity checks
        is_valid = True
        warnings = []
        
        if is_future:
            is_valid = False
            warnings.append("⚠️ Timestamp is in the FUTURE!")
        
        if years_ago > 50:
            is_valid = False
            warnings.append(f"⚠️ Timestamp is {int(years_ago)} years ago (too old?)")
        
        # Check if month/year roughly matches description
        if "january" in expected_description.lower() and dt.month != 1:
            warnings.append(f"⚠️ Expected January, but got {dt.strftime('%B')}")
        if "2024" in expected_description and dt.year != 2024:
            warnings.append(f"⚠️ Expected 2024, but got {dt.year}")
        
        return {
            "success": True,
            "is_valid": is_valid,
            "unix_timestamp": unix_timestamp,
            "human_readable": dt.strftime("%B %d, %Y %I:%M %p UTC"),
            "iso_string": dt.isoformat(),
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
            "is_future": is_future,
            "years_ago": round(years_ago, 2),
            "days_ago": diff.days,
            "expected": expected_description,
            "warnings": warnings
        }
    except Exception as e:
        logger.error(f"Failed to validate timestamp: {e}")
        return {
            "success": False,
            "error": str(e),
            "is_valid": False,
            "unix_timestamp": unix_timestamp,
            "expected": expected_description
        }
