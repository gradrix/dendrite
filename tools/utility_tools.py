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
