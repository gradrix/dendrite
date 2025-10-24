# Radical Simplification: Micro-Prompting Architecture

## The Problem with Current Approach

Even the "simplified" format is **still too complex**:
```yaml
- id: update_visibility
  do: Make activities public if they meet visibility criteria
  when: activities
  rules:
    - Type is NOT "Walk"
    - If type is "Ride", distance must be >= 10km
  for_each: activities
  optional: true
```

This assumes the LLM can:
- Understand complex rules
- Handle loops
- Manage dependencies
- Work with all tools at once

**For a 3B model, this is too much!**

---

## New Philosophy: Neuron-Like Micro-Prompting

### Core Idea
**Many tiny LLM calls >> Few large LLM calls**

Like neurons in a brain:
- Each call is small and focused
- Gradually build up understanding
- Tool discovery on-demand
- Let complexity emerge naturally

### Architecture

```
User goal: "List 3 last activities from 24h"
    ↓
[Micro-Prompt 1] What do I need to do?
    → "Need to get activities from Strava"
    ↓
[Micro-Prompt 2] What tools help with getting activities?
    → Search tool registry: "get", "activities", "strava"
    → Found: getMyActivities, getCurrentDateTime, getDateTimeHoursAgo
    ↓
[Micro-Prompt 3] Which tool is most relevant?
    → Context: goal + tool descriptions (only 3 tools!)
    → Answer: "getMyActivities"
    ↓
[Micro-Prompt 4] What parameters does getMyActivities need?
    → Show signature: getMyActivities(after_unix?, before_unix?, per_page?)
    → Answer: {per_page: 3}
    ↓
[Micro-Prompt 5] Do I need time filtering?
    → Goal mentions "24h"
    → Answer: "Yes, need after_unix = now - 24h"
    ↓
[Micro-Prompt 6] What tools help with time?
    → Search: "time", "hours", "ago"
    → Found: getCurrentDateTime, getDateTimeHoursAgo
    ↓
[Micro-Prompt 7] Execute getCurrentDateTime
    → Result: {unix: 1234567890}
    ↓
[Micro-Prompt 8] Execute getDateTimeHoursAgo(hours=24)
    → Result: {unix: 1234481490}
    ↓
[Micro-Prompt 9] Now execute getMyActivities(after_unix=1234481490, per_page=3)
    → Result: [activity1, activity2, activity3]
    ↓
[Micro-Prompt 10] Format result for user
    → "Here are your last 3 activities from the last 24 hours: ..."
```

**Total**: 10 tiny prompts instead of 1-2 huge prompts!

---

## Ultra-Minimal Instruction Format

### Before (Even "Simplified" Was Complex)
```yaml
name: "Strava Activity Monitor"
settings:
  time_range: 24h
  state_tracking: true
tasks:
  - id: fetch
    do: Get my activities from last 24 hours
    save_as: activities
  - id: update
    do: Make activities public if criteria met
    when: activities
    rules: [...]
    for_each: activities
```

### After (Radical Simplification)
```yaml
goal: "Check for new activities in the last 24 hours, make qualifying activities public with 3D maps, and track kudos"
schedule: hourly
```

**That's it!** 2 lines!

---

## Implementation: Enhanced AgentV3

### Current AgentV3 Problem
- Creates full plan upfront
- Passes all tools to LLM at once
- Large context per decision

### New Micro-Prompting AgentV3

