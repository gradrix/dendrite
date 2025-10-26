"""
Execution module for neuron-based goal processing.

Handles the execution of individual neurons including:
- Tool selection
- Parameter determination
- Code validation
- Error reflection
- Result validation
"""

import re
import json
import logging
import ast
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def execute_neuron(
    neuron: Any,
    parent_goal: str,
    context: Dict,
    tools: Any,
    ollama: Any,
    execute_goal_fn: Any,
    micro_validate_fn: Any,
    summarize_result_fn: Any,
    find_context_list_fn: Any,
    spawn_from_context_fn: Any,
    detect_multi_step_fn: Any,
    spawn_for_subtasks_fn: Any,
    spawn_dendrites_fn: Any,
    aggregate_dendrites_fn: Any,
    detect_spawn_needed_fn: Any,
    ai_response_fn: Any,
    max_depth: int = 4,
    max_retries: int = 3
) -> Any:
    """
    Execute a single neuron with validation and auto-spawning.
    
    Flow:
    1. Check if this neuron needs to iterate over previous results (pre-execution spawning)
    2. Find tool and determine params
    3. Execute tool
    4. Detect if result needs spawning (post-execution spawning)
    5. Validate result
    6. Retry if validation fails (max 2 times)
    
    Args:
        neuron: The neuron to execute
        parent_goal: The parent goal
        context: Execution context dictionary
        tools: Tool registry
        ollama: Ollama client
        execute_goal_fn: Function to execute sub-goals
        micro_validate_fn: Function to validate results
        summarize_result_fn: Function to summarize results
        find_context_list_fn: Function to find iteration lists
        spawn_from_context_fn: Function to spawn from context
        detect_multi_step_fn: Function to detect multi-step tasks
        spawn_for_subtasks_fn: Function to spawn for subtasks
        spawn_dendrites_fn: Function to spawn dendrites
        aggregate_dendrites_fn: Function to aggregate dendrites
        detect_spawn_needed_fn: Function to detect if spawning is needed
        ai_response_fn: Function for AI fallback responses
        max_depth: Maximum recursion depth
        max_retries: Maximum number of retries
        
    Returns:
        Execution result
    """
    indent = '  ' * neuron.depth
    
    # Pre-execution check: Does this neuron need spawning?
    if neuron.depth < max_depth - 1:
        logger.info(f"{indent}│  ├─ Checking for pre-execution spawning...")
        logger.info(f"{indent}│  │  Context keys: {list(context.keys())}")
        
        # Type 1: Iteration spawning ("for each activity")
        context_list = find_context_list_fn(neuron.description, context)
        if context_list:
            logger.info(f"{indent}│  ├─ 🌿 Pre-execution spawning (iterate over context)")
            return spawn_from_context_fn(neuron, context_list, parent_goal)
        
        # Type 2: Multi-step spawning ("start AND end", "both X and Y")
        subtasks = detect_multi_step_fn(neuron.description, context, tools)
        if subtasks and len(subtasks) > 1:
            logger.info(f"{indent}│  ├─ 🌿 Pre-execution spawning ({len(subtasks)} sub-tasks)")
            return spawn_for_subtasks_fn(neuron, subtasks, parent_goal)
        
        logger.info(f"{indent}│  │  No spawning needed")
    
    for attempt in range(1, max_retries + 1):
        logger.info(f"{indent}│  ├─ Attempt {attempt}/{max_retries}")
        
        # Step 1: Find tool
        tool = micro_find_tool(neuron.description, context, tools, ollama)
        if not tool:
            logger.warning(f"{indent}│  │  ⚠️  No tool found, using AI")
            return ai_response_fn(neuron.description, depth=neuron.depth, sequence=neuron.index)
        
        logger.info(f"{indent}│  ├─ Tool: {tool.name}")
        
        # Step 2: Determine parameters
        try:
            params = micro_determine_params(neuron.description, tool, context, ollama, summarize_result_fn)
        except Exception as param_error:
            import traceback
            logger.error(f"{indent}│  ❌ Parameter determination failed: {param_error}")
            logger.info(f"{indent}│  Traceback:\n{traceback.format_exc()}")
            raise
        
        try:
            params_str = json.dumps(params)[:100]
        except Exception as je:
            params_str = str(params)[:100]
        logger.info(f"{indent}│  ├─ Params: {params_str}")
        
        # Step 2.5: Validate Python code for executeDataAnalysis
        if tool.name == 'executeDataAnalysis' and 'python_code' in params:
            validated_code = validate_python_code(
                neuron.description,
                params['python_code'],
                context,
                summarize_result_fn,
                ollama
            )
            if validated_code:
                logger.info(f"{indent}│  ├─ ✅ Code validated")
                params['python_code'] = validated_code
        
        # Step 3: Execute tool
        try:
            # Special case: executeDataAnalysis needs context
            if tool.name == 'executeDataAnalysis':
                result = tool.execute(**params, **context)
            else:
                result = tool.execute(**params)
            logger.info(f"{indent}│  ├─ Result: {summarize_result_fn(result)}")
            
            # Check if execution returned an error with retry flag
            if isinstance(result, dict) and not result.get('success', True):
                error_msg = result.get('error', 'Unknown error')
                should_retry = result.get('retry', False)
                hint = result.get('hint', '')
                
                logger.warning(f"{indent}│  │  ⚠️  Tool returned error: {error_msg}")
                if hint:
                    logger.info(f"{indent}│  │  💡 Hint: {hint}")
                
                if should_retry and attempt < max_retries:
                    logger.info(f"{indent}│  │  🔄 Retrying with corrected code...")
                    # Re-validate and regenerate code
                    continue
                elif not should_retry:
                    # Fatal error, don't retry
                    logger.error(f"{indent}│  │  ❌ Fatal error, cannot retry")
                    raise Exception(error_msg)
                
        except Exception as e:
            import traceback
            error_msg = str(e)
            logger.warning(f"{indent}│  │  ⚠️  Execution error: {error_msg}")
            logger.debug(f"{indent}│  │  Traceback: {traceback.format_exc()}")
            
            # ERROR REFLECTION: Ask LLM what went wrong
            if "404" in error_msg or "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                logger.info(f"{indent}│  │  🔍 Reflecting on error - likely hallucinated parameter")
                
                reflection = reflect_on_error(
                    neuron_desc=neuron.description,
                    tool_name=tool.name,
                    params=params,
                    error=error_msg,
                    context=context,
                    ollama=ollama
                )
                
                logger.info(f"{indent}│  │  💡 Reflection: {reflection.get('diagnosis', 'Unknown')}")
                
                # If reflection suggests parameter fix, try it
                if reflection.get('suggested_fix'):
                    logger.info(f"{indent}│  │  🔧 Applying suggested fix...")
                    suggested_params = reflection.get('suggested_params', {})
                    if suggested_params:
                        try:
                            logger.info(f"{indent}│  │  🔄 Retry with: {json.dumps(suggested_params)[:100]}")
                            result = tool.execute(**suggested_params)
                            logger.info(f"{indent}│  ├─ Result: {summarize_result_fn(result)}")
                            # Success! Continue with validation
                        except Exception as retry_error:
                            logger.warning(f"{indent}│  │  ❌ Suggested fix failed: {retry_error}")
                            if attempt == max_retries:
                                raise
                            continue
                    else:
                        # No suggested params, retry from scratch
                        if attempt == max_retries:
                            raise
                        continue
                else:
                    # No fix suggested, retry
                    if attempt == max_retries:
                        raise
                    continue
            else:
                # Not a 404 error, just retry
                if attempt == max_retries:
                    raise
                continue
        
        # Step 4: Detect list → spawn dendrites
        if neuron.depth < max_depth - 1:  # Leave room for one more level
            spawn_needed = detect_spawn_needed_fn(neuron.description, result)
            
            if spawn_needed:
                logger.info(f"{indent}│  ├─ 🌿 Spawning dendrites")
                result = spawn_dendrites_fn(neuron, result, parent_goal, context)
        
        # Step 5: Validate
        is_valid = micro_validate_fn(parent_goal, neuron.description, result)
        logger.info(f"{indent}│  ├─ Valid: {is_valid}")
        
        if is_valid:
            neuron.validated = True
            logger.info(f"{indent}│  ╰─ ✅ Neuron complete")
            return result
        else:
            logger.warning(f"{indent}│  │  ⚠️  Validation failed, retrying")
            if attempt == max_retries:
                logger.error(f"{indent}│  ╰─ ❌ Max retries reached, accepting result")
                return result
    
    return result


