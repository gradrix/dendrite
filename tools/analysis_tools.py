"""
Utility tool for executing safe Python code for data analysis.

Allows the AI to write simple Python code to analyze data.
Supports loading large data from disk references.
"""

import json
import logging
import signal
import ast
import re
from typing import Any, Dict

from agent.tool_registry import tool
from agent.data_compaction import load_data_reference

logger = logging.getLogger(__name__)


def validate_code_structure(python_code: str, context: Dict) -> Dict[str, Any]:
    """
    Validate Python code against actual data structure in context.
    Catches issues like accessing non-existent fields.
    
    Args:
        python_code: The Python code to validate
        context: The actual context data available
        
    Returns:
        Dictionary with validation results and suggested fixes
    """
    issues = []
    suggested_fix = python_code
    
    # Extract field accesses like x['field'] or x.get('field')
    field_access_pattern = r"x\[(['\"])(\w+)\1\]"
    field_accesses = re.findall(field_access_pattern, python_code)
    
    if not field_accesses:
        return {'has_issues': False}
    
    # Extract which context key is being used
    context_key_pattern = r"get_context_list\(['\"](\w+)['\"]"
    context_keys = re.findall(context_key_pattern, python_code)
    
    if not context_keys:
        return {'has_issues': False}
    
    # Get actual data structure from first context key
    context_key = context_keys[0]
    data = context.get(context_key)
    
    if not data:
        return {'has_issues': False}
    
    # Load actual items to inspect structure
    actual_items = None
    if isinstance(data, dict):
        if data.get('_format') == 'disk_reference':
            try:
                loaded = load_data_reference(data['_ref_id'])
                if isinstance(loaded, list) and len(loaded) > 0:
                    actual_items = loaded
                elif isinstance(loaded, dict):
                    for field in ['items', 'entries', 'data', 'results']:
                        if field in loaded and isinstance(loaded[field], list) and len(loaded[field]) > 0:
                            actual_items = loaded[field]
                            break
            except:
                pass
        elif 'items' in data and isinstance(data['items'], list) and len(data['items']) > 0:
            actual_items = data['items']
        elif 'result' in data and isinstance(data['result'], list) and len(data['result']) > 0:
            actual_items = data['result']
    elif isinstance(data, list) and len(data) > 0:
        actual_items = data
    
    if not actual_items:
        return {'has_issues': False}
    
    # Get first item to check structure
    sample_item = actual_items[0]
    if not isinstance(sample_item, dict):
        return {'has_issues': False}
    
    available_fields = set(sample_item.keys())
    
    # Check each accessed field
    accessed_fields = set(field[1] for field in field_accesses)
    missing_fields = accessed_fields - available_fields
    
    if missing_fields:
        issues.append(f"Fields {missing_fields} not found in data. Available: {list(available_fields)[:10]}")
        
        # Try to auto-fix by using .get() with defaults
        for field in missing_fields:
            # Replace x['field'] with x.get('field', None)
            suggested_fix = re.sub(
                rf"x\[['\"]"+ field + rf"['\"]\]",
                f"x.get('{field}', None)",
                suggested_fix
            )
        
        return {
            'has_issues': True,
            'issues': issues,
            'suggested_fix': suggested_fix,
            'available_fields': list(available_fields)
        }
    
    return {'has_issues': False}


