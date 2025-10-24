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
    description="Use LLM to analyze, filter, format, or transform data. NOT a regular tool - use 'input' and 'output_format' fields instead of 'tool' and 'params'. Example: analyze activities to find which need updates, format data for display, extract specific fields, summarize results.",
    parameters=[
        {"name": "input", "type": "any", "description": "Data to analyze (use template variables like {{step_id.result}})", "required": True},
        {"name": "context", "type": "string", "description": "Instructions for what to analyze/extract/format", "required": True},
        {"name": "output_format", "type": "object", "description": "JSON structure defining expected output format", "required": True}
    ],
    returns="Analyzed/formatted data matching output_format",
    permissions="read"
)
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