def micro_find_tool(neuron_desc: str, context: Dict, tools: Any, ollama: Any) -> Optional[Any]:
    """
    Micro-prompt: Which tool for this neuron?
    
    Args:
        neuron_desc: The neuron description
        context: Current execution context
        tools: Tool registry
        ollama: Ollama client
        
    Returns:
        Selected tool or None
    """
    # Check if this is a counting/filtering task - MUST use Python tool
    counting_keywords = ['count', 'how many', 'filter', 'where', 'matching', 'with type']
    is_counting = any(kw in neuron_desc.lower() for kw in counting_keywords)
    
    # If counting/filtering, force executeDataAnalysis tool
    if is_counting:
        for tool in tools.list_tools():
            if tool.name.lower() == 'executedataanalysis':
                logger.info(f"   │  │  🐍 Counting task detected, forcing Python tool: {tool.name}")
                return tool
    
    # Check if this is a formatting/display task (no tool needed)
    formatting_keywords = ['format', 'display', 'show', 'report', 'present', 'output', 'print', 'organize']
    has_format_keyword = any(kw in neuron_desc.lower() for kw in formatting_keywords)
    
    # Check if task mentions working with existing/fetched/previous data (for formatting only)
    works_with_existing = any(word in neuron_desc.lower() for word in [
        'existing', 'available', 'fetched', 'current results', 'all three', 
        'above', 'results', 'data', 'from previous', 'from fetched', 'first'
    ])
    
    has_context = len(context) > 0
    
    # Check if context contains a data reference (compacted large data)
    has_data_reference = any(
        isinstance(v, dict) and v.get('_format') == 'disk_reference' 
        for v in context.values()
    )
    
    # If it's about formatting EXISTING data...
    if has_format_keyword and (works_with_existing or has_context):
        # If data is compacted to disk, we need executeDataAnalysis to load it
        if has_data_reference:
            logger.info(f"   │  │  💡 Detected formatting of compacted data, suggesting executeDataAnalysis")
            # Return executeDataAnalysis tool for loading and formatting
            for tool in tools.list_tools():
                if tool.name.lower() == 'executedataanalysis':
                    return tool
            # Fallback if tool not found
            logger.warning(f"   │  │  ⚠️  executeDataAnalysis tool not found, using AI")
            return None
        else:
            # Small data in context, AI can format directly
            logger.info(f"   │  │  💡 Detected formatting task on existing data, will use AI response")
            return None
    
    # Intent-based matching with stronger signals
    desc_lower = neuron_desc.lower()
    relevant_tools = []
    
    for tool in tools.list_tools():
        score = 0
        tool_name_lower = tool.name.lower()
        tool_desc_lower = tool.description.lower()
        
        # Strong intent signals (worth 10 points each)
        intent_signals = {
            'fetch.*activities': ['getmyactivities', 'getdashboardfeed'],
            'get.*my.*activities': ['getmyactivities'],
            'get.*strava.*activities': ['getmyactivities'],
            'retrieve.*activities': ['getmyactivities', 'getdashboardfeed'],
            'convert.*timestamp': ['datetounixtimestamp', 'getdaterangetimestamps'],
            'start.*end.*timestamp': ['getdaterangetimestamps'],
            'date.*range': ['getdaterangetimestamps'],
            'give.*kudos': ['givekudos', 'givekudostoparticipants'],
            'validate.*timestamp': ['validatetimestamp'],
            'current.*date': ['getcurrentdatetime'],
            # Python execution for counting/filtering
            'count.*activities': ['executedataanalysis'],
            'count.*where': ['executedataanalysis'],
            'filter.*where': ['executedataanalysis'],
            'executedataanalysis.*count': ['executedataanalysis'],
            'python.*count': ['executedataanalysis'],
            'use.*executedataanalysis': ['executedataanalysis'],
        }
        
        for pattern, matching_tools in intent_signals.items():
            if re.search(pattern, desc_lower):
                if tool_name_lower in matching_tools:
                    score += 10
        
        # Extract keywords for general matching (worth 1 point each)
        keywords = re.findall(r'\b\w{4,}\b', desc_lower)
        tool_text = f"{tool_name_lower} {tool_desc_lower}"
        score += sum(1 for kw in keywords if kw in tool_text)
        
        # Boost for exact key phrase matches in description (worth 5 points)
        key_phrases = {
            'my activities': 'getmyactivities',
            'my own': 'getmyactivities',
            'strava activities': 'getmyactivities',
            'friends activities': 'getdashboardfeed',
            'dashboard feed': 'getdashboardfeed',
            'executedataanalysis': 'executedataanalysis',
            'python code': 'executedataanalysis',
            'count activities': 'executedataanalysis',
        }
        
        for phrase, matching_tool in key_phrases.items():
            if phrase in desc_lower and tool_name_lower == matching_tool:
                score += 5
        
        if score > 0:
            relevant_tools.append((score, tool))
    
    if not relevant_tools:
        return None
    
    # Sort by score and take top 5
    relevant_tools.sort(reverse=True, key=lambda x: x[0])
    top_tools = [t[1] for t in relevant_tools[:5]]
    
    logger.debug(f"   │  │  Top tools: {[(t.name, s) for s, t in relevant_tools[:5]]}")
    
    # If top tool has significantly higher score, use it directly
    if len(relevant_tools) >= 2:
        top_score = relevant_tools[0][0]
        second_score = relevant_tools[1][0]
        if top_score >= second_score + 5:  # Clear winner
            logger.debug(f"   │  │  ✓ Clear winner: {relevant_tools[0][1].name} (score {top_score} vs {second_score})")
            return relevant_tools[0][1]
    
    # Otherwise, ask LLM to pick from top 5
    tool_list = "\n".join([f"- {t.name}: {t.description}" for t in top_tools])
    
    prompt = f"""Select the BEST tool for this task:

Task: {neuron_desc}

Available tools:
{tool_list}

Instructions:
- Choose the tool that most directly accomplishes the task
- For fetching data: use get/fetch tools
- For converting dates: use timestamp tools
- For counting/filtering: if data already exists, don't use tools (use AI analysis)

Output ONLY the tool name:"""
    
    response = ollama.generate(
        prompt,
        system="You select tools. Output only the tool name, nothing else.",
        temperature=0.1
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    tool_name = response_str.strip().split()[0]
    
    # Find matching tool
    selected_tool = None
    for tool in top_tools:
        if tool.name.lower() in tool_name.lower():
            selected_tool = tool
            break
    
    if not selected_tool:
        selected_tool = top_tools[0] if top_tools else None
    
    # VALIDATION: Double-check if tool matches the task
    if selected_tool and len(top_tools) > 1:
        validation_prompt = f"""Is this tool correct for the task?

Task: {neuron_desc}
Selected tool: {selected_tool.name} - {selected_tool.description}

Question: Does this tool do what the task asks?
- If YES, output: YES
- If NO, output: NO and suggest better tool name

Answer:"""
        
        validation_response = ollama.generate(
            validation_prompt,
            system="Validate tool selection. Output YES or NO.",
            temperature=0.1
        )
        
        validation_str = str(validation_response) if not isinstance(validation_response, str) else validation_response
        
        if 'no' in validation_str.lower():
            logger.warning(f"   │  │  ⚠️  Tool validation failed: {selected_tool.name} may not be correct")
            # Try to extract suggested tool name
            for tool in top_tools:
                if tool.name.lower() in validation_str.lower() and tool != selected_tool:
                    logger.info(f"   │  │  🔄 Switching to suggested tool: {tool.name}")
                    selected_tool = tool
                    break
    
    return selected_tool


def clarify_vague_terms(neuron_desc: str, tool: Any, context: Dict, ollama: Any) -> str:
    """
    Inter-neuron communication: Ask decomposer to clarify vague terms.
    
    This allows Neuron N to ask "what did you mean by X?" to the neuron
    that created the task decomposition.
    
    Returns: Clarified description or original if no clarification needed
    """
    # Detect vague terms that need clarification
    vague_terms = []
    
    # Common vague patterns
    vague_patterns = {
        r'\bkudos data\b': 'kudos data',
        r'\bextract.*data\b': 'extract data',
        r'\bprocess.*items\b': 'process items',
        r'\bhandle.*activities\b': 'handle activities',
        r'\bget.*information\b': 'get information',
        r'\bfetch.*details\b': 'fetch details',
    }
    
    desc_lower = neuron_desc.lower()
    for pattern, term in vague_patterns.items():
        if re.search(pattern, desc_lower):
            vague_terms.append(term)
    
    if not vague_terms:
        return neuron_desc  # No vague terms, no clarification needed
    
    # Get original goal from context (if available)
    original_goal = context.get('_original_goal', 'Unknown goal')
    
    # Get sample data from context to show actual field names available
    sample_data_info = ""
    for key, value in context.items():
        if key.startswith('_') or key.startswith('dendrite_'):
            continue
        if isinstance(value, dict):
            if '_format' in value and value.get('_format') == 'disk_reference':
                # Show what fields are in this large data
                sample_data_info += f"\n  - {key} contains: {value.get('summary', 'data')}"
            elif 'result' in value:
                # Show sample of result data
                result = value.get('result')
                if isinstance(result, list) and len(result) > 0:
                    first_item = result[0]
                    if isinstance(first_item, dict):
                        sample_data_info += f"\n  - {key} has items with fields: {', '.join(first_item.keys())}"
    
    # Ask for clarification from the "decomposer" (simulate inter-neuron communication)
    prompt = f"""You are the decomposer neuron that created this sub-task. A child neuron needs clarification.

ORIGINAL GOAL: {original_goal}

SUB-TASK (created by you): {neuron_desc}

TOOL SELECTED: {tool.name} - {tool.description}

AVAILABLE DATA IN CONTEXT:{sample_data_info}

QUESTION: The child neuron asks: "What exactly do you mean by '{vague_terms[0]}'?"

Think about:
1. What was the ORIGINAL goal asking for?
2. What fields/attributes should be extracted? (Use ACTUAL field names from AVAILABLE DATA above)
3. What format should the result have?

CRITICAL: Use the EXACT field names that exist in the data!
- For Strava activities, use: 'id' (NOT 'activity_id'), 'start_date' (NOT 'timestamp'), 'name', 'sport_type', 'kudos_count'
- Don't invent field names that don't exist in the data

Examples:
- Vague: "extract kudos data" 
  → Clear: "extract these fields from activities: id, start_date, name, sport_type, kudos_count"

- Vague: "process activities"
  → Clear: "for each activity, extract the 'name' and 'start_date' fields"

Output ONLY the clarified task description (rewrite the sub-task with EXACT field names):"""
    
    response = ollama.generate(
        prompt,
        system="You clarify vague task descriptions. Be specific about field names and formats.",
        temperature=0.1
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    clarified = response_str.strip().split('\n')[0]  # Take first line
    
    # Only use clarification if it's actually more specific (longer and mentions fields)
    if len(clarified) > len(neuron_desc) and any(word in clarified.lower() for word in ['field', 'attribute', 'name', 'type', 'count', 'id', 'timestamp']):
        return clarified
    else:
        return neuron_desc


def micro_determine_params(
    neuron_desc: str,
    tool: Any,
    context: Dict,
    ollama: Any,
    summarize_result_fn: Any
) -> Dict[str, Any]:
    """
    Micro-prompt: What parameters?
    
    Args:
        neuron_desc: The neuron description
        tool: The selected tool
        context: Current execution context
        ollama: Ollama client
        summarize_result_fn: Function to summarize results
        
    Returns:
        Parameter dictionary
    """
    # STEP 0: CLARIFY vague terms before proceeding
    # Check if neuron description contains vague terms that need clarification
    clarified_desc = clarify_vague_terms(neuron_desc, tool, context, ollama)
    if clarified_desc != neuron_desc:
        logger.info(f"   │  │  💬 Clarified task: {clarified_desc}")
        neuron_desc = clarified_desc  # Use clarified description
    
    param_info = "\n".join([
        f"  - {p['name']} ({p.get('type', 'any')}): {p.get('description', '')}"
        for p in tool.parameters
    ])
    
    # STEP 1: AUTO-MAP parameters from context (deterministic matching)
    # Only auto-map if the tool ACTUALLY accepts these parameters
    auto_mapped_params = {}
    param_names = [p['name'] for p in tool.parameters]
    
    # Search context for exact parameter name matches (only for params this tool accepts)
    for param_name in param_names:
        for ctx_key, ctx_value in context.items():
            # Direct key match in dict - tool accepts this param, context has it
            if isinstance(ctx_value, dict) and param_name in ctx_value:
                auto_mapped_params[param_name] = ctx_value[param_name]
                logger.debug(f"   │  │  🔗 Auto-mapped {param_name} = {ctx_value[param_name]} from {ctx_key}")
                break
    
    # Find dendrite item data in context (most relevant for current execution)
    dendrite_item = None
    for key, value in context.items():
        if key.startswith('dendrite_item_') and isinstance(value, dict):
            dendrite_item = value
            break
    
    # Build context info - show what we auto-mapped and what else is available
    context_info = ""
    if auto_mapped_params:
        context_info += f"\n\nAuto-mapped parameters (ALREADY SET - do not override):\n{json.dumps(auto_mapped_params, indent=2)}"
    
    if dendrite_item:
        # Show the specific item we're processing
        context_info += f"\n\nCurrent item data:\n{json.dumps(dendrite_item, indent=2)[:500]}"
    elif context:
        # Show detailed data from previous steps with actual values
        context_info += "\n\nData available from previous neurons (YOUR DISPOSAL - use as needed):"
        
        # UNIVERSAL CONTEXT GUIDE: Show what's available for ANY tool
        context_info += "\n\nCONTEXT KEYS AVAILABLE:"
        for key, value in context.items():
            if key.startswith('_'):  # Skip internal keys like _original_goal
                continue
                
            if isinstance(value, dict):
                if '_format' in value and value.get('_format') == 'disk_reference':
                    # This is a DATA reference (for executeDataAnalysis)
                    context_info += f"\n  📦 {key}: LARGE DATA - {value.get('summary', 'data reference')}"
                    context_info += f"\n     → For Python: data['{key}']['_ref_id'] then load_data_reference(...)"
                elif 'success' in value and 'result' in value:
                    # This is a RESULT from a previous neuron - SHOW THE ACTUAL DATA!
                    result_data = value.get('result')
                    # Format result nicely for display
                    if isinstance(result_data, list) and len(result_data) > 0:
                        result_str = json.dumps(result_data, indent=2)[:500]  # Show up to 500 chars
                        context_info += f"\n  ✅ {key}: Result (list with {len(result_data)} items)"
                        context_info += f"\n     DATA: {result_str}"
                        context_info += f"\n     → To use as parameter: Copy this data directly into your JSON"
                    elif isinstance(result_data, dict):
                        result_str = json.dumps(result_data, indent=2)[:500]
                        context_info += f"\n  ✅ {key}: Result (dict)"
                        context_info += f"\n     DATA: {result_str}"
                        context_info += f"\n     → To use as parameter: Copy this data directly into your JSON"
                    else:
                        context_info += f"\n  ✅ {key}: Result = {result_data}"
                        context_info += f"\n     → To use as parameter: Use this value directly"
                elif 'success' in value:
                    # This is a SCALAR result (no 'result' field, but has direct values like unix_timestamp)
                    # Extract key fields to show
                    key_fields = {k: v for k, v in value.items() if k != 'success' and k != 'input'}
                    context_info += f"\n  📊 {key}: SCALAR RESULT - {key_fields}"
                    context_info += f"\n     → NOT a data reference! Use values directly: data['{key}']['unix_timestamp']"
                    context_info += f"\n     → ⚠️ WARNING: NO '_ref_id' field! This is NOT disk data!"
                    context_info += f"\n     → ❌ DO NOT try: load_data_reference(data['{key}']['_ref_id']) - will fail!"
                else:
                    context_info += f"\n  📋 {key}: {summarize_result_fn(value)}"
        
        context_info += "\n\nHOW TO USE CONTEXT DATA:"
        context_info += "\n  - CRITICAL: ONLY use context keys that are listed above! Don't invent keys that don't exist!"
        context_info += "\n  - If you need data that's not in context, the tool will fail. That's OK - describe what you need."
        context_info += "\n  - If tool needs 'entries' parameter and context shows DATA → copy that data AS-IS (keep field names unchanged)"
        context_info += "\n  - For scalar results (📊), access fields directly: data['neuron_X_Y']['unix_timestamp']"
        context_info += "\n  - For disk data (📦), use: data['neuron_X_Y']['_ref_id'] then load_data_reference(...)"
        context_info += "\n  - NEVER try to load_data_reference on scalar results - they have NO _ref_id!"
    
    prompt = """Extract parameters from the task description and available data.

Task: {task}
Tool: {tool_name}

Parameters needed:
{param_info}
{context_info}

CRITICAL RULES FOR PARAMETER EXTRACTION:
0. **CRITICAL**: ONLY use context keys listed in "CONTEXT KEYS AVAILABLE" above! 
   - If you try to use a key that doesn't exist (e.g., data['neuron_0_2'] when only neuron_1_1 exists), you will get KeyError!
   - Check the list carefully and ONLY use keys that are actually shown!
1. If parameters are already auto-mapped (shown above), include them in your output
2. For remaining REQUIRED parameters - extract from task description or context data
3. ONLY use parameters that this tool actually accepts (check parameter list above)
4. IMPORTANT: Check "CONTEXT KEYS AVAILABLE" - previous neurons have produced data you can use!
   - 📦 (LARGE DATA): Has '_ref_id' → use load_data_reference(data['key']['_ref_id'])
   - 📊 (SCALAR RESULT): NO '_ref_id' → access fields directly like data['key']['unix_timestamp']
   - ✅ (RESULT): Has 'result' field → access as data['key']['result']
5. For mergeTimeseriesState specifically:
   - Copy 'entries' data with original field names unchanged
   - Set 'timestamp_field' to match the actual field name in the data (e.g., 'start_date' not 'timestamp')
   - Set 'id_field' to match the actual ID field in the data (e.g., 'id')
6. For date/time filtering (after_unix, before_unix): 
   - Use these ONLY if the tool accepts them AND the task requires date filtering
   - If task says "format" or "display" without mentioning dates, DON'T add date filters
7. If task mentions extracting data from previous steps, look for it in context (e.g., "activities", "activity_id")
8. Extract numeric values as integers, not strings
8. Do NOT use fake/example values like 12345 or 1234567890
9. Check the parameter list - if a parameter is not listed, do NOT include it

EXAMPLES:
- Task: "Fetch activities from January 2024", auto-mapped: {{"after_unix": 1704067200, "before_unix": 1706745599}}
  → Output: {{"after_unix": 1704067200, "before_unix": 1706745599, "per_page": 200}}

- Task: "Format the activities", Tool params: [name, description], auto-mapped: {{"after_unix": 1704067200}}
  → Output: {{}} (don't include after_unix - tool doesn't accept it!)

- Task: "Merge extracted data", Tool needs: entries, Context shows: neuron_0_2: Result = [{{...}}, {{...}}]
  → Output: {{"entries": [extracted data from neuron_0_2]}}

- Task: "Get first 3 activities", context shows activities list
  → Output: {{}} or {{"per_page": 3}} (depending on tool params)

Output JSON only (no explanation):""".format(
        task=neuron_desc,
        tool_name=tool.name,
        param_info=param_info,
        context_info=context_info
    )
    
    response = ollama.generate(
        prompt,
        system="Extract parameters from context and output as JSON. When context shows 'neuron_0_X: Result = [data]', include that actual data in your JSON output. Output only valid JSON with actual values, not references.",
        temperature=0.1  # Lower temperature for more deterministic extraction
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    
    # Extract JSON
    json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
    if json_match:
        try:
            params = json.loads(json_match.group())
            
            # FIX: Sometimes LLM wraps params in {"tool": "X", "parameters": {...}}
            # Extract the actual parameters if this happens
            if isinstance(params, dict) and 'parameters' in params and 'tool' in params:
                logger.debug(f"   │  │  🔧 Unwrapping nested parameters structure")
                params = params['parameters']
            
            # MERGE: Start with auto-mapped params, then overlay LLM-extracted ones
            final_params = {**auto_mapped_params, **params}
            
            # VALIDATION: Filter out parameters the tool doesn't accept
            valid_param_names = [p['name'] for p in tool.parameters]
            invalid_params = [k for k in final_params.keys() if k not in valid_param_names]
            if invalid_params:
                logger.debug(f"   │  │  🗑️  Removing invalid params: {invalid_params} (tool {tool.name} doesn't accept them)")
                final_params = {k: v for k, v in final_params.items() if k in valid_param_names}
            
            # Clean up None values (but keep auto-mapped values even if None)
            final_params = {k: v for k, v in final_params.items() if v is not None or k in auto_mapped_params}
            
            # Validate required parameters
            required_params = [p['name'] for p in tool.parameters if p.get('required', False)]
            missing_params = [p for p in required_params if p not in final_params or final_params[p] in [None, "", {}, []]]
            
            # Fallback: If still missing required params, search context for values
            if missing_params:
                logger.debug(f"   │  │  ⚠️  Missing required parameters: {missing_params}, trying context search")
                
                # Search context for required param values
                for param_name in missing_params:
                    # Look through all context for this param
                    for ctx_key, ctx_value in context.items():
                        if isinstance(ctx_value, dict) and param_name in ctx_value:
                            final_params[param_name] = ctx_value[param_name]
                            logger.debug(f"   │  │  ✓ Found {param_name} = {final_params[param_name]} in {ctx_key}")
                            break
                    
                    # Special handling for validateTimestamp
                    if tool.name == 'validateTimestamp':
                        if param_name == 'unix_timestamp' and param_name not in final_params:
                            # Look for unix_timestamp in previous conversion result
                            for ctx_value in context.values():
                                if isinstance(ctx_value, dict) and 'unix_timestamp' in ctx_value:
                                    final_params['unix_timestamp'] = ctx_value['unix_timestamp']
                                    logger.debug(f"   │  │  ✓ Found unix_timestamp = {final_params['unix_timestamp']} from previous result")
                                    break
            
            logger.debug(f"   │  │  📦 Final parameters: {final_params}")
            return final_params
            
        except json.JSONDecodeError as e:
            logger.error(f"   │  │  ❌ Failed to parse parameters: {e}")
            # Return auto-mapped params if JSON parsing failed
            return auto_mapped_params if auto_mapped_params else {}
    
    # If no JSON match, return auto-mapped params
    return auto_mapped_params if auto_mapped_params else {}


def validate_python_code(
    task: str,
    python_code: str,
    context: Dict,
    summarize_result_fn: Any,
    ollama: Any
) -> Optional[str]:
    """
    Validate that Python code will correctly answer the task.
    Returns simplified/corrected code or None if validation fails.
    
    Args:
        task: The task description
        python_code: The Python code to validate
        context: Current execution context
        summarize_result_fn: Function to summarize results
        ollama: Ollama client
        
    Returns:
        Validated/corrected code or None
    """
    # FIRST: Check Python syntax before asking LLM
    try:
        ast.parse(python_code)
    except SyntaxError as e:
        logger.warning(f"   │  │  ⚠️  Python syntax error detected: {e}")
        return None  # Force regeneration with new code
    
    # Get context summary for validation
    context_summary = []
    for key, value in context.items():
        if isinstance(value, dict):
            if '_format' in value and value.get('_format') == 'disk_reference':
                context_summary.append(f"  ✓ {key}: LARGE DATA - {value.get('summary', 'N/A')}")
                context_summary.append(f"     → Use: data['{key}']['_ref_id'] then load_data_reference(...)")
            elif 'success' in value and 'result' in value:
                context_summary.append(f"  ✗ {key}: Scalar result = {value.get('result')} (NOT a data reference)")
            else:
                context_summary.append(f"  {key}: {summarize_result_fn(value)}")
    
    prompt = f"""Validate this Python code will correctly answer the task.

TASK: {task}

PYTHON CODE:
```python
{python_code}
```

AVAILABLE CONTEXT KEYS:
{chr(10).join(context_summary)}

KEY GUIDE:
✓ = Large data reference (has _ref_id, must load with load_data_reference)
✗ = Scalar result (just a number/value, NOT loadable)

VALIDATION CHECKS:
1. Does the code use the CORRECT context key? (✓ keys for data, not ✗ keys)
2. Does it answer the EXACT question asked?
3. Does it access fields that actually exist in the data?
4. Is it unnecessarily complex? (Simple is better)
5. Does it handle the disk reference correctly? (load_data_reference returns {{'activities': [...], 'count': N}})

CRITICAL: For counting tasks, the code should be SIMPLE:
- Load data: loaded = load_data_reference(ref_id)
- Count: result = len([x for x in loaded['activities'] if condition])
- DON'T try to extract extra fields like 'date', 'description' unless specifically asked

COMMON ERRORS TO FIX:
- Using neuron_0_2 when it's a scalar result, should use neuron_0_1 (the actual data)
- Trying to load_data_reference on a scalar result
- Accessing wrong fields in the data structure

If code is CORRECT, output: VALID
If code needs fixing, output corrected Python code (just the code, no explanation)
If code is completely wrong, output: INVALID

Response:"""
    
    response = ollama.generate(
        prompt,
        system="You validate Python code. Output VALID, corrected code, or INVALID.",
        temperature=0.1
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    
    if 'VALID' in response_str.upper() and 'INVALID' not in response_str.upper():
        logger.debug(f"   │  │  ✓ Code validation passed")
        return python_code
    elif 'INVALID' in response_str.upper():
        logger.warning(f"   │  │  ⚠️  Code validation failed - code is invalid")
        return None
    else:
        # LLM provided corrected code
        # Extract code block
        code_match = re.search(r'```(?:python)?\n(.+?)\n```', response_str, re.DOTALL)
        if code_match:
            corrected = code_match.group(1).strip()
            logger.info(f"   │  │  🔧 Code corrected by validator")
            logger.debug(f"   │  │  Original: {python_code[:100]}...")
            logger.debug(f"   │  │  Corrected: {corrected[:100]}...")
            return corrected
        else:
            # Try to extract code without markers
            corrected = response_str.strip()
            if corrected and not corrected.startswith('VALID') and not corrected.startswith('INVALID'):
                logger.info(f"   │  │  🔧 Code corrected by validator")
                return corrected
            else:
                logger.warning(f"   │  │  ⚠️  Could not extract corrected code")
                return python_code  # Return original if we can't parse correction


def reflect_on_error(
    neuron_desc: str,
    tool_name: str,
    params: Dict,
    error: str,
    context: Dict,
    ollama: Any
) -> Dict:
    """
    Reflect on tool execution error to diagnose the problem.
    Returns diagnosis and suggested fix if available.
    
    Args:
        neuron_desc: The neuron description
        tool_name: The tool that failed
        params: Parameters used
        error: Error message
        context: Execution context
        ollama: Ollama client
        
    Returns:
        Dictionary with diagnosis, suggested_fix, and suggested_params
    """
    # Summarize context
    context_summary = []
    for key, value in context.items():
        if isinstance(value, list):
            context_summary.append(f"- {key}: list of {len(value)} items")
            if value and isinstance(value[0], dict):
                sample_keys = list(value[0].keys())[:3]
                context_summary.append(f"  Sample keys: {sample_keys}")
        elif isinstance(value, dict):
            sample_keys = list(value.keys())[:3]
            context_summary.append(f"- {key}: dict with keys {sample_keys}")
        else:
            context_summary.append(f"- {key}: {str(value)[:50]}")
    
    context_str = '\n'.join(context_summary) if context_summary else "No context available"
    
    prompt = f"""A tool execution failed. Diagnose what went wrong.

Neuron Goal: {neuron_desc}
Tool Called: {tool_name}
Parameters Used: {json.dumps(params, indent=2)}
Error: {error}

Available Context Data:
{context_str}

Common Issues:
1. Hallucinated ID: Parameter uses made-up ID instead of actual ID from context
2. Wrong parameter type: String instead of int, etc.
3. Missing required parameter
4. Wrong parameter extracted from context

Provide:
1. diagnosis: What went wrong (1 sentence)
2. suggested_fix: Brief description of fix (if available)
3. suggested_params: Corrected parameters (JSON, if applicable)

Response format (JSON):
{{"diagnosis": "...", "suggested_fix": "...", "suggested_params": {{...}} }}"""
    
    response = ollama.generate(
        prompt,
        system="Diagnose tool execution errors and suggest fixes. Focus on parameter issues.",
        temperature=0.2
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    
    # Parse JSON response
    try:
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
        if json_match:
            reflection = json.loads(json_match.group())
            return reflection
    except Exception as e:
        logger.warning(f"Failed to parse reflection: {e}")
    
    return {"diagnosis": response_str.strip(), "suggested_fix": None, "suggested_params": None}
