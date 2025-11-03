# Dendrite Architecture

This document explains the design and implementation of Dendrite's autonomous AI orchestration system.

## System Overview

Dendrite is built around a **voting-based architecture** where decisions are made through LLM consensus rather than hardcoded rules. This makes the system naturally scalable and adaptable.

```
User Goal
    ↓
[Intent Classifier] → Generative or Tool-Use?
    ↓
[Domain Router] → Which domain? (memory, Strava, calculator, general)
    ↓
[Tool Selector] → Which tool? (semantic search + LLM voting)
    ↓
[Parameter Extractor] → What parameters?
    ↓
[Code Generator] → Generate execution code
    ↓
[Sandbox] → Execute safely
    ↓
Result
```

## Core Principles

### 1. Voting Over Rules

**Traditional Approach:**
```python
if "remember" in goal or "store" in goal:
    return "memory_write"
```

**Dendrite Approach:**
```python
domains = ["memory", "strava", "calculator"]
for domain in domains:
    confidence = llm.vote("Does '{goal}' match {domain}?")
    votes[domain] = confidence
return max(votes, key=votes.get)
```

**Why:** Adding new domains requires no code changes - just add to the list.

### 2. Micro-LLM Prompts

Every LLM call is focused and small (50-200 tokens):
- "Does this goal need tools? YES/NO"
- "Does this belong to memory domain? (0-100 confidence)"
- "Is tool_A the right choice? YES/NO with confidence"

**Why:** Smaller prompts = faster, cheaper, more accurate.

### 3. Three-Stage Tool Selection

Stage 1: **Semantic Search** (1000+ tools → 10 candidates)
- Uses ChromaDB vector embeddings
- Finds tools with similar descriptions
- Fast pre-filtering

Stage 2: **Statistical Ranking** (10 → 5 candidates)
- Ranks by historical success rate
- Considers usage frequency
- Promotes reliable tools

Stage 3: **LLM Voting** (5 → 1 best tool)
- Each remaining tool gets YES/NO vote
- Returns confidence score
- Highest confidence wins

**Why:** Handles large tool repositories without overwhelming LLM context.

### 4. Pattern Caching

First time seeing goal:
- Full LLM voting process
- Store decision in pattern cache

Subsequent similar goals:
- Check pattern cache first (5ms)
- Skip LLM if high confidence match
- Dramatically faster

## Core Components

### Orchestrator

**Location:** `neural_engine/core/orchestrator.py`

**Responsibility:** Central coordinator that routes goals through processing pipeline.

**Key Methods:**
- `process(goal)` - Main entry point
- `execute(goal_id, goal, depth)` - Execute with recursion tracking
- `_execute_generative_pipeline()` - For conversational queries
- `_execute_tool_use_pipeline()` - For tool-requiring goals

**Decision Flow:**
```python
intent = intent_classifier.process(goal)
if intent == "generative":
    return generative_neuron.process(goal)
else:
    return tool_use_pipeline(goal)
```

### Intent Classifier

**Location:** `neural_engine/core/intent_classifier_neuron.py`

**Responsibility:** Determines if goal requires tool execution.

**Prompt:** "Does this goal require using a tool? YES/NO"

**Examples:**
- "What is 2+2?" → generative (LLM can answer directly)
- "Remember my name is Alice" → tool_use (needs memory_write tool)
- "Explain Docker" → generative
- "Show my activities" → tool_use (needs Strava API)

**Caching:** Uses pattern cache for instant classification of similar goals.

### Domain Router

**Location:** `neural_engine/core/domain_router.py`

**Responsibility:** Detects specialized domains that have specialist handlers.

**Current Domains:**
- `memory` - Key-value storage operations
- `strava` - Fitness activity queries
- `calculator` - Mathematical operations
- `general` - Everything else

**Voting Process:**
```python
for domain_name, domain_desc in domains:
    prompt = f"Goal: {goal}\nDoes this belong to {domain_name} domain?"
    response = llm.generate(prompt)
    confidence = extract_confidence(response)  # 0-100
    votes[domain_name] = confidence

return max(votes, key=votes.get)
```

