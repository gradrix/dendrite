"""
Utility tool for executing safe Python code for data analysis.

Allows the AI to write simple Python code to analyze data.
Supports loading large data from disk references.
"""

import json
import logging
import signal
import ast
from typing import Any, Dict

from agent.tool_registry import tool
from agent.data_compaction import load_data_reference

logger = logging.getLogger(__name__)


@tool(
    name="executeDataAnalysis",
    description="Execute Python code for 100% accurate counting, filtering, and FORMATTING. CRITICAL: Use this for ANY counting task - AI models miscount, Python doesn't. For FORMATTING tasks: ALWAYS follow 3 steps: 1) Load data: loaded = load_data_reference(REF_ID), 2) Extract list: my_list = loaded.get('items') or loaded.get('data') or loaded, 3) Format: result = 'formatted string'. NEVER assume 'items' exists - always extract first! Must assign result to 'result' variable. Safe execution - no file I/O (except load_data_reference), no imports.",
    parameters=[
        {
            "name": "python_code",
            "type": "string",
            "description": "Python code to execute. Has access to 'data' dict and load_data_reference() function. CRITICAL: NEVER use undefined variables! ALWAYS extract data first. STEP-BY-STEP PATTERN: (1) Get ref_id from data dict - LOOK at available keys in data to find the right one, e.g., ref_id = data['neuron_0_2']['_ref_id']; (2) Load: loaded = load_data_reference(ref_id); (3) Extract list: my_list = loaded.get('items') or loaded.get('data') or loaded; (4) Format: result = '\\n'.join([f\"{x['name']}: {x['distance']}m\" for x in my_list[:3]]). DO NOT use placeholder keys like 'neuron_0_X' - use ACTUAL keys from context. DO NOT call format() function - construct the result string yourself. Must assign final output to 'result' variable.",
            "required": True
        }
    ],
    permissions="read"
)
def execute_data_analysis(python_code: str, **context) -> Dict[str, Any]:
    """
    Execute safe Python code for data analysis.
    
    Args:
        python_code: Python code to execute
        **context: Context data available as 'data' variable
        
    Returns:
        Result of the analysis
    """
    
    # Timeout handler
    def timeout_handler(signum, frame):
        raise TimeoutError("Code execution exceeded 10 second timeout")
    
    try:
        # Validate syntax first
        try:
            parsed = ast.parse(python_code)
        except SyntaxError as e:
            logger.error(f"❌ Syntax error in Python code: {e}")
            return {
                'success': False,
                'error': f"Syntax error: {e}",
                'retry': True
            }
        
        # Check for undefined variables (like 'items' when it doesn't exist)
        # This catches common AI mistakes where it assumes variables exist
        used_names = set()
        for node in ast.walk(parsed):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
        
        # Variables that will be available during execution
        available_vars = {'data', 'result', 'load_data_reference', 'len', 'sum', 'min', 'max', 
                         'sorted', 'list', 'dict', 'str', 'int', 'float', 'bool', 'enumerate', 
                         'range', 'zip', 'filter', 'map', 'any', 'all', 'round', 'abs'}
        
        # Check if code uses undefined variables
        undefined = used_names - available_vars
        if undefined:
            # Common mistake: using 'items' without defining it first
            if 'items' in undefined:
                logger.error(f"❌ Variable 'items' is not defined. Must extract from data first!")
                return {
                    'success': False,
                    'error': "name 'items' is not defined",
                    'retry': True,
                    'hint': "Need to extract items from data first. Check if data has '_ref_id' and load it, or access data['key']['items']. Available keys: " + str(list(context.keys()))
                }
            else:
                logger.warning(f"⚠️ Code uses potentially undefined variables: {undefined}")
                # Don't block - might be defined in the code itself
        
        # Check for dangerous patterns
        dangerous_patterns = ['import os', 'import sys', 'import subprocess', '__import__', 'eval(', 'exec(', 'open(', 'file(']
        for pattern in dangerous_patterns:
            if pattern in python_code:
                logger.warning(f"⚠️ Potentially dangerous pattern detected: {pattern}")
                return {
                    'success': False,
                    'error': f"Code contains potentially dangerous pattern: {pattern}",
                    'retry': False
                }
        
        # Prepare safe execution environment
        safe_globals = {
            '__builtins__': {
                'len': len,
                'sum': sum,
                'min': min,
                'max': max,
                'sorted': sorted,
                'list': list,
                'dict': dict,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'enumerate': enumerate,
                'range': range,
                'zip': zip,
                'filter': filter,
                'map': map,
                'any': any,
                'all': all,
                'round': round,
                'abs': abs,
            },
            'data': context,
            'result': None,
            'load_data_reference': load_data_reference,  # Allow loading disk references
        }
        
        # Execute the code with timeout
        logger.info(f"🐍 Executing Python code for data analysis...")
        logger.debug(f"Code:\n{python_code}")
        
        # Set timeout alarm (10 seconds)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)
        
        try:
            exec(python_code, safe_globals)
        finally:
            # Cancel the alarm
            signal.alarm(0)
        
        result = safe_globals.get('result')
        
        if result is None:
            logger.warning("Code did not assign to 'result' variable")
            return {
                'success': False,
                'error': "Code must assign result to 'result' variable",
                'retry': True
            }
        
        logger.info(f"✅ Analysis complete: {result}")
        
        return {
            'success': True,
            'result': result
        }
        
    except TimeoutError as e:
        logger.error(f"⏱️ Timeout: {e}")
        return {
            'success': False,
            'error': str(e),
            'retry': True,
            'hint': 'Code took too long - simplify the logic or reduce iterations'
        }
    except Exception as e:
        logger.error(f"❌ Error executing Python code: {e}")
        return {
            'success': False,
            'error': str(e),
            'retry': True
        }


