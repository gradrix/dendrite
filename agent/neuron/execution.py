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
    max_retries: int = 5
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
        
        # Type 1: Iteration spawning ("for each item")
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
    
    # Track previous errors for retry feedback
    previous_error = None
    
    for attempt in range(1, max_retries + 1):
        logger.info(f"{indent}│  ├─ Attempt {attempt}/{max_retries}")
        
        # Show previous error context if this is a retry
        if previous_error and attempt > 1:
            logger.info(f"{indent}│  │  📋 Retrying with error context from attempt {attempt-1}:")
            logger.info(f"{indent}│  │     Error: {previous_error.get('error', 'unknown')}")
            if previous_error.get('hint'):
                logger.info(f"{indent}│  │     Hint: {previous_error['hint']}")
        
        # Step 1: Find tool
        tool = micro_find_tool(neuron.description, context, tools, ollama)
        if not tool:
            logger.warning(f"{indent}│  │  ⚠️  No tool found, using AI")
            return ai_response_fn(neuron.description, depth=neuron.depth, sequence=neuron.index)
        
        logger.info(f"{indent}│  ├─ Tool: {tool.name}")
        
        # Step 2: Determine parameters (with previous error context if retrying)
        try:
            params = micro_determine_params(neuron.description, tool, context, ollama, summarize_result_fn, previous_error=previous_error)
        except Exception as param_error:
            import traceback
            logger.error(f"{indent}│  ❌ Parameter determination failed: {param_error}")
            logger.info(f"{indent}│  Traceback:\n{traceback.format_exc()}")
            raise
        
        # Step 2.1: Handle special case where code generation is explicitly needed
        if isinstance(params, dict) and params.get('_needs_code_generation'):
            logger.warning(f"{indent}│  ⚠️ Code generation explicitly required, retrying with enhanced prompt...")
            task_desc = params.get('task', neuron.description)
            
            # Build enhanced error context for retry
            enhanced_error = {
                'error': 'python_code parameter is required but was not generated',
                'hint': f"""CRITICAL: You MUST generate Python code for this task.

Task: {task_desc}

Available data in context: {', '.join([k for k in context.keys() if not k.startswith('_')])}

You MUST return JSON with a 'python_code' field containing executable Python code.
Example: {{"python_code": "my_list = get_context_list('neuron_0_2')\\nresult = len(my_list)"}}

Generate the complete python_code parameter now.""",
                'failed_params': {}
            }
            
            # Retry parameter determination with explicit code generation instructions
            try:
                params = micro_determine_params(
                    neuron.description,  # Use original description, not enhanced prompt
                    tool,
                    context,
                    ollama,
                    summarize_result_fn,
                    previous_error=enhanced_error  # Pass as error context
                )
            except Exception as retry_error:
                logger.error(f"{indent}│  ❌ Code generation retry failed: {retry_error}")
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
                    # Show what failed for transparency
                    if 'python_code' in params:
                        failed_code = params['python_code'][:200] + "..." if len(params['python_code']) > 200 else params['python_code']
                        logger.info(f"{indent}│  │     ❌ Attempt {attempt} failed with code: {failed_code}")
                    logger.info(f"{indent}│  │     💬 Error was: {error_msg}")
                    if hint:
                        logger.info(f"{indent}│  │     💡 Hint: {hint}")
                    
                    # Store error context for next attempt
                    previous_error = {
                        'error': error_msg,
                        'hint': hint,
                        'failed_params': params if 'params' in locals() else None
                    }
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
            
            # ERROR REFLECTION: Missing required parameter
            if "missing" in error_msg.lower() and "required" in error_msg.lower() and "argument" in error_msg.lower():
                logger.info(f"{indent}│  │  🔍 Reflecting on missing parameter...")
                
                # Extract the missing parameter name from error
                # Error format: "get_activity_kudos() missing 1 required positional argument: 'activity_id'"
                import re
                param_match = re.search(r"argument: '(\w+)'", error_msg)
                missing_param = param_match.group(1) if param_match else "unknown"
                
                logger.info(f"{indent}│  │  ❓ Missing parameter: {missing_param}")
                
                # Quick focused prompt: Where should this parameter come from?
                reflection = reflect_on_missing_param(
                    neuron_desc=neuron.description,
                    tool_name=tool.name,
                    missing_param=missing_param,
                    current_params=params,
                    context=context,
                    ollama=ollama
                )
                
                if reflection.get('suggested_value'):
                    logger.info(f"{indent}│  │  💡 Found value: {reflection['suggested_value']}")
                    # Add the missing parameter
                    params[missing_param] = reflection['suggested_value']
                    
                    # Store as previous error for next retry
                    previous_error = {
                        'error': error_msg,
                        'hint': f"Parameter '{missing_param}' was missing. Now using: {reflection['suggested_value']}",
                        'failed_params': params
                    }
                    
                    # Try again with the fixed params
                    try:
                        logger.info(f"{indent}│  │  🔄 Retry with fixed params: {json.dumps(params)[:150]}")
                        result = tool.execute(**params) if tool.name != 'executeDataAnalysis' else tool.execute(**params, **context)
                        logger.info(f"{indent}│  ├─ Result: {summarize_result_fn(result)}")
                        # Success! Continue with validation
                    except Exception as retry_error:
                        logger.warning(f"{indent}│  │  ❌ Retry failed: {retry_error}")
                        if attempt == max_retries:
                            raise
                        continue
                else:
                    # Couldn't find the parameter, let normal retry handle it
                    logger.warning(f"{indent}│  │  ⚠️  Couldn't determine value for '{missing_param}'")
                    previous_error = {
                        'error': error_msg,
                        'hint': f"Parameter '{missing_param}' is required but was not provided",
                        'failed_params': params
                    }
                    if attempt == max_retries:
                        raise
                    continue
            
            # ERROR REFLECTION: Ask LLM what went wrong for 404s
            elif "404" in error_msg or "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
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
        # Generic patterns that work across integrations
        intent_signals = {
            'convert.*timestamp': ['timestamp', 'unix', 'convert'],
            'start.*end.*timestamp': ['range', 'timestamps', 'date'],
            'date.*range': ['range', 'timestamps', 'date'],
            'validate.*timestamp': ['validate', 'timestamp'],
            'current.*date': ['current', 'date', 'time', 'now'],
            # Python execution for counting/filtering
            'count.*where': ['executedataanalysis', 'analysis'],
            'filter.*where': ['executedataanalysis', 'analysis'],
            'executedataanalysis.*count': ['executedataanalysis', 'analysis'],
            'python.*count': ['executedataanalysis', 'python'],
            'use.*executedataanalysis': ['executedataanalysis'],
        }
        
        for pattern, matching_keywords in intent_signals.items():
            if re.search(pattern, desc_lower):
                # Check if tool matches any of the keywords
                if any(kw in tool_name_lower or kw in tool_desc_lower for kw in matching_keywords):
                    score += 10
        
        # Extract keywords for general matching (worth 1 point each)
        keywords = re.findall(r'\b\w{4,}\b', desc_lower)
        tool_text = f"{tool_name_lower} {tool_desc_lower}"
        score += sum(1 for kw in keywords if kw in tool_text)
        
        # Boost for exact key phrase matches in description (worth 5 points)
        # Generic patterns only
        key_phrases = {
            'executedataanalysis': ['executedataanalysis', 'analysis'],
            'python code': ['executedataanalysis', 'python'],
        }
        
        for phrase, matching_keywords in key_phrases.items():
            if phrase in desc_lower:
                if any(kw in tool_name_lower or kw in tool_desc_lower for kw in matching_keywords):
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
        r'\bextract.*data\b': 'extract data',
        r'\bprocess.*items\b': 'process items',
        r'\bget.*information\b': 'get information',
        r'\bfetch.*details\b': 'fetch details',
        r'\bhandle.*data\b': 'handle data',
        r'\bretrieve.*content\b': 'retrieve content',
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
- Check the sample data above to see what fields are available
- Don't invent field names that don't exist in the data
- Common fields might include: 'id', 'name', 'date', 'type', 'count', etc.

