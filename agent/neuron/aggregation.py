"""
Neuron Result Aggregation

Handles combining neuron results into final answers with intelligent
formatting detection and quantity constraint matching.

See docs/AGGREGATION.md for detailed explanation.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def aggregate_results(
    goal: str,
    neurons: List[Any],  # List[Neuron]
    results: List[Any],
    ollama_client: Any
) -> Any:
    """
    Aggregate neuron results into final answer.
    
    Key features:
    - Detects formatting results by checking result TYPE (not just description keywords)
    - Extracts quantity constraints from goal ("first 3" -> target_count=3)
    - Prefers results with line counts matching the target
    - Falls back to most recent successful result
    
    Args:
        goal: Original user goal
        neurons: List of executed neurons
        results: List of results from neurons
        ollama_client: Ollama client for generating summaries
        
    Returns:
        Aggregated result (dict with 'summary' and 'detailed_results')
    """
    # If only one neuron, return its result directly
    if len(neurons) == 1:
        return results[0]
    
    # Scan backwards to find ANY successful formatting result (not just the last)
    # This handles cases where a formatting neuron succeeded but later neurons failed
    formatting_keywords = ['format', 'report', 'present', 'show', 'display', 'human-readable']
    
    # Extract quantity constraints from goal (e.g., "first 3", "top 5")
    quantity_match = re.search(r'\b(first|top|last)\s+(\d+)\b', goal.lower())
    target_count = int(quantity_match.group(2)) if quantity_match else None
    
    if target_count:
        logger.info(f"🎯 Target count from goal: {target_count}")
    
    # Collect all successful formatting results
    formatting_results = []
    dendrite_result_neuron = None  # Track neuron with dendrite results
    
    for neuron, result in zip(reversed(neurons), reversed(results)):
        logger.info(f"   Checking neuron {neuron.index}: {neuron.description[:50]}...")
        
        # Check result type first - if it's a string result from executeDataAnalysis, it's likely formatting
        found_result = False
        
        # PRIORITY 1: Check for dendrite results (most important - has actual collected data)
        if isinstance(result, dict) and 'dendrite_results' in result and result.get('items_processed', 0) > 0:
            logger.info(f"   🌳 Found dendrite results: {result['items_processed']} items processed")
            dendrite_result_neuron = (neuron.index, result, neuron)
            # Don't add to formatting_results yet - we'll format it if needed
            found_result = True
        # PRIORITY 2: Check for executeDataAnalysis result with string output (explicit formatting)
        elif isinstance(result, dict) and result.get('success') and 'result' in result and isinstance(result['result'], str):
            formatting_results.append((neuron.index, result['result'], 'python'))
            logger.info(f"   ✅ Found Python result with {len(result['result'].split(chr(10)))} lines")
            found_result = True
        # PRIORITY 3: Check for AI response type (fallback - often just explanations)
        elif isinstance(result, dict) and result.get('type') == 'ai_response':
            # Only use AI response if it's NOT just explaining steps
            answer = result.get('answer', '')
            is_explanation = any(phrase in answer.lower() for phrase in ['step 1:', 'first,', 'to filter', 'we need to'])
            if not is_explanation:
                formatting_results.append((neuron.index, answer, 'ai'))
                logger.info(f"   ✅ Found AI response")
                found_result = True
            else:
                logger.info(f"   ⚠️ AI response looks like explanation, skipping")
        
        # If no result found, check if description suggests formatting
        if not found_result and neuron.index != (dendrite_result_neuron[0] if dendrite_result_neuron else None):
            is_formatting = any(kw in neuron.description.lower() for kw in formatting_keywords)
            if is_formatting:
                logger.info(f"   ⚠️ Formatting keywords found but no string result")
    
    logger.info(f"📋 Found {len(formatting_results)} formatting results total")
    
    # PRIORITY 1: If we have dendrite results, ALWAYS prefer them (actual collected data)
    if dendrite_result_neuron:
        logger.info(f"🌳 Auto-formatting dendrite results from neuron {dendrite_result_neuron[0]}")
        formatted_text = format_dendrite_results(dendrite_result_neuron[1], goal)
        if formatted_text:
            logger.info(f"✅ Generated formatted output from dendrite results")
            return {
                'summary': formatted_text,
                'detailed_results': results
            }
        else:
            logger.warning(f"⚠️ Failed to format dendrite results")
            # Try Python-based formatting as backup
            python_formatted = try_python_formatting(dendrite_result_neuron[1], goal, neurons, results)
            if python_formatted:
                logger.info(f"✅ Python formatting succeeded as fallback")
                return {
                    'summary': python_formatted,
                    'detailed_results': results
                }
            logger.warning(f"⚠️ All dendrite formatting attempts failed, falling back to other results")
    
    # PRIORITY 2: If no dendrite results (or formatting failed), use other formatting results
    if formatting_results:
        best_result = None
        
        # If goal specifies a quantity, prefer results with that many lines
        if target_count:
            for idx, text, rtype in formatting_results:
                line_count = len([l for l in text.strip().split('\n') if l.strip()])
                if line_count == target_count:
                    logger.info(f"📝 Using formatted answer from neuron {idx} ({rtype}, matches target count {target_count})")
                    best_result = text
                    break
        
        # Otherwise, use the most recent successful one
        if not best_result and formatting_results:
            idx, text, rtype = formatting_results[0]  # Most recent
            logger.info(f"📝 Using formatted answer from neuron {idx} ({rtype})")
            best_result = text
        
        if best_result:
            return {
                'summary': best_result,
                'detailed_results': results
            }
    
    # For counting questions, find the final count result
    is_counting = any(word in goal.lower() for word in ['how many', 'count'])
    if is_counting:
        # Look for the last result that has a 'result' key with a number
        for r in reversed(results):
            if isinstance(r, dict) and 'result' in r and isinstance(r['result'], (int, float)):
                count = r['result']
                logger.info(f"📊 Found count result: {count}")
                return {
                    'success': True,
                    'count': int(count),
                    'answer': f"{int(count)} items"
                }
    
    # Build summary of what each neuron did
    summary = "\n".join([
        f"Step {n.index + 1}: {n.description}\n  Result: {summarize_result(r)}"
        for n, r in zip(neurons, results)
    ])
    
    # Detect if this is a question that needs a simple answer
    is_question = any(word in goal.lower() for word in ['how many', 'what', 'which', 'when', 'where', 'who', 'count'])
    
    if is_question:
        prompt = f"""Answer this question using the results:

