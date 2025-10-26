"""
Dendrite Spawning Module

Handles spawning sub-neurons (dendrites) for:
1. Iterating over lists (pre-execution spawning)
2. Multi-step tasks that can't be done by a single tool
3. Post-execution spawning when a result needs further processing

All functions are designed to be stateless and accept dependencies as parameters.
"""

import logging
import re
import json
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


def find_context_list_for_iteration(neuron_desc: str, context: Dict) -> Optional[List[Dict]]:
    """
    Check if this neuron needs to iterate over a list from context.
    
    Args:
        neuron_desc: Neuron description to check for iteration keywords
        context: Context dictionary to search for lists
        
    Returns:
        List of items if iteration detected, None otherwise
    """
    # Check for "for each" / "each X" / "all items" iteration patterns
    iteration_keywords = ['for each', 'each item', 'all items', 'every item', 'for all']
    if not any(kw in neuron_desc.lower() for kw in iteration_keywords):
        return None
    
    # Look for lists in context (from previous neurons)
    for key, value in context.items():
        if not isinstance(value, dict):
            continue
        
        # Check if this looks like a list result
        items = extract_list_items(value)
        if items and len(items) > 1:
            return items
    
    return None


def spawn_dendrites_from_context(
    parent_neuron: Any,
    items: List[Dict],
    parent_goal: str,
    context: Dict,
    execute_goal_fn: Callable,
    ollama=None
) -> Any:
    """
    Spawn dendrites based on context list (pre-execution spawning).
    
    This is used when a neuron like "Get details for each item" needs to iterate
    over a list from a previous neuron.
    
    Args:
        parent_neuron: The parent neuron spawning dendrites
        items: List of items to iterate over
        parent_goal: Parent goal for context
        context: Context dictionary to update with item data
        execute_goal_fn: Function to execute each dendrite goal (signature: execute_goal(goal, depth))
        ollama: OllamaClient for LLM calls (optional, falls back to pattern matching)
        
    Returns:
        Aggregated result with dendrite results
    """
    indent = '  ' * parent_neuron.depth
    logger.info(f"{indent}│  ├─ Found {len(items)} items in context")
    
    # Extract what to do with each item from neuron description
    item_goal_template = micro_extract_item_goal_from_desc(parent_neuron.description, ollama)
    logger.info(f"{indent}│  ├─ Item goal: {item_goal_template}")
    
    # Spawn dendrite for each item
    dendrite_results = []
    for i, item in enumerate(items, 1):
        logger.info(f"{indent}│  ├─ Dendrite {i}/{len(items)}")
        
        # Format goal for this specific item
        item_goal = format_item_goal(item_goal_template, item, i)
        
        # IMPORTANT: Store item data in context so it can be used for parameter extraction
        item_context_key = f'dendrite_item_{parent_neuron.depth + 1}_{i}'
        context[item_context_key] = item
        
        # Execute recursively via callback
        dendrite_result = execute_goal_fn(item_goal, depth=parent_neuron.depth + 1)
        
        # Clean up item context after execution
        context.pop(item_context_key, None)
        
        # Store result in parent's dendrites list if it has one
        if hasattr(parent_neuron, 'spawned_dendrites'):
            # Create a simple dendrite object (not importing Neuron to avoid circular deps)
            dendrite = type('Dendrite', (), {
                'description': item_goal,
                'index': i,
                'depth': parent_neuron.depth + 1,
                'result': dendrite_result
            })()
            parent_neuron.spawned_dendrites.append(dendrite)
        
        dendrite_results.append(dendrite_result)
    
    logger.info(f"{indent}│  ╰─ All dendrites complete, aggregating")
    
    # Create aggregated result
    aggregated = {
        'success': True,
        'items_processed': len(items),
        'dendrite_results': dendrite_results,
        'items': items
    }
    
    return aggregated


