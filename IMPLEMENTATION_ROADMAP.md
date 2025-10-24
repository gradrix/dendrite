# Implementation Roadmap: Simplified Task List Format

## 📋 Overview

This document provides a step-by-step implementation roadmap for the simplified task list format project.

## 🎯 Goals

- [x] Reduce instruction complexity by 70%
- [ ] Reduce LLM token usage by 40%
- [ ] Improve execution speed by 20%
- [ ] Add self-correction to all tasks
- [ ] Create unified execution model
- [ ] Maintain backward compatibility

## 📊 Progress Tracker

```
Planning & Design:    ████████████████████ 100% ✅
Implementation:       ░░░░░░░░░░░░░░░░░░░░   0%
Testing:              ░░░░░░░░░░░░░░░░░░░░   0%
Documentation:        ████████████████████ 100% ✅
Deployment:           ░░░░░░░░░░░░░░░░░░░░   0%
```

## 🗓️ Timeline

| Phase | Duration | Status | Start | End |
|-------|----------|--------|-------|-----|
| **Phase 0: Planning** | 1 day | ✅ Done | Oct 24 | Oct 24 |
| **Phase 1: Core Implementation** | 2 days | ⏳ Next | Oct 25 | Oct 26 |
| **Phase 2: Integration** | 1 day | 📅 Planned | Oct 27 | Oct 27 |
| **Phase 3: Migration** | 1 day | 📅 Planned | Oct 28 | Oct 28 |
| **Phase 4: Testing** | 1 day | 📅 Planned | Oct 29 | Oct 29 |
| **Phase 5: Deployment** | 1 day | 📅 Planned | Oct 30 | Oct 30 |

**Total Estimated Time**: 6 days (including planning)

---

## Phase 0: Planning & Design ✅ COMPLETE

### Deliverables
- [x] SIMPLIFICATION_PLAN.md (Full technical plan)
- [x] SIMPLIFIED_FORMAT_REFERENCE.md (User guide)
- [x] ARCHITECTURE_COMPARISON.md (Technical architecture)
- [x] SIMPLIFICATION_EXECUTIVE_SUMMARY.md (Summary)
- [x] strava_monitor_simplified_example.yaml (Example)
- [x] IMPLEMENTATION_ROADMAP.md (This file)

### Key Decisions Made
- ✅ 3-level format (ultra-simple, simple, advanced)
- ✅ Smart routing (V3 for simple, structured for complex)
- ✅ V3-style self-correction for all tasks
- ✅ Backward compatible with V2
- ✅ Auto-detection of format
- ✅ Gradual deprecation strategy

### Approval Status
- [x] Technical approach approved
- [x] Format specification approved
- [x] Implementation plan approved
- [ ] Stakeholder sign-off ⏳

---

## Phase 1: Core Implementation (2 days) ⏳ NEXT

### Day 1: Parser & Pattern Detection

#### Task 1.1: Create SimpleParser
**File**: `agent/instruction_parser_simple.py`

**Requirements**:
```python
class SimpleInstruction:
    """Parse simplified task list format."""
    
    def __init__(self, filepath: Path)
    def _load()  # Parse YAML
    def _validate()  # Validate structure
    def to_v3_goal() -> str  # Convert to V3 goal
    def needs_structured_execution() -> bool
    def is_ultra_simple() -> bool
```

**Features**:
- [ ] Parse ultra-simple format (goal only)
- [ ] Parse simple format (task list strings)
- [ ] Parse advanced format (task dicts with options)
- [ ] Validate structure and dependencies
- [ ] Auto-detect format type
- [ ] Convert simple to V3 goal when possible

**Tests**: `test_simple_parser.py`
- [ ] Test parse ultra-simple
- [ ] Test parse simple task list
- [ ] Test parse advanced tasks
- [ ] Test validation errors
- [ ] Test format detection
- [ ] Test V3 conversion

**Estimated Time**: 4 hours

#### Task 1.2: Create PatternDetector
**File**: `agent/pattern_detector.py`