**Specialist Routing:**
If domain == "memory" → Use Memory Specialist (pattern-based, instant)
Otherwise → Use general tool selection pipeline

**Adding New Domains:**
Simply add to the domains list - no code changes needed!

### Memory Operations Specialist

**Location:** `neural_engine/core/memory_operations_specialist.py`

**Responsibility:** Fast, deterministic memory operation detection.

**Why Special:** Memory operations are so common that LLM voting is wasteful.

**Pattern Matching:**
```python
# Write patterns
"remember that", "store", "save", "my X is Y"

# Read patterns
"what is my", "recall", "what did I tell you"

# Delete patterns
"forget", "delete", "remove"
```

**Confidence:** Always returns 0.95 (very high confidence).

**Parameter Extraction:**
- "Remember that my name is Alice" → `{key: "name", value: "Alice"}`
- "What is my favorite color?" → `{key: "favorite_color"}`

### Tool Discovery

**Location:** `neural_engine/core/tool_discovery.py`

**Responsibility:** Semantic search over large tool repositories.

**Technology:** ChromaDB with sentence transformers for embeddings.

**Indexing Process:**
```python
for tool in registry.get_all_tools():
    text = f"{tool.name}: {tool.description}"
    embedding = embed(text)
    chroma_collection.add(id=tool.name, embedding=embedding)
```

**Search Process:**
```python
query_embedding = embed(goal)
results = chroma_collection.query(
    query_embedding,
    n_results=10  # Get top 10 candidates
)
return results
```

**When Used:** Enabled when tool registry has 10+ tools.

**Performance:** Scales to 1000+ tools with <100ms search time.

### Tool Selector

**Location:** `neural_engine/core/tool_selector_neuron.py`

**Responsibility:** Selects best tool using three-stage process.

**Stage 0.5:** Check Pattern Cache (~5ms)
- Look for cached decision
- If found with high confidence → return immediately
- Massively speeds up repeated goals

**Stage 0.75:** Try Domain Specialist
- If memory domain → use Memory Specialist
- Returns instant decision with pattern matching

**Stage 1:** Semantic Search (optional, if tool discovery enabled)
- Query ChromaDB: 1000+ tools → 10 candidates
- Fast pre-filtering based on description similarity

**Stage 2:** Statistical Ranking
- Rank 10 candidates by success rate & usage
- Select top 5 performers

**Stage 3:** LLM Voting
- Each of 5 tools gets vote: "Is this the right tool? YES/NO (confidence)"
- Parse responses and extract confidence scores
- Select tool with highest confidence
- Raise error if no tool voted YES

**Result Format:**
```python
{
    "goal": "Remember my name is Alice",
    "selected_tools": [{
        "name": "memory_write",
        "module": "neural_engine.tools.memory_write_tool",
        "class": "MemoryWriteTool",
        "confidence": 0.98
    }],
    "method": "memory_specialist"  # or "llm_voting", "pattern_cache"
}
```

### Voting Tool Selector

**Location:** `neural_engine/core/voting_tool_selector.py`

**Responsibility:** Per-tool LLM voting implementation.

**Process:**
```python
for tool in candidates:
    prompt = f"""
    Goal: {goal}
    Tool: {tool.name}
    Description: {tool.description}
    
    Is this the right tool? YES or NO
    Confidence: 0-100
    """
    response = llm.generate(prompt)
    vote = parse_vote(response)  # Extract YES/NO + confidence
    votes.append((tool, vote))

# Find best YES vote
yes_votes = [v for v in votes if v['answer'] == 'YES']
if yes_votes:
    return max(yes_votes, key=lambda x: x['confidence'])
else:
    raise ValueError("No tools voted YES")
```

**Smart Caching:** Caches votes per (goal, tool) pair to avoid re-voting.

### Parameter Extractor

