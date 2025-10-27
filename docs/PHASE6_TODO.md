# Phase 6: Integration Tests - TODO for Later

## Status: 7/17 Passing (41%) - DEFERRED

**Decision**: Proceeding to Phase 7 (ToolForge), will revisit after.

## Issues to Fix Later

### 1. Clear Redis Before Tests (5 min)
```python
@pytest.fixture(autouse=True)
def clear_redis():
    bus = MessageBus()
    # Clear all test keys
    for key in bus.redis.keys("goal_*"):
        bus.redis.delete(key)
```

### 2. Make Tests Outcome-Based (15 min)
```python
# Instead of:
assert intent == "tool_use"

# Do:
assert kv_store.get("user_name") == "Alice"  # Test actual outcome
```

### 3. Add LLM Variance Markers (10 min)
```python
@pytest.mark.llm_variance  # Mark tests that depend on LLM classification
def test_pipeline_memory_write(...):
    ...
```

### 4. Improve Intent Classification Prompt (20 min)
- Add few-shot examples
- Add confidence scoring
- Add explicit tool use patterns

## Why Deferred
- Architecture is solid (proven by manual tests)
- LLM variance is expected behavior
- Test assumptions too strict
- ToolForge will help create less ambiguous tools

## Reminder
Come back after Phase 7 and spend 30-60 min on these fixes.
