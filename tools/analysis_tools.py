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
    description="Execute Python code for 100% accurate counting, filtering, and analysis. CRITICAL: Use this for ANY counting task (even 'how many' questions) - AI models miscount, Python doesn't. Access data via context keys like data['neuron_0_2']. If data is a disk reference (_format='disk_reference'), use load_data_reference(ref_id) which returns a dict with 'activities' key. Must assign result to 'result' variable. Safe execution - no file I/O (except load_data_reference), no imports.",
    parameters=[
        {
            "name": "python_code",
            "type": "string",
            "description": "Python code to execute. Has access to 'data' variable containing all context and load_data_reference() function. IMPORTANT: load_data_reference() returns {'activities': [...], 'count': N, 'success': True}, so use loaded_data['activities'] to access the list. Example: ref_id = data['neuron_0_2']['_ref_id']; loaded = load_data_reference(ref_id); result = len([x for x in loaded['activities'] if 'Run' in x.get('sport_type', '')]). Must assign to 'result' variable.",
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
            ast.parse(python_code)
        except SyntaxError as e:
            logger.error(f"❌ Syntax error in Python code: {e}")
            return {
                'success': False,
                'error': f"Syntax error: {e}",
                'retry': True
            }
        
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