**Location:** `neural_engine/core/parameter_extractor.py`

**Responsibility:** Extracts required parameters from goal text.

**Two Implementations:**

**1. MemoryParameterExtractor** (fast, pattern-based)
```python
# "Remember that my name is Alice"
patterns = {
    'write': r'my (\w+) is (.+)',  # → key="name", value="Alice"
    'read': r'what is my (\w+)',   # → key="name"
}
```

**2. ParameterExtractor** (general, LLM-based)
```python
prompt = f"""
Goal: {goal}
Tool: {tool_name}
Parameters needed: {param_list}

Extract EXACT values for each parameter from the goal.
If a parameter is not mentioned, return 'NotSpecified'.

Format: {{"param1": "value1", "param2": "value2"}}
"""
```

**Why Two:** Memory operations are so common that patterns are faster. General extractor handles complex parameter parsing.

### Code Generator

**Location:** `neural_engine/core/code_generator_neuron.py`

**Responsibility:** Generates Python code to execute selected tool.

**Template:**
```python
from {tool.module} import {tool.class_name}

tool = {tool.class_name}()
result = tool.execute(**{params})
sandbox.set_result(result)
```

**With Validation:**
Uses `code_validator_neuron.py` to check:
- Valid Python syntax
- Imports correct module
- Calls execute() method
- Uses sandbox.set_result()
- No dangerous operations

**Retry Logic:**
If validation fails, regenerates code with feedback:
```python
prompt = f"""
Your previous code had this error: {error}
Here's what went wrong: {validation_feedback}
Generate corrected code.
"""
```

### Sandbox

**Location:** `neural_engine/core/sandbox.py`

**Responsibility:** Isolated Python code execution.

**Namespace:**
```python
namespace = {
    'tool_registry': self.tool_registry,
    'sandbox': self,  # For set_result()
    '__builtins__': safe_builtins  # Filtered built-ins
}
exec(generated_code, namespace)
```

**Security:**
- No file system access (except approved tools)
- No network access (except approved tools)
- No dangerous builtins (eval, compile, etc.)
- Timeout after 30 seconds

**Result Handling:**
```python
def set_result(self, result):
    self.result = result
    # Store in message bus for later retrieval
```

### Message Bus

**Location:** `neural_engine/core/message_bus.py`

**Responsibility:** Communication and state storage between components.

**Storage Backend:** Redis

**Database Isolation:**
- Production: db=0
- Tests: db=1 (prevents test data from contaminating production)

**Message Format:**
```python
{
    "goal_id": "goal_123",
    "type": "tool_selection",
    "data": {...},
    "depth": 0,
    "timestamp": 1699000000
}
```

**Key Pattern:** `goal_{goal_id}` → List of messages

**Usage:**
```python
bus = MessageBus()
goal_id = bus.get_new_goal_id()
bus.add_message(goal_id, "intent_classification", {"intent": "tool_use"})
messages = bus.get_messages(goal_id)  # Retrieve conversation
```

## Intelligent Caching

### Pattern Cache

**Location:** `neural_engine/core/pattern_cache.py`

**Purpose:** Store successful LLM decisions for reuse.

**Storage:** In-memory dictionary + disk persistence

**Entry Format:**
```python
{
    "pattern": "Remember that my name is Alice",
    "decision": {"tool": "memory_write", "params": {...}},
    "confidence": 0.95,
    "usage_count": 42,
    "success_count": 40
}
```

**Lookup:** Fuzzy string similarity matching (threshold=0.85)

**Updating:**
```python
# After successful execution
cache.store_pattern(
    pattern=goal,
    decision=selected_tool,
    confidence=0.95
)

# After execution result
cache.update_usage(pattern, success=True)
```

**Hit Rate:** Typically 60-80% for repeated workflows.

### Neural Pathway Cache

**Location:** `neural_engine/core/neural_pathway_cache.py`

**Purpose:** Cache complete execution paths, not just single decisions.