**Requirements**:
```python
class PatternDetector:
    """Detect patterns in natural language tasks."""
    
    def detect_time_range(task: str) -> Optional[TimeRange]
    def detect_loop(task: str) -> Optional[str]
    def detect_condition(task: str) -> Optional[Condition]
    def map_to_tools(task: str, tools: List[Tool]) -> List[str]
```

**Features**:
- [ ] Detect time ranges ("last 24h", "yesterday", etc.)
- [ ] Detect loops ("for each", "all X")
- [ ] Detect conditions ("if", "when", "only if")
- [ ] Map natural language to tool hints
- [ ] Handle ambiguity with LLM fallback

**Tests**: `test_pattern_detector.py`
- [ ] Test time range detection
- [ ] Test loop detection
- [ ] Test condition detection
- [ ] Test tool mapping
- [ ] Test ambiguous cases

**Estimated Time**: 3 hours

#### Task 1.3: Enhance Tool Registry
**File**: `agent/tool_registry.py`

**Changes**:
```python
class Tool:
    def __init__(self, ..., nl_hints: List[str] = None):
        self.nl_hints = nl_hints or []

@tool(
    name="getMyActivities",
    nl_hints=[
        "get my activities",
        "fetch activities",
        "list activities"
    ]
)
```

**Features**:
- [ ] Add nl_hints parameter to Tool
- [ ] Update @tool decorator
- [ ] Add hints to existing tools
- [ ] Update tool_to_dict() method

**Estimated Time**: 1 hour

### Day 2: Executor & Router

#### Task 1.4: Create TaskExecutor
**File**: `agent/task_executor.py`

**Requirements**:
```python
class TaskExecutor:
    """Execute tasks with self-correction."""
    
    def __init__(self, ollama, registry, state_manager)
    def execute(self, instruction: SimpleInstruction)
    def _execute_structured(self, instruction)
    def _execute_task(self, task, context)
    def _self_correct_retry(self, task, error, attempt)
```

**Features**:
- [ ] Execute simple task list
- [ ] Execute advanced task list
- [ ] Self-correcting retry on errors (like V3)
- [ ] Auto time range calculation
- [ ] Auto loop detection and execution
- [ ] Auto state management
- [ ] Progress tracking and logging

**Tests**: `test_task_executor.py`
- [ ] Test simple task execution
- [ ] Test self-correction on error
- [ ] Test auto time calculation
- [ ] Test auto loop handling
- [ ] Test auto state save/load
- [ ] Test progress tracking

**Estimated Time**: 5 hours

#### Task 1.5: Create SmartRouter
**File**: `agent/smart_router.py`

**Requirements**:
```python
class SmartRouter:
    """Route to appropriate execution engine."""
    
    def route(self, instruction: SimpleInstruction) -> ExecutionEngine
    def should_use_v3(self, instruction) -> bool
```

**Features**:
- [ ] Detect ultra-simple instructions
- [ ] Route to V3 for ultra-simple
- [ ] Route to TaskExecutor for structured
- [ ] Decision logging

**Tests**: `test_smart_router.py`
- [ ] Test V3 routing
- [ ] Test structured routing
- [ ] Test edge cases

**Estimated Time**: 2 hours

### Day 1-2 Summary
- **Total Tasks**: 5
- **Estimated Time**: 15 hours (2 work days)
- **Key Deliverables**: Parser, Detector, Executor, Router
- **Risk Level**: Medium (core functionality)

---

## Phase 2: Integration (1 day)

### Day 3: Main.py Integration

#### Task 2.1: Update main.py
**File**: `main.py`

**Changes**:
```python
# Add new arguments
parser.add_argument('--simple', action='store_true')
parser.add_argument('--format', choices=['simple', 'v2', 'v3'], default='simple')

# Add new execution method
def execute_instruction_simple(self, instruction_name: str):
    # Load with SimpleParser
    # Create TaskExecutor
    # Execute with SmartRouter
    pass

# Update run_once
def run_once(self, format='simple'):
    # Detect format from file
    # Route to appropriate executor
    pass
```

