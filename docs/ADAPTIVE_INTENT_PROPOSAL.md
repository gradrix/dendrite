# Adaptive Intent Classification - Dynamic Learning Proposal

## Problem Statement

Current approaches have limitations:

### Hard-coded Keywords (TaskSimplifier)
- ✅ **Works**: Fast, deterministic, good for common cases
- ❌ **Brittle**: Doesn't generalize to new patterns
- ❌ **Maintenance**: Requires manual keyword additions
- ❌ **Real-world**: Won't handle novel phrasing

### Big Prompts with Examples
- ✅ **Works**: Can show LLM what we want
- ❌ **Bloat**: Prompts grow to 1000+ tokens
- ❌ **Slow**: Small LLM struggles with long context
- ❌ **Overfits**: Examples might not match user's actual phrasing

### Current Validation+Retry
- ✅ **Works**: Fixes mechanical errors (syntax, structure)
- ❌ **Limited**: Can't fix semantic understanding failures
- ❌ **Expensive**: Multiple LLM calls for same result

## Proposed Solution: Adaptive Feedback Loop

### Core Idea
**Learn from successes, not failures**. When the LLM makes a correct decision, remember that pattern dynamically.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Goal                               │
│                 "Say hello world"                            │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│          1. Pattern Cache Lookup (Fast)                      │
│   - Check if similar goal seen before                        │
│   - Use embedding similarity or keyword match                │
│   - Confidence threshold: 0.85+                              │
└─────────────┬───────────────────────────────────────────────┘
              │
         ┌────┴────┐
         │         │
    Hit  │         │  Miss
         ▼         ▼
    ┌─────┐   ┌──────────────────────────────┐
    │ Use │   │ 2. LLM with Focused Prompt   │
    │Cache│   │   - Short, clear task        │
    └──┬──┘   │   - 3-5 most similar examples│
       │      │   - From pattern cache       │
       │      └──────────┬───────────────────┘
       │                 │
       │                 ▼
       │      ┌──────────────────────────────┐
       │      │ 3. Execute & Validate        │
       │      │   - Run the decision         │
       │      │   - Check outcome            │
       │      └──────────┬───────────────────┘
       │                 │
       │            ┌────┴────┐
       │       Success│        │Failure
       │            ▼          ▼
       │      ┌─────────┐  ┌─────────┐
       │      │  Store  │  │  Retry  │
       │      │ Pattern │  │  with   │
       │      └────┬────┘  │Feedback │
       │           │       └────┬────┘
       └───────────┴────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  Pattern Cache      │
         │  (Grows over time)  │
         └─────────────────────┘
```

### Key Components

#### 1. Pattern Cache (Lightweight Storage)

```python
class PatternCache:
    """Stores successful patterns for fast lookup."""
    
    def __init__(self):
        self.patterns = []  # List of (embedding, decision, confidence, count)
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')  # Fast, local
    
    def lookup(self, goal: str, threshold=0.85):
        """
        Find similar pattern in cache.
        
        Returns:
            (decision, confidence) or (None, 0.0)
        """
        goal_embedding = self.embedder.encode(goal)
        
        for pattern_embedding, decision, confidence, usage_count in self.patterns:
            similarity = cosine_similarity(goal_embedding, pattern_embedding)
            
            if similarity >= threshold:
                # Higher usage count = more confidence
                adjusted_confidence = min(0.99, confidence + (usage_count * 0.01))
                return decision, adjusted_confidence
        
        return None, 0.0
    
    def store(self, goal: str, decision: dict, confidence: float):
        """Store successful pattern."""
        goal_embedding = self.embedder.encode(goal)
        
        # Check if pattern already exists (update count)
        for i, (emb, dec, conf, count) in enumerate(self.patterns):
            if cosine_similarity(goal_embedding, emb) >= 0.95:
                # Very similar - update count
                self.patterns[i] = (emb, dec, max(conf, confidence), count + 1)
                return
        
        # New pattern - add it
        self.patterns.append((goal_embedding, decision, confidence, 1))
    
    def get_similar_examples(self, goal: str, k=3):
        """Get k most similar patterns for prompt context."""
        goal_embedding = self.embedder.encode(goal)
        
        similarities = [
            (cosine_similarity(goal_embedding, emb), dec, conf, count)
            for emb, dec, conf, count in self.patterns
        ]
        
        # Sort by similarity * usage_count (prefer proven patterns)
        similarities.sort(key=lambda x: x[0] * x[3], reverse=True)
        
        return similarities[:k]