def spawn_dendrites(
    parent_neuron: Any,
    result: Any,
    parent_goal: str,
    context: Dict,
    execute_goal_fn: Callable,
    aggregate_dendrites_fn: Callable,
    ollama
) -> Any:
    """
    Spawn dendrites (sub-neurons) for each item in a list result.
    
    Args:
        parent_neuron: The neuron that produced the list
        result: The result containing a list
        parent_goal: Original goal for context
        context: Context dictionary to update
        execute_goal_fn: Function to execute each dendrite goal (signature: execute_goal(goal, depth))
        aggregate_dendrites_fn: Function to aggregate dendrite results (signature: aggregate(result, items, results))
        ollama: OllamaClient for LLM calls
        
    Returns:
        Enhanced result with dendrite outputs aggregated
    """
    indent = '  ' * parent_neuron.depth
    
    # Extract items from result
    items = extract_list_items(result)
    if not items:
        logger.info(f"{indent}│  │  No items to spawn for")
        return result
    
    logger.info(f"{indent}│  ├─ Found {len(items)} items")
    
    # Micro-prompt: What should we do with each item?
    item_goal_template = micro_extract_item_goal(parent_neuron.description, result, ollama)
    logger.info(f"{indent}│  ├─ Item goal: {item_goal_template}")
    
    # Spawn dendrite for each item (sequential execution)
    dendrite_results = []
    for i, item in enumerate(items, 1):
        logger.info(f"{indent}│  ├─ Dendrite {i}/{len(items)}")
        
        # Format goal for this specific item
        item_goal = format_item_goal(item_goal_template, item, i)
        
        # IMPORTANT: Store item data in context so it can be used for parameter extraction
        item_context_key = f'dendrite_item_{parent_neuron.depth + 1}_{i}'
        context[item_context_key] = item
        
        # Execute recursively via callback
        dendrite_result = execute_goal_fn(item_goal, depth=parent_neuron.depth + 1)
        
        # Clean up item context after execution
        context.pop(item_context_key, None)
        
        # Store result in parent's dendrites list if it has one
        if hasattr(parent_neuron, 'spawned_dendrites'):
            # Create a simple dendrite object
            dendrite = type('Dendrite', (), {
                'description': item_goal,
                'index': i,
                'depth': parent_neuron.depth + 1,
                'result': dendrite_result
            })()
            parent_neuron.spawned_dendrites.append(dendrite)
        
        dendrite_results.append(dendrite_result)
    
    logger.info(f"{indent}│  ╰─ All dendrites complete, aggregating")
    
    # Aggregate dendrite results back into parent result via callback
    aggregated = aggregate_dendrites_fn(result, items, dendrite_results)
    return aggregated


