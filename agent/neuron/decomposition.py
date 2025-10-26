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


def micro_decompose(goal: str, depth: int, config: Dict, ollama, tools=None) -> List[Neuron]:
    """
    Micro-prompt: Decompose goal into 1-4 neurons.
    
    Args:
        goal: The goal to decompose
        depth: Current recursion depth
        config: Configuration dictionary (contains force_python_counting setting)
        ollama: Ollama client for LLM calls
        tools: Optional list of available tools (for dynamic tool discovery)
        
    Returns:
        List of Neuron objects (1-4 neurons)
    """
    # STEP 0: Get expert strategy recommendation first
    strategy_advice = get_strategy_advice(goal, config, ollama)
    
    # Build tool catalog if tools provided
    tool_catalog = ""
    if tools:
        tool_catalog = "\n\nAVAILABLE TOOLS:\n"
        # Group tools by category
        time_tools = [t for t in tools if any(x in t.name.lower() for x in ['date', 'time', 'timestamp'])]
        data_tools = [t for t in tools if any(x in t.name.lower() for x in ['activities', 'kudos', 'feed', 'strava'])]
        analysis_tools = [t for t in tools if any(x in t.name.lower() for x in ['execute', 'analysis', 'state'])]
        
        if time_tools:
            tool_catalog += "\n📅 TIME TOOLS:\n"
            for t in time_tools[:5]:  # Limit to avoid token overflow
                tool_catalog += f"  - {t.name}: {t.description[:100]}...\n"
        
        if data_tools:
            tool_catalog += "\n🏃 DATA TOOLS:\n"
            for t in data_tools[:5]:
                tool_catalog += f"  - {t.name}: {t.description[:100]}...\n"
        
        if analysis_tools:
            tool_catalog += "\n🐍 ANALYSIS TOOLS:\n"
            for t in analysis_tools[:3]:
                tool_catalog += f"  - {t.name}: {t.description[:100]}...\n"
    
    prompt = f"""Break this goal into 1-4 simple steps. NO DUPLICATES.

Goal: {goal}

{strategy_advice}
{tool_catalog}

CORE PRINCIPLES:
1. Each step = ONE atomic action (ONE tool call OR one computation)
2. Think about the DATA FLOW: what data does each step need from previous steps?
3. For "for each X do Y" patterns → fetch X first, then iterate (dendrites will spawn automatically)
4. For counting/filtering large lists → use executeDataAnalysis with Python (100% accurate)
   - BE EXPLICIT about filter conditions: e.g., "count activities where sport_type='Run'"
   - Don't just say "count running activities" - specify the exact field and value
5. For date/time → check AVAILABLE TOOLS above, pick the right one for the time period
6. NO DUPLICATES - each step must be unique

SMART DECOMPOSITION:
- Look at available tools and pick the RIGHT one for the task
- If goal mentions "last N hours/days" → look for tools with "hours" or "relative" in the name
- If goal mentions "January 2024" or "September 2025" → look for tools with "range" in the name
- If goal says "for each X get Y" → Step 1: fetch list of X, Step 2: "For each X call [tool] to get Y"
- Don't hardcode - be adaptive based on what tools are available

Output numbered list (1-4 steps, NO duplicates):"""
    
    response = ollama.generate(
        prompt,
        system="You are an intelligent task decomposer. Analyze the goal, look at available tools, and create a smart execution plan. Be adaptive, not prescriptive.",
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
    
    # Detect specific type/category filtering needs
    mentions_type = any(word in goal.lower() for word in ['running', 'rides', 'walks', 'swims', 'type', 'kind of'])
    
    advice_parts = []
    
    # Force Python counting if configured or if task involves counting
    force_python = config.get('ollama', {}).get('force_python_counting', True)
    
    if is_counting or is_filtering:
        if force_python or mentions_large_data:
            advice_parts.append("⚠️ CRITICAL: Use executeDataAnalysis tool with Python code for counting/filtering.")
            advice_parts.append("   Reason: AI models (even 32B+) can miscount. Python is 100% reliable.")
            if mentions_type:
                advice_parts.append("   ⚠️ Be EXPLICIT about filter field: e.g., \"count where sport_type=='Run'\" or \"count where type=='Run'\"")
            advice_parts.append("   Example: executeDataAnalysis(python_code='result = len([x for x in activities if x.get(\"sport_type\", \"\") == \"Run\"])')")
        
        if mentions_large_data:
            advice_parts.append("⚠️ Large dataset detected: Counting 50+ items by AI is unreliable. MUST use Python.")
    
    if has_date_range:
        advice_parts.append("💡 Date range detected: First convert to timestamps, then fetch once, then analyze.")
    
    if not advice_parts:
        return ""
    
    strategy = "\n🎯 EXPERT STRATEGY RECOMMENDATION:\n" + "\n".join(advice_parts) + "\n"
    logger.info(f"   💡 Strategy advice provided for: {goal[:50]}...")
    return strategy