Examples:
- Vague: "extract data" 
  → Clear: "extract these fields from items: id, name, date, type, count"

- Vague: "process items"
  → Clear: "for each item, extract the 'name' and 'date' fields"

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
    summarize_result_fn: Any,
    previous_error: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Micro-prompt: What parameters?
    
    Args:
        neuron_desc: The neuron description
        tool: The selected tool
        context: Current execution context
        ollama: Ollama client
        summarize_result_fn: Function to summarize results
        previous_error: Error from previous attempt (if retrying)
        
    Returns:
        Parameter dictionary
    """
    import json
    from pathlib import Path
    
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
    dendrite_item_key = None
    for key, value in context.items():
        if key.startswith('dendrite_item_') and isinstance(value, dict):
            dendrite_item = value
            dendrite_item_key = key
            logger.info(f"   │  │  🎯 Found dendrite item in context: {key}")
            break
    
    # CRITICAL: Extract ID/key from goal string for dendrite spawning scenarios
    # When processing "Extract details for activity 16243029035", we need to use that ID
    goal_extracted_id = None
    goal_extracted_key = None
    
    # Pattern 1: "activity 12345" or "activity_id 12345"
    activity_id_match = re.search(r'activity[_ ]?(?:id[_ ]?)?(\d+)', neuron_desc, re.IGNORECASE)
    if activity_id_match:
        goal_extracted_id = activity_id_match.group(1)
        goal_extracted_key = 'activity_id'
        logger.info(f"   │  │  🎯 Extracted activity ID from goal: {goal_extracted_id}")
    
    # Pattern 2: "record 12345" or "record_id 12345"
    if not goal_extracted_id:
        record_id_match = re.search(r'record[_ ]?(?:id[_ ]?)?(\d+)', neuron_desc, re.IGNORECASE)
        if record_id_match:
            goal_extracted_id = record_id_match.group(1)
            goal_extracted_key = 'record_id'
            logger.info(f"   │  │  🎯 Extracted record ID from goal: {goal_extracted_id}")
    
    # Pattern 3: "item 12345" or any ID-like number in goal
    if not goal_extracted_id:
        item_id_match = re.search(r'(?:item|id|key)[:\s]+(\d+)', neuron_desc, re.IGNORECASE)
        if item_id_match:
            goal_extracted_id = item_id_match.group(1)
            goal_extracted_key = 'id'
            logger.info(f"   │  │  🎯 Extracted item ID from goal: {goal_extracted_id}")
    
    # If we extracted an ID from goal and it matches dendrite item's ID, USE IT!
    if goal_extracted_id and dendrite_item and 'id' in dendrite_item:
        dendrite_item_id = str(dendrite_item['id'])
        if goal_extracted_id == dendrite_item_id:
            logger.info(f"   │  │  ✅ Goal ID matches dendrite item ID: {goal_extracted_id}")
            # Auto-map the ID to common parameter names if tool accepts them
            for param_name in ['activity_id', 'id', 'key', 'record_id']:
                if param_name in param_names and param_name not in auto_mapped_params:
                    auto_mapped_params[param_name] = goal_extracted_id
                    logger.info(f"   │  │  🔗 Auto-mapped {param_name} = {goal_extracted_id} from goal string")
        else:
            logger.warning(f"   │  │  ⚠️  Goal ID ({goal_extracted_id}) doesn't match dendrite item ID ({dendrite_item_id})!")
    
    # Build context info - show what we auto-mapped and what else is available
    context_info = ""
    if auto_mapped_params:
        context_info += f"\n\nAuto-mapped parameters (ALREADY SET - do not override):\n{json.dumps(auto_mapped_params, indent=2)}"
    
    if dendrite_item:
        # Show the specific item we're processing
        # Filter out non-serializable objects (like Neuron instances)
        try:
            serializable_item = {k: v for k, v in dendrite_item.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
            context_info += f"\n\n🎯 CURRENT ITEM DATA (use this for parameters!):\n{json.dumps(serializable_item, indent=2)[:500]}"
            
            # Highlight the ID field specifically
            if 'id' in serializable_item:
                context_info += f"\n\n⚠️  CRITICAL: This item's ID is {serializable_item['id']} - USE THIS ID for any ID/key parameters!"
        except Exception as e:
            context_info += f"\n\nCurrent item data: (serialization error: {e})"
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
                    
                    # NEW: Show actual data structure from the compacted file
                    try:
                        from tools.analysis_tools import inspect_data_structure
                        data_file = value.get('_data_file')
                        if data_file:
                            if Path(data_file).exists():
                                with open(data_file, 'r') as f:
                                    loaded = json.load(f)
                                
                                # Show structure
                                if isinstance(loaded, list) and len(loaded) > 0:
                                    context_info += f"\n     📋 DATA STRUCTURE: List with {len(loaded)} items"
                                    if isinstance(loaded[0], dict):
                                        sample_keys = list(loaded[0].keys())
                                        context_info += f"\n     📋 Each item has keys: {sample_keys[:20]}"
                                        context_info += f"\n     ⚠️  USE THESE KEYS! Don't reference 'athlete', 'items' unless listed above!"
                                elif isinstance(loaded, dict):
                                    context_info += f"\n     📋 DATA STRUCTURE: Dict with keys: {list(loaded.keys())[:20]}"
                                    context_info += f"\n     ⚠️  USE THESE KEYS! Don't invent keys that don't exist!"
                    except Exception as e:
                        logger.debug(f"Could not inspect data structure: {e}")
                        
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
                    # Regular dict or other value - show structure for dicts
                    if isinstance(value, dict) and len(value) > 0:
                        # Show keys available in this dict
                        dict_keys = list(value.keys())
                        context_info += f"\n  📋 {key}: Dict with {len(dict_keys)} keys"
                        context_info += f"\n     🔑 Available keys: {dict_keys[:30]}"
                        context_info += f"\n     💡 Access via: get_context_field('{key}', 'field_name')"
                    else:
                        context_info += f"\n  📋 {key}: {summarize_result_fn(value)}"
        
        context_info += "\n\n✨ SIMPLE DATA ACCESS (for executeDataAnalysis):"
        context_info += "\n  Use these helper functions - they handle everything automatically:"
        context_info += "\n  • get_context_list('key') - Returns list (handles disk/inline/result formats)"
        context_info += "\n  • get_context_data('key') - Returns any data type"
        context_info += "\n  • get_context_field('key', 'field') - Get specific field from dict"
        context_info += "\n\n  Example: my_list = get_context_list('neuron_0_2')"
        context_info += "\n           result = '\\n'.join([f\"{x['name']}\" for x in my_list])"
        context_info += "\n\n  ⚠️  CRITICAL: ONLY use keys listed above! Don't invent keys!"
    
    # Add previous error context if retrying
    error_context = ""
    if previous_error:
        error_msg = previous_error.get('error', 'Unknown')
        hint = previous_error.get('hint', 'N/A')
        failed_code = previous_error.get('failed_params', {}).get('python_code', '')
        
        # Special handling for executeDataAnalysis code errors
        code_fix_instructions = ""
        if tool.name == 'executeDataAnalysis':
            code_fix_instructions = """