```

#### 2. Adaptive Intent Classifier

```python
class AdaptiveIntentClassifier(BaseNeuron):
    """Intent classifier with dynamic learning."""
    
    def __init__(self, *args, cache_threshold=0.85, **kwargs):
        super().__init__(*args, **kwargs)
        self.pattern_cache = PatternCache()
        self.cache_threshold = cache_threshold
        
        # Load successful patterns from disk (if exists)
        self._load_patterns()
    
    def process(self, goal_id: str, goal: str, depth=0):
        # Stage 1: Check pattern cache (fast)
        cached_decision, confidence = self.pattern_cache.lookup(
            goal, 
            threshold=self.cache_threshold
        )
        
        if cached_decision:
            print(f"✓ Pattern cache hit (confidence: {confidence:.2f})")
            
            self.add_message_with_metadata(
                goal_id=goal_id,
                message_type="intent",
                data={
                    "intent": cached_decision["intent"],
                    "goal": goal,
                    "method": "cache",
                    "confidence": confidence
                },
                depth=depth
            )
            
            return {"goal": goal, "intent": cached_decision["intent"]}
        
        # Stage 2: LLM with focused prompt + similar examples
        print(f"✗ Cache miss, using LLM with focused prompt")
        
        # Get 3 most similar patterns for context
        similar_patterns = self.pattern_cache.get_similar_examples(goal, k=3)
        
        # Build focused prompt
        prompt = self._build_focused_prompt(goal, similar_patterns)
        
        response = self.ollama_client.generate(prompt=prompt)
        intent = response['response'].strip().lower()
        
        # Stage 3: Validate decision (if possible)
        is_valid = self._validate_intent(intent)
        
        if is_valid:
            # Store successful pattern for future
            self.pattern_cache.store(
                goal, 
                {"intent": intent}, 
                confidence=0.8  # Initial confidence
            )
            self._save_patterns()  # Persist to disk
        
        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="intent",
            data={
                "intent": intent,
                "goal": goal,
                "method": "llm_adaptive",
                "confidence": 0.8 if is_valid else 0.5
            },
            depth=depth
        )
        
        return {"goal": goal, "intent": intent}
    
    def _build_focused_prompt(self, goal: str, similar_patterns: list) -> str:
        """
        Build short, focused prompt with similar examples.
        
        Key: Only 3-5 examples, dynamically selected based on similarity.
        """
        base_prompt = """Classify the intent of this goal.

Intent types:
- "generative": Generate text, answer questions, creative tasks
- "tool_use": Use a specific tool/function

Goal: {goal}

"""
        
        # Add similar examples if available (dynamic, not hardcoded!)
        if similar_patterns:
            examples = "\nSimilar examples:\n"
            for similarity, decision, confidence, usage_count in similar_patterns[:3]:
                examples += f"- Similar goal → {decision['intent']} (used {usage_count}x)\n"
            base_prompt += examples
        
        base_prompt += "\nIntent:"
        
        return base_prompt.format(goal=goal)
    
    def _validate_intent(self, intent: str) -> bool:
        """Simple validation - is it a known intent?"""
        return intent in ["generative", "tool_use"]
    
    def _load_patterns(self):
        """Load patterns from disk cache."""
        # Implementation: Load from var/pattern_cache.json
        pass
    
    def _save_patterns(self):
        """Save patterns to disk cache."""
        # Implementation: Save to var/pattern_cache.json
        pass
