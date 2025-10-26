"""
Dendrite Validation Module

Handles validation of neuron results:
1. Micro-validation: Check if a single neuron's result is valid
2. Goal completion validation: Check if entire goal is completed
3. Missing info detection: Identify what's missing from results
4. Corrective goal generation: Create goals to fix incomplete results

All functions are stateless and accept dependencies as parameters.
"""

import logging
import json
from typing import Any, Dict

logger = logging.getLogger(__name__)


def micro_validate(parent_goal: str, neuron_desc: str, result: Any, summarize_fn: callable, ollama) -> bool:
    """
    Validate if a single neuron's result is valid.
    
    Args:
        parent_goal: The parent goal for context
        neuron_desc: Description of the neuron being validated
        result: The result to validate
        summarize_fn: Function to summarize results (signature: summarize(result) -> str)
        ollama: OllamaClient for LLM calls
        
    Returns:
        True if valid, False otherwise
    """
    result_summary = summarize_fn(result)
    
    # Check for explicit success/error indicators
    if isinstance(result, dict):
        # Write operations: success=True means valid
        if 'success' in result:
            return result['success'] is True or result['success'] == 'true'
        # Explicit errors are invalid
        if 'error' in result:
            return False
    
    # For read operations, ask LLM to validate
    prompt = f"""Is this result valid for the goal?

Parent goal: {parent_goal}
Current step: {neuron_desc}
Result: {result_summary}

Valid if:
- No error occurred
- Returned data matches what was requested
- Makes progress toward parent goal
- For write operations: "Success: operation completed" means VALID

Answer yes or no:"""
    
    response = ollama.generate(
        prompt,
        system="Validate results. Answer yes or no only.",
        temperature=0.1
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    return 'yes' in response_str.lower()


def validate_goal_completion(goal: str, result: Any, summarize_validation_fn: callable, ollama) -> bool:
    """
    Validate if the entire goal has been fully completed.
    
    Args:
        goal: The goal to validate completion for
        result: The final result
        summarize_validation_fn: Function to summarize for validation (signature: summarize(result, max_length) -> str)
        ollama: OllamaClient for LLM calls
        
    Returns:
        True if goal is complete, False otherwise
    """
    result_summary = summarize_validation_fn(result, 500)
    
    # Check if goal explicitly asks for formatting/display
    format_keywords = ['show', 'display', 'report', 'summary', 'list', 'format', 'readable', 'human-readable']
    needs_formatting = any(keyword in goal.lower() for keyword in format_keywords)
    
    # Check if result is raw data structure
    # Look in top level OR in detailed_results
    def contains_raw_data(obj):
        if isinstance(obj, dict):
            # Check top level
            if any(key in obj for key in ['activities', 'entries']):
                return True
            # Check nested detailed_results
            if 'detailed_results' in obj:
                detailed = obj['detailed_results']
                if isinstance(detailed, list):
                    # Check if there's at least one AI response in the list
                    has_ai_response = any(
                        isinstance(item, dict) and item.get('type') == 'ai_response' 
                        for item in detailed
                    )
                    # If there's an AI response, consider it formatted
                    if has_ai_response:
                        return False
                    return any(contains_raw_data(item) for item in detailed)
                else:
                    return contains_raw_data(detailed)
        return False
    
    is_raw_data = contains_raw_data(result)
    
    # Determine result type for validation
    if is_raw_data:
        result_type = f"⚠️ RAW DATA STRUCTURE (contains API response fields)"
    elif isinstance(result, str):
        result_type = "✅ HUMAN-READABLE TEXT (string)"
    elif isinstance(result, dict) and 'summary' in result:
        # Check if summary is descriptive text or just a confirmation
        summary = result.get('summary', '')
        if isinstance(summary, str) and len(summary) > 100:
            result_type = "✅ FORMATTED SUMMARY (contains descriptive text)"
        else:
            result_type = "⚠️ SUMMARY TOO SHORT (not human-readable report)"
    else:
        result_type = f"❓ UNKNOWN TYPE: {type(result).__name__}"
    
    prompt = f"""Has this goal been FULLY completed?

Goal: {goal}

Result Type: {result_type}

Result summary:
{result_summary}

Requirements for "FULLY completed":
1. All data requested in the goal is present ✓
2. Data is in the format requested
3. No partial results or missing fields
4. If goal asked for "show", "display", "report", or "summary", the output MUST be human-readable text (not raw JSON/dict with API fields like 'activities', 'success', 'count')

CRITICAL FORMAT CHECK:
- Goal requires formatting? {'YES - Must be human-readable text' if needs_formatting else 'NO - Any format OK'}
- Result is raw data? {'YES - This is NOT acceptable for formatted output!' if is_raw_data else 'NO - Format is OK'}

❌ REJECT if goal needs formatting but result is raw data!

Answer (YES or NO only):"""
    
    response = ollama.generate(
        prompt,
        system="You are a strict validator. If goal requires human-readable output (show/display/report) but result type is RAW DATA STRUCTURE, you MUST answer NO.",
        temperature=0.1
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    is_complete = 'yes' in response_str.lower()
    
    if is_complete:
        logger.info(f"   ✅ Goal validation passed: Complete")
    else:
        logger.warning(f"   ⚠️  Goal validation failed: Incomplete")
    
    return is_complete


def check_what_is_missing(goal: str, result: Any, summarize_validation_fn: callable, ollama) -> str:
    """
    Determine what is missing from the goal completion.
    
    Args:
        goal: The goal to check
        result: The current result
        summarize_validation_fn: Function to summarize for validation
        ollama: OllamaClient for LLM calls
        
    Returns:
        Description of what's missing (string)
    """
    result_summary = summarize_validation_fn(result, 500)
    
    prompt = f"""What is missing or wrong with this result?

Goal: {goal}

Current result:
{result_summary}

Identify what's missing or needs to be fixed:
- Missing data fields?
- Wrong format?
- Not human-readable when it should be?
- Partial results?

Be specific and concise (1-2 sentences):"""
    
    response = ollama.generate(
        prompt,
        system="Identify what's missing to complete the goal. Be specific.",
        temperature=0.2
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    return response_str.strip()


def generate_corrective_goal(original_goal: str, missing_info: str, current_result: Any, summarize_validation_fn: callable, ollama) -> str:
    """
    Generate a corrective goal to fix what's missing.
    
    Args:
        original_goal: The original goal that wasn't fully completed
        missing_info: Description of what's missing
        current_result: The current result
        summarize_validation_fn: Function to summarize for validation
        ollama: OllamaClient for LLM calls
        
    Returns:
        Corrective goal (string)
    """
    result_summary = summarize_validation_fn(current_result, 500)
    
    prompt = f"""Create a corrective step to complete this goal.

Original goal: {original_goal}

What's missing: {missing_info}

Current data available:
{result_summary}

CRITICAL RULES:
1. The data is ALREADY FETCHED - don't fetch again
2. Only format/transform what's already there
3. Use phrases like "Format the existing", "Display the current", "Transform the available"
4. Do NOT use "extract", "get", "retrieve", "fetch" - data is already here!

Examples (GOOD):
- "Format the existing activities data into a readable summary with name, type, and kudos count"
- "Display the current results in a human-readable report"
- "Transform the available activity list into a summary report showing name, type, and kudos"

Examples (BAD - will trigger re-fetching):
- "Extract name, type, kudos from each activity" ❌
- "Get activity details for each item" ❌
- "Retrieve kudos count for activities" ❌

Corrective step (use ONLY formatting/display verbs):"""
    
    response = ollama.generate(
        prompt,
        system="Generate a FORMATTING-ONLY corrective step. Data is already available. Do NOT use extraction verbs.",
        temperature=0.2
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    return response_str.strip().split('\n')[0]  # Take first line only