🔧 PYTHON CODE GENERATION RULES (AFTER FAILURE):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ PREVIOUS CODE FAILED - Generate NEW code following SIMPLE pattern:

✅ USE THESE HELPER FUNCTIONS (they handle everything automatically):
   • get_context_list('key') - Returns list, handles disk/inline automatically
   • get_context_data('key') - Returns any data type
   • get_context_field('key', 'field') - Get specific field

❌ DO NOT USE:
   • load_data_reference() - DEPRECATED, use helpers instead
   • data['key']['_ref_id'] - DEPRECATED, use helpers instead
   • Complex 3-step load pattern - DEPRECATED, use helpers instead

📋 SIMPLE 2-STEP PATTERN:
   Step 1: my_list = get_context_list('neuron_0_2')
   Step 2: result = '\\n'.join([f"{x['name']}" for x in my_list])

EXAMPLE - OLD vs NEW:
❌ OLD (complex, error-prone):
```python
ref_id = data['neuron_0_2']['_ref_id']
loaded = load_data_reference(ref_id)
my_list = loaded.get('items') or loaded
result = '\\n'.join([f"{x['name']}" for x in my_list])
```

✅ NEW (simple, works always):
```python
my_list = get_context_list('neuron_0_2')
result = '\\n'.join([f"{x['name']}" for x in my_list])
```

