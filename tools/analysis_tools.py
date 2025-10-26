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
    description="Execute Python code for 100% accurate counting, filtering, and FORMATTING. CRITICAL: Use this for ANY counting task - AI models miscount, Python doesn't. For FORMATTING tasks with disk references: 1) Load data with load_data_reference(), 2) Build human-readable STRING output (not raw dicts). Access data via context keys like data['neuron_0_2']. Check if '_ref_id' exists - if yes, must load first. Must assign result to 'result' variable. Safe execution - no file I/O (except load_data_reference), no imports.",
    parameters=[
        {
            "name": "python_code",
            "type": "string",
            "description": "Python code to execute. Has access to 'data' variable and load_data_reference() function. FOR FORMATTING: Build readable STRING, e.g. result = '\\n'.join([f\"{item['name']} - {item['distance']}m on {item['start_date'][:10]}\" for item in items]). FOR COUNTING: result = len([x for x in items if...]). IMPORTANT: If '_ref_id' in data, MUST load first: loaded = load_data_reference(data['key']['_ref_id']); items = loaded['items']. If no _ref_id: items = data['key']['items']. Must assign to 'result' variable.",
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