**Features**:
- [ ] Add command-line flags
- [ ] Add execute_instruction_simple()
- [ ] Update run_once() with format detection
- [ ] Add auto-format detection
- [ ] Update help text
- [ ] Backward compatibility with v2/v3

**Tests**: `test_main_integration.py`
- [ ] Test --simple flag
- [ ] Test format auto-detection
- [ ] Test v2 backward compat
- [ ] Test v3 backward compat

**Estimated Time**: 4 hours

#### Task 2.2: Format Auto-Detection
**File**: `agent/format_detector.py`

**Requirements**:
```python
class FormatDetector:
    """Detect instruction format from YAML structure."""
    
    def detect(self, filepath: Path) -> Format
```

**Features**:
- [ ] Detect V2 format (has 'steps' key)
- [ ] Detect simplified format (has 'tasks' key)
- [ ] Detect V3 format (only 'goal' key)
- [ ] Handle ambiguous cases

**Tests**: `test_format_detector.py`
- [ ] Test V2 detection
- [ ] Test simplified detection
- [ ] Test V3 detection

**Estimated Time**: 2 hours

#### Task 2.3: Update Configuration
**File**: `config.yaml`

**Changes**:
```yaml
# Add format preference
agent:
  default_format: "simple"  # simple, v2, v3
  auto_detect_format: true
```

**Estimated Time**: 0.5 hours

### Day 3 Summary
- **Total Tasks**: 3
- **Estimated Time**: 6.5 hours (1 work day)
- **Key Deliverables**: Integration with main.py
- **Risk Level**: Low (glue code)

---

## Phase 3: Migration (1 day)

### Day 4: Documentation & Examples

#### Task 3.1: Convert strava_monitor_v2.yaml
**File**: `instructions/strava_monitor.yaml`

**Features**:
- [ ] Convert 130 lines → 40 lines
- [ ] Test functionality parity
- [ ] Add explanatory comments
- [ ] Keep v2 version as reference

**Estimated Time**: 2 hours

#### Task 3.2: Create MIGRATION_GUIDE.md
**File**: `MIGRATION_GUIDE.md`

**Contents**:
- [ ] V2 → Simplified conversion patterns
- [ ] Common patterns (time, loops, state)
- [ ] Step-by-step examples
- [ ] Automated conversion tool
- [ ] FAQ section

**Estimated Time**: 3 hours

#### Task 3.3: Update Documentation
**Files**: `README.md`, `V2_USAGE.md`, `QUICK_REFERENCE.md`

**Changes**:
- [ ] Update README.md with simplified examples
- [ ] Mark V2_USAGE.md as legacy
- [ ] Update QUICK_REFERENCE.md with new syntax
- [ ] Add "Getting Started" section
- [ ] Add migration notes

**Estimated Time**: 2 hours

#### Task 3.4: Create Example Instructions
**Files**: `instructions/examples/`

**Examples**:
- [ ] `simple_hello.yaml` - Ultra-simple
- [ ] `activity_check.yaml` - Simple task list
- [ ] `advanced_workflow.yaml` - Advanced features
- [ ] `migration_example.yaml` - Side-by-side comparison

**Estimated Time**: 1 hour

### Day 4 Summary
- **Total Tasks**: 4
- **Estimated Time**: 8 hours (1 work day)
- **Key Deliverables**: Migration guide, examples, updated docs
- **Risk Level**: Low (documentation)

---

## Phase 4: Testing (1 day)

### Day 5: Comprehensive Testing

#### Task 4.1: Unit Tests
**Files**: Various test files

**Coverage**:
- [ ] SimpleParser (90%+ coverage)
- [ ] PatternDetector (90%+ coverage)
- [ ] TaskExecutor (90%+ coverage)
- [ ] SmartRouter (90%+ coverage)
- [ ] FormatDetector (100% coverage)

**Estimated Time**: 3 hours

#### Task 4.2: Integration Tests
**File**: `test_integration.py`

**Tests**:
- [ ] Full workflow: Parse → Execute → Verify
- [ ] V2 backward compatibility
- [ ] V3 backward compatibility
- [ ] Format auto-detection
- [ ] Self-correction scenarios
- [ ] State persistence
- [ ] Error handling