```

#### 3. Adaptive Tool Selector

Same pattern for tool selection:

```python
class AdaptiveToolSelector(BaseNeuron):
    """Tool selector with dynamic learning."""
    
    def process(self, goal_id: str, goal: str, depth: int):
        # 1. Check pattern cache
        cached_tools, confidence = self.pattern_cache.lookup(goal, threshold=0.80)
        
        if cached_tools:
            return cached_tools
        
        # 2. Use TaskSimplifier for keyword narrowing (keep this!)
        narrowed_tools = self.simplifier.narrow_tools(goal, all_tools)
        
        # 3. Get similar examples from cache
        similar_patterns = self.pattern_cache.get_similar_examples(goal, k=3)
        
        # 4. LLM with focused prompt
        prompt = self._build_focused_prompt(goal, narrowed_tools, similar_patterns)
        selected = self._select_tool(prompt)
        
        # 5. Validate by execution
        execution_result = self._execute_tool(selected, goal)
        
        if execution_result.success:
            # Store successful pattern
            self.pattern_cache.store(goal, selected, confidence=0.85)
        
        return selected
```

## Key Advantages

### 1. Dynamic Learning
- ✅ Learns from real usage, not pre-defined examples
- ✅ Adapts to user's specific language patterns
- ✅ Gets better over time automatically

### 2. Efficient
- ✅ Cache hits are instant (no LLM call)
- ✅ Cache misses use focused prompts (3-5 examples, not 50)
- ✅ Small LLM can handle short prompts well

### 3. Robust
- ✅ Handles novel phrasing (LLM figures it out once, then cached)
- ✅ No manual maintenance (auto-learns patterns)
- ✅ Graceful degradation (falls back to LLM)

### 4. Combines Best of Both
- ✅ Keep TaskSimplifier for keyword-based narrowing (fast)
- ✅ Add pattern cache for learned behaviors (adaptive)
- ✅ Use small LLM only when needed (cost-effective)

## Implementation Strategy

### Phase 1: Pattern Cache (1-2 hours)
1. Implement `PatternCache` with embedding similarity
2. Add persistence (save/load from disk)
3. Unit tests for cache lookup/store

### Phase 2: Adaptive Intent Classifier (2 hours)
1. Integrate pattern cache into `IntentClassifierNeuron`
2. Build focused prompt generation
3. Add validation and storage logic
4. Test on failing examples

### Phase 3: Adaptive Tool Selector (2 hours)
1. Integrate pattern cache into `ToolSelectorNeuron`
2. Keep TaskSimplifier for initial narrowing
3. Add execution-based validation
4. Test on failing examples

### Phase 4: Test & Tune (1 hour)
1. Run full test suite
2. Tune confidence thresholds
3. Measure cache hit rates
4. Document learned patterns

## Expected Results

### Cache Hit Rate
- **Day 1**: 20-30% (cold start)
- **Week 1**: 60-70% (common patterns learned)
- **Month 1**: 80-90% (stable patterns)

### Performance
- **Cache hit**: ~5ms (embedding similarity)
- **Cache miss**: ~300ms (focused LLM prompt)
- **Average**: ~100ms (assuming 70% hit rate)

### Accuracy
- **Current**: 95.0% with hard-coded keywords
- **Expected**: 96-97% with adaptive learning
- **Long-term**: 98%+ as cache grows

## Comparison to Current Approach

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **Hard-coded keywords** | Fast, deterministic | Brittle, needs maintenance | Common patterns |
| **Big prompts** | Flexible | Slow, bloated, overfits | Few-shot learning |
| **Validation+retry** | Fixes mechanical errors | Can't fix semantic issues | Code generation |
| **Adaptive cache** ✨ | Learns, fast, robust | Needs cold start | Real-world usage |

## Recommendation

**Hybrid approach** (best of all worlds):

1. **TaskSimplifier** (keep): Fast keyword narrowing for tool selection
2. **Pattern Cache** (new): Learn successful patterns dynamically  
3. **Focused LLM** (new): Small prompts with 3-5 similar examples
4. **Validation** (keep): Verify execution success, store if good

This gives us:
- ✅ Fast common cases (keyword match or cache hit)
- ✅ Robust edge cases (LLM with focused context)
- ✅ Continuous improvement (learns from usage)
- ✅ Low maintenance (no manual keyword updates)

## Next Steps

Want me to implement the **Pattern Cache** and **Adaptive Intent Classifier**? This would give us:

1. Dynamic learning from successful patterns
2. Faster responses (cache hits = no LLM)
3. Better handling of novel phrasing
4. Automatic improvement over time

This is more robust than hard-coding examples in prompts, and more scalable than maintaining 1000+ keywords manually.

What do you think? Should we build this?