```python
class MicroPromptAgent:
    """
    Agent that uses many tiny LLM calls instead of few large ones.
    Perfect for small models (3B params).
    """
    
    def execute_goal(self, goal: str):
        """Execute goal through micro-prompting."""
        
        # Step 1: Break goal into micro-tasks (tiny prompt)
        tasks = self._decompose_goal(goal)  # "Get activities", "Update visibility", etc.
        
        for task in tasks:
            # Step 2: Find relevant tools (tiny prompt)
            tool_keywords = self._extract_keywords(task)
            relevant_tools = self._search_tools(tool_keywords)  # Only 3-5 tools
            
            # Step 3: Select best tool (tiny prompt with only relevant tools)
            tool_name = self._select_tool(task, relevant_tools)
            
            # Step 4: Determine parameters (tiny prompt)
            params = self._determine_params(task, tool_name)
            
            # Step 5: Check if need helper tools (tiny prompt)
            if self._needs_helpers(params):
                helper_tools = self._get_helper_tools(params)
                for helper in helper_tools:
                    helper_result = self._execute_tool(helper)
                    params = self._merge_helper_result(params, helper_result)
            
            # Step 6: Execute main tool (tiny prompt for retry logic)
            result = self._execute_with_retry(tool_name, params)
            
            # Step 7: Save result (automatic)
            self.context[task] = result
    
    def _decompose_goal(self, goal: str) -> List[str]:
        """Micro-prompt: Break goal into 3-5 micro-tasks."""
        prompt = f"""Break this goal into 3-5 simple tasks.
Goal: {goal}

Output only task list, one per line:
- Task 1
- Task 2
..."""
        
        response = self.ollama.generate(prompt, max_tokens=100)
        return self._parse_task_list(response)
    
    def _extract_keywords(self, task: str) -> List[str]:
        """Micro-prompt: Extract search keywords."""
        prompt = f"""What are 3 keywords to search for tools?
Task: {task}

Output only keywords, comma-separated:"""
        
        response = self.ollama.generate(prompt, max_tokens=20)
        return response.strip().split(',')
    
    def _search_tools(self, keywords: List[str]) -> List[Tool]:
        """Search tool registry by keywords."""
        # Fuzzy search in tool names and descriptions
        # Return only top 3-5 matches
        return self.registry.search(keywords, limit=5)
    
    def _select_tool(self, task: str, tools: List[Tool]) -> str:
        """Micro-prompt: Select best tool from small list."""
        tool_info = "\n".join([f"- {t.name}: {t.description}" for t in tools])
        
        prompt = f"""Which tool is best for this task?
Task: {task}

Available tools (pick one):
{tool_info}

Answer with just the tool name:"""
        
        response = self.ollama.generate(prompt, max_tokens=30)
        return response.strip()
    
    def _determine_params(self, task: str, tool_name: str) -> Dict:
        """Micro-prompt: Determine parameters."""
        tool = self.registry.get(tool_name)
        param_info = self._format_params(tool.parameters)
        
        prompt = f"""What parameters for this tool?
Task: {task}
Tool: {tool_name}

Parameters:
{param_info}

Output JSON:"""
        
        response = self.ollama.generate(prompt, max_tokens=100)
        return self._parse_json(response)
    
    def _needs_helpers(self, params: Dict) -> bool:
        """Micro-prompt: Check if need helper tools."""
        prompt = f"""Do these parameters need helper tools?
Parameters: {params}

Common needs:
- Time calculation (after_unix, before_unix)
- ID lookup
- Data transformation

Answer yes/no:"""
        
        response = self.ollama.generate(prompt, max_tokens=10)
        return "yes" in response.lower()
    
    def _execute_with_retry(self, tool_name: str, params: Dict, max_retries=3):
        """Execute with micro-prompt retry logic."""
        for attempt in range(max_retries):
            try:
                return self.registry.execute(tool_name, **params)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                # Micro-prompt: How to fix error?
                params = self._fix_error(tool_name, params, str(e))
    
    def _fix_error(self, tool_name: str, params: Dict, error: str) -> Dict:
        """Micro-prompt: Fix error."""
        prompt = f"""How to fix this error?
Tool: {tool_name}
Parameters: {params}
Error: {error}

Output corrected parameters as JSON:"""
        
        response = self.ollama.generate(prompt, max_tokens=100)
        return self._parse_json(response)
```

---

## Comparison

### Old Agent (Even V3)
```python
# One big prompt with all tools
prompt = f"""
Goal: {goal}
Available tools (50+ tools):
- tool1: description
- tool2: description
... (huge context)

Create a plan and execute:
"""

response = ollama.generate(prompt)  # 5000 tokens!
```

**Problems**:
- Huge context (5000+ tokens)
- 3B model overwhelmed
- One-shot, no gradual building

### New Micro-Prompt Agent
```python
# Many tiny prompts with focused context

# Prompt 1 (100 tokens)
tasks = decompose_goal(goal)

# Prompt 2 (50 tokens)
keywords = extract_keywords(task)

# Prompt 3 (200 tokens, only 5 tools)
tool = select_tool(task, relevant_tools)

# Prompt 4 (150 tokens)
params = determine_params(task, tool)

# ... more tiny prompts
```

**Benefits**:
- Tiny contexts (50-200 tokens each)
- 3B model can handle easily
- Gradual building like neurons
- More resilient

---

## Token Usage Comparison

### Current V3 (One Big Prompt)
```
Prompt 1: "Create plan for goal X with 50 tools"
  → 5000 tokens input
  → 500 tokens output
  → Total: 5500 tokens

Prompt 2: "Execute step 1 with context"
  → 2000 tokens input
  → 300 tokens output
  → Total: 2300 tokens

Grand Total: ~8000 tokens per goal
```

### New Micro-Prompting
```
Prompt 1: Decompose goal
  → 100 tokens input, 50 tokens output
Prompt 2: Extract keywords
  → 50 tokens input, 20 tokens output
Prompt 3: Select tool (5 tools only!)
  → 200 tokens input, 30 tokens output
Prompt 4: Determine params
  → 150 tokens input, 50 tokens output
Prompt 5-10: Various micro-prompts
  → 100-200 tokens each

Grand Total: ~1500 tokens per goal (80% reduction!)
```

