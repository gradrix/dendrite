# Error Handling & Recovery Strategy

## Current State Analysis

### What Happens When a Tool Fails?

Currently, when a tool fails:

1. **Tool Execution Fails** in Sandbox
   - Exception caught in `sandbox.py`
   - Returns: `{"success": False, "result": None, "error": str(e)}`

2. **Execution Logged** to Database
   - `execution_store.store_tool_execution()` records the failure
   - Error message and parameters saved for analysis

3. **Failure Returned** to User
   - No automatic retry
   - No fallback tool selection
   - No "best effort" alternative approach
   - **Thinking stops completely**

### Critical Gaps

1. **No Retry Logic**: One failure = complete stop
2. **No Fallback Tools**: Doesn't try alternative tools
3. **No Adaptive Reasoning**: Can't conclude "impossible" vs "try another way"
4. **No Context Preservation**: Loses reasoning chain on failure
5. **No Tool Comparison**: Can't distinguish between similar tools (getX vs getXx)

## Problem Scenarios

### Scenario 1: Tool Fails Slightly

**Example**: Strava tool times out on first try, but would work on retry.

**Current Behavior**:
```
1. User: "Get my last 6 months of Strava activities and calculate total distance"
2. Tool selected: strava_get_my_activities_tool
3. Tool execution: TIMEOUT after 25 seconds
4. Result: {"success": False, "error": "Request timeout"}
5. Response: "Failed to execute tool. Error: Request timeout"
6. ❌ THINKING STOPS
```

**Desired Behavior**:
```
1-3. Same as above
4. Result: {"success": False, "error": "Request timeout"}
5. AgenticCore decides: "Retry with smaller date range"
6. Break into 6 separate monthly requests
7. Aggregate results
8. ✅ Success with best effort
```

### Scenario 2: Tool Fundamentally Can't Do Task

**Example**: User asks to retrieve private data the tool doesn't have access to.

**Current Behavior**:
```
1. User: "Get competitor X's private training data from Strava"
2. Tool selected: strava_get_activity_tool
3. Tool execution: 403 Forbidden
4. Result: {"success": False, "error": "Access denied"}
5. Response: "Failed to execute tool"
6. ❌ THINKING STOPS - no explanation why it's impossible
```

**Desired Behavior**:
```
1-3. Same as above
4. Result: {"success": False, "error": "Access denied"}
5. AgenticCore analyzes: "This is a permissions issue, not retryable"
6. Reasoning: "Strava API doesn't allow accessing other athletes' private data"
7. Response: "I cannot retrieve competitor X's private training data because:
   - Strava API requires authentication
   - Athletes' private data is only accessible to themselves
   - This is an API limitation, not a tool failure
   Possible alternatives:
   - Retrieve your own training data for comparison
   - Look for publicly shared activities"
8. ✅ Intelligent explanation with alternatives
```

### Scenario 3: Wrong Tool Selected

**Example**: Similar tool names cause confusion (getActivities vs getActivity).

**Current Behavior**:
```
1. User: "Get details about my activity ID 12345"
2. Tool selected: strava_get_my_activities_tool (WRONG - gets all activities)
3. Tool execution: Returns list of 100 activities
4. Code tries to find activity 12345 in list
5. Result: {"success": False, "error": "Activity not found"}
6. ❌ THINKING STOPS
```

**Desired Behavior**:
```
1-3. Same as above
4. Result: {"success": False, "error": "Activity not found"}
5. AgenticCore reasons: "I got a list but need a single activity"
6. Realizes: "Wrong tool - should use strava_get_activity_tool instead"
7. Retry with correct tool: strava_get_activity_tool(activity_id=12345)
8. ✅ Success with tool correction
```

### Scenario 4: Tool Improved But Breaks Existing Workflow

**Example**: Autonomous improvement changes tool signature, breaking dependent code.

**Current Behavior**:
```
1. AutonomousLoop improves strava_get_my_activities_tool
2. Changes parameter from 'limit' to 'max_results'
3. Testing passes (synthetic tests use new signature)
4. Deployed successfully
5. User asks: "Get my last 10 activities"
6. Orchestrator generates code with old parameter: limit=10
7. Tool execution: TypeError("unexpected keyword argument 'limit'")
8. Result: {"success": False}
9. ❌ BREAKS USER WORKFLOW
```

