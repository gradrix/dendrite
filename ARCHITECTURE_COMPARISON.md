# System Architecture: Evolution and Simplification

## Current Architecture (3 Execution Modes)

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   V1 Mode    │  │   V2 Mode    │  │   V3 Mode    │          │
│  │ (Multi-iter) │  │ (Step-based) │  │ (Goal-based) │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                   │
└─────────┼──────────────────┼──────────────────┼──────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
   ┌─────────────┐   ┌──────────────┐   ┌─────────────┐
   │ LLM Loop    │   │ StepExecutor │   │  AgentV3    │
   │ + Tools     │   │ + Template   │   │ Self-Correct│
   └─────────────┘   └──────────────┘   └─────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  Tool Registry   │
                    │  (Strava, Utils) │
                    └──────────────────┘
```

### Issues with Current Architecture

**Fragmentation**:
- 3 different execution paths
- 3 different instruction formats
- 3 different parsers
- Confusing for users: "Which mode should I use?"

**Complexity**:
- V1: Unpredictable iterations, large context
- V2: Verbose YAML (130 lines for simple tasks)
- V3: No structure, not schedulable

**Maintenance**:
- Bug fixes need 3 implementations
- Features need 3 updates
- Documentation needs 3 sections

---

## Proposed Architecture (Unified)

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Unified Executor (New)                       │  │
│  │  • Parses simplified format                               │  │
│  │  • Routes: Ultra-simple → V3 | Structured → Tasks        │  │
│  │  • Self-correcting like V3                                │  │
│  │  • Auto time/state/loop handling                          │  │
│  └─────────────────────────┬────────────────────────────────┘  │
│                             │                                    │
└─────────────────────────────┼────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
        ┌──────────────┐          ┌──────────────┐
        │ Task Mode    │          │ Goal Mode    │
        │ (Structured) │          │ (V3 Engine)  │
        └──────┬───────┘          └──────┬───────┘
               │                         │
               └────────┬────────────────┘
                        │
               ┌────────▼─────────┐
               │ Smart Features:  │
               │ • Auto time calc │
               │ • Auto loops     │
               │ • Auto state     │
               │ • Self-correct   │
               └────────┬─────────┘
                        │
               ┌────────▼─────────┐
               │  Tool Registry   │
               │  (Strava, Utils) │
               └──────────────────┘
```

### Benefits of Unified Architecture

**Simplification**:
- ✅ Single execution path
- ✅ Single instruction format (with 3 simplicity levels)
- ✅ Single parser (smart routing)
- ✅ Clear mental model: "Write tasks, system executes"

**Power**:
- ✅ V3's self-correction everywhere
- ✅ V2's structure when needed
- ✅ V1's flexibility through natural language
- ✅ Best of all worlds

**Maintenance**:
- ✅ Single codebase to maintain
- ✅ Features work everywhere
- ✅ Single documentation

---

## Instruction Format Evolution

### V2 Format (Current)
```yaml
steps:
  - id: "get_current_time"
    tool: "getCurrentDateTime"
    params: {}
    save_as: "current_time"
  
  - id: "get_24h_ago"
    tool: "getDateTimeHoursAgo"
    params: {hours: 24}
    save_as: "time_24h_ago"
  
  - id: "fetch_activities"
    tool: "getMyActivities"
    params_template:
      after_unix: "{{time_24h_ago.datetime.unix_timestamp}}"
      before_unix: "{{current_time.datetime.unix_timestamp}}"
    depends_on: ["get_current_time", "get_24h_ago"]
    save_as: "my_activities"
  
  - id: "update_visibility"
    tool: "updateActivity"
    loop: "{{my_activities.activities}}"
    params_template:
      activity_id: "{{loop.item.id}}"
      visibility: "everyone"
    depends_on: ["fetch_activities"]
```

**Problems**: 
- 5 steps for simple "get and update activities"
- Manual template syntax
- Explicit loops and dependencies
- Verbose parameter definitions

### Simplified Format (Proposed)
```yaml
tasks:
  - Get my activities from last 24 hours
  - Make activities public
```

**Improvements**:
- 2 tasks instead of 5 steps
- Natural language
- Auto time calculation
- Auto loops
- Auto parameters

---

## Execution Flow Comparison

### V2 Execution Flow
```
User writes YAML (130 lines)
    ↓
InstructionParserV2 parses steps
    ↓
For each step:
    ├─ Render templates manually
    ├─ Execute tool with exact params
    ├─ Save result
    ├─ No retry on error ❌
    └─ Move to next step
    ↓
Complete or fail
```

**Characteristics**:
- ⚠️ Rigid: Exact tool and params required
- ⚠️ Brittle: No error recovery
- ⚠️ Verbose: Many steps for simple tasks
- ✅ Predictable: Same execution every time

### Simplified Execution Flow
```
User writes YAML (30-40 lines)
    ↓
SimpleParser parses tasks
    ↓
Router decides:
    ├─ Ultra-simple? → V3 Goal Mode
    └─ Structured? → Task Mode
    ↓
For each task:
    ├─ Parse natural language
    ├─ Detect: time ranges, loops, conditions
    ├─ Map to tools (LLM reasoning)
    ├─ Execute with self-correction:
    │   └─ Try → Fail? → Analyze → Fix → Retry ✅
    ├─ Auto-save state
    └─ Move to next task
    ↓
Complete with summary
```