def detect_multi_step_task(
    neuron_desc: str,
    context: Dict,
    tools,
    ollama
) -> Optional[List[str]]:
    """
    Detect if this neuron requires multiple sub-tasks (e.g., "get start AND end timestamps").
    
    Args:
        neuron_desc: Neuron description to analyze
        context: Context dictionary to check for available data
        tools: ToolRegistry to search for capable tools
        ollama: OllamaClient for LLM decomposition
        
    Returns:
        List of sub-task descriptions if detected, None otherwise
    """
    # Keywords that suggest multiple parallel tasks
    multi_keywords = [
        'start and end',
        'both',
        'and also',
        'as well as',
        'along with'
    ]
    
    # Check if description mentions needing multiple things
    desc_lower = neuron_desc.lower()
    if not any(kw in desc_lower for kw in multi_keywords):
        return None
    
    # CRITICAL: First check if there's a tool that can do this in one call
    # Extract keywords for tool search
    keywords = re.findall(r'\b\w{4,}\b', neuron_desc.lower())
    
    # Search for tools that match
    relevant_tools = []
    for tool in tools.list_tools():
        tool_text = f"{tool.name} {tool.description}".lower()
        score = sum(1 for kw in keywords if kw in tool_text)
        if score > 2:  # Good match
            relevant_tools.append((score, tool))
    
    if relevant_tools:
        # Sort by score and check top tool
        relevant_tools.sort(reverse=True, key=lambda x: x[0])
        top_tool = relevant_tools[0][1]
        
        # If tool description mentions "start and end" or "both", it can handle this
        if any(kw in top_tool.description.lower() for kw in ['start and end', 'both', 'range']):
            logger.debug(f"   │  │  ✓ Found tool {top_tool.name} that handles multi-step task")
            return None  # Don't spawn - let tool handle it
    
    # No suitable tool found, need to decompose
    # Use LLM to decompose into ATOMIC sub-tasks
    # CRITICAL: Show what data is already available to avoid "fetch" tasks
    context_summary = ""
    if context:
        available_keys = [k for k in context.keys() if not k.startswith('_')]
        if available_keys:
            context_summary = f"\n\nData already in context (DON'T create 'fetch' tasks for these):\n"
            for key in available_keys[:5]:  # Show first 5
                value = context[key]
                if isinstance(value, dict):
                    if '_ref_id' in value:
                        context_summary += f"  - {key}: Large data (already loaded)\n"
                    elif 'unix_timestamp' in value:
                        context_summary += f"  - {key}: Timestamp = {value.get('unix_timestamp')}\n"
                    elif 'result' in value:
                        context_summary += f"  - {key}: Result already computed\n"
                    else:
                        context_summary += f"  - {key}: Data available\n"
    
    prompt = f"""Break this into ATOMIC sub-tasks that each call ONE tool.

Task: {neuron_desc}
{context_summary}
IMPORTANT Rules:
1. Each sub-task must be ONE specific tool call (e.g., "Call dateToUnixTimestamp for January 1").
2. Do NOT create "fetch" or "get result" tasks for data that's already in context!
3. Do NOT create tasks like "Parse January" or "Extract value" - those aren't tool calls.
4. If data is already available in context, the sub-task should USE it, not fetch it.

If this can be done with a SINGLE tool call, output "SINGLE_TASK".

Output (numbered list of specific tool calls, or SINGLE_TASK):"""
    
    response = ollama.generate(
        prompt,
        system="Decompose into atomic tool calls. Each sub-task = ONE tool execution.",
        temperature=0.1
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    
    if 'SINGLE_TASK' in response_str.upper():
        return None
    
    # Extract numbered items
    subtasks = []
    for match in re.finditer(r'^\d+\.\s*(.+)$', response_str, re.MULTILINE):
        subtasks.append(match.group(1).strip())
    
    # Only return if we have 2-3 subtasks (not 5+)
    if 2 <= len(subtasks) <= 3:
        return subtasks
    else:
        logger.debug(f"   │  │  ⚠️  Too many subtasks ({len(subtasks)}), treating as single task")
        return None


def spawn_dendrites_for_subtasks(
    parent_neuron: Any,
    subtasks: List[str],
    parent_goal: str,
    execute_goal_fn: Callable
) -> Any:
    """
    Spawn dendrites for multiple sub-tasks that need to be completed.
    
    Example: "Get start and end timestamps" spawns 2 dendrites:
    - Dendrite 1: "Get start timestamp"
    - Dendrite 2: "Get end timestamp"
    
    Args:
        parent_neuron: The parent neuron spawning dendrites
        subtasks: List of sub-task descriptions
        parent_goal: Parent goal for context
        execute_goal_fn: Function to execute each dendrite goal (signature: execute_goal(goal, depth))
        
    Returns:
        Aggregated result with all sub-task results
    """
    indent = '  ' * parent_neuron.depth
    logger.info(f"{indent}│  ├─ Sub-tasks:")
    for i, task in enumerate(subtasks, 1):
        logger.info(f"{indent}│  │  {i}. {task}")
    
    # Execute each sub-task
    dendrite_results = []
    for i, task_desc in enumerate(subtasks, 1):
        logger.info(f"{indent}│  ├─ Sub-task {i}/{len(subtasks)}")
        
        # Execute recursively via callback
        dendrite_result = execute_goal_fn(task_desc, depth=parent_neuron.depth + 1)
        
        # Store result in parent's dendrites list if it has one
        if hasattr(parent_neuron, 'spawned_dendrites'):
            # Create a simple dendrite object
            dendrite = type('Dendrite', (), {
                'description': task_desc,
                'index': i,
                'depth': parent_neuron.depth + 1,
                'result': dendrite_result
            })()
            parent_neuron.spawned_dendrites.append(dendrite)
        
        dendrite_results.append(dendrite_result)
    
    logger.info(f"{indent}│  ╰─ All sub-tasks complete, aggregating")
    
    # Aggregate results from all sub-tasks
    aggregated = {
        'success': True,
        'subtasks_completed': len(subtasks),
        'results': dendrite_results
    }
    
    # Merge specific fields if available (e.g., timestamps)
    for result in dendrite_results:
        if isinstance(result, dict):
            # Merge timestamp fields
            for key in ['after_unix', 'before_unix', 'unix_timestamp', 'start_timestamp', 'end_timestamp']:
                if key in result:
                    aggregated[key] = result[key]
    
    return aggregated


# ========================================================================
# Helper Functions
# ========================================================================

def extract_list_items(result: Any) -> List[Dict]:
    """Extract list of items from result."""
    if not isinstance(result, dict):
        return []
    
    # Check if this is a compacted data reference
    if '_ref_id' in result and '_format' in result and result['_format'] == 'disk_reference':
        # Load the actual data from disk to get real items
        try:
            import json
            from pathlib import Path
            data_file = result.get('_data_file')
            if data_file and Path(data_file).exists():
                with open(data_file, 'r') as f:
                    loaded = json.load(f)
                # Try to extract list from loaded data
                for field in ['items', 'entries', 'data', 'results', 'list']:
                    if field in loaded and isinstance(loaded[field], list):
                        logger.info(f"   Loaded {len(loaded[field])} items from disk reference")
                        return loaded[field]
                # If the loaded data itself is a list
                if isinstance(loaded, list):
                    logger.info(f"   Loaded {len(loaded)} items from disk reference (root list)")
                    return loaded
        except Exception as e:
            logger.warning(f"   Failed to load disk reference: {e}")
            # Fall back to extracting count from summary
            pass
        
        # Fallback: Extract count from summary if loading failed
        summary = result.get('summary', '')
        import re
        match = re.search(r'List of (\d+)', summary)
        if match:
            count = int(match.group(1))
            logger.warning(f"   Using placeholder items (count={count}) - disk load failed")
            return [{'_index': i, '_ref_id': result['_ref_id']} for i in range(count)]
    
    # Try common list fields (order matters - more specific first)
    for field in ['items', 'entries', 'data', 'results', 'list']:
        if field in result and isinstance(result[field], list):
            return result[field]
    
    return []


def format_item_goal(template: str, item: Dict, index: int) -> str:
    """Format goal template with item data."""
    try:
        return template.format(**item)
    except KeyError:
        # Fallback: Map common ID fields flexibly
        # E.g., if template has {record_id} but item has 'id', map it
        result_template = template
        
        # Extract placeholder names from template
        import re
        placeholders = re.findall(r'\{(\w+)\}', template)
        
        for placeholder in placeholders:
            # Try to find matching field in item
            if placeholder in item:
                result_template = result_template.replace(
                    '{' + placeholder + '}',
                    str(item[placeholder])
                )
            # Try common fallbacks: if placeholder ends with '_id', try just 'id'
            elif placeholder.endswith('_id') and 'id' in item:
                result_template = result_template.replace(
                    '{' + placeholder + '}',
                    str(item['id'])
                )
        
        # If still has placeholders, replace with index
        if '{' in result_template:
            return f"{result_template} (item {index})"
        
        return result_template


def micro_extract_item_goal(neuron_desc: str, result: Any, ollama) -> str:
    """Micro-prompt: What to do with each item?"""
    
    items = extract_list_items(result)
    sample_item = items[0] if items else {}
    
    prompt = f"""What should be done for EACH item?

Original task: {neuron_desc}
Sample item: {json.dumps(sample_item, indent=2)[:200]}

Output a goal template (use {{field_name}} for placeholders):
Example: "Get details for record {{id}}"

Goal template:"""
    
    response = ollama.generate(
        prompt,
        system="Extract goal template for list items.",
        temperature=0.2
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    return response_str.strip().split('\n')[0]


def micro_extract_item_goal_from_desc(neuron_desc: str, ollama=None) -> str:
    """Extract goal template from description without result data."""
    
    # Use LLM if available to extract a better template
    if ollama:
        prompt = f"""Extract a goal template for processing each item in a list.

Original task description: {neuron_desc}

Output a short, actionable goal template using {{id}} for the item identifier.
Example inputs:
- "Get kudos for each activity" → "Get kudos for item {{id}}"
- "Update each record" → "Update item {{id}}"
- "Process all entries" → "Process item {{id}}"

Goal template:"""
        
        try:
            response = ollama.generate(
                prompt,
                system="Extract goal template for list iteration.",
                temperature=0.2
            )
            response_str = str(response) if not isinstance(response, str) else response
            template = response_str.strip().split('\n')[0]
            if template and '{' in template:
                return template
        except Exception:
            pass  # Fall through to pattern matching
    
    # Pattern matching fallback
    import re
    
    # Try to extract "X for each Y" or "each Y, X"
    match = re.search(r'(get|fetch|retrieve|update|process|delete)\s+(\w+)\s+for\s+each', neuron_desc, re.IGNORECASE)
    if match:
        action = match.group(1).capitalize()
        subject = match.group(2)
        return f"{action} {subject} for item {{id}}"
    
    match = re.search(r'for\s+each\s+\w+,?\s+(get|fetch|retrieve|update|process)', neuron_desc, re.IGNORECASE)
    if match:
        action = match.group(1).capitalize()
        return f"{action} data for item {{id}}"
    
    # Last resort: just use the description as-is
    return f"Process item {{id}}: {neuron_desc}"
