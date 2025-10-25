# Dendrite Architecture

Understanding the neuron-based self-organizing AI agent.

## Core Concepts

### Biological Neural Network Metaphor

Dendrite uses a functional biological metaphor:

- **Neurons**: Individual execution units (50-100 token micro-prompts + tool call)
- **Dendrites**: Auto-spawned sub-tasks for list iteration
- **Axons**: Result aggregation pathways back to parent neurons
- **Synapses**: Context passing between neurons

This isn't just naming - the system actually behaves like neural signal propagation!

### Example Execution Flow

```
User Goal: "How many running activities did I have in September?"

├─ Neuron 0.1: Convert dates to timestamps
│  ├─ Dendrite 1.1: Convert "September 1, 2025" → 1756684800
│  └─ Dendrite 1.2: Convert "September 30, 2025" → 1759190400
│  └─ Aggregate: start=1756684800, end=1759190400
│
├─ Neuron 0.2: Fetch activities in range
│  └─ Tool: getMyActivities(after=1756684800, before=1759190400)
│  └─ Result: 63 activities (136KB) → Saved to disk
│  └─ Context: {'_ref_id': 'neuron_0_2_abc123', 'summary': '63 activities...'}
│
├─ Neuron 0.3: Count running activities
│  └─ Tool: executeDataAnalysis
│  └─ Code: data = load_data_reference('neuron_0_2_abc123')
│           result = len([x for x in data['activities'] if 'Run' in x['sport_type']])
│  └─ Result: 28
│
└─ Final Output: "28 activities"
```

## Key Design Patterns

### 1. Micro-Prompting

Every LLM call uses minimal tokens (50-200):

- `_micro_decompose`: Break goal into 1-3 neurons
- `_micro_find_tool`: Match neuron description to available tool
- `_micro_determine_params`: Extract parameters from context
- `_micro_validate`: Check if result satisfies neuron goal
- `_micro_aggregate`: Combine neuron results

**Benefits:**
- Reduces token usage (cost-effective)
- Increases accuracy (focused prompts)
- Easier debugging (isolated steps)
- Better validation (check each micro-step)

### 2. Automatic Dendrite Spawning

The agent automatically detects when to iterate:

#### Pre-Execution Spawning

Checks context for lists before tool execution:

```python
Neuron: "Get kudos for each activity"
         ↓
Context Check: Found 30 activities in neuron_0_1
         ↓
Decision: Spawn 30 dendrites (one per activity)
         ↓
Execute: 30 parallel sub-neurons
         ↓
Aggregate: Merge all kudos data back
```

**Triggers:**
- Keywords: "for each", "all activities", "every item"
- Context contains list data
- Action requires per-item processing

#### Post-Execution Spawning

Checks result after tool execution:

```python
Tool: getDashboardFeed() → Returns [50 activities]
         ↓
Detection: Result is a list
         ↓
LLM Check: "Does task require per-item API calls?"
         ↓
Decision: No (data already complete) → Skip spawning
```

**Smart Detection:**
- Only spawns if additional API calls needed
- Skips if data is already complete
- Prevents unnecessary spawning (10x speedup)

### 3. Smart Data Compaction

Prevents context overflow with automatic disk caching:

```python
# Large API response (136KB)
result = getMyActivities(...)

# System checks size
if size > 5KB:
    # Save full data to disk
    save_to_disk('state/data_cache/neuron_0_2_abc123.json', result)
    
    # Store only reference in context
    return {
        '_ref_id': 'neuron_0_2_abc123',
        '_data_file': '/path/to/file.json',
        '_size_kb': 136.1,
        '_format': 'disk_reference',
        'summary': '63 activities with fields: name, distance, moving_time...',
        '_usage_hint': 'Use executeDataAnalysis with: load_data_reference("neuron_0_2_abc123")'
    }
```

**Python tools can load full data:**
```python
# In executeDataAnalysis tool
data = load_data_reference('neuron_0_2_abc123')
# Now has access to full 136KB dataset
```

**Benefits:**
- Keeps LLM context lean (<5KB per result)
- No context window overflow
- Full data available when needed
- Automatic, no manual intervention

### 4. Error Reflection & Self-Correction

LLM diagnoses its own errors and retries:

```python
# Execution fails
try:
    result = load_data_reference(data['neuron_0_2']['_ref_id'])
except KeyError as e:
    # Ask LLM what went wrong
    diagnosis = _reflect_on_error(
        neuron_desc="Count running activities",
        tool_name="executeDataAnalysis",
        params={'python_code': '...'},
        error="KeyError: '_ref_id'",
        context=self.context
    )
    
    # LLM Response:
    # "The code tried to access data['neuron_0_2']['_ref_id'] but 
    #  neuron_0_2 is a scalar result with no '_ref_id' field.
    #  Should access data['neuron_0_2'] directly."
    
    # Regenerate corrected code
    fixed_code = regenerate_with_diagnosis(diagnosis)
    
    # Auto-retry
    result = execute_tool(fixed_code)
```

**Retry Strategy:**
- Max 3 attempts per neuron
- Each retry uses reflection
- Corrective neurons for goal completion
- No user intervention required

### 5. Intelligent Result Aggregation

The agent uses smart aggregation to detect and prioritize formatted results:

```python
# Multiple neurons executed:
# neuron_0_1: Convert dates → timestamps
# neuron_0_2: Fetch activities → 48 activities (raw data)
# neuron_0_3: Filter first 3 → [3 dict objects]
# neuron_0_4: Format → "Activity 1\nActivity 2\nActivity 3"

# Aggregation scans backwards for formatting results
def aggregate_results(goal, neurons, results):
    # Extract quantity constraint from goal
    "Get my first 3 activities..."  →  target_count = 3
    
    # Check each neuron's RESULT TYPE (not just description)
    for neuron, result in reversed(neurons, results):
        if result is executeDataAnalysis string output:
            line_count = count_non_empty_lines(result)
            
            # Prefer results matching target count
            if line_count == 3:  # Matches "first 3"!
                return result  ✓ Perfect match
    
    # Fallback: most recent formatted result
```

**Key Insights:**

1. **Detect by Result Type, Not Keywords**
   - Checks if result is a `string` from `executeDataAnalysis`
   - Doesn't rely on "format" keyword in description
   - neuron "Filter first 3" → produces formatted string → detected!

2. **Quantity Constraint Matching**
   - Extracts "first 3", "top 5", "last 10" from goal
   - Counts non-empty lines in formatted results
   - Prefers results with matching line counts
   - Prevents returning 48 activities when goal says "first 3"

3. **Priority Order**
   - ① Result matching exact line count
   - ② Most recent formatted string result
   - ③ Any string result from executeDataAnalysis
   - ④ Last successful result

**Why This Matters:**

Prevents meta-summaries like:
```
❌ "The goal was to retrieve and display the first three activities..."
✓ "Morning Snowboard - 57944.4m on 2024-01-31
   Lunch Snowboard - 44090.3m on 2024-01-30
   Morning Snowboard - 46589.7m on 2024-01-29"
```

See [AGGREGATION.md](AGGREGATION.md) for detailed explanation.

### 6. Memory Overseer

Intelligent pre-execution context loading:

```python
def execute_goal(goal):
    # Before decomposition, check saved state
    memory_context = _check_memory_relevance(goal)
    
    # LLM decides which saved keys are relevant:
    # Goal: "How many runs this month?"
    # Available: ['last_kudos_check', 'september_activities', 'athlete_profile']
    # LLM selects: ['september_activities']  # relevant!
    
    if memory_context:
        # Inject only relevant memory
        context['_memory'] = memory_context
    
    # Continue with lean context
    execute_neurons(goal)
```

