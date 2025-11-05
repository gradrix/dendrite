"""
Shadow Testing - Safe Parallel Version Comparison

Run old and new versions of a tool in parallel, compare outputs.
Safe for tools with no side effects (read-only operations).
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime
import hashlib
import json

logger = logging.getLogger(__name__)


class ShadowTester:
    """
    Execute shadow tests by running old and new tool versions in parallel.
    
    Shadow testing is ideal for:
    - Read-only tools (no side effects)
    - Tools marked as safe_for_shadow_testing
    - Tools with deterministic outputs
    
    NOT suitable for:
    - Tools with side effects (writes, API calls, mutations)
    - Non-idempotent operations
    - Tools that modify state
    """
    
    def __init__(self, execution_store=None, agreement_threshold: float = 0.95):
        """
        Initialize shadow tester.
        
        Args:
            execution_store: ExecutionStore for logging results
            agreement_threshold: Minimum agreement rate to pass (default: 95%)
        """
        self.execution_store = execution_store
        self.agreement_threshold = agreement_threshold
    
    async def shadow_test(self,
                         old_tool,
                         new_tool,
                         test_inputs: List[Dict[str, Any]],
                         tool_name: str) -> Dict[str, Any]:
        """
        Run shadow test comparing old and new tool versions.
        
        Args:
            old_tool: Original tool instance
            new_tool: Improved tool instance
            test_inputs: List of input parameter dictionaries
            tool_name: Name of the tool being tested
        
        Returns:
            Test results with agreement rate, differences, and recommendation
        """
        logger.info(f"🌓 Starting shadow test for {tool_name}")
        logger.info(f"   Test cases: {len(test_inputs)}")
        
        results = {
            'tool_name': tool_name,
            'test_count': len(test_inputs),
            'agreements': 0,
            'disagreements': 0,
            'errors': [],
            'differences': [],
            'agreement_rate': 0.0,
            'passed': False,
            'started_at': datetime.now().isoformat()
        }
        
        # Run tests in parallel
        for idx, test_input in enumerate(test_inputs, 1):
            logger.info(f"   Test {idx}/{len(test_inputs)}: {test_input}")
            
            comparison = await self._run_parallel_comparison(
                old_tool, new_tool, test_input, idx
            )
            
            if comparison['agreed']:
                results['agreements'] += 1
                logger.info(f"      ✓ Agreement")
            else:
                results['disagreements'] += 1
                results['differences'].append(comparison)
                logger.info(f"      ✗ Disagreement")
            
            if comparison.get('error'):
                results['errors'].append(comparison['error'])
        
        # Calculate agreement rate
        total_valid = results['agreements'] + results['disagreements']
        if total_valid > 0:
            results['agreement_rate'] = results['agreements'] / total_valid
        
        # Determine if test passed
        results['passed'] = results['agreement_rate'] >= self.agreement_threshold
        
        results['completed_at'] = datetime.now().isoformat()
        
        # Log to database
        if self.execution_store:
            self._log_shadow_test(results)
        
        # Print summary
        logger.info(f"\n   Shadow Test Summary:")
        logger.info(f"      Agreement rate: {results['agreement_rate']:.1%}")
        logger.info(f"      Agreements: {results['agreements']}")
        logger.info(f"      Disagreements: {results['disagreements']}")
        logger.info(f"      Errors: {len(results['errors'])}")
        logger.info(f"      Result: {'✅ PASSED' if results['passed'] else '❌ FAILED'}")
        
        return results
    
    async def _run_parallel_comparison(self,
                                      old_tool,
                                      new_tool,
                                      test_input: Dict,
                                      test_number: int) -> Dict[str, Any]:
        """
        Run old and new tools in parallel and compare results.
        """
        comparison = {
            'test_number': test_number,
            'input': test_input,
            'agreed': False,
            'old_output': None,
            'new_output': None,
            'difference': None,
            'error': None
        }
        
        try:
            # Run both versions in parallel
            old_task = asyncio.create_task(
                self._run_tool_async(old_tool, test_input, 'old')
            )
            new_task = asyncio.create_task(
                self._run_tool_async(new_tool, test_input, 'new')
            )
            
            old_result, new_result = await asyncio.gather(
                old_task, new_task, return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(old_result, Exception):
                comparison['error'] = f"Old version error: {str(old_result)}"
                comparison['old_output'] = {'error': str(old_result)}
            else:
                comparison['old_output'] = old_result
            
            if isinstance(new_result, Exception):
                comparison['error'] = f"New version error: {str(new_result)}"
                comparison['new_output'] = {'error': str(new_result)}
            else:
                comparison['new_output'] = new_result
            
            # Compare outputs
            if not comparison['error']:
                comparison['agreed'] = self._compare_outputs(
                    comparison['old_output'],
                    comparison['new_output']
                )
                
                if not comparison['agreed']:
                    comparison['difference'] = self._describe_difference(
                        comparison['old_output'],
                        comparison['new_output']
                    )
        
        except Exception as e:
            comparison['error'] = f"Shadow test execution error: {str(e)}"
            logger.error(f"Shadow test error: {e}", exc_info=True)
        
        return comparison
    
    async def _run_tool_async(self, tool, params: Dict, version: str) -> Any:
        """Run tool asynchronously."""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, tool.execute, params)
            return result
        except Exception as e:
            logger.error(f"Error running {version} version: {e}")
            raise
    
    def _compare_outputs(self, old_output: Any, new_output: Any) -> bool:
        """
        Compare two outputs for equivalence.
        
        Uses multiple comparison strategies:
        1. Exact equality
        2. JSON serialization equality
        3. Semantic equality (for dicts)
        """
        # Strategy 1: Direct equality
        if old_output == new_output:
            return True
        
        # Strategy 2: JSON serialization (handles dict ordering)
        try:
            old_json = self._normalize_for_comparison(old_output)
            new_json = self._normalize_for_comparison(new_output)
            if old_json == new_json:
                return True
        except (TypeError, ValueError):
            pass
        
        # Strategy 3: Semantic dict comparison
        if isinstance(old_output, dict) and isinstance(new_output, dict):
            return self._compare_dicts_semantically(old_output, new_output)
        
        # Strategy 4: List comparison (order-independent for sets)
        if isinstance(old_output, list) and isinstance(new_output, list):
            return self._compare_lists_semantically(old_output, new_output)
        
        return False
    
    def _normalize_for_comparison(self, obj: Any) -> str:
        """Normalize object for comparison via JSON."""
        return json.dumps(obj, sort_keys=True, default=str)
    
    def _compare_dicts_semantically(self, old: Dict, new: Dict) -> bool:
        """Compare dicts semantically (ignoring minor differences)."""
        # Same keys?
        if set(old.keys()) != set(new.keys()):
            return False
        
        # Compare each value
        for key in old.keys():
            if not self._compare_outputs(old[key], new[key]):
                return False
        
        return True
    
    def _compare_lists_semantically(self, old: List, new: List) -> bool:
        """Compare lists semantically."""
        if len(old) != len(new):
            return False
        
        # Try direct comparison first
        if old == new:
            return True
        
        # Try set comparison (for unordered lists)
        try:
            return set(old) == set(new)
        except TypeError:
            # Unhashable elements, compare element by element
            return all(self._compare_outputs(o, n) for o, n in zip(old, new))
    
    def _describe_difference(self, old_output: Any, new_output: Any) -> str:
        """Generate human-readable description of difference."""
        if type(old_output) != type(new_output):
            return f"Type mismatch: {type(old_output).__name__} vs {type(new_output).__name__}"
        
        if isinstance(old_output, dict):
            old_keys = set(old_output.keys())
            new_keys = set(new_output.keys())
            
            if old_keys != new_keys:
                missing = old_keys - new_keys
                extra = new_keys - old_keys
                parts = []
                if missing:
                    parts.append(f"Missing keys: {missing}")
                if extra:
                    parts.append(f"Extra keys: {extra}")
                return "; ".join(parts)
            
            # Find differing values
            diffs = []
            for key in old_keys:
                if old_output[key] != new_output[key]:
                    diffs.append(f"{key}: {old_output[key]} → {new_output[key]}")
            
            return "Value differences: " + "; ".join(diffs[:3])  # Show first 3
        
        if isinstance(old_output, list):
            return f"List length: {len(old_output)} vs {len(new_output)}"
        
        # Truncate long strings
        old_str = str(old_output)[:100]
        new_str = str(new_output)[:100]
        return f"'{old_str}' vs '{new_str}'"
    
    def _log_shadow_test(self, results: Dict[str, Any]):
        """Log shadow test results to database."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO shadow_test_results (
                            tool_name, test_count, agreements, disagreements,
                            agreement_rate, passed, differences, errors,
                            started_at, completed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        results['tool_name'],
                        results['test_count'],
                        results['agreements'],
                        results['disagreements'],
                        results['agreement_rate'],
                        results['passed'],
                        json.dumps(results['differences']),
                        json.dumps(results['errors']),
                        results['started_at'],
                        results['completed_at']
                    ))
                    conn.commit()
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error logging shadow test: {e}")


