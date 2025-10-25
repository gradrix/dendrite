# Memory Overseer Architecture Proposal

## Problem Statement
Current system has state tools (`saveState`, `loadState`, `listStateKeys`) but no smart way to:
1. **Decide WHEN to load** memory (risk: inject everything, bloat context)
2. **Decide WHAT to save** after execution (risk: save nothing, or save everything)
3. **Search/filter** saved state for relevance

## Proposed Solution: Two-Phase Overseer

### Phase 1: Pre-Query Memory Injection (PRIORITY)

**When**: Before executing main goal
**What**: Ask LLM which saved state keys are relevant to the current goal
**Why**: Only inject relevant context, keep prompts lean

```python
def _check_memory_relevance(self, goal: str) -> Dict[str, Any]:
    """
    Check if any saved state is relevant to this goal.
    Returns: Dict of {key: value} for relevant state only
    """
    # 1. Get all state keys (fast, no data loading)
    keys = self.tool_registry.call_tool('listStateKeys', {})
    if not keys.get('keys'):
        return {}
    
    # 2. Ask LLM (tiny prompt!)
    prompt = f"""Goal: "{goal}"

Available memory: {', '.join(keys['keys'])}

Which memories are relevant? Output JSON only:
{{"relevant_keys": ["key1", "key2"]}}

If none relevant, output: {{"relevant_keys": []}}"""
    
    response = self.ollama.generate(
        prompt, 
        system="You identify relevant saved state. Output only JSON, no explanation.",
        temperature=0
    )
    
    # 3. Parse and load only relevant state
    try:
        decision = json.loads(response)
        relevant = {}
        for key in decision.get('relevant_keys', []):
            result = self.tool_registry.call_tool('loadState', {'key': key})
            if result.get('success'):
                relevant[key] = result['value']
        return relevant
    except:
        return {}

# Usage in execute():
def execute(self, goal: str):
    # Check memory BEFORE planning
    memory_context = self._check_memory_relevance(goal)
    
    if memory_context:
        # Inject into system prompt or first neuron context
        goal_with_memory = f"""{goal}

[Relevant Memory]
{json.dumps(memory_context, indent=2)}"""
    else:
        goal_with_memory = goal
    
    # Continue with normal execution
    return self._execute_neurons(goal_with_memory)
```

**Estimated overhead**: 
- 1 extra LLM call per goal (~500ms)
- Only if state keys exist
- Prompt size: ~200 tokens (just key names)

---

### Phase 2: Post-Execution Save Decision (FUTURE)

**When**: After tool execution or neuron completion
**What**: Ask LLM if result should be saved to memory
**Why**: Automate memory management

```python
def _evaluate_for_storage(self, tool_name: str, result: Dict, goal: str) -> None:
    """
    Decide if this result should be saved to memory.
    Only for specific tool types (e.g., getActivityKudos, getUserProfile)
    """
    # Skip for read-only or utility tools
    if tool_name in ['getCurrentDate', 'calculateTimestamp', 'llm_analyze']:
        return
    
    # Truncate large results for evaluation
    result_preview = json.dumps(result)[:500]
    
    prompt = f"""Tool: {tool_name}
Result preview: {result_preview}...
Goal: {goal}

Should this be saved to memory for future use?

Output JSON only:
{{"save": true/false, "key": "descriptive_key", "reason": "brief explanation"}}

Only save if it's useful across multiple sessions (e.g., preferences, people lists, patterns).
Don't save single-query data."""
    
    response = self.ollama.generate(prompt, temperature=0)
    decision = json.loads(response)
    
    if decision.get('save'):
        self.tool_registry.call_tool('saveState', {
            'key': decision['key'],
            'value': result
        })
        logger.info(f"💾 Auto-saved to memory: {decision['key']} - {decision['reason']}")
```

---

## Additional Features for State Tools