**Entry Format:**
```python
{
    "goal_pattern": "Remember my X is Y",
    "context_hash": "abc123",
    "pathway": [
        {"neuron": "intent_classifier", "result": "tool_use"},
        {"neuron": "domain_router", "result": "memory"},
        {"neuron": "tool_selector", "result": "memory_write"},
        {"neuron": "parameter_extractor", "result": {"key": "X", "value": "Y"}},
        {"neuron": "code_generator", "result": "...code..."},
        {"neuron": "sandbox", "result": {"success": True}}
    ],
    "success_count": 10,
    "failure_count": 0,
    "confidence": 0.99
}
```

**Context Hashing:** Similar goals with similar available tools get same hash.

**Invalidation:** If any tool in pathway changes, invalidate cached pathways.

**Performance:** Can replay entire pathway in <50ms vs 2-5s for fresh execution.

## Autonomous Systems

### Autonomous Loop

**Location:** `neural_engine/core/autonomous_loop.py`

**Purpose:** Background monitoring and self-improvement.

**Main Loop:**
```python
while not stopped:
    # Every 5 minutes
    stats = execution_store.get_statistics()
    
    # Detect problems
    opportunities = detect_improvement_opportunities(stats)
    # → Low success rate tools
    # → Frequently failing tools
    # → Missing tools for common goals
    
    # Generate improvements
    for opp in opportunities:
        improvement = generate_improvement(opp)
        # → Modify existing tool
        # → Create new tool
        # → Update prompts
        
        # Validate with shadow testing
        shadow_test_results = shadow_test(improvement)
        
        # Deploy if successful
        if shadow_test_results['success_rate'] > baseline:
            deploy_improvement(improvement)
```

**Shadow Testing:** Runs improved version alongside production, compares results.

**Rollback:** Automatically rolls back if regression detected.

### Execution Store

**Location:** `neural_engine/core/execution_store.py`

**Purpose:** PostgreSQL-backed analytics storage.

**Tables:**
- `executions` - Every goal execution with success/failure
- `tool_executions` - Every tool call with latency
- `tool_feedback` - User corrections and feedback
- `tool_statistics` - Aggregated metrics

**Queries:**
```python
# Get tool success rate
store.get_success_rate(tool_name="memory_write")

# Get recent failures
store.get_recent_executions(
    tool_name="strava_get_activities",
    success=False,
    limit=10
)

# Get top performing tools
store.get_top_tools(limit=5)
```

**Used By:**
- Autonomous loop for monitoring
- Statistical ranking in tool selection
- Analytics and reporting

### Self-Investigation Neuron

**Location:** `neural_engine/core/self_investigation_neuron.py`

**Purpose:** Proactive health monitoring and issue detection.

**Capabilities:**
- Detect anomalies in tool performance
- Identify degrading tools over time
- Generate insights about system health
- Alert on critical issues
- Recommend remediation actions

**Investigation Types:**
```python
# Health check
result = neuron.investigate_health()
# → {health_score: 0.85, issues: [...], recommendations: [...]}

# Anomaly detection
anomalies = neuron.detect_anomalies()
# → [{type: "performance_drop", tool: "X", severity: "high"}]

# Degradation analysis
degrading = neuron.detect_degradation()
# → [{tool: "Y", trend: "declining", recommendation: "rewrite"}]
```

## Tool Management

### Tool Registry

**Location:** `neural_engine/core/tool_registry.py`

**Purpose:** Dynamic discovery and loading of tools.

**Discovery:**
```python
# Scans neural_engine/tools/ directory
tools = []
for file in os.listdir("neural_engine/tools"):
    if file.endswith("_tool.py"):
        module = import_module(f"neural_engine.tools.{file[:-3]}")
        for item in dir(module):
            if item.endswith("Tool"):
                tool_class = getattr(module, item)
                tools.append(tool_class())
```

**Tool Interface:**
```python
class BaseTool:
    def get_tool_definition(self) -> dict:
        return {
            "name": "tool_name",
            "description": "What it does",
            "parameters": [...]
        }
    
    def execute(self, **kwargs) -> dict:
        # Implementation
        return {"result": "..."}
```

