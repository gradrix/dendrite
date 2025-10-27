# Development Plan: Incremental Testing Strategy

Based on your ROADMAP.md and current codebase, here's a **testable, incremental** approach to build your Neural Engine.

## 🎯 Philosophy: Test-Driven Lego Bricks

Each phase builds on the previous, with **tests first**, ensuring every "Lego brick" works before composing them.

---

## Phase 0: Foundation - Intent Classification ⭐ **START HERE**

### Goal
Test that the first LLM interaction works: classifying user intent.

### What You're Testing
```
User Goal → IntentClassifierNeuron → LLM → "generative" or "tool_use"
```

### Files Involved
- `neural_engine/core/intent_classifier_neuron.py` ✅ (exists)
- `neural_engine/prompts/intent_classifier_prompt.txt` ✅ (exists)
- `neural_engine/tests/test_phase0_intent_classification.py` ✅ (created)

### Run Tests
```bash
./scripts/test.sh -k test_phase0
```

### Success Criteria
- ✅ Ollama connectivity works
- ✅ Prompt template loads
- ✅ LLM classifies simple questions
- ✅ Message bus stores intent
- ✅ Results are deterministic enough

### Why This Matters
- **Foundation for everything** - If this doesn't work, nothing else will
- **Tests LLM integration** - Verifies your Ollama setup
- **Validates prompt design** - You can iterate on prompts with tests
- **Establishes patterns** - All other neurons follow this structure

---

## Phase 1: Generative Pipeline

### Goal
Test the simplest end-to-end flow: conversational response.

### What You're Testing
```
"Tell me a joke" → IntentClassifier → "generative" 
                → GenerativeNeuron → LLM → Response
```

### New Files Needed
- `neural_engine/tests/test_phase1_generative_pipeline.py`

### Implementation Steps
1. **Test generative neuron in isolation**
   ```python
   def test_generative_neuron_simple_prompt(generative_neuron):
       goal = "Tell me a joke"
       result = generative_neuron.process("test-id", {"goal": goal})
       assert "response" in result
       assert len(result["response"]) > 0
   ```

2. **Test orchestrator with generative intent**
   ```python
   def test_orchestrator_generative_flow(orchestrator):
       result = orchestrator.execute("test-id", "What is Python?")
       assert "response" in result
   ```

### Success Criteria
- ✅ Generative neuron produces responses
- ✅ Orchestrator routes to generative pipeline
- ✅ End-to-end flow works for simple questions

---

## Phase 2: Tool Registry & Discovery

### Goal
Make tools discoverable and queryable. This is **critical** for the ROADMAP vision.

### What You're Testing
```
Startup → ToolRegistry.scan_tools() → Discovers tools in tools/ directory
        → Stores metadata in Redis
        → Can query available tools
```

### New Files Needed
- Update: `neural_engine/core/tool_registry.py` (enhance existing)
- Create: `neural_engine/tests/test_phase2_tool_registry.py`
- Create: `neural_engine/tools/example_tool.py` (simple test tool)

### Implementation Steps
1. **Enhance ToolRegistry**
   ```python
   class ToolRegistry:
       def scan_tools_directory(self, tools_path="neural_engine/tools"):
           """Scan tools/ directory and register all tools."""
           
       def register_tool(self, tool_class):
           """Register a tool with metadata."""
           
       def get_tool(self, tool_name):
           """Retrieve a tool by name."""
           
       def list_tools(self):
           """List all available tools."""
   ```

2. **Create test tool**
   ```python
   # tools/example_tool.py
   class ExampleTool:
       """A simple tool for testing."""
       name = "example"
       description = "Returns a greeting"
       
       def execute(self, name: str) -> dict:
           return {"success": True, "message": f"Hello, {name}!"}
   ```

3. **Test tool discovery**
   ```python
   def test_tool_registry_scans_directory(tool_registry):
       tool_registry.scan_tools_directory()
       tools = tool_registry.list_tools()
       assert len(tools) > 0
       assert "example" in [t["name"] for t in tools]
   ```

### Success Criteria
- ✅ Tool registry scans tools/ directory
- ✅ Tools are registered with metadata
- ✅ Can query available tools
- ✅ Tools persist across restarts (Redis)

---

## Phase 3: Tool Selection

### Goal
Test that the system can select the right tool for a goal.

### What You're Testing
```
"What time is it?" → IntentClassifier → "tool_use"
                   → ToolSelectorNeuron → LLM → Selects "time_tool"
```

### New Files Needed
- `neural_engine/tests/test_phase3_tool_selection.py`
- `neural_engine/tools/time_tool.py` (simple tool)

### Implementation Steps
1. **Create time tool**
   ```python
   from datetime import datetime
   
   class TimeTool:
       name = "get_current_time"
       description = "Returns the current time"
       
       def execute(self) -> dict:
           return {
               "success": True, 
               "time": datetime.now().isoformat()
           }
   ```