@tool(
    name="executeDataAnalysis",
    description="Execute Python code for 100% accurate counting, filtering, and formatting. Use this for ANY counting or formatting task. Has helper functions to access context data easily: get_context_data(key), get_context_list(key), get_context_field(key, field). Must assign result to 'result' variable.",
    parameters=[
        {
            "name": "python_code",
            "type": "string",
            "description": "Python code to execute. SIMPLE PATTERN: (1) Get data: my_list = get_context_list('neuron_0_2') - automatically handles disk/inline data; (2) Process: result = '\\n'.join([f\"{x['name']}: {x['distance']}m\" for x in my_list[:3]]). Available functions: get_context_data(key) - get any data, get_context_list(key) - always returns list, get_context_field(key, field) - get specific field. USE ACTUAL KEYS from context (e.g., 'neuron_0_2', 'dendrite_item_1_2'). Must assign to 'result' variable. DO NOT use load_data_reference or _ref_id - use helper functions instead!",
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
        
        # Helper functions for unified context access
        def get_context_data(key):
            """
            Universal data accessor - handles all storage formats automatically.
            Returns the actual data regardless of whether it's:
            - Disk reference (_format: disk_reference)
            - Result wrapper (has 'result' field)
            - Direct data (dict, list, scalar)
            """
            value = context.get(key)
            if value is None:
                return None
            
            # Handle disk reference
            if isinstance(value, dict) and value.get('_format') == 'disk_reference':
                return load_data_reference(value['_ref_id'])
            
            # Handle result wrapper
            if isinstance(value, dict) and 'result' in value and 'success' in value:
                return value['result']
            
            # Return direct data
            return value
        
        def get_context_list(key):
            """
            Get a list from context, handling all storage formats.
            Always returns a list or None.
            """
            data = get_context_data(key)
            if data is None:
                return None
            
            # Already a list
            if isinstance(data, list):
                return data
            
            # Try common list field names
            if isinstance(data, dict):
                for field in ['items', 'entries', 'data', 'results', 'activities']:
                    if field in data and isinstance(data[field], list):
                        return data[field]
            
            # Single item - wrap in list
            return [data]
        
        def get_context_field(key, field):
            """
            Get a specific field from context data.
            Example: get_context_field('dendrite_item_1_2', 'name')
            """
            data = get_context_data(key)
            if data is None:
                return None
            
            if isinstance(data, dict):
                return data.get(field)
            
            return None
        
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
            # New unified access functions
            'get_context_data': get_context_data,
            'get_context_list': get_context_list,
            'get_context_field': get_context_field,
        }
        
        # STEP 1: Validate code against actual data structure
        # This catches issues like accessing x['athlete'] when 'athlete' doesn't exist
        validation_result = validate_code_structure(python_code, context)
        if validation_result.get('has_issues'):
            logger.warning(f"⚠️ Code structure issues detected:")
            for issue in validation_result.get('issues', []):
                logger.warning(f"   - {issue}")
            
            # Try to auto-fix simple issues
            fixed_code = validation_result.get('suggested_fix')
            if fixed_code and fixed_code != python_code:
                logger.info(f"🔧 Attempting auto-fix...")
                logger.info(f"   Original: {python_code[:100]}...")
                logger.info(f"   Fixed:    {fixed_code[:100]}...")
                python_code = fixed_code
        
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
    except KeyError as e:
        # Special handling for KeyError - very common with wrong field access
        field_name = str(e).strip("'\"")
        logger.error(f"❌ KeyError: Field '{field_name}' not found in data")
        
        # Try to identify which data structure caused the error
        hint = f"Field '{field_name}' doesn't exist in the data. "
        
        # Get sample of available fields from context
        available_fields = set()
        for key, value in context.items():
            if isinstance(value, dict) and not key.startswith('_'):
                # Check if this is the data being accessed
                if '_ref_id' in value:
                    try:
                        loaded = load_data_reference(value['_ref_id'])
                        if isinstance(loaded, list) and len(loaded) > 0 and isinstance(loaded[0], dict):
                            available_fields.update(loaded[0].keys())
                            break
                    except:
                        pass
                elif 'items' in value and isinstance(value['items'], list) and len(value['items']) > 0:
                    if isinstance(value['items'][0], dict):
                        available_fields.update(value['items'][0].keys())
                        break
        
        if available_fields:
            hint += f"Available fields: {list(available_fields)[:15]}. Use x.get('{field_name}', default) for optional fields."
        else:
            hint += "Check the data structure - the field you're trying to access doesn't exist."
        
        return {
            'success': False,
            'error': f"KeyError: '{field_name}'",
            'retry': True,
            'hint': hint,
            'available_fields': list(available_fields) if available_fields else None
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