---

## New Instruction Format

### Format
```yaml
goal: "Natural language description of what to do"
schedule: once|hourly|daily|weekly  # Optional
```

**That's it!** No tasks, no rules, no complexity!

### Examples

#### Example 1: Simple Query
```yaml
goal: "List my last 3 activities"
```

#### Example 2: Monitoring
```yaml
goal: "Check for new activities in the last 24 hours, make qualifying activities public with 3D maps, and track kudos"
schedule: hourly
```

#### Example 3: Reporting
```yaml
goal: "Generate a weekly summary of all my activities with total distance and time"
schedule: weekly
```

---

## Implementation Plan

### Phase 1: Remove Complexity (1 day)

**Delete these files** (no longer needed):
- ❌ `agent/instruction_parser_v2.py`
- ❌ `agent/step_executor.py`
- ❌ `agent/template_engine.py`
- ❌ `agent/instruction_loader.py` (complex version)
- ❌ All V2-related code

**Simplify main.py**:
- Remove `execute_instruction()` (V1)
- Remove `execute_instruction_v2()` (V2)
- Keep only `execute_goal()` (V3 enhanced)

### Phase 2: Enhance Agent V3 (2 days)

**Modify `agent/agent_v3.py`**:
- Add micro-prompting methods
- Tool search by keywords
- On-demand tool discovery
- Tiny context per call

**Add `agent/tool_search.py`**:
- Fuzzy search tools by keywords
- Return only top 5 matches
- Score by relevance

### Phase 3: Test & Deploy (1 day)

**Test with 3B model**:
- qwen3:3b or llama3.2:3b
- Verify micro-prompting works
- Measure token usage
- Compare with old approach

---

## Benefits

| Aspect | Old Approach | Micro-Prompting | Improvement |
|--------|--------------|----------------|-------------|
| **YAML Lines** | 130 (V2) / 40 (simplified) | 2 | 98% ↓ |
| **LLM Context** | 5000 tokens | 100-200 tokens | 96% ↓ |
| **Total Tokens** | ~8000 | ~1500 | 81% ↓ |
| **3B Model Friendly** | No | Yes | ∞ |
| **Tools Per Prompt** | 50+ | 3-5 | 90% ↓ |
| **Complexity** | High | Ultra-low | Massive ↓ |

---

## Risks & Mitigation

### Risk 1: Too Many LLM Calls = Slow
**Reality**: Small prompts are FAST
- 100 tokens @ 50 tok/sec = 2 seconds
- 10 calls = 20 seconds total
- Old way: 5000 tokens @ 30 tok/sec = 167 seconds!
- **Micro-prompting is FASTER!**

### Risk 2: LLM Makes Mistakes
**Mitigation**: Each step is verified
- Tool search: Exact match on keywords
- Tool selection: Only 3-5 options
- Params: Auto-validated
- Execution: Retry with fix

### Risk 3: Lose Capability
**Reality**: Gain capability!
- Can handle more complex goals
- Self-healing built-in
- Works with tiny models
- More reliable

---

## Migration

### Instructions
```bash
# Before: Complex YAML files
instructions/
├── strava_monitor_v2.yaml  (130 lines)
└── other_instruction.yaml  (80 lines)

# After: Simple goals
instructions/
├── strava_monitor.yaml  (2 lines: goal + schedule)
└── other_instruction.yaml (2 lines: goal + schedule)
```

### Code
```bash
# Delete
rm agent/instruction_parser_v2.py
rm agent/step_executor.py
rm agent/template_engine.py
rm agent/instruction_loader.py

# Enhance
vim agent/agent_v3.py  # Add micro-prompting
vim agent/tool_registry.py  # Add keyword search

# Simplify
vim main.py  # Remove V1/V2, keep only V3
```

---

## Next Steps

1. ✅ **Approve radical simplification**
2. [ ] **Delete V1/V2 code** (clean slate)
3. [ ] **Implement micro-prompting in agent_v3.py**
4. [ ] **Add tool keyword search**
5. [ ] **Test with qwen3:3b**
6. [ ] **Convert all instructions to 2-line format**

---

## Conclusion

The radical simplification:
- **98% less YAML** (130 lines → 2 lines)
- **96% less LLM context** (5000 → 100-200 tokens)
- **Perfect for 3B models** (neuron-like micro-prompting)
- **Faster execution** (many small calls < few big calls)
- **More reliable** (gradual building, self-correction)

**This is the way!** 🚀

Let's delete the complexity and embrace simplicity!
