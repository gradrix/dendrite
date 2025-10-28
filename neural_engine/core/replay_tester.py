"""
Replay Testing - Test with Historical Data

Replay historical successful executions with improved tool version.
Validates that improvements don't break existing functionality.
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class ReplayTester:
    """
    Test improved tools by replaying historical successful executions.
    
    Replay testing is ideal for:
    - Tools with execution history in database
    - Idempotent tools (can run multiple times)
    - Tools where we want to validate against known-good results
    
    Benefits:
    - Uses real production data
    - Tests actual user scenarios
    - Validates backwards compatibility
    """
    
    def __init__(self, execution_store, min_replays: int = 10, success_threshold: float = 0.9):
        """
        Initialize replay tester.
        
        Args:
            execution_store: ExecutionStore with historical data
            min_replays: Minimum number of replays to consider valid test
            success_threshold: Minimum success rate to pass (default: 90%)
        """
        self.execution_store = execution_store
        self.min_replays = min_replays
        self.success_threshold = success_threshold
    
    async def replay_test(self,
                         new_tool,
                         tool_name: str,
                         lookback_days: int = 30,
                         max_replays: int = 50) -> Dict[str, Any]:
        """
        Test new tool version by replaying historical executions.
        
        Args:
            new_tool: Improved tool instance to test
            tool_name: Name of the tool
            lookback_days: How many days back to look for historical executions
            max_replays: Maximum number of executions to replay
        
        Returns:
            Test results with success rate, failures, and recommendation
        """
        logger.info(f"🔄 Starting replay test for {tool_name}")
        
        # Get historical successful executions
        historical = self._get_historical_executions(
            tool_name, lookback_days, max_replays
        )
        
        if not historical:
            logger.warning(f"   No historical data found for {tool_name}")
            return {
                'tool_name': tool_name,
                'error': 'No historical executions found',
                'passed': False,
                'reason': 'insufficient_data'
            }
        
        logger.info(f"   Found {len(historical)} historical executions")
        
        if len(historical) < self.min_replays:
            logger.warning(f"   Insufficient data ({len(historical)} < {self.min_replays})")
            return {
                'tool_name': tool_name,
                'error': f'Insufficient historical data ({len(historical)} executions)',
                'passed': False,
                'reason': 'insufficient_data',
                'found_executions': len(historical),
                'required_minimum': self.min_replays
            }
        
        # Run replays
        results = {
            'tool_name': tool_name,
            'replay_count': len(historical),
            'successes': 0,
            'failures': 0,
            'errors': [],
            'improvements': [],
            'regressions': [],
            'success_rate': 0.0,
            'passed': False,
            'started_at': datetime.now().isoformat()
        }
        
        for idx, hist in enumerate(historical, 1):
            logger.info(f"   Replay {idx}/{len(historical)}")
            
            replay_result = await self._replay_execution(
                new_tool, hist, idx
            )
            
            if replay_result['success']:
                results['successes'] += 1
                logger.info(f"      ✓ Success")
                
                # Check if output improved
                if replay_result.get('improved'):
                    results['improvements'].append(replay_result)
                    logger.info(f"      ⬆️  Output improved!")
            else:
                results['failures'] += 1
                results['errors'].append(replay_result['error'])
                logger.info(f"      ✗ Failed: {replay_result['error']}")
                
                # Check if this is a regression (worked before, fails now)
                if hist.get('original_success'):
                    results['regressions'].append(replay_result)
                    logger.warning(f"      ⬇️  REGRESSION detected!")
        
        # Calculate success rate
        total = results['successes'] + results['failures']
        if total > 0:
            results['success_rate'] = results['successes'] / total
        
        # Determine if test passed
        results['passed'] = (
            results['success_rate'] >= self.success_threshold and
            len(results['regressions']) == 0  # No regressions allowed
        )
        
        results['completed_at'] = datetime.now().isoformat()
        
        # Log to database
        self._log_replay_test(results)
        
        # Print summary
        logger.info(f"\n   Replay Test Summary:")
        logger.info(f"      Success rate: {results['success_rate']:.1%}")
        logger.info(f"      Successes: {results['successes']}")
        logger.info(f"      Failures: {results['failures']}")
        logger.info(f"      Improvements: {len(results['improvements'])}")
        logger.info(f"      Regressions: {len(results['regressions'])}")
        logger.info(f"      Result: {'✅ PASSED' if results['passed'] else '❌ FAILED'}")
        
        return results
    
    def _get_historical_executions(self,
                                  tool_name: str,
                                  lookback_days: int,
                                  max_replays: int) -> List[Dict]:
        """
        Get historical successful executions from database.
        """
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    # Query recent successful executions
                    cursor.execute("""
                        SELECT 
                            te.execution_id,
                            te.tool_name,
                            te.parameters,
                            te.result,
                            te.success AS original_success,
                            te.executed_at,
                            te.duration_ms
                        FROM tool_executions te
                        WHERE te.tool_name = %s
                          AND te.success = TRUE
                          AND te.executed_at > NOW() - INTERVAL '%s days'
                        ORDER BY te.executed_at DESC
                        LIMIT %s
                    """, (tool_name, lookback_days, max_replays))
                    
                    rows = cursor.fetchall()
                    
                    historical = []
                    for row in rows:
                        historical.append({
                            'execution_id': row[0],
                            'tool_name': row[1],
                            'parameters': row[2],
                            'original_result': row[3],
                            'original_success': row[4],
                            'executed_at': row[5],
                            'original_duration_ms': row[6]
                        })
                    
                    return historical
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting historical executions: {e}")
            return []
    
    async def _replay_execution(self,
                               new_tool,
                               historical: Dict,
                               replay_number: int) -> Dict[str, Any]:
        """
        Replay a single historical execution with new tool.
        """
        replay_result = {
            'replay_number': replay_number,
            'execution_id': historical['execution_id'],
            'parameters': historical['parameters'],
            'success': False,
            'new_result': None,
            'error': None,
            'improved': False,
            'duration_ms': None
        }
        
        try:
            start_time = datetime.now()
            
            # Run new tool with historical parameters
            loop = asyncio.get_event_loop()
            new_result = await loop.run_in_executor(
                None, new_tool.execute, historical['parameters']
            )
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            replay_result['duration_ms'] = int(duration)
            
            replay_result['new_result'] = new_result
            replay_result['success'] = True
            
            # Compare with original result
            if self._is_improved(historical['original_result'], new_result):
                replay_result['improved'] = True
        
        except Exception as e:
            replay_result['error'] = {
                'type': type(e).__name__,
                'message': str(e)
            }
            logger.error(f"Replay error: {e}")
        
        return replay_result
    
    def _is_improved(self, old_result: Any, new_result: Any) -> bool:
        """
        Determine if new result is an improvement over old result.
        
        Checks:
        - More data returned
        - Better formatted
        - More complete information
        """
        # If old failed but new succeeded, that's an improvement
        if isinstance(old_result, dict) and 'error' in old_result:
            if not (isinstance(new_result, dict) and 'error' in new_result):
                return True
        
        # If both are dicts, check if new has more keys
        if isinstance(old_result, dict) and isinstance(new_result, dict):
            old_keys = set(old_result.keys())
            new_keys = set(new_result.keys())
            if new_keys > old_keys:  # new is superset
                return True
        
        # If both are lists, check if new has more items
        if isinstance(old_result, list) and isinstance(new_result, list):
            if len(new_result) > len(old_result):
                return True
        
        return False
    
    def _log_replay_test(self, results: Dict[str, Any]):
        """Log replay test results to database."""
        try:
            conn = self.execution_store._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO replay_test_results (
                            tool_name, replay_count, successes, failures,
                            success_rate, passed, improvements_count,
                            regressions_count, errors, started_at, completed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        results['tool_name'],
                        results['replay_count'],
                        results['successes'],
                        results['failures'],
                        results['success_rate'],
                        results['passed'],
                        len(results['improvements']),
                        len(results['regressions']),
                        json.dumps(results['errors']),
                        results['started_at'],
                        results['completed_at']
                    ))
                    conn.commit()
            finally:
                self.execution_store._release_connection(conn)
        except Exception as e:
            logger.error(f"Error logging replay test: {e}")


class ReplayTestRecommender:
    """
    Recommend whether replay testing is appropriate for a tool.
    """
    
    @staticmethod
    def can_replay_test(tool, execution_store, tool_name: str) -> Dict[str, Any]:
        """
        Determine if tool has sufficient history for replay testing.
        
        Returns:
            {
                'suitable': bool,
                'reason': str,
                'execution_count': int
            }
        """
        # Check if tool is idempotent
        if hasattr(tool, 'get_tool_characteristics'):
            chars = tool.get_tool_characteristics()
            if not chars.get('idempotent', False):
                return {
                    'suitable': False,
                    'reason': 'Tool is not idempotent (cannot run multiple times safely)',
                    'execution_count': 0
                }
        
        # Check if sufficient historical data exists
        try:
            stats = execution_store.get_tool_statistics(tool_name)
            if not stats:
                return {
                    'suitable': False,
                    'reason': 'No execution history found',
                    'execution_count': 0
                }
            
            exec_count = stats.get('total_executions', 0)
            
            if exec_count < 10:
                return {
                    'suitable': False,
                    'reason': f'Insufficient execution history ({exec_count} < 10)',
                    'execution_count': exec_count
                }
            
            return {
                'suitable': True,
                'reason': f'Sufficient execution history ({exec_count} executions)',
                'execution_count': exec_count
            }
        
        except Exception as e:
            return {
                'suitable': False,
                'reason': f'Error checking history: {str(e)}',
                'execution_count': 0
            }