**When Does Rollback Happen?**
- **Post-deployment monitoring** detects success rate drop from 90% → 60%
- **After 10+ failures** (need minimum executions)
- **Could take hours** to accumulate enough data
- **Meanwhile**: Users experience failures

**Desired Behavior**:
```
6. Tool execution: TypeError
7. AgenticCore detects: "Parameter mismatch - tool signature changed"
8. Checks tool version history
9. Realizes: "This tool was recently updated"
10. Tries with new signature: max_results=10
11. ✅ Success with signature adaptation
12. OR: Fast rollback triggered after 2-3 failures (not 10+)
```

## Proposed Solution: Resilient Reasoning Layer

### Component: ErrorRecoveryNeuron

A new neuron that wraps tool execution with intelligent recovery:

```python
class ErrorRecoveryNeuron:
    """
    Wraps tool execution with intelligent error recovery.
    
    Strategies:
    1. Retry with exponential backoff (transient failures)
    2. Fallback to alternative tools (wrong tool selected)
    3. Adapt parameters (signature changes)
    4. Break into smaller chunks (timeout/rate limit)
    5. Explain impossibility (fundamental limitations)
    """
    
    def execute_with_recovery(self, tool_name, params, goal_context):
        """
        Execute tool with automatic recovery on failure.
        
        Returns:
        - success: bool
        - result: Any
        - recovery_applied: str (none, retry, fallback, adapt, chunk, impossible)
        - reasoning: str (explanation of what happened)
        """
        
        # First attempt
        result = self._execute_tool(tool_name, params)
        
        if result['success']:
            return result
        
        # Analyze failure
        error_type = self._classify_error(result['error'])
        
        if error_type == 'transient':
            # Retry with backoff
            return self._retry_with_backoff(tool_name, params)
        
        elif error_type == 'wrong_tool':
            # Find alternative tool
            alternative = self._find_alternative_tool(goal_context)
            if alternative:
                return self._execute_tool(alternative, params)
        
        elif error_type == 'parameter_mismatch':
            # Adapt to new signature
            adapted_params = self._adapt_parameters(tool_name, params)
            return self._execute_tool(tool_name, adapted_params)
        
        elif error_type == 'rate_limit' or error_type == 'timeout':
            # Break into chunks
            return self._chunk_and_aggregate(tool_name, params, goal_context)
        
        elif error_type == 'impossible':
            # Explain why it's impossible
            return {
                'success': False,
                'recovery_applied': 'impossible',
                'reasoning': self._explain_impossibility(result['error']),
                'alternatives': self._suggest_alternatives(goal_context)
            }
```

### Error Classification

```python
def _classify_error(self, error: str) -> str:
    """Classify error type for recovery strategy."""
    
    # Pattern matching on error messages
    if any(x in error.lower() for x in ['timeout', 'connection', 'network']):
        return 'transient'
    
    if 'typeerror' in error.lower() and 'argument' in error.lower():
        return 'parameter_mismatch'
    
    if any(x in error.lower() for x in ['rate limit', '429', 'too many requests']):
        return 'rate_limit'
    
    if any(x in error.lower() for x in ['403', 'forbidden', 'unauthorized', 'permission']):
        return 'impossible'
    
    if 'not found' in error.lower() or 'no such' in error.lower():
        return 'wrong_tool'
    
    return 'unknown'
```

### Integration Points

#### 1. Orchestrator Enhancement

```python
def _execute_tool_use_pipeline(self, goal_id, data, depth):
    # 1. Select the tool
    tool_selection_data = tool_selector.process(goal_id, data['goal'], depth)
    
    # 2. Generate the code
    code_generation_data = code_generator.process(goal_id, tool_selection_data, depth)
    
    # 3. Execute with recovery (NEW)
    code = code_generation_data.get("generated_code") or code_generation_data.get("code")
    
    recovery_neuron = self.neuron_registry.get("error_recovery")
    if recovery_neuron:
        # Execute with automatic recovery
        execution_result = recovery_neuron.execute_with_recovery(
            code=code,
            goal_id=goal_id,
            depth=depth,
            tool_name=tool_selection_data.get('selected_tools'),
            goal_context=data
        )
    else:
        # Fallback to current behavior
        sandbox = self.neuron_registry["sandbox"]
        execution_result = sandbox.execute(code, goal_id=goal_id, depth=depth)
    
    return execution_result
```

