"""
Utility tool for executing safe Python code for data analysis.

Allows the AI to write simple Python code to analyze data.
"""

import json
import logging
from typing import Any, Dict

from agent.tool_registry import tool

logger = logging.getLogger(__name__)


@tool(
    name="executeDataAnalysis",
    description="Execute Python code for 100% accurate counting, filtering, and analysis. CRITICAL: Use this for ANY counting task (even 'how many' questions) - AI models miscount, Python doesn't. Access data via context keys like data['neuron_0_2']['activities']. Example: count runs = len([x for x in data['neuron_0_2']['activities'] if 'Run' in x.get('sport_type', '')]). Must assign result to 'result' variable. Safe execution - no file I/O, no imports.",
    parameters=[
        {
            "name": "python_code",
            "type": "string",
            "description": "Python code to execute. Has access to 'data' variable containing all context. Must assign result to 'result' variable. Example for counting: result = {'count': len([x for x in data['neuron_0_2']['activities'] if 'Run' in x.get('sport_type', '')])}}. Context keys are like 'neuron_0_1', 'neuron_0_2', etc.",
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
    try:
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
            'result': None
        }
        
        # Execute the code
        logger.info(f"🐍 Executing Python code for data analysis...")
        logger.debug(f"Code:\n{python_code}")
        
        exec(python_code, safe_globals)
        
        result = safe_globals.get('result')
        
        if result is None:
            logger.warning("Code did not assign to 'result' variable")
            return {
                'success': False,
                'error': "Code must assign result to 'result' variable"
            }
        
        logger.info(f"✅ Analysis complete: {result}")
        
        return {
            'success': True,
            'result': result
        }
        
    except Exception as e:
        logger.error(f"❌ Error executing Python code: {e}")
        return {
            'success': False,
            'error': str(e)
        }