Question: {goal}

Steps taken:
{summary}

Provide a direct, concise answer (1-2 sentences):"""
        
        response = ollama_client.generate(
            prompt,
            system="Answer questions directly and concisely. For 'how many' questions, start with the number.",
            temperature=0.2
        )
    else:
        prompt = f"""Summarize what was accomplished:

Goal: {goal}

Steps:
{summary}

Provide a brief summary (2-3 sentences):"""
        
        response = ollama_client.generate(
            prompt,
            system="Summarize accomplishments concisely.",
            temperature=0.3
        )
    
    response_str = str(response) if not isinstance(response, str) else response
    
    # Truncate large detailed_results to keep logs readable
    truncated_results = truncate_large_results(results, max_size_kb=10)
    
    # Check for failed neurons and add warning
    failed_neurons = []
    for i, (neuron, result) in enumerate(zip(neurons, results), 1):
        if isinstance(result, dict):
            if not result.get('success', True):  # Explicit failure
                failed_neurons.append(i)
            elif result.get('error'):  # Has error field
                failed_neurons.append(i)
    
    summary_text = response_str.strip()
    if failed_neurons:
        warning = f"\n\n⚠️  Warning: Some processing steps failed (steps {', '.join(map(str, failed_neurons))}). Results may be incomplete or inaccurate."
        summary_text += warning
        logger.warning(f"Adding failure warning to response: {len(failed_neurons)} neurons failed")
    
    return {
        'summary': summary_text,
        'detailed_results': truncated_results
    }


def try_python_formatting(dendrite_data: Dict, goal: str, neurons: List, results: List) -> Optional[str]:
    """
    Try to format dendrite results using safe, pre-validated Python code.
    
    This is a fallback when format_dendrite_results() fails.
    Generates simple, safe Python to extract and format the data.
    
    Args:
        dendrite_data: Dict with 'dendrite_results' and 'items_processed'
        goal: Original goal
        neurons: List of neurons
        results: List of results
        
    Returns:
        Formatted string or None if failed
    """
    dendrite_results = dendrite_data.get('dendrite_results', [])
    if not dendrite_results:
        return None
    
    logger.info(f"🐍 Attempting Python-based formatting for {len(dendrite_results)} dendrite results")
    
    # Check if goal asks for names
    wants_names = any(word in goal.lower() for word in ['names', 'who', 'people', 'users', 'givers'])
    
    # Generate safe Python code
    if wants_names:
        # Format: "Activity X: name1, name2, name3"
        python_code = """
