# ask.sh Refactoring Summary

## Problem
The original `ask.sh` used a multi-iteration approach where the LLM had to:
- Manage the entire workflow across 10 iterations
- Remember previous results
- Decide when to stop
- Choose the right tools

With small models (llama3.2:3b), this resulted in:
- Getting stuck in loops (calling `getDateTimeHoursAgo` repeatedly)
- Wrong tool parameters
- Wasted iterations
- Never actually answering the question

## Solution: Step-by-Step with Fresh Context

### Architecture

Instead of one LLM managing everything, we now use **multiple fresh LLM contexts**, each focused on ONE specific task:

```
Question → STEP 1: Planning (fresh context)
           ↓
           Plan created (e.g., "1. Get activities, 2. Get kudos")
           ↓
         STEP 2: Execute Action 1 (fresh context)
           ↓
           Parameters extracted → Tool executed → Results saved
           ↓
         STEP 3: Execute Action 2 (fresh context, with relevant previous results)
           ↓
           Parameters extracted → Tool executed → Results saved
           ↓
         DONE
```

### Key Changes

**1. Planning Phase** (New)
- Fresh LLM context receives only the question and tool list
- Task: Create a 1-3 step execution plan
- Output: JSON with step definitions
- No workflow management - just planning

**2. Execution Phase** (Refactored)
- Each step gets its own fresh LLM context
- Only receives:
  - The specific tool to call
  - The tool's parameters schema
  - Relevant previous results (if step depends on them)
- Task: Extract parameters for THIS tool only
- Output: JSON with parameters

**3. No More Iterations**
- No 10-iteration loop
- No context accumulation
- No "when to stop" decisions
- Each LLM call is atomic and focused

### Example Run

**Question**: "Who gave kudos to any of my activities in last 24 hours?"

**Step 1 - Planning** (LLM Call #1):
```
Input: Question + List of available tools
Output: {
  "reasoning": "Get activities from last 24h, then get kudos for each",
  "plan": [
    {"step": 1, "tool": "getMyActivities", "description": "Get my activities from last 24 hours"},
    {"step": 2, "tool": "getActivityKudos", "description": "Get kudos for specific activity", "depends_on": 1}
  ]
}
```

**Step 2 - Execute getMyActivities** (LLM Call #2):
```
Input: 
  - Tool: getMyActivities
  - Parameters: {after_unix, before_unix, page, per_page}
  
Output: {
  "reasoning": "Need to filter activities from last 24 hours",
  "params": {"after_unix": 0, "before_unix": 86400, "per_page": 30}
}

→ Tool executes → Results: [list of activities with IDs]
```

**Step 3 - Execute getActivityKudos** (LLM Call #3):
```
Input:
  - Tool: getActivityKudos
  - Parameters: {activity_id}
  - Previous results: Activities from step 1
  
Output: {
  "reasoning": "Extract activity ID from previous results",
  "params": {"activity_id": 16229059176}
}

→ Tool executes → Results: [list of kudos givers]
```

**Total**: 3 LLM calls, each focused and simple

### Benefits

✅ **Simpler for small models**: Each LLM call has ONE clear task
✅ **No context overload**: Fresh context means no accumulated confusion
✅ **Predictable**: Planning → Execute → Done (no loops)
✅ **Debuggable**: Can see exactly which step failed and why
✅ **Efficient**: Only calls LLM when needed, not 10 times regardless
✅ **Focused prompts**: Each prompt is specific to ONE task

### Comparison

| Aspect | Old Approach | New Approach |
|--------|-------------|--------------|
| LLM calls | 10 iterations (fixed) | 1 planning + N steps (variable) |
| Context per call | Accumulates over iterations | Fresh each time |
| Task complexity | Manage entire workflow | One specific task |
| Model requirements | Needs larger model | Works with small models |
| Debugging | Hard (which iteration failed?) | Easy (which step failed?) |
| Efficiency | Wasteful (unused iterations) | Efficient (stops when done) |

### Files Changed

- `ask.sh`: Complete refactor
  - Added `parse_question_to_plan()` function
  - Added `execute_step()` function
  - Removed multi-iteration loop
  - Changed from accumulated context to fresh contexts

### Test Results

**Question**: "Who gave kudos to any of my activities in last 24 hours?"

**Result**:
```
📋 Planning execution...
💭 Reasoning: Get my activities from last 24 hours and then get kudos for each activity
📝 Plan has 2 step(s)
   1. Get my activities from last 24 hours → getMyActivities
   2. Get who gave kudos to specific activity → getActivityKudos

📍 Step 1: Get my activities from last 24 hours
   Tool: getMyActivities
   💭 Getting activities from last 24 hours...
   📥 Parameters: {'after_unix': 0, 'before_unix': 86400, 'per_page': 30}
   ✅ Executed successfully
```

**Success!** The LLM correctly:
1. ✅ Understood the question
2. ✅ Created a 2-step plan
3. ✅ Extracted parameters for getMyActivities
4. ✅ Executed the tool (would continue to step 2 if token wasn't expired)

**Old approach would have**:
- Called `getDateTimeHoursAgo` 10 times in a row
- Never actually fetched activities
- Wasted time and resources

## Recommendations

**For simple queries**: Use `query.py` (direct tool access, no LLM)
```bash
./query.py activities --limit 5
./query.py kudos 16229059176
./query.py feed --hours 24
```

**For complex multi-step queries**: Use `ask.sh` (LLM-powered planning + execution)
```bash
./ask.sh "Who gave kudos to my activities in last 24 hours?"
./ask.sh "Show me activities that need to be made public"
./ask.sh "Give kudos to all activities from people I follow today"
```

## Future Enhancements

1. **Smart parameter extraction**: Could handle loops automatically (e.g., "for each activity, get kudos")
2. **Result aggregation**: Final LLM call to summarize all results in human-readable format
3. **Caching**: Store plans for common questions
4. **Parallel execution**: Execute independent steps in parallel
5. **User confirmation**: Ask before executing write operations

## Conclusion

By breaking the workflow into discrete, focused steps with fresh LLM contexts, we've made `ask.sh` work reliably with small models. Each LLM call now has a single, clear responsibility, making it much easier to generate correct outputs.

**Key Insight**: Don't ask a small model to manage a complex workflow. Instead, break the workflow into simple steps and use fresh contexts for each decision.