🔑 ONLY use keys that ACTUALLY EXIST in "CONTEXT KEYS AVAILABLE" above!
"""
        
        error_context = f"""

⚠️ PREVIOUS ATTEMPT FAILED:
Error: {error_msg}
Hint: {hint}
{code_fix_instructions}
IMPORTANT - Your previous output had errors and MUST be completely regenerated following the rules above!

"""
    
    prompt = """Extract parameters from the task description and available data.
{error_context}
Task: {task}
Tool: {tool_name}

Parameters needed:
{param_info}
{context_info}

CRITICAL RULES FOR PARAMETER EXTRACTION:
0. **PARSE TASK DESCRIPTION FIRST**: If task contains explicit IDs/keys (e.g., "activity 16243029035"), USE THOSE VALUES!
   - Example: "Extract details for activity 16243029035" → {{"activity_id": "16243029035"}} or {{"key": "16243029035"}}
   - Example: "Get record 12345" → {{"record_id": "12345"}} or {{"id": "12345"}}
   - ⚠️  CRITICAL: Don't use a different ID from context - use what's in the task description!
1. **CRITICAL**: ONLY use context keys listed in "CONTEXT KEYS AVAILABLE" above! 
   - If you try to use a key that doesn't exist (e.g., data['neuron_0_2'] when only neuron_1_1 exists), you will get KeyError!
   - Check the list carefully and ONLY use keys that are actually shown!