**Estimated Time**: 3 hours

#### Task 4.3: Performance Tests
**File**: `test_performance.py`

**Metrics**:
- [ ] Token usage (V2 vs Simplified)
- [ ] Execution time (V2 vs Simplified)
- [ ] LLM call count
- [ ] Memory usage
- [ ] Generate performance report

**Estimated Time**: 2 hours

### Day 5 Summary
- **Total Tasks**: 3
- **Estimated Time**: 8 hours (1 work day)
- **Key Deliverables**: Test suite, performance report
- **Risk Level**: Low (testing)

---

## Phase 5: Deployment (1 day)

### Day 6: Release Preparation

#### Task 5.1: Beta Testing
- [ ] Test with real Strava monitor
- [ ] Test with small models (qwen3:4b)
- [ ] Test with scheduler
- [ ] Collect feedback
- [ ] Fix critical bugs

**Estimated Time**: 3 hours

#### Task 5.2: Final Documentation
- [ ] Release notes
- [ ] Changelog
- [ ] Deprecation notices
- [ ] Upgrade guide
- [ ] Blog post / announcement

**Estimated Time**: 2 hours

#### Task 5.3: Release
- [ ] Merge feature branch
- [ ] Tag release (v3.0.0)
- [ ] Update main branch
- [ ] Announce release

**Estimated Time**: 1 hour

#### Task 5.4: Post-Release
- [ ] Monitor for issues
- [ ] Respond to feedback
- [ ] Plan hotfixes if needed
- [ ] Schedule follow-up improvements

**Estimated Time**: 2 hours

### Day 6 Summary
- **Total Tasks**: 4
- **Estimated Time**: 8 hours (1 work day)
- **Key Deliverables**: Released v3.0.0
- **Risk Level**: Medium (first release)

---

## 📦 Deliverables Checklist

### Code
- [ ] `agent/instruction_parser_simple.py`
- [ ] `agent/pattern_detector.py`
- [ ] `agent/task_executor.py`
- [ ] `agent/smart_router.py`
- [ ] `agent/format_detector.py`
- [ ] Updated `agent/tool_registry.py`
- [ ] Updated `main.py`
- [ ] Updated `config.yaml`

### Instructions
- [ ] `instructions/strava_monitor.yaml` (simplified)
- [ ] `instructions/examples/simple_hello.yaml`
- [ ] `instructions/examples/activity_check.yaml`
- [ ] `instructions/examples/advanced_workflow.yaml`
- [ ] `instructions/examples/migration_example.yaml`

### Tests
- [ ] `test_simple_parser.py`
- [ ] `test_pattern_detector.py`
- [ ] `test_task_executor.py`
- [ ] `test_smart_router.py`
- [ ] `test_format_detector.py`
- [ ] `test_main_integration.py`
- [ ] `test_integration.py`
- [ ] `test_performance.py`

### Documentation
- [x] `SIMPLIFICATION_PLAN.md`
- [x] `SIMPLIFIED_FORMAT_REFERENCE.md`
- [x] `ARCHITECTURE_COMPARISON.md`
- [x] `SIMPLIFICATION_EXECUTIVE_SUMMARY.md`
- [x] `IMPLEMENTATION_ROADMAP.md` (this file)
- [ ] `MIGRATION_GUIDE.md`
- [ ] Updated `README.md`
- [ ] Updated `V2_USAGE.md` (mark legacy)
- [ ] Updated `QUICK_REFERENCE.md`
- [ ] `CHANGELOG.md` (v3.0.0 entry)
- [ ] `RELEASE_NOTES.md` (v3.0.0)

---

## 🎯 Success Criteria

### Must Have (Blocking)
- [ ] All unit tests pass (90%+ coverage)
- [ ] All integration tests pass
- [ ] V2 backward compatibility works
- [ ] V3 backward compatibility works
- [ ] strava_monitor.yaml works correctly
- [ ] Performance improvements verified
- [ ] Documentation complete