**Metadata Tracking:**
- Module name and path
- Class name
- Creation timestamp
- Version (if specified)

### Tool Forge

**Location:** `neural_engine/core/tool_forge_neuron.py`

**Purpose:** Dynamic tool creation from natural language.

**Process:**
```python
# User: "Create a tool that converts Celsius to Fahrenheit"

forge = ToolForgeNeuron()
result = forge.process(
    goal_id="forge_123",
    data={"goal": "Create tool for C to F conversion"},
    depth=0
)

# Generated tool code:
class CelsiusToFahrenheitTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "celsius_to_fahrenheit",
            "description": "Convert Celsius to Fahrenheit",
            "parameters": [
                {"name": "celsius", "type": "number", "required": True}
            ]
        }
    
    def execute(self, **kwargs):
        celsius = kwargs.get('celsius')
        fahrenheit = (celsius * 9/5) + 32
        return {"result": fahrenheit}

# Validation checks:
# ✓ Has BaseTool import
# ✓ Class ends with 'Tool'
# ✓ Has get_tool_definition method
# ✓ Has execute method
# ✓ Valid Python syntax

# Auto-saved to: neural_engine/tools/celsius_to_fahrenheit_tool.py
# Auto-registered in registry
# Immediately available for use!
```

### Tool Lifecycle Manager

**Location:** `neural_engine/core/tool_lifecycle_manager.py`

**Purpose:** Manages tool deployment, versioning, and cleanup.

**Features:**
- Detect manually created tools (admin-created)
- Detect AI-generated tools (forge-created)
- Track usage and success rates
- Identify unused tools for cleanup
- Backup before deletion
- Restore from backup if needed

**Cleanup Logic:**
```python
# Safe to delete if:
# - Not used in 30+ days
# - Success rate < 50%
# - Never successfully used
# - AI-generated (not admin-created)

manager.auto_cleanup(
    dry_run=False,
    age_threshold_days=30,
    min_usage_count=0
)
```

### Tool Version Manager

**Location:** `neural_engine/core/tool_version_manager.py`

**Purpose:** Version control and rollback for tools.

**Versioning:**
```python
# Create version on modification
version_id = manager.create_version(
    tool_name="memory_write",
    code=new_code,
    reason="Improved parameter extraction"
)

# Get history
history = manager.get_version_history("memory_write")
# → [{version: 1, timestamp: ..., reason: "..."}, ...]

# Rollback if needed
manager.rollback_to_version("memory_write", version_id=2)
```

**Automatic Rollback Triggers:**
- 3+ consecutive failures
- Critical error rate spike
- Signature breaking changes

## Performance Optimizations

### Token Limit Management

**Problem:** LLMs have context limits (typically 4096-8192 tokens).

**Solution 1:** Tool Discovery
- Use semantic search to reduce 1000+ tools → 10 candidates
- Only these 10 are sent to LLM for voting

**Solution 2:** Candidate Limiting
- Fallback without discovery: Only use first 10 tools from registry
- Prevents token overflow in voting process

**Solution 3:** Result Truncation
- Large tool results (>5KB) not shown in full
- Summary + reference ID provided instead

### Parallel Execution

**Where:** Voting process can vote on multiple tools in parallel.

**Implementation:**
```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = []
    for tool in candidates:
        future = executor.submit(vote_on_tool, goal, tool)
        futures.append(future)
    
    votes = [f.result() for f in futures]
```

**Speedup:** 5x faster for 5-tool voting (2.5s → 0.5s).

### Caching Strategy

**Layer 1:** Pattern Cache (fastest - ~5ms)
- Check for exact or very similar goals
- Return cached decision immediately

**Layer 2:** Memory Specialist (fast - ~10ms)
- Pattern matching for memory operations
- No LLM call needed