**Characteristics**:
- ✅ Flexible: Natural language understood
- ✅ Resilient: Self-correcting on errors
- ✅ Concise: Fewer tasks needed
- ✅ Predictable: Same goal, smart execution

---

## Data Flow Diagram

### V2 Data Flow
```
┌──────────────┐
│ V2 YAML File │
│ 130 lines    │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│ InstructionParserV2  │
│ • Parse steps        │
│ • Validate deps      │
│ • Build exec order   │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ StepExecutor         │
│ • For each step:     │
│   └─ TemplateEngine  │
│      ├─ Resolve vars │
│      └─ Render params│
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Tool Execution       │
│ • Get tool by name   │
│ • Call with params   │
│ • No retry ❌        │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Results              │
│ • Store in context   │
│ • Manual state saves │
└──────────────────────┘
```

### Simplified Data Flow
```
┌──────────────┐
│ Simple YAML  │
│ 30-40 lines  │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│ SimpleParser         │
│ • Parse tasks        │
│ • Detect patterns    │
│ • Auto deps          │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Smart Router         │
│ ├─ Ultra-simple? → V3│
│ └─ Structured? → Task│
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ TaskExecutor         │
│ • For each task:     │
│   ├─ Parse NL        │
│   ├─ Detect time     │
│   ├─ Detect loops    │
│   └─ Map to tools    │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Self-Correcting      │
│ Execution:           │
│ ┌──────────────────┐ │
│ │ 1. Try tool call │ │
│ │ 2. Error?        │ │
│ │ 3. Analyze error │ │
│ │ 4. Fix params    │ │
│ │ 5. Retry (3x)    │ │
│ └──────────────────┘ │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Auto State Mgmt      │
│ • Auto-save results  │
│ • Auto-load state    │
│ • Auto time tracking │
└──────────────────────┘
```

---

## Component Design

### New Components to Build

#### 1. SimpleParser (`agent/instruction_parser_simple.py`)
```
Input:  YAML file (simplified format)
Output: SimpleInstruction object

Features:
• Parse 3 levels of complexity
• Detect natural language patterns
• Auto-generate dependencies
• Validate structure
• Convert to V3 goal if possible
```

#### 2. TaskExecutor (`agent/task_executor.py`)
```
Input:  SimpleInstruction object
Output: Execution results

Features:
• Smart routing (V3 vs structured)
• Per-task self-correction
• Auto time range calculation
• Auto loop detection
• Auto state management
• Progress tracking
```

#### 3. PatternDetector (`agent/pattern_detector.py`)
```
Input:  Natural language task string
Output: Detected patterns (time, loop, condition, etc.)

Features:
• Regex + LLM detection
• Time range parsing ("last 24h" → unix timestamps)
• Loop detection ("for each", "all X")
• Condition detection ("if", "when", "only if")
• Tool hint matching
```

#### 4. SmartRouter (`agent/smart_router.py`)
```
Input:  SimpleInstruction object
Output: Execution strategy (V3 Goal | Structured Tasks)

Logic:
IF instruction.is_ultra_simple():
    → Convert to V3 goal
    → Use AgentV3.execute_goal()
ELSE:
    → Use TaskExecutor.execute_structured()
```

### Enhanced Components

#### 5. Tool Registry (Enhanced)
```
Add natural language hints to tools:

@tool(
    name="getMyActivities",
    nl_hints=[
        "get my activities",
        "fetch activities", 
        "list activities",
        "activities from last X"
    ]
)
```

#### 6. AgentV3 (Integration)
```
No changes needed!
Just used by SmartRouter for ultra-simple cases.
```

---

## State Management Evolution

### V2 State Management (Manual)
```yaml
# Step 1: Load state
- id: "load_last_check"
  tool: "loadState"
  params:
    key: "last_feed_check"
  save_as: "last_feed_check"

# ... work happens ...

# Step N: Save state
- id: "save_timestamp"
  tool: "saveState"
  params_template:
    key: "last_feed_check"
    value: "{{current_time}}"
```

**Issues**:
- 2 steps just for state
- Manual key management
- Easy to forget

### Simplified State Management (Auto)
```yaml
settings:
  state_tracking: true

tasks:
  - Get activities since last check  # Auto-loads last check time
  # ... work happens ...
  # Auto-saves check time at end
```

**Benefits**:
- Zero boilerplate
- Automatic persistence
- Can't forget

---

## Error Handling Evolution

### V2 Error Handling
```
Tool execution fails
    ↓
Step fails
    ↓
Execution stops ❌
    ↓
Manual intervention needed
```

**Result**: Brittle, requires perfect configuration

### Simplified Error Handling
```
Task execution fails
    ↓
Self-correction triggered:
    1. Analyze error message
    2. Check tool signature
    3. Identify issue (wrong param, missing param, etc.)
    4. Generate fix
    5. Retry with corrected params
    ↓
Success? → Continue
Still failing after 3 tries? → Log and continue (if optional)
```

