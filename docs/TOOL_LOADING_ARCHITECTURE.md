# Tool Loading & Evolution: Admin vs AI Tools

## ✅ Fixed Configuration Issue

**Problem Found**: Docker Compose had conflicting volume mounts:
- `.:/app` (bind mount - source code)
- `ai_tools:/app/neural_engine/tools` (named volume - **overrode** bind mount!)

**Result**: Admin-created tools were hidden, AI-created tools would be isolated in Docker volume.

**Solution**: Removed `ai_tools` volume mount. Now everything uses `.:/app` bind mount.

---

## Current Tool Loading Behavior

### Architecture
```
neural_engine/tools/
├── __init__.py
├── base_tool.py (abstract)
├── hello_world_tool.py (admin-created)
├── memory_read_tool.py (admin-created)
├── memory_write_tool.py (admin-created)
├── python_script_tool.py (admin-created)
├── ... (7 Strava tools - admin-created)
└── ai_generated_tool.py (AI-created - coming in Phase 7!)
```

---

## ✅ Scenario 1: Admin Adds New Tool (Manual Creation)

### Steps:
1. **Create file on host**:
   ```bash
   # On your machine
   vi neural_engine/tools/my_awesome_tool.py
   ```

2. **File immediately visible in container**:
   - Bind mount `.:/app` makes all host files instantly available
   - No rebuild needed!

3. **Load new tool at runtime**:
   ```python
   # In running container/code
   tool_registry.refresh()  # Scans tools/ directory again
   ```

4. **Tool now available**:
   ```python
   tool = tool_registry.get_tool("my_awesome_tool")
   # Ready to use!
   ```

### Alternative: Restart Container
- New tools auto-load on startup (ToolRegistry.__init__ calls refresh())
- But **refresh() is better** - no restart needed!

---

## ✅ Scenario 2: AI Creates New Tool (ToolForge - Phase 7)

### Steps:
1. **User asks**: "Create a tool that calculates prime numbers"

2. **ToolForgeNeuron generates**:
   ```python
   # AI writes this code
   class PrimeCheckerTool(BaseTool):
       def get_tool_definition(self):
           return {
               "name": "prime_checker",
               "description": "Check if a number is prime",
               "parameters": [{"name": "n", "type": "int", "required": True}]
           }
       
       def execute(self, n):
           # AI-generated prime checking logic
           return {"is_prime": self._check_prime(n)}
   ```

3. **ToolForge writes file**:
   ```python
   # Inside container
   with open("neural_engine/tools/prime_checker_tool.py", "w") as f:
       f.write(generated_code)
   ```

4. **File appears on host**:
   - Bind mount `.:/app` syncs container → host
   - You can see `prime_checker_tool.py` in your editor immediately!

5. **ToolForge auto-refreshes registry**:
   ```python
   tool_registry.refresh()  # Automatic after file write
   ```

6. **Tool immediately available**:
   ```python
   # No restart needed!
   tool = tool_registry.get_tool("prime_checker")
   ```

---

## Key Insight: No Distinction Between Admin & AI Tools! 🎯

### ToolRegistry behavior:
```python
def _scan_and_load(self):
    for root, _, files in os.walk(self.tool_directory):
        for filename in files:
            if filename.endswith(".py") and \
               filename != "__init__.py" and \
               filename != "base_tool.py":
                self._load_tool(root, filename)
```

**It doesn't care who created the file!**
- Admin-created tool: `hello_world_tool.py` → Loaded ✅
- AI-created tool: `prime_checker_tool.py` → Loaded ✅

---

## System Evolution: How It Works

### Initial State (Phase 0-5):
```
tools/
├── hello_world_tool.py (admin)
├── memory_read_tool.py (admin)
└── memory_write_tool.py (admin)

ToolRegistry: 3 tools available
```

### After AI Creates Tool (Phase 7):
```
tools/
├── hello_world_tool.py (admin)
├── memory_read_tool.py (admin)
├── memory_write_tool.py (admin)
└── prime_checker_tool.py (AI) ← NEW!

ToolRegistry: 4 tools available
```

### Next Request:
```
User: "Is 17 prime?"
    ↓
Tool Selector: Finds "prime_checker" (AI-created!)
    ↓
Code Generator: Generates code to call prime_checker
    ↓
Sandbox: Executes AI-generated code calling AI-generated tool
    ↓
User: "Yes, 17 is prime" ✅
```

**The system just evolved itself!** 🚀

---

## Persistence & Durability

### ✅ Tools Survive Container Restarts
- Files on host filesystem (bind mount)
- ToolRegistry reloads on startup
- AI-created tools are permanent

### ✅ Tools Visible in Git
- `neural_engine/tools/` is in your repo
- AI-created tools can be committed
- You can version control AI improvements!

### ✅ Tools Editable by Humans
- Open `ai_generated_tool.py` in editor
- Fix bugs, improve logic
- Save → call `tool_registry.refresh()` → updated!

---

## Self-Evolution Workflow

### Cycle 1: Human Creates Foundation
```
Admin: Creates hello_world, memory_read, memory_write
System: Has 3 basic tools
```

### Cycle 2: AI Creates Specialized Tools
```
User: "Create a tool for prime numbers"
AI: Writes prime_checker_tool.py
System: Now has 4 tools (including AI-created!)
```

### Cycle 3: AI Uses AI-Created Tools
```
User: "Is 17 prime?"
AI: Uses prime_checker (which AI created!)
Result: "Yes, 17 is prime"
```

### Cycle 4: AI Improves AI-Created Tools
```
User: "Make prime_checker faster"
AI: Modifies prime_checker_tool.py
System: Tool improved (AI improved itself!)
```

---

## Technical Details

### ToolRegistry.refresh() Implementation:
```python
def refresh(self):
    self.tools = {}  # Clear existing tools
    self._scan_and_load()  # Re-scan directory
    
    # Result: All tools (admin + AI) reloaded
    # Tool metadata preserved (_module_name, _class_name)
```

### When to Call refresh():
1. **After AI creates tool** (ToolForge - automatic)
2. **After admin adds tool** (manual - via API or restart)
3. **After modifying tool** (manual - to reload changes)
4. **Never needed on container start** (auto-called in __init__)

---

## Benefits of This Architecture

### 1. **True Self-Evolution**
- AI can extend its own capabilities
- No special "AI tool" vs "admin tool" distinction
- System capabilities grow over time

### 2. **Human-AI Collaboration**
- Humans create foundational tools
- AI creates specialized tools
- Humans can review/improve AI tools
- Version control everything!

### 3. **No Rebuild Required**
- Add tool → refresh() → available
- Fast iteration cycle
- Testable in real-time

### 4. **Transparent & Debuggable**
- All tools are Python files on disk
- Can read AI-generated code
- Can test, modify, improve
- Git history of evolution!

---

## Security Considerations (Future)

### Current State (Phase 5):
- ✅ Sandbox executes tool code safely
- ✅ Errors caught and reported
- ⚠️ No validation of AI-generated tool code

### Phase 7 (ToolForge):
- Need to add: Code validation before writing file
- Need to add: Test execution before registration
- Need to add: Rollback if tool fails
- Need to add: Human approval for sensitive operations

---

## Summary

**The system treats all tools equally:**
- Admin-created tools load from filesystem
- AI-created tools load from filesystem
- `tool_registry.refresh()` makes new tools available instantly
- No container rebuild needed
- System can truly evolve!

**This enables the ROADMAP vision:**
> "The agent is part of a larger ecosystem that allows it to monitor its own performance and autonomously improve its own components."

**We're building that ecosystem!** 🌟