**Layer 3:** Tool Discovery (fast - ~100ms)
- Semantic search reduces LLM context
- Faster than full-registry voting

**Layer 4:** Full LLM Voting (slow - ~2-5s)
- Only when all else fails
- Results cached for future use

**Cache Hit Rates:**
- Pattern cache: 60-80% (for repeated workflows)
- Memory specialist: ~10% (common operations)
- Tool discovery: Always runs if enabled
- Full voting: 10-30% (novel goals)

## Error Handling

### Error Recovery Neuron

**Location:** `neural_engine/core/error_recovery_neuron.py`

**Strategies:**

**1. Retry Strategy** (for transient errors)
```python
max_retries = 3
for attempt in range(max_retries):
    try:
        result = execute_tool(...)
        return result
    except TransientError:
        time.sleep(2 ** attempt)  # Exponential backoff
```

**2. Fallback Strategy** (for tool unavailability)
```python
try:
    return strava_api_tool.execute(...)
except ToolUnavailable:
    # Fallback to alternative
    return cached_data_tool.execute(...)
```

**3. Adapt Strategy** (for parameter mismatches)
```python
try:
    return tool.execute(param1=x, param2=y)
except ParameterError as e:
    # Re-extract parameters with error context
    corrected_params = extractor.extract_with_feedback(
        goal, tool, error=str(e)
    )
    return tool.execute(**corrected_params)
```

### Validation

**Code Validation** (`code_validator_neuron.py`):
- Syntax check with ast.parse()
- Required imports present
- Tool class properly instantiated
- execute() method called
- Result stored via sandbox.set_result()

**Result Validation**:
- Non-empty result
- Expected type (dict)
- Contains required fields
- Success flag present

## Testing Architecture

### Test Organization

Tests are organized by "phase" representing development stages:

- **Phase 0:** Intent classification
- **Phase 1:** Generative pipeline
- **Phase 2:** Tool registry
- **Phase 3:** Tool selection
- **Phase 4:** Code generation
- **Phase 5:** Sandbox execution
- **Phase 6:** Full pipeline integration
- **Phase 7:** Tool forge
- **Phase 9:** Autonomous systems

### Test Isolation

**Global Fixture** (`conftest.py`):
```python
@pytest.fixture(autouse=True)
def cleanup_redis_before_each_test():
    """Runs before EVERY test automatically"""
    redis_client = redis.Redis(db=1)  # Test database
    # Clear all goal keys
    for key in redis_client.scan_iter("goal_*"):
        redis_client.delete(key)
    # Clear pattern cache
    PatternCache.clear()
    yield
```

**Database Isolation:**
- Production: Redis db=0, PostgreSQL dendrite_prod
- Tests: Redis db=1, PostgreSQL dendrite_test

**Why:** Prevents test contamination and allows parallel testing.

### Test Fixtures

**Common Fixtures:**
```python
@pytest.fixture
def ollama_client():
    return OllamaClient()

@pytest.fixture
def message_bus():
    return MessageBus()  # Auto-uses Redis db=1 in tests

@pytest.fixture
def tool_registry():
    return ToolRegistry()

@pytest.fixture
def execution_store():
    return ExecutionStore()  # Auto-uses test database
```

**Composition:**
```python
@pytest.fixture
def tool_selector(message_bus, ollama_client, tool_registry):
    return ToolSelectorNeuron(message_bus, ollama_client, tool_registry)
```

## Extension Points

### Adding a New Domain

1. **Update Domain Router:**
```python
# neural_engine/core/domain_router.py
domains = [
    ("memory", "personal information, remembering facts"),
    ("strava", "fitness activities, running, cycling"),
    ("calculator", "mathematical calculations"),
    ("github", "code repositories, pull requests, issues"),  # NEW!
]
```

2. **Create Specialist (optional):**
```python
# neural_engine/core/github_specialist.py
class GitHubSpecialist:
    def detect_operation(self, goal):
        if "pull request" in goal.lower():
            return {"tool": "github_pr", "confidence": 0.95}
        # ...
```