### 1. `searchState` Tool (NEW)
```python
@tool(
    description="Search state keys by pattern",
    parameters=[
        {"name": "pattern", "type": "string", "description": "Search pattern (e.g., 'kudos*', '*_givers')", "required": True}
    ],
    returns="Matching keys and their values",
    permissions="read"
)
def searchState(pattern: str) -> Dict[str, Any]:
    """Search for state keys matching a pattern."""
    state_manager = StateManager()
    all_keys = state_manager.list_keys()
    
    # Simple glob-style matching
    import fnmatch
    matching = [k for k in all_keys if fnmatch.fnmatch(k, pattern)]
    
    results = {}
    for key in matching:
        results[key] = state_manager.get_state(key)
    
    return {
        "success": True,
        "pattern": pattern,
        "matches": matching,
        "results": results
    }
```

### 2. Enhanced `listStateKeys` (shows metadata)
```python
@tool(
    description="List all state keys with metadata",
    parameters=[
        {"name": "include_values", "type": "boolean", "description": "Include preview of values", "required": False}
    ],
    returns="List of keys with timestamps and optional previews",
    permissions="read"
)
def listStateKeys(include_values: bool = False) -> Dict[str, Any]:
    """List all state keys with metadata."""
    state_manager = StateManager()
    keys_meta = state_manager.list_keys_with_metadata()  # Returns [(key, timestamp, size)]
    
    result = {
        "success": True,
        "count": len(keys_meta),
        "keys": []
    }
    
    for key, timestamp, size in keys_meta:
        entry = {
            "key": key,
            "updated_at": timestamp,
            "size_bytes": size
        }
        
        if include_values:
            value = state_manager.get_state(key)
            preview = json.dumps(value)[:100]
            entry["preview"] = preview + "..." if len(json.dumps(value)) > 100 else preview
        
        result["keys"].append(entry)
    
    return result
```

---

## Implementation Priority

1. ✅ **Phase 1: Pre-Query Memory Check** (HIGHEST)
   - Solves context bloat
   - Simple to implement
   - Immediate value

2. ⏳ **Phase 2: Post-Execution Save Decision** (MEDIUM)
   - Nice to have
   - Can be manual for now

3. ⏳ **Enhanced State Tools** (LOW)
   - `searchState` useful but not critical
   - Enhanced `listStateKeys` helpful for debugging

---

## Example Workflow

### Before (Current)
```yaml
goal: "Who from my kudos list was active recently?"
# Agent has no memory of kudos list
# → Fails or tries to fetch everything
```

### After (With Overseer)
```yaml
goal: "Who from my kudos list was active recently?"

# 1. Pre-query check
Overseer: "Does goal mention 'kudos'?"
Overseer: listStateKeys() → ["kudos_givers_2025", "favorite_routes"]
Overseer: LLM decides → "kudos_givers_2025" is relevant
Overseer: loadState("kudos_givers_2025") → ["athlete_123", "athlete_456", ...]

# 2. Execute with memory context
Agent receives:
  Goal: "Who from my kudos list was active recently?"
  Memory: {"kudos_givers_2025": ["athlete_123", "athlete_456", ...]}

# 3. Agent uses memory efficiently
Agent: "I have kudos list in memory. Fetch recent activities and filter."
```

---

## Questions to Answer

1. **Frequency**: Run memory check for every goal, or only if goal contains keywords like "remember", "saved", "list"?
   - **Recommendation**: Every goal (fast enough, ~500ms)

2. **Context injection**: Add to system prompt, or as first neuron context?
   - **Recommendation**: First neuron context (more explicit)

3. **Auto-save triggers**: Which tools should trigger save evaluation?
   - **Recommendation**: Start manual, add auto-save later

4. **Memory expiry**: Should old state be auto-deleted?
   - **Recommendation**: Manual cleanup for now (use `scripts/state.sh clear`)

---

## Next Steps

1. Implement `_check_memory_relevance()` in `agent/neuron_agent.py`
2. Add memory injection to `execute()` method
3. Test with kudos example:
   ```yaml
   # First: Save kudos list
   goal: "Get last week activities and save kudos givers to memory"
   
   # Later: Use saved list
   goal: "Who from my kudos list was active recently?"
   ```
4. Measure performance impact (expect <1s overhead)
5. Add Phase 2 (auto-save) if manual memory management becomes tedious