class ShadowTestRecommender:
    """
    Recommend whether shadow testing is appropriate for a tool.
    """
    
    @staticmethod
    def can_shadow_test(tool) -> Dict[str, Any]:
        """
        Determine if tool is suitable for shadow testing.
        
        Returns:
            {
                'suitable': bool,
                'reason': str,
                'confidence': float
            }
        """
        # Get tool characteristics
        if hasattr(tool, 'get_tool_characteristics'):
            chars = tool.get_tool_characteristics()
        else:
            # Conservative default: not safe
            return {
                'suitable': False,
                'reason': 'Tool does not declare characteristics',
                'confidence': 1.0
            }
        
        # Check if explicitly marked safe
        if chars.get('safe_for_shadow_testing'):
            return {
                'suitable': True,
                'reason': 'Tool marked as safe for shadow testing',
                'confidence': 1.0
            }
        
        # Check if read-only (no side effects)
        side_effects = chars.get('side_effects', ['unknown'])
        if 'none' in side_effects or 'read_only' in side_effects:
            return {
                'suitable': True,
                'reason': 'Tool is read-only with no side effects',
                'confidence': 0.9
            }
        
        # Check if idempotent
        if chars.get('idempotent'):
            return {
                'suitable': True,
                'reason': 'Tool is idempotent (can run multiple times safely)',
                'confidence': 0.7
            }
        
        # Has side effects - not safe
        return {
            'suitable': False,
            'reason': f'Tool has side effects: {side_effects}',
            'confidence': 0.9
        }