2. **Test tool selector**
   ```python
   def test_tool_selector_picks_time_tool(tool_selector):
       goal = "What time is it?"
       result = tool_selector.process("test-id", goal, depth=0)
       assert "tool_name" in result
       assert result["tool_name"] == "get_current_time"
   ```

### Success Criteria
- ✅ Tool selector chooses correct tool
- ✅ Prompt includes available tools list
- ✅ Selection is reasonable for given goal

---

## Phase 4: Code Generation & Execution

### Goal
Generate code to call a tool and execute it safely.

### What You're Testing
```
Tool: time_tool → CodeGenerator → Generates: `time_tool.execute()`
                → Sandbox → Executes code → Returns result
```

### New Files Needed
- `neural_engine/tests/test_phase4_code_execution.py`

### Implementation Steps
1. **Test code generator**
   ```python
   def test_code_generator_creates_tool_call(code_generator):
       tool_info = {
           "tool_name": "get_current_time",
           "tool_signature": "execute() -> dict"
       }
       result = code_generator.process("test-id", tool_info, depth=0)
       assert "code" in result
       assert "get_current_time" in result["code"]
   ```

2. **Test sandbox execution**
   ```python
   def test_sandbox_executes_simple_code(sandbox):
       code = "result = {'answer': 2 + 2}"
       result = sandbox.execute(code)
       assert result["answer"] == 4
   ```

### Success Criteria
- ✅ Code generator produces valid Python
- ✅ Sandbox executes code safely
- ✅ Results are returned correctly

---

## Phase 5: End-to-End Tool Use

### Goal
Complete the full tool use pipeline.

### What You're Testing
```
"What time is it?" → Intent → ToolSelect → CodeGen → Sandbox → Response
```

### New Files Needed
- `neural_engine/tests/test_phase5_tool_use_pipeline.py`

### Implementation Steps
1. **Test full pipeline**
   ```python
   def test_full_tool_use_pipeline(orchestrator):
       result = orchestrator.execute("test-id", "What time is it?")
       assert "time" in str(result)
       # Should contain current time
   ```

### Success Criteria
- ✅ Full pipeline works end-to-end
- ✅ Real tool is called
- ✅ Result is returned to user

---

## Phase 6: Neuron Spawning (Future)

### Goal
Implement the "dendrite" concept from your ROADMAP.

### What You're Testing
```
Goal with sub-goals → AgenticCoreNeuron → Spawns child neurons
                                        → Parallel execution
                                        → Result aggregation
```

### This is the advanced phase with:
- Sub-goal generation
- Parallel neuron execution
- Result merging
- Recursive decomposition

**Note:** Build this AFTER phases 0-5 are solid.

---

## How to Use This Plan

### 1. Start with Phase 0
```bash
# Run the foundation tests
./scripts/test-debug.sh -k test_phase0

# Press F5 in VS Code, select "Python: Debug Tests in Docker"
# Set breakpoints in intent_classifier_neuron.py
# Watch the LLM call in action!
```

### 2. Iterate on Prompts
If tests fail or results are inconsistent:
1. Edit `neural_engine/prompts/intent_classifier_prompt.txt`
2. Run tests again
3. See immediate feedback

### 3. Move to Next Phase
Only when Phase 0 tests pass reliably.

### 4. Build Tool Registry (Phase 2)
This is **critical** for your ROADMAP vision of persistent, discoverable tools.

---

## Testing Strategy

### Unit Tests (Fast)
Test each neuron in isolation:
```bash
./scripts/test-unit.sh
```

### Integration Tests (Slower)
Test full pipelines:
```bash
./scripts/test-integration.sh
```

### Debug Mode
```bash
./scripts/test-debug.sh -k test_phase0
# Press F5 in VS Code
```

---

## Current Status

- ✅ Phase 0: Test file created, ready to run
- ⏳ Phase 1: Generative pipeline exists, needs tests
- ⏳ Phase 2: Tool registry exists, needs enhancement + tests
- ⏳ Phase 3: Tool selector exists, needs tests
- ⏳ Phase 4: Code generator exists, needs tests
- ⏳ Phase 5: Orchestrator exists, needs end-to-end tests
- ❌ Phase 6: Not started (future)

---

## Next Steps

1. **Run Phase 0 tests NOW:**
   ```bash
   ./scripts/test.sh -k test_phase0
   ```

2. **Fix any issues** with prompts or connections

3. **Move to Phase 1** when confident

4. **Build tool registry properly** (Phase 2) - This unlocks the ROADMAP vision

---

## Why This Approach?

✅ **Incremental** - Each phase builds on previous  
✅ **Testable** - Every component has tests  
✅ **Debuggable** - Can step through with VS Code  
✅ **Aligned with ROADMAP** - Each phase moves toward the vision  
✅ **Confidence** - Know each piece works before composing  

**You can't build a skyscraper without testing each floor!** 🏗️
