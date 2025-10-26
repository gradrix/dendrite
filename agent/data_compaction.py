"""
Smart context storage with automatic large data handling.

Instead of hardcoded compaction rules, this system:
1. Detects large data structures (> threshold size)
2. Saves full data to disk with a reference ID
3. Stores only a summary + reference in context
4. Python analysis tools can load full data when needed

This is tool-agnostic and lets AI work with any size data.
"""
import logging
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Configuration
MAX_CONTEXT_SIZE_BYTES = 5000  # Store full data if under 5KB, otherwise save to disk
STATE_DIR = Path(__file__).parent.parent / "state" / "data_cache"


def compact_data(data: Any, context_key: str = "data", run_id: Optional[str] = None) -> Any:
    """
    Smart data storage: Keep small data in context, save large data to disk.
    
    Args:
        data: The data to store (any type)
        context_key: Key name for this data (used in filename)
        run_id: Unique run identifier to prevent cache reuse across runs
        
    Returns:
        Either the original data (if small) or a reference dict (if large)
    """
    # Calculate data size
    data_str = json.dumps(data, default=str)
    data_size = len(data_str.encode('utf-8'))
    
    # If small enough, return as-is
    if data_size < MAX_CONTEXT_SIZE_BYTES:
        return data
    
    # Large data: Save to disk and return reference
    logger.info(f"💾 Large data detected ({data_size / 1024:.1f}KB), saving to disk...")
    
    # Create state directory if needed
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate reference ID with run_id to prevent cache reuse
    data_hash = hashlib.md5(data_str.encode()).hexdigest()[:12]
    ref_id = f"{context_key}_{run_id}_{data_hash}" if run_id else f"{context_key}_{data_hash}"
    
    # Save full data to disk
    data_file = STATE_DIR / f"{ref_id}.json"
    with open(data_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    # Generate summary for context
    summary = _generate_summary(data)
    
    # Return reference object
    reference = {
        '_ref_id': ref_id,
        '_data_file': str(data_file),
        '_size_kb': round(data_size / 1024, 1),
        '_format': 'disk_reference',
        'summary': summary,
        '_usage_hint': f'Use executeDataAnalysis with: data = load_data_reference("{ref_id}")'
    }
    
    logger.info(f"✅ Saved to: {data_file.name}")
    logger.info(f"📋 Summary: {summary[:100]}...")
    
    return reference


def load_data_reference(ref_id: str) -> Any:
    """
    Load full data from disk reference.
    
    This function is available in executeDataAnalysis Python environment.
    
    Args:
        ref_id: Reference ID from the context
        
    Returns:
        Full data structure
    """
    data_file = STATE_DIR / f"{ref_id}.json"
    
    if not data_file.exists():
        raise FileNotFoundError(f"Data reference not found: {ref_id}")
    
    with open(data_file, 'r') as f:
        return json.load(f)


def _generate_summary(data: Any) -> str:
    """
    Generate a human-readable summary of data structure.
    Includes sample data for the first few items to help with formatting tasks.
    
    Args:
        data: The data to summarize
        
    Returns:
        Summary string
    """
    if isinstance(data, dict):
        # Check for common list patterns
        for key in data.keys():
            value = data[key]
            if isinstance(value, list) and len(value) > 0:
                item_type = type(value[0]).__name__
                sample_keys = list(value[0].keys())[:5] if isinstance(value[0], dict) else []
                keys_str = f" with fields: {', '.join(sample_keys)}" if sample_keys else ""
                
                # Include sample of first 3 items for formatting tasks
                sample_data = ""
                if isinstance(value[0], dict):
                    sample_items = value[:3]  # First 3 items
                    sample_data = "\nFirst 3 items: " + json.dumps(sample_items, indent=2, default=str)[:500]
                
                return f"List of {len(value)} {item_type}{keys_str}{sample_data}"
        
        # Generic dict summary
        keys = list(data.keys())[:5]
        return f"Dict with keys: {', '.join(keys)}"
    
    elif isinstance(data, list):
        if len(data) == 0:
            return "Empty list"
        item_type = type(data[0]).__name__
        sample_keys = list(data[0].keys())[:5] if isinstance(data[0], dict) else []
        keys_str = f" with fields: {', '.join(sample_keys)}" if sample_keys else ""
        
        # Include sample of first 3 items for formatting tasks
        sample_data = ""
        if isinstance(data[0], dict):
            sample_items = data[:3]  # First 3 items
            # Extract key fields only to keep it compact
            compact_sample = []
            for item in sample_items:
                compact_item = {}
                # Common important fields
                for field in ['name', 'type', 'distance', 'moving_time', 'start_date', 'start_date_local', 'id']:
                    if field in item:
                        compact_item[field] = item[field]
                compact_sample.append(compact_item)
            sample_data = "\n\nFirst 3 items:\n" + json.dumps(compact_sample, indent=2, default=str)
        
        return f"List of {len(data)} {item_type}{keys_str}{sample_data}"
    
    else:
        return f"{type(data).__name__}: {str(data)[:100]}"