#### 2. Fast Rollback Trigger

Current rollback waits for 10+ failures over time. Add immediate rollback on critical patterns:

```python
class DeploymentMonitor:
    def check_immediate_rollback_needed(self, tool_name: str) -> bool:
        """
        Check if immediate rollback needed (don't wait for statistics).
        
        Triggers:
        - 3+ consecutive failures within 5 minutes (deployment issue)
        - 100% failure rate with 5+ attempts (broken deployment)
        - TypeError or AttributeError (signature change)
        """
        
        recent_failures = self._get_last_n_executions(tool_name, n=5, minutes=5)
        
        # All recent attempts failed
        if len(recent_failures) >= 3 and all(not ex['success'] for ex in recent_failures):
            # Check error types
            errors = [ex['error'] for ex in recent_failures]
            
            # Signature change detected
            if any('TypeError' in e or 'AttributeError' in e for e in errors):
                return True, 'signature_change'
            
            # Complete breakage
            if all(not ex['success'] for ex in recent_failures):
                return True, 'complete_failure'
        
        return False, None
```

#### 3. Context-Aware Reasoning

Enhance AgenticCoreNeuron to maintain reasoning context across failures:

```python
class AgenticCoreNeuron:
    def process(self, goal_id, goal, depth):
        # Track attempts for this goal
        self.attempt_history[goal_id] = self.attempt_history.get(goal_id, [])
        
        # Generate thinking with failure context
        prompt = self._build_prompt_with_context(goal, self.attempt_history[goal_id])
        
        thinking = self.generative_neuron.generate(prompt)
        
        # Record this attempt
        self.attempt_history[goal_id].append({
            'thinking': thinking,
            'timestamp': datetime.now(),
            'depth': depth
        })
        
        return thinking
    
    def _build_prompt_with_context(self, goal, history):
        """Include previous attempts in prompt."""
        base_prompt = f"Goal: {goal}\n\n"
        
        if history:
            base_prompt += "Previous attempts:\n"
            for i, attempt in enumerate(history[-3:], 1):  # Last 3 attempts
                base_prompt += f"{i}. {attempt['thinking'].get('reasoning', 'No reasoning')}\n"
                if attempt.get('error'):
                    base_prompt += f"   Error: {attempt['error']}\n"
            base_prompt += "\nBased on previous attempts, what should we try differently?\n\n"
        
        return base_prompt
```

## Rollback Decision Matrix

| Scenario | Detection | Rollback Timing | Recovery Strategy |
|----------|-----------|----------------|-------------------|
| **Tool timeout** | Single failure | No rollback | Retry with backoff |
| **Wrong tool selected** | Single failure | No rollback | Try alternative tool |
| **Signature change** | 2-3 failures, TypeError | **Immediate** (<5 min) | Rollback + signature adaptation |
| **Complete breakage** | 5 consecutive failures | **Fast** (<10 min) | Immediate rollback |
| **Gradual regression** | 15%+ success rate drop over 10+ execs | **Standard** (hours) | Statistical rollback |
| **Rate limiting** | 429 errors | No rollback | Chunk + exponential backoff |
| **Permission denied** | 403 error | No rollback | Explain impossibility |

## Where Does Rollback Fit?

### In the Thinking Process