2. If parameters are already auto-mapped (shown above), include them in your output
3. For remaining REQUIRED parameters - extract from task description or context data
4. ONLY use parameters that this tool actually accepts (check parameter list above)
5. IMPORTANT: Check "CONTEXT KEYS AVAILABLE" - previous neurons have produced data you can use!
   - 📦 (LARGE DATA): Has '_ref_id' → use load_data_reference(data['key']['_ref_id'])
   - 📊 (SCALAR RESULT): NO '_ref_id' → access fields directly like data['key']['unix_timestamp']
   - ✅ (RESULT): Has 'result' field → access as data['key']['result']
   - 🎯 (CURRENT ITEM DATA): If shown, this is THE item you're processing - use its ID!
6. For mergeTimeseriesState specifically:
   - Copy 'entries' data with original field names unchanged
   - Set 'timestamp_field' to match the actual field name in the data (e.g., 'start_date' not 'timestamp')
   - Set 'id_field' to match the actual ID field in the data (e.g., 'id')
7. For date/time filtering (after_unix, before_unix): 
   - Use these ONLY if the tool accepts them AND the task requires date filtering
   - If task says "format" or "display" without mentioning dates, DON'T add date filters
8. If task mentions extracting data from previous steps, look for it in context
9. Extract numeric values as integers, not strings
10. Do NOT use fake/example values like 12345 or 1234567890
11. Check the parameter list - if a parameter is not listed, do NOT include it

EXAMPLES:
- Task: "Extract details for activity 16243029035", Tool accepts: [activity_id, key]
  → Output: {{"activity_id": "16243029035"}} (ID extracted from task description!)

- Task: "Fetch items from January 2024", auto-mapped: {{"after_unix": 1704067200, "before_unix": 1706745599}}
  → Output: {{"after_unix": 1704067200, "before_unix": 1706745599, "per_page": 200}}

- Task: "Format the items", Tool params: [name, description], auto-mapped: {{"after_unix": 1704067200}}
  → Output: {{}} (don't include after_unix - tool doesn't accept it!)

- Task: "Merge extracted data", Tool needs: entries, Context shows: neuron_0_2: Result = [{{...}}, {{...}}]
  → Output: {{"entries": [extracted data from neuron_0_2]}}

- Task: "Get first 3 items", context shows items list
  → Output: {{}} or {{"per_page": 3}} (depending on tool params)