formatted_lines = []
dendrite_results = data.get('dendrite_results', [])
for dr in dendrite_results:
    final_result = dr.get('final', {})
    if not isinstance(final_result, dict):
        continue
    
    # Look for athletes/users/people lists
    for key in ['athletes', 'users', 'people', 'members']:
        if key in final_result and isinstance(final_result[key], list):
            names = []
            for entity in final_result[key]:
                if isinstance(entity, dict):
                    name = entity.get('name') or entity.get('username') or entity.get('display_name')
                    if name:
                        names.append(name)
                elif isinstance(entity, str):
                    names.append(entity)
            
            if names:
                activity_id = final_result.get('activity_id') or final_result.get('id') or final_result.get('item_id')
                if activity_id:
                    formatted_lines.append(f"Activity {activity_id}: {', '.join(names)}")
                break

result = '\\n'.join(formatted_lines) if formatted_lines else None
"""
    else:
        # Generic formatting
        python_code = """
formatted_lines = []
dendrite_results = data.get('dendrite_results', [])
for i, dr in enumerate(dendrite_results, 1):
    final_result = dr.get('final', {})
    if isinstance(final_result, dict) and final_result.get('success'):
        formatted_lines.append(f"Item {i}: Success")
    elif isinstance(final_result, dict) and 'error' in final_result:
        continue  # Skip errors
        