### Should Have (Important)
- [ ] Token usage reduced by 30%+
- [ ] Execution time reduced by 20%+
- [ ] Error recovery rate 70%+
- [ ] Learning time reduced by 80%+
- [ ] Migration guide with examples
- [ ] Performance report

### Nice to Have (Optional)
- [ ] Auto-converter tool (V2 → Simplified)
- [ ] Interactive tutorial
- [ ] Video walkthrough
- [ ] Community examples
- [ ] VS Code extension for syntax

---

## 🚧 Risks & Mitigation

### Risk 1: Implementation Complexity
**Probability**: Medium  
**Impact**: High  
**Mitigation**:
- Start with simplest features
- Incremental development
- Frequent testing
- Code reviews

### Risk 2: Performance Regressions
**Probability**: Low  
**Impact**: Medium  
**Mitigation**:
- Performance tests before/after
- Continuous benchmarking
- Profiling and optimization

### Risk 3: Breaking V2 Compatibility
**Probability**: Low  
**Impact**: High  
**Mitigation**:
- Keep V2 parser untouched
- Comprehensive backward compat tests
- Format auto-detection
- Gradual migration

### Risk 4: User Confusion During Transition
**Probability**: Medium  
**Impact**: Medium  
**Mitigation**:
- Clear documentation
- Migration guide
- Examples
- Deprecation warnings (not errors)

### Risk 5: LLM Misinterpretation
**Probability**: Medium  
**Impact**: Medium  
**Mitigation**:
- Tool nl_hints for disambiguation
- Fallback to explicit syntax
- Dry-run preview mode
- User can add details

---

## 📈 Metrics Dashboard

### Development Metrics
```
Code Coverage:       ░░░░░░░░░░░░░░░░░░░░   0% → Target: 90%
Tests Written:       ░░░░░░░░░░░░░░░░░░░░   0 → Target: 50+
Tests Passing:       ░░░░░░░░░░░░░░░░░░░░   0 → Target: 100%
Documentation:       ████████████████████ 100% → Target: 100%
```

### Performance Metrics
```
Token Reduction:     ░░░░░░░░░░░░░░░░░░░░   0% → Target: 40%
Speed Improvement:   ░░░░░░░░░░░░░░░░░░░░   0% → Target: 20%
Error Recovery:      ░░░░░░░░░░░░░░░░░░░░   0% → Target: 70%
Learning Time:       ░░░░░░░░░░░░░░░░░░░░   0% → Target: 88%
```

---

## 🔄 Daily Standup Template

### What did I do yesterday?
- [ ] Task X completed
- [ ] Progress on task Y

### What will I do today?
- [ ] Complete task Z
- [ ] Start task W

### Any blockers?
- [ ] Issue A needs resolution
- [ ] Waiting on B

---

## 📞 Communication Plan

### Daily Updates
- Post progress in team channel
- Update this roadmap document
- Flag blockers immediately

### Weekly Review
- Review metrics
- Adjust timeline if needed
- Plan next week's priorities

### Release Communication
- Announce to users
- Post in community
- Update all documentation
- Offer support for migration

---

## 🎉 Celebration Plan

### Milestones
- ✅ Planning complete → Team coffee ☕
- [ ] Phase 1 complete → Team lunch 🍕
- [ ] All tests passing → Happy hour 🍻
- [ ] Release v3.0.0 → Team dinner 🎉

---

## 📚 References

- [SIMPLIFICATION_PLAN.md](SIMPLIFICATION_PLAN.md) - Technical plan
- [SIMPLIFIED_FORMAT_REFERENCE.md](SIMPLIFIED_FORMAT_REFERENCE.md) - User guide
- [ARCHITECTURE_COMPARISON.md](ARCHITECTURE_COMPARISON.md) - Architecture
- [strava_monitor_v2.yaml](instructions/strava_monitor_v2.yaml) - Current format
- [strava_monitor_simplified_example.yaml](instructions/strava_monitor_simplified_example.yaml) - New format

---

**Status**: 📋 Planning Complete - Ready to Start Phase 1  
**Last Updated**: October 24, 2025  
**Next Review**: End of Phase 1 (Oct 26)  
**Version**: 1.0