Output JSON only (no explanation):""".format(
        error_context=error_context,
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
            
            # CRITICAL FIX: If tool is executeDataAnalysis and python_code is missing, this is an error
            if tool.name == 'executeDataAnalysis' and 'python_code' not in final_params:
                logger.error(f"   │  │  ❌ CRITICAL: executeDataAnalysis requires python_code but it's missing!")
                logger.error(f"   │  │     Task: {neuron_desc}")
                logger.error(f"   │  │     This usually means the AI was forced to use Python but didn't generate code")
                logger.error(f"   │  │     Returning error to trigger retry with explicit code generation")
                return {'_needs_code_generation': True, 'task': neuron_desc}
            
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
5. Does it handle the disk reference correctly? (load_data_reference returns dict with data array and count)

CRITICAL: For counting tasks, the code should be SIMPLE:
- Load data: loaded = load_data_reference(ref_id)
- Get items: items = loaded.get('items') or loaded.get('data') or loaded.get('results')
- Count: result = len([x for x in items if condition])
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




def reflect_on_missing_param(
    neuron_desc: str,
    tool_name: str,
    missing_param: str,
    current_params: Dict,
    context: Dict,
    ollama: Any
) -> Dict:
    """
    Quick focused prompt to find value for missing required parameter.
    
    Args:
        neuron_desc: The neuron description
        tool_name: The tool that needs the parameter
        missing_param: Name of the missing parameter
        current_params: Parameters that were provided
        context: Execution context
        ollama: Ollama client
        
    Returns:
        Dictionary with suggested_value if found
    """
    # Debug: Log what context keys are available
    context_keys = [k for k in context.keys() if not k.startswith('_')]
    logger.info(f"   🔍 Context keys available: {context_keys[:10]}")
    
    # Look for obvious matches in context first
    for key, value in context.items():
        if key.startswith('dendrite_item_') and isinstance(value, dict):
            # Check if this item has the parameter we need
            if missing_param in value:
                logger.info(f"   💡 Found {missing_param} in {key}: {value[missing_param]}")
                return {'suggested_value': value[missing_param]}
            # Check common ID field mappings
            if missing_param.endswith('_id') and 'id' in value:
                logger.info(f"   💡 Found 'id' in {key}, mapping to {missing_param}: {value['id']}")
                return {'suggested_value': value['id']}
    
    # If not found in dendrite_item, look in _memory for lists with id fields
    # This handles cases where we're iterating over wrong data structure
    if missing_param.endswith('_id') or missing_param == 'id' or missing_param == 'activity_id':
        memory = context.get('_memory', {})
        
        # Find the dendrite item index from context keys
        dendrite_index = None
        for key in context.keys():
            if key.startswith('dendrite_item_'):
                # Extract index: dendrite_item_1_2 -> index 2
                parts = key.split('_')
                if len(parts) >= 4:
                    try:
                        dendrite_index = int(parts[-1])
                        logger.info(f"   🔢 Detected dendrite index: {dendrite_index}")
                        break
                    except ValueError:
                        pass
        
        if dendrite_index is not None:
            # Look for lists in memory that have 'id' fields
            for mem_key, mem_value in memory.items():
                if isinstance(mem_value, dict):
                    # Try different common field names for lists
                    entries = mem_value.get('entries') or mem_value.get('items') or mem_value.get('data')
                    if isinstance(entries, list) and len(entries) > 0:
                        # Check if entries have 'id' field
                        if 'id' in entries[0]:
                            # Try to get the item at dendrite_index - 1 (1-indexed to 0-indexed)
                            if 0 <= dendrite_index - 1 < len(entries):
                                item = entries[dendrite_index - 1]
                                if 'id' in item:
                                    logger.info(f"   💡 Found 'id' in _memory.{mem_key}.entries[{dendrite_index-1}]: {item['id']}")
                                    # Also log item name for better UX per user request
                                    item_name = item.get('name') or item.get('description') or item.get('title') or f"item {dendrite_index}"
                                    logger.info(f"   📝 Item name: {item_name}")
                                    return {'suggested_value': item['id']}
    
    # Build focused prompt
    context_hints = []
    for key, value in context.items():
        if isinstance(value, dict):
            if key.startswith('dendrite_item_'):
                # This is the current item we're processing
                fields = list(value.keys())[:10]
                context_hints.append(f"Current item ({key}): {fields}")
                context_hints.append(f"  Sample values: {json.dumps({k: value[k] for k in fields[:5] if k in value}, default=str)[:200]}")
    
    hints_str = '\n'.join(context_hints) if context_hints else "No item context available"
    
    prompt = f"""Find the value for a missing parameter.

Goal: {neuron_desc}
Tool: {tool_name}
Missing Parameter: {missing_param}
Current Parameters: {json.dumps(current_params)}

Available Context:
{hints_str}

QUESTION: What value should be used for '{missing_param}'?

RULES:
1. Look at "Current item" - it usually has the ID or value needed
2. If missing_param is 'activity_id' and item has 'id', use that
3. If missing_param ends with '_id', look for 'id' field in current item
4. Output ONLY the value (number, string, etc.) - no explanation

If you can find the value, output just the value.
If you cannot find it, output: NOT_FOUND

Response:"""
    
    response = ollama.generate(
        prompt,
        system="You extract parameter values from context. Output only the value or NOT_FOUND.",
        temperature=0.0
    )
    
    response_str = str(response).strip()
    
    if response_str == "NOT_FOUND" or not response_str:
        return {}
    
    # Try to parse as number if it looks like one
    try:
        if response_str.isdigit():
            return {'suggested_value': int(response_str)}
        elif response_str.replace('.', '').isdigit():
            return {'suggested_value': float(response_str)}
    except:
        pass
    
    # Return as string
    return {'suggested_value': response_str}


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