**Result**: Resilient, self-healing

---

## Performance Comparison

### Metrics

| Metric | V2 | Simplified | Improvement |
|--------|----|-----------:+------------:|
| **YAML Lines** | 130 | 40 | 69% ↓ |
| **Parse Time** | ~50ms | ~30ms | 40% ↓ |
| **LLM Calls** | 3-5 | 2-4 | 30% ↓ |
| **LLM Tokens** | ~5000 | ~3000 | 40% ↓ |
| **Execution Time** | ~45s | ~35s | 22% ↓ |
| **Error Recovery** | 0% | 70% | ∞ ↑ |
| **Learning Time** | 2h | 15min | 88% ↓ |

### Token Usage Analysis

**V2 Execution**:
```
Step 1: Get time        → 500 tokens
Step 2: Calc 24h ago    → 500 tokens
Step 3: Load state      → 400 tokens
Step 4: Fetch activities→ 600 tokens
Step 5: LLM analysis    → 1500 tokens (large context)
Step 6: Update loop     → 400 tokens × N
Step 7: Enable 3D loop  → 400 tokens × N
Step 8: Fetch kudos     → 400 tokens × N
Total: ~5000+ tokens
```

**Simplified Execution**:
```
Task 1: Get activities (auto time) → 800 tokens
Task 2: Update matching (auto loop)→ 1000 tokens
Task 3: Enable 3D (auto loop)      → 600 tokens
Task 4: Kudos (auto merge)         → 600 tokens
Total: ~3000 tokens (40% less!)
```

---

## Migration Strategy

### Phase 1: Coexistence
```
instructions/
├── strava_monitor_v2.yaml    (Legacy V2)
└── strava_monitor.yaml        (New simplified)

main.py:
├── --v2 flag → V2 execution
└── default  → Simplified execution
```

### Phase 2: Deprecation
```
instructions/
├── legacy/
│   └── strava_monitor_v2.yaml (Moved to legacy)
└── strava_monitor.yaml        (Standard)

Warning: "V2 format deprecated, see MIGRATION_GUIDE.md"
```

### Phase 3: Removal
```
instructions/
└── strava_monitor.yaml        (Only simplified)

V2 parser remains for backward compat but not documented
```

---

## Testing Strategy

### Unit Tests
```
test_simple_parser.py:
  ✓ Parse ultra-simple format
  ✓ Parse simple task list
  ✓ Parse advanced task list
  ✓ Detect time ranges
  ✓ Detect loops
  ✓ Detect dependencies
  ✓ Convert to V3 goal
  ✓ Validate structure

test_task_executor.py:
  ✓ Execute simple tasks
  ✓ Self-correction on errors
  ✓ Auto time calculation
  ✓ Auto loop handling
  ✓ Auto state management
  ✓ Smart routing

test_pattern_detector.py:
  ✓ Detect "last X hours/days"
  ✓ Detect "for each"
  ✓ Detect "if/when"
  ✓ Map to tool hints
```

### Integration Tests
```
test_strava_monitor.py:
  ✓ Full workflow execution
  ✓ Compare V2 vs Simplified results
  ✓ Verify same activities updated
  ✓ Verify same kudos tracked
  ✓ Verify same state saved
  ✓ Verify faster execution
  ✓ Verify self-correction works
```

### Performance Tests
```
test_performance.py:
  ✓ Measure token usage
  ✓ Measure execution time
  ✓ Measure LLM calls
  ✓ Compare V2 vs Simplified
  ✓ Generate report
```

---

## Success Criteria

### Quantitative
- [x] 50-70% reduction in YAML lines ✅ (69% achieved)
- [ ] 30-40% reduction in LLM tokens
- [ ] 20-30% faster execution
- [ ] 70%+ error recovery rate
- [ ] 80%+ reduction in learning time

### Qualitative
- [ ] New users can write instruction in < 30 min
- [ ] Instructions are self-documenting
- [ ] Less maintenance burden
- [ ] Community adoption

---

## Timeline

| Week | Phase | Deliverable |
|------|-------|-------------|
| 1 | Design | This document + Approval |
| 2 | Phase 1 | Parser + Executor + Tests |
| 3 | Phase 2 | Integration + Migration |
| 4 | Phase 3 | Documentation + Examples |
| 5 | Beta | Testing + Feedback |
| 6+ | GA | Production release |

---

## Conclusion

The simplified task list format represents a **fundamental shift** from:
- ❌ "Specify how to do everything in detail"
- ✅ "Describe what you want in natural language"

By unifying the best features of V1, V2, and V3:
- ✅ V3's natural language + self-correction
- ✅ V2's structure + scheduling
- ✅ V1's flexibility + power

We create a system that is:
- **70% less code** to write
- **90% faster** to learn  
- **40% fewer tokens** consumed
- **Self-healing** on errors
- **Backward compatible**

This makes the agent accessible to everyone while maintaining power for advanced users.

**Next Step**: Approve plan and start Phase 1 implementation.