3. **Register Specialist:**
```python
# neural_engine/core/tool_selector_neuron.py
if domain == "github" and self.github_specialist:
    return self.github_specialist.select_tool(goal)
```

That's it! No hardcoded patterns needed.

### Adding a New Tool

See [Getting Started](GETTING_STARTED.md#adding-a-new-tool)

### Customizing Voting Logic

Override `voting_tool_selector.py`:
```python
class CustomVotingSelector(VotingToolSelector):
    def vote_on_tool(self, goal, tool):
        # Your custom voting logic
        # Can use different LLM, different prompt, etc.
        return {"answer": "YES", "confidence": 0.88}
```

## Design Decisions

### Why Voting Instead of Classification?

**Classification approach:**
```python
categories = {"memory": [...tools...], "strava": [...tools...]}
category = classify(goal)
tools = categories[category]
```

**Problems:**
- Must maintain category mappings
- Tools can fit multiple categories
- Rigid structure

**Voting approach:**
```python
for tool in tools:
    vote = llm.vote("Is this right? YES/NO")
```

**Benefits:**
- No category maintenance
- Natural multi-domain support
- Self-documenting (votes show reasoning)
- Scales to any number of tools

### Why Three-Stage Selection?

**Why not just LLM vote all tools?**
- Token limit: Can't fit 1000+ tool descriptions
- Cost: Voting on 1000 tools = 1000 LLM calls
- Speed: Sequential voting is slow

**Why semantic search first?**
- Reduces 1000+ → 10 in <100ms
- Vector embeddings are fast
- Good enough for pre-filtering

**Why statistical ranking second?**
- Promotes reliable tools
- Learn from historical data
- No LLM call needed

**Why LLM voting last?**
- Highest quality decision
- Only 5-10 calls needed
- Best matches user intent

### Why Redis + PostgreSQL?

**Redis:** Fast in-memory message bus
- Sub-millisecond access
- Perfect for conversation state
- Simple key-value API
- Easy cleanup (just flush db=1 for tests)

**PostgreSQL:** Persistent analytics storage
- Complex queries (success rate, trends)
- Reliable for long-term data
- pgvector support for future semantic queries
- Production-grade reliability

**Why not just one?**
- Redis too volatile for analytics
- PostgreSQL too slow for message bus
- Each optimized for its use case

## Future Architecture

### Planned Improvements

1. **Multi-Agent Collaboration**
   - Multiple orchestrators working together
   - Specialization by domain
   - Shared knowledge base

2. **Reinforcement Learning**
   - Learn from user corrections
   - Optimize selection strategy
   - Adaptive confidence thresholds

3. **Streaming Results**
   - Long-running tools stream progress
   - Real-time user feedback
   - Cancellation support

4. **Distributed Execution**
   - Multiple sandbox workers
   - Parallel tool execution
   - Load balancing

5. **Advanced Caching**
   - Embedding-based pathway matching
   - Cross-goal knowledge transfer
   - Predictive pre-caching

## Performance Benchmarks

Typical latencies (on CPU, mistral model):

- Intent classification: 200-500ms
- Domain routing: 300-600ms
- Tool discovery (semantic): 50-100ms
- Tool selection (5 candidates): 2-5s
- Parameter extraction: 300-800ms
- Code generation: 1-2s
- Sandbox execution: 10-500ms (depends on tool)

**Total:** 4-9 seconds for cold start (no caching)

With caching:
- Pattern cache hit: <50ms
- Memory specialist: <100ms
- Pathway cache hit: <200ms

**90% of repeated goals:** <200ms

## Conclusion

Dendrite's architecture is designed for:
- **Scalability:** Add domains/tools without code changes
- **Reliability:** Multiple fallback strategies
- **Performance:** Aggressive caching and optimization
- **Maintainability:** Clear separation of concerns
- **Extensibility:** Well-defined extension points

The voting-based approach eliminates most hardcoded rules, making the system naturally adaptable and self-improving.