```
User Request
    ↓
[Intent Classification] → generative_response OR tool_use
    ↓
[Tool Selection] → Select best tool
    ↓
[Code Generation] → Generate execution code
    ↓
[Execute with Recovery] ← NEW: Wrap execution
    ↓
    ├─► Success → Return result
    ├─► Transient Failure → Retry (no rollback)
    ├─► Wrong Tool → Try alternative (no rollback)
    ├─► Signature Mismatch → Adapt OR trigger fast rollback
    ├─► Rate Limit → Chunk request (no rollback)
    └─► Impossible → Explain why (no rollback)
    ↓
[Post-Deployment Monitor] ← Runs in background
    ↓
    ├─► Pattern: 3+ consecutive failures → IMMEDIATE ROLLBACK
    ├─► Pattern: 100% failure in 5 attempts → FAST ROLLBACK
    └─► Pattern: 15%+ drop over time → STANDARD ROLLBACK
```

### Rollback Layers

1. **No Rollback** (95% of cases)
   - Single transient failures
   - Wrong tool selection
   - Rate limiting
   - Permission issues
   - **Recovery**: Retry, fallback, adapt, explain

2. **Immediate Rollback** (<5 minutes)
   - Signature change (TypeError/AttributeError)
   - 3+ consecutive failures
   - **Trigger**: Error pattern matching
   - **Why**: Deployment is clearly broken

3. **Fast Rollback** (10-30 minutes)
   - 100% failure rate with 5+ attempts
   - Complete tool breakage
   - **Trigger**: Statistical pattern
   - **Why**: High confidence of regression

4. **Standard Rollback** (hours)
   - Gradual success rate drop (15%+)
   - Requires 10+ executions for statistics
   - **Trigger**: Sliding window comparison
   - **Why**: Subtle regression, needs data

### Tool Not Used After Improvement

**Question**: If improved tool is never used, should we rollback?

**Answer**: No - this is not a rollback scenario:

```python
# In ToolLifecycleManager maintenance
def check_unused_improvements(self):
    """Check for improved tools that aren't being used."""
    
    # Get tools improved in last 30 days
    improved_tools = self._get_recently_improved_tools(days=30)
    
    for tool_name, improvement_date in improved_tools:
        # Check usage since improvement
        usage = self.execution_store.get_tool_usage_since(
            tool_name=tool_name,
            since=improvement_date
        )
        
        if usage['total_executions'] == 0:
            # Not a failure - just unused
            logger.info(f"ℹ️  Tool '{tool_name}' improved but not used in 30 days")
            logger.info(f"   Consider: Tool may no longer be needed")
            
            # Don't rollback - keep improvement
            # If tool is truly obsolete, auto-cleanup will archive it later
```

**Reason**: Lack of use != regression. The improvement is fine, the tool just isn't needed right now.

## Implementation Priority

### Phase 9f Enhancement: Fast Rollback

Before implementing full error recovery, add fast rollback to deployment monitor:

1. **Immediate Rollback Patterns** (5 minutes)
   - 3+ consecutive failures
   - TypeError/AttributeError pattern
   - 100% failure in first 5 attempts

2. **Update DeploymentMonitor**
   - Add `check_immediate_rollback_needed()`
   - Call on every health check
   - Don't wait for 10+ executions

3. **Update Autonomous Loop**
   - Check immediately after each deployment failure
   - Trigger fast rollback if pattern detected

### Phase 10d: Error Recovery Neuron

Full intelligent error recovery:

1. **ErrorRecoveryNeuron** class
2. **Error classification** logic
3. **Recovery strategies**: retry, fallback, adapt, chunk, explain
4. **Integration** with orchestrator
5. **Context preservation** in AgenticCore

### Phase 10e: Adaptive Tool Selection

Learn from wrong tool selections:

1. **Tool confusion patterns** (getX vs getXx)
2. **Success/failure correlation** with tool choice
3. **Automatic fallback** to alternative tools
4. **Tool similarity scoring** for better selection

## Summary

**Current State**: Thinking stops completely on any tool failure.

**Desired State**: Resilient reasoning that tries alternatives, adapts to changes, and explains when truly impossible.

**Rollback Fits**: As a safety net for deployment regressions, not for single execution failures.

**Key Insight**: Most failures should be recovered through reasoning, not rollback. Rollback is only for "the improved tool itself is broken" scenarios.

**Next Steps**:
1. Add fast rollback patterns to Phase 9f
2. Document tool version history
3. Implement full error recovery in Phase 10d