**Benefits:**
- Prevents context bloat (only loads what's needed)
- Faster execution (less prompt tokens)
- Smarter continuations (remembers relevant data)

## Execution Layers

### Layer 0: Root Goal (Depth=0)

User's natural language goal:
```
"How many running activities in September 2025?"
```

### Layer 1: Primary Neurons (Depth=0)

Decomposed into 1-3 neurons:
```
Neuron 0.1: Convert dates to timestamps
Neuron 0.2: Fetch activities
Neuron 0.3: Count running activities
```

### Layer 2: Dendrites (Depth=1)

Auto-spawned for iteration:
```
Neuron 0.1 spawns:
  ├─ Dendrite 1.1: Convert Sept 1
  └─ Dendrite 1.2: Convert Sept 30
```

### Layer 3+: Nested Dendrites (Depth=2-4)

Recursive spawning if needed:
```
Dendrite 1.1 could spawn:
  ├─ Sub-dendrite 2.1: Validate date
  └─ Sub-dendrite 2.2: Handle timezone
```

**Max Depth:** 5 levels (prevents infinite recursion)

## Tool System

### Tool Registry

All tools are registered with:
- **Name**: camelCase identifier
- **Function**: Python callable
- **Description**: What the tool does (for LLM)
- **Parameters**: Type hints and descriptions

### Tool Categories

1. **API Tools** (`tools/strava_tools.py`):
   - `getMyActivities`: Fetch activities
   - `getActivityKudos`: Get kudos for activity
   - `getDashboardFeed`: Get recent feed

2. **Analysis Tools** (`tools/analysis_tools.py`):
   - `executeDataAnalysis`: Run Python code on data
   - Automatic context injection
   - Access to `load_data_reference()`

3. **Utility Tools** (`tools/utility_tools.py`):
   - `dateToUnixTimestamp`: Convert dates
   - `getCurrentDate`: Get current date/time
   - `calculateTimestamp`: Date math

### Adding New Tools

```python
# 1. Create function with docstring
def my_custom_tool(param1: str, param2: int) -> dict:
    """
    Description visible to LLM.
    
    Args:
        param1: Description of parameter
        param2: Another parameter
    
    Returns:
        dict with 'success' and result data
    """
    return {'success': True, 'result': 'data'}

# 2. Register in tool_registry.py
registry.register_tool(
    name="myCustomTool",
    func=my_custom_tool,
    description="What this tool does"
)
```

Agent will automatically:
- Discover the tool
- Understand when to use it
- Extract parameters from context
- Handle errors and retry

## Performance Characteristics

### Token Efficiency

- **Micro-prompts**: 50-200 tokens each
- **Traditional agents**: 1000+ tokens per prompt
- **Savings**: 5-10x fewer tokens

### Execution Speed

- **Before optimization**: 324 seconds (unnecessary spawning)
- **After optimization**: 33 seconds (smart detection)
- **Speedup**: 10x faster

### Context Management

- **Traditional**: Everything in memory (context overflow at ~200KB)
- **Dendrite**: Disk caching at >5KB (handles MB of data)
- **Benefit**: Virtually unlimited data handling

### Success Rate

- **Self-correction**: >90% goal completion
- **Retry logic**: Max 3 attempts with reflection
- **Corrective neurons**: Auto-fix incomplete results

## Comparison to Traditional Agents

| Aspect | Traditional Agent | Dendrite |
|--------|------------------|----------|
| Planning | Upfront plan generation | Dynamic per-neuron decomposition |
| Prompt Size | Large (1000+ tokens) | Micro (50-200 tokens) |
| Iteration | Manual loops/map operations | Auto-spawning dendrites |
| Context | Everything in memory | Smart disk caching (>5KB) |
| Errors | Fail or ask user | Self-diagnosis + auto-correction |
| Execution | Linear steps | Recursive neuron chains |
| Validation | End-of-task only | Every neuron continuously |
| Data Handling | Limited by context window | Virtually unlimited (disk cache) |

## Code Structure

```
agent/
├── neuron_agent.py          # Core neuron execution engine
│   ├── NeuronAgent class
│   ├── execute_goal()       # Entry point
│   ├── _execute_neuron()    # Single neuron execution
│   ├── _spawn_dendrites()   # Auto-iteration
│   ├── _micro_* methods     # Micro-prompting functions
│   └── _reflect_on_error()  # Error diagnosis
│
├── tool_registry.py         # Tool discovery and execution
├── data_compaction.py       # Smart disk caching
├── ollama_client.py         # LLM communication
└── model_config.py          # Model selection

tools/
├── strava_tools.py          # Strava API integration
├── analysis_tools.py        # Python execution
└── utility_tools.py         # Date/time helpers
```

## Research Applications

This architecture demonstrates:

1. **Recursive Micro-Prompting**: Breaking LLM tasks into biological-scale units
2. **Emergent Decomposition**: No hardcoded workflows, agent discovers structure
3. **Bounded Recursion**: MAX_DEPTH=5 prevents infinite loops
4. **Context Compaction**: Automatic large-data management
5. **Error Reflection**: LLM diagnoses its own failures
6. **Memory Overseer**: Intelligent pre-execution context loading

These patterns could be applied to:
- Any REST API automation
- Multi-step data pipelines
- Research workflows
- Personal assistant tasks
- Complex goal decomposition problems