def inspect_data_structure(data_dict: Dict, max_depth: int = 3) -> str:
    """
    Inspect the structure of data to help AI understand what's available.
    Returns a tree-like string showing keys and types.
    
    Args:
        data_dict: Dictionary to inspect
        max_depth: Maximum depth to recurse
        
    Returns:
        String representation of data structure
    """
    def inspect_value(val, depth=0, key_name="root"):
        if depth > max_depth:
            return f"{'  ' * depth}... (max depth)\n"
        
        indent = '  ' * depth
        result = ""
        
        if isinstance(val, dict):
            # Show dict keys
            if '_ref_id' in val and '_format' in val:
                # This is a compacted reference - try to load it
                try:
                    from pathlib import Path
                    import json
                    data_file = val.get('_data_file')
                    if data_file and Path(data_file).exists():
                        with open(data_file, 'r') as f:
                            loaded = json.load(f)
                        result += f"{indent}{key_name}: <compacted_data> → "
                        # Show what's inside the compacted data
                        if isinstance(loaded, list):
                            result += f"List[{len(loaded)} items]\n"
                            if len(loaded) > 0:
                                result += f"{indent}  Sample item keys: {list(loaded[0].keys())[:15]}\n"
                        elif isinstance(loaded, dict):
                            result += f"Dict with keys: {list(loaded.keys())[:15]}\n"
                        return result
                except Exception:
                    pass
            
            result += f"{indent}{key_name}: Dict with {len(val)} keys\n"
            for k, v in list(val.items())[:10]:  # Limit to first 10 keys
                result += inspect_value(v, depth + 1, k)
            if len(val) > 10:
                result += f"{indent}  ... and {len(val) - 10} more keys\n"
                
        elif isinstance(val, list):
            result += f"{indent}{key_name}: List[{len(val)} items]\n"
            if len(val) > 0:
                result += f"{indent}  Sample item type: {type(val[0]).__name__}\n"
                if isinstance(val[0], dict):
                    result += f"{indent}  Sample item keys: {list(val[0].keys())[:15]}\n"
                    
        else:
            val_type = type(val).__name__
            result += f"{indent}{key_name}: {val_type}\n"
            
        return result
    
    return inspect_value(data_dict)

