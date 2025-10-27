# 🎯 Quick Start: Debugging Tests with F5

## The Simple Way (Recommended)

### Step 1: Open VS Code in your project
```bash
cd /home/gradrix/repos/center
code .
```

### Step 2: Press F5
Just press **F5** on your keyboard!

### Step 3: Select debug configuration
From the dropdown at the top, choose:
- **"Python: Debug Tests in Docker"** - Runs all tests
- **"Python: Debug Current Test File in Docker"** - Runs only the open file

### Step 4: Debug!
- Container starts automatically
- Debugger attaches
- Your breakpoints work!

## Visual Workflow

```
┌─────────────────────────────────────────────┐
│  You: Press F5                              │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  VS Code: "Which debug config?"             │
│  ○ Python: Debug Tests in Docker ⭐         │
│  ○ Python: Debug Current Test File          │
│  ○ Python: Attach to Docker (manual)        │
│  ○ Python: Debug Tests Locally              │
└─────────────────┬───────────────────────────┘
                  │ You select one
                  ▼
┌─────────────────────────────────────────────┐
│  VS Code Task: Runs ./scripts/test-debug.sh │
│  - Starts Redis & Ollama                    │
│  - Builds test container                    │
│  - Starts debugpy server on port 5678       │
└─────────────────┬───────────────────────────┘
                  │ Waits for "ready" signal
                  ▼
┌─────────────────────────────────────────────┐
│  VS Code Debugger: Connects to port 5678    │
│  - Maps local files ↔ container paths       │
│  - Your breakpoints are now active          │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Tests run and pause at your breakpoints!   │
│  - Inspect variables                        │
│  - Step through code (F10, F11)             │
│  - Use Debug Console                        │
└─────────────────────────────────────────────┘
```

## Setting Breakpoints

**Before** pressing F5:
1. Open any test file (e.g., `neural_engine/tests/test_ollama_client.py`)
2. Click in the left gutter (red dot appears)
3. Press F5
4. Tests run and pause at your breakpoint!

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **F5** | Start debugging or continue |
| **F9** | Toggle breakpoint |
| **F10** | Step over (next line) |
| **F11** | Step into (go into function) |
| **Shift+F11** | Step out (exit function) |
| **Shift+F5** | Stop debugging |
| **Ctrl+Shift+F5** | Restart debugging |

## Debug Panels

When debugging, you'll see these panels:

1. **VARIABLES** - All local variables and their values
2. **WATCH** - Add expressions to monitor (e.g., `len(activities)`)
3. **CALL STACK** - Function call chain
4. **BREAKPOINTS** - All your breakpoints
5. **DEBUG CONSOLE** - Interactive Python shell (try typing variable names!)

## Common Scenarios

### Debug One Specific Test
1. Open the test file (e.g., `test_ollama_client.py`)
2. Set breakpoint in the test function
3. Press F5 → "Python: Debug Current Test File in Docker"

### Debug All Tests
1. Press F5 → "Python: Debug Tests in Docker"
2. Tests run in order, pausing at any breakpoints

### Debug Integration Tests Only
1. Press F5 → "Python: Debug Tests in Docker"
2. When task panel opens, you'll see the command
3. It's running: `./scripts/test-debug.sh`
4. You can manually edit the task to add: `-m integration`

### Quick Local Debugging (No Docker)
1. Press F5 → "Python: Debug Tests Locally"
2. Much faster, but runs on your machine (not in Docker)
3. Good for quick iterations

## Troubleshooting

### F5 does nothing
- Make sure you have the Python extension installed
- Open a Python file first

### "No debug configuration"
- The `.vscode/launch.json` file should exist
- Try reopening the folder: File → Open Folder

### Container starts but debugger doesn't attach
- Check the terminal output for errors
- Look for "Waiting for client to attach..."
- Try "Python: Attach to Docker (manual)" from F5 menu

### Breakpoints are gray circles (not solid red)
- Debugger hasn't attached yet
- Wait for container to start
- Check terminal for "Waiting for client to attach..."

## Pro Tips

### 💡 Use Debug Console
While paused, type in Debug Console:
```python
>>> variable_name           # See value
>>> dir(obj)               # See attributes  
>>> len(my_list)           # Evaluate expressions
>>> import pprint; pprint.pprint(data)  # Pretty print
```

### 💡 Conditional Breakpoints
Right-click on breakpoint → Edit Breakpoint:
```python
iteration > 5              # Only break after 5th iteration
len(results) == 0          # Only break when empty
```

### 💡 Logpoints (Non-breaking logs)
Right-click gutter → Add Logpoint:
```
Activity: {activity['name']} at iteration {i}
```
Logs to Debug Console without stopping!

### 💡 Watch Expressions
Add to WATCH panel:
```python
len(activities)
result['success']
redis_client.dbsize()
```
Updates automatically as you step through!

## What's Next?

See `docs/DEBUGGING.md` for advanced techniques:
- Remote debugging strategies
- Performance tuning
- Debugging specific scenarios
- Docker debugging internals

---

**TL;DR: Press F5, select "Python: Debug Tests in Docker", set breakpoints, debug!** 🎉
