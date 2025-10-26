"""
Decomposition module for neuron-based goal processing.

Handles breaking down high-level goals into smaller executable neurons.
"""

import re
import logging
from typing import List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Neuron:
    """Represents a single computation unit in the neural execution graph."""
    description: str
    index: int
    depth: int
    result: Any = None
    error: str = None


def micro_decompose(goal: str, depth: int, config: Dict, ollama) -> List[Neuron]:
    """
    Micro-prompt: Decompose goal into 1-4 neurons.
    
    Args:
        goal: The goal to decompose
        depth: Current recursion depth
        config: Configuration dictionary (contains force_python_counting setting)
        ollama: Ollama client for LLM calls
        
    Returns:
        List of Neuron objects (1-4 neurons)
    """
    # STEP 0: Get expert strategy recommendation first
    strategy_advice = get_strategy_advice(goal, config, ollama)
    
    prompt = f"""Break this goal into 1-4 simple steps. NO DUPLICATES.

Goal: {goal}

{strategy_advice}

Rules:
- Each step = ONE action (ONE tool call OR one AI response)
- If goal asks "how many X activities", that's typically: (1) convert dates, (2) fetch ALL activities, (3) use executeDataAnalysis with Python to count type=X
- When fetching data, get ALL data first, then filter/analyze in a separate step
- Format/display/report steps go at the end
- NO DUPLICATE STEPS - each step must be different
- IMPORTANT: If goal mentions a date period (like "January 2024", "September 2025", "last week"):
  * First step: Use getDateRangeTimestamps for the month/period (returns BOTH start AND end timestamps in one call)
  * Second step: Fetch data using those timestamps
  * Third step: Use executeDataAnalysis to count/filter (NO new fetch, work with existing data)
  * Fourth step: Format results
- If goal asks for a specific activity TYPE (e.g., "running activities", "rides"):
  * The filtering step should say "Use executeDataAnalysis to count activities where type=Run"
  * Do NOT rely on AI counting - use Python for accurate counting

Examples:
- "How many runs in Jan 2024?" → (1) Use getDateRangeTimestamps for January 2024, (2) Fetch all activities, (3) Use executeDataAnalysis to count where sport_type contains 'Run'
- "Show my 3 rides from last month" → (1) Use getDateRangeTimestamps for last month, (2) Fetch all activities, (3) Use executeDataAnalysis to filter type=Ride and take first 3, (4) Format

Output numbered list (1-4 steps, NO duplicates):"""
    
    response = ollama.generate(
        prompt,
        system="Decompose goals into minimal steps. NO duplicates. Prefer executeDataAnalysis for counting/filtering. Output numbered list only.",
        temperature=0.2  # Lower temperature for more deterministic output
    )
    
    response_str = str(response) if not isinstance(response, str) else response
    
    # Parse neurons
    neurons = []
    seen_descriptions = set()  # Track to prevent duplicates
    
    for line in response_str.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        match = re.match(r'^[\d\-\*\.)\]]+\s*(.+)$', line)
        if match:
            description = match.group(1).strip()
            
            # Check for duplicates (normalize text for comparison)
            normalized = description.lower().strip('.')
            if normalized in seen_descriptions:
                logger.warning(f"   │  ⚠️  Skipping duplicate neuron: {description}")
                continue
            
            seen_descriptions.add(normalized)
            neurons.append(Neuron(
                description=description,
                index=len(neurons) + 1,
                depth=depth
            ))
    
    # Limit to 4 neurons maximum
    if len(neurons) > 4:
        logger.warning(f"   │  ⚠️  Too many neurons ({len(neurons)}), keeping first 4")
        neurons = neurons[:4]
    
    return neurons


def get_strategy_advice(goal: str, config: Dict, ollama) -> str:
    """
    Get expert strategy advice for approaching the goal.
    This guides the AI towards better tool selection (especially Python for counting).
    
    Args:
        goal: The goal to analyze
        config: Configuration dictionary
        ollama: Ollama client (not used currently but kept for consistency)
        
    Returns:
        Strategy advice string (may be empty)
    """
    # Detect task characteristics
    is_counting = any(word in goal.lower() for word in ['how many', 'count', 'number of'])
    is_filtering = any(word in goal.lower() for word in ['filter', 'where', 'type=', 'matching'])
    mentions_large_data = any(word in goal.lower() for word in ['all', 'every', 'total'])
    has_date_range = any(word in goal.lower() for word in ['month', 'week', 'year', 'september', 'january', 'last'])
    
    advice_parts = []
    
    # Force Python counting if configured or if task involves counting
    force_python = config.get('ollama', {}).get('force_python_counting', True)
    
    if is_counting or is_filtering:
        if force_python or mentions_large_data:
            advice_parts.append("⚠️ CRITICAL: Use executeDataAnalysis tool with Python code for counting/filtering.")
            advice_parts.append("   Reason: AI models (even 32B+) can miscount. Python is 100% reliable.")
            advice_parts.append("   Example: executeDataAnalysis(python_code='result = {\"count\": len([x for x in data[\"neuron_0_2\"][\"activities\"] if \"Run\" in x.get(\"sport_type\", \"\")])}')")
        
        if mentions_large_data:
            advice_parts.append("⚠️ Large dataset detected: Counting 50+ items by AI is unreliable. MUST use Python.")
    
    if has_date_range:
        advice_parts.append("💡 Date range detected: First convert to timestamps, then fetch once, then analyze.")
    
    if not advice_parts:
        return ""
    
    strategy = "\n🎯 EXPERT STRATEGY RECOMMENDATION:\n" + "\n".join(advice_parts) + "\n"
    logger.info(f"   💡 Strategy advice provided for: {goal[:50]}...")
    return strategy