result = '\\n'.join(formatted_lines) if formatted_lines else None
"""
    
    # Execute safely
    try:
        from tools.analysis_tools import execute_data_analysis
        # Build data context with all neurons + dendrite results
        data_context = {
            **{f'neuron_{n.index}': n.result for n in neurons if n.result},
            **results,  # Include other context data
            'dendrite_results': dendrite_results
        }
        exec_result = execute_data_analysis(
            python_code=python_code.strip(),
            **data_context
        )
        
        if exec_result.get('success') and exec_result.get('result'):
            logger.info(f"✅ Python formatting succeeded as fallback")
            return exec_result['result']
        else:
            logger.warning(f"⚠️ Python formatting failed: {exec_result.get('error')}")
            return None
    except Exception as e:
        logger.error(f"❌ Python formatting exception: {e}")
        return None


def format_dendrite_results(dendrite_data: Dict, goal: str) -> Optional[str]:
    """
    Format dendrite results into human-readable output.
    
    Extracts data from dendrite results and formats it based on the goal.
    Completely domain-agnostic - works with any field names.
    
    Args:
        dendrite_data: Dict with 'dendrite_results' and 'items_processed'
        goal: Original goal to understand what format is needed
        
    Returns:
        Formatted string or None if can't format
    """
    dendrite_results = dendrite_data.get('dendrite_results', [])
    if not dendrite_results:
        logger.warning("⚠️ No dendrite_results found in dendrite_data")
        return None
    
    logger.info(f"🔍 Formatting {len(dendrite_results)} dendrite results")
    
    # Determine what type of data we're looking at
    # Look at first dendrite's final result to understand structure
    sample_result = None
    for dr in dendrite_results:
        if isinstance(dr, dict) and 'final' in dr and dr['final']:
            sample_result = dr['final']
            logger.info(f"📦 Found sample result in 'final': {list(sample_result.keys()) if isinstance(sample_result, dict) else type(sample_result)}")
            break
        elif isinstance(dr, dict) and 'results' in dr and dr['results']:
            sample_result = dr['results'][0] if dr['results'] else None
            logger.info(f"📦 Found sample result in 'results[0]': {list(sample_result.keys()) if isinstance(sample_result, dict) else type(sample_result)}")
            break
    
    if not sample_result:
        logger.warning("⚠️ Could not find sample_result in dendrite_results")
        return None
    
    # Generic approach: Look for common patterns in the data
    formatted_lines = []
    
    # Check if goal asks for names/people (look for list fields with name-like data)
    wants_names = any(word in goal.lower() for word in ['names', 'who', 'people', 'users', 'givers'])
    logger.info(f"🎯 wants_names={wants_names} based on goal: {goal[:50]}...")
    
    for i, dr in enumerate(dendrite_results, 1):
        result = dr.get('final') or (dr.get('results', [{}])[0] if dr.get('results') else {})
        
        if not isinstance(result, dict):
            logger.info(f"   Item {i}: result is not a dict, skipping")
            continue
        
        logger.info(f"   Item {i}: checking fields {list(result.keys())}")
        
        # Look for list fields that might contain the answer
        for key in ['athletes', 'users', 'people', 'members', 'participants', 'contributors', 'items', 'entries']:
            if key in result and isinstance(result[key], list) and result[key]:
                logger.info(f"   ✓ Found list field '{key}' with {len(result[key])} items")
                # Found a list of entities
                entity_list = result[key]
                
                if wants_names:
                    # Extract names from entities
                    names = []
                    for entity in entity_list:
                        if isinstance(entity, dict):
                            # Try common name fields
                            name = entity.get('name') or entity.get('username') or entity.get('display_name') or entity.get('full_name')
                            if name:
                                names.append(name)
                        elif isinstance(entity, str):
                            names.append(entity)
                    
                    if names:
                        # Get context about what these names are for
                        context_id = result.get('activity_id') or result.get('id') or result.get('item_id') or result.get('record_id')
                        count = result.get(f'{key}_count') or result.get('count') or len(names)
                        
                        # Format: "Item X: name1, name2, name3 (count)"
                        if context_id:
                            formatted_lines.append(f"Activity {context_id}: {', '.join(names)} ({count} total)")
                            logger.info(f"   ✓ Formatted as: Activity {context_id}: {len(names)} names")
                        else:
                            formatted_lines.append(f"Item {i}: {', '.join(names)} ({count} total)")
                            logger.info(f"   ✓ Formatted as: Item {i}: {len(names)} names")
                        break
                    else:
                        logger.info(f"   ✗ No names extracted from {len(entity_list)} entities")
                else:
                    # Just show count of items
                    count = len(entity_list)
                    formatted_lines.append(f"Item {i}: {count} {key}")
                    break
        
        # If no list found, check for simple count/status
        if i > len(formatted_lines):  # Didn't add anything yet
            if 'count' in result:
                formatted_lines.append(f"Item {i}: {result['count']} items")
            elif 'success' in result and result['success']:
                formatted_lines.append(f"Item {i}: Completed successfully")
    
    if formatted_lines:
        logger.info(f"✅ Successfully formatted {len(formatted_lines)} dendrite results")
        return '\n'.join(formatted_lines)
    
    logger.warning(f"⚠️ Could not format any of {len(dendrite_results)} dendrite results")
    return None


def aggregate_dendrite_results(parent_result: Any, items: List[Dict], dendrite_results: List[Any]) -> Any:
    """
    Aggregate dendrite results back to parent neuron.
    
    Args:
        parent_result: Original parent result (before dendrite spawning)
        items: List of items that were iterated
        dendrite_results: Results from dendrite executions
        
    Returns:
        Aggregated result combining all dendrite outputs
    """
    # Simple merge: add dendrite data to each item
    if isinstance(parent_result, dict) and 'entries' in parent_result:
        enhanced_entries = []
        for item, dendrite in zip(items, dendrite_results):
            enhanced_item = item.copy()
            enhanced_item['_dendrite_result'] = dendrite.get('final', dendrite)
            enhanced_entries.append(enhanced_item)
        
        parent_result['entries'] = enhanced_entries
    
    return parent_result


def summarize_result(result: Any) -> str:
    """
    Summarize a result for logging.
    
    Args:
        result: Result to summarize
        
    Returns:
        Human-readable summary string
    """
    if isinstance(result, dict):
        # Handle AI responses first (most important for formatting tasks)
        if result.get('type') == 'ai_response' and 'answer' in result:
            return result['answer']
        if 'error' in result:
            return f"Error: {result['error']}"
        if 'entries' in result:
            return f"{len(result['entries'])} entries"
        if 'success' in result:
            # Handle write operations better
            success_val = result['success']
            if success_val is True or success_val == 'true':
                # Check for result key first (most specific)
                if 'result' in result:
                    return f"Result: {result['result']}"
                # Check for count or other indicators
                elif 'count' in result:
                    return f"Success: {result['count']} items"
                # Check for any ID field indicating operation completion
                elif any(key.endswith('_id') for key in result.keys()):
                    id_key = next(key for key in result.keys() if key.endswith('_id'))
                    return f"Success: operation completed for {id_key}={result[id_key]}"
                # For timestamp/date conversions, show the actual values
                elif 'unix_timestamp' in result or 'human_readable' in result:
                    parts = []
                    if 'unix_timestamp' in result:
                        parts.append(f"timestamp={result['unix_timestamp']}")
                    if 'human_readable' in result:
                        parts.append(f"date={result['human_readable']}")
                    if 'is_valid' in result:
                        parts.append(f"valid={result['is_valid']}")
                    return f"Success: {', '.join(parts)}"
                else:
                    return "Success: operation completed"
            else:
                return f"Failed: {result.get('error', 'Unknown error')}"
        return f"{len(result)} fields"
    elif isinstance(result, list):
        return f"{len(result)} items"
    else:
        return str(result)[:100]


def summarize_result_for_validation(result: Any, max_length: int = 500) -> str:
    """
    Summarize result specifically for validation checks.
    
    This checks for the 'summary' field first (from aggregation)
    to ensure validation sees the formatted result, not raw data.
    
    Args:
        result: Result to summarize
        max_length: Maximum length of summary
        
    Returns:
        Summary string for validation
    """
    if isinstance(result, dict):
        # Show structure and sample data
        
        if 'final' in result:
            # This is a nested result from execute_goal
            return summarize_result_for_validation(result['final'], max_length)
        
        # Check for formatted summary first (from aggregation)
        if 'summary' in result and isinstance(result['summary'], str) and len(result['summary']) > 0:
            return result['summary'][:max_length]
        
        # Check for AI response
        if result.get('type') == 'ai_response' and 'answer' in result:
            return result['answer'][:max_length]
        
        # For other dicts, show structure
        if 'error' in result:
            return f"Error: {result['error']}"
        
        if 'result' in result:
            return summarize_result_for_validation(result['result'], max_length)
        
        # Show dict structure
        return str(result)[:max_length]
    
    elif isinstance(result, list):
        if len(result) == 0:
            return "Empty list"
        # Show sample items
        return f"List of {len(result)} items: {result[:2]}"[:max_length]
    
    else:
        return str(result)[:max_length]


def truncate_large_results(results: List[Any], max_size_kb: int = 10) -> List[Any]:
    """
    Truncate large results to avoid overwhelming LLM context.
    
    Args:
        results: List of results
        max_size_kb: Maximum size in KB for each result
        
    Returns:
        List of truncated results
    """
    # Convert any Neuron objects to dicts first
    serializable_results = []
    for result in results:
        if hasattr(result, '__dict__'):  # Neuron or other objects
            # Convert to basic dict, excluding complex nested objects
            result_dict = {}
            for key, value in result.__dict__.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    result_dict[key] = value
                elif isinstance(value, dict):
                    result_dict[key] = "[dict]"
                elif isinstance(value, list):
                    result_dict[key] = f"[list with {len(value)} items]"
                else:
                    result_dict[key] = str(type(value).__name__)
            serializable_results.append(result_dict)
        else:
            serializable_results.append(result)
    
    # Check total size
    try:
        results_json = json.dumps(serializable_results)
        size_kb = len(results_json) / 1024
    except (TypeError, ValueError):
        # If still not serializable, just return simplified version
        return [{"info": "Result truncated - could not serialize"}]
    
    if size_kb <= max_size_kb:
        return serializable_results  # Small enough, keep as-is
    
    # Truncate each result
    truncated = []
    for result in serializable_results:
        if isinstance(result, dict):
            # Keep metadata but truncate large data fields
            truncated_result = {}
            for key, value in result.items():
                if key in ['success', 'count', 'error', 'message', 'added', 'duplicates', 'total_count']:
                    # Keep small metadata fields
                    truncated_result[key] = value
                elif isinstance(value, (list, dict)):
                    # Truncate large structures
                    value_json = json.dumps(value)
                    if len(value_json) > 500:
                        if isinstance(value, list):
                            truncated_result[key] = f"[{len(value)} items, truncated for brevity]"
                        else:
                            truncated_result[key] = "[large object, truncated for brevity]"
                    else:
                        truncated_result[key] = value
                else:
                    truncated_result[key] = value
            truncated.append(truncated_result)
        else:
            truncated.append(result)
    
    return truncated
