# Debugging Tests in Docker with VS Code

This guide explains how to attach VS Code's debugger to tests running inside Docker containers.

## Quick Start

1. **Start tests in debug mode:**
   ```bash
   ./scripts/test-debug.sh
   ```

2. **Attach VS Code debugger:**
   - Press `F5` in VS Code
   - Select `Python: Attach to Docker` from the dropdown
   - Or go to Run → Start Debugging

3. **Set breakpoints and debug!**
   - Click in the left gutter of any Python file to set breakpoints
   - Debugger will pause when breakpoints are hit
   - Inspect variables, step through code, etc.

## How It Works

### The Stack

```
┌─────────────────────────────────────┐
│   VS Code (your machine)             │
│   - Breakpoints                      │
│   - Variable inspection              │
│   - Step through controls            │
└──────────────┬──────────────────────┘
               │ Debug Adapter Protocol (DAP)
               │ Port 5678
               ▼
┌─────────────────────────────────────┐
│   Docker Container (test container)  │
│   - Python debugpy server            │
│   - Running pytest                   │
│   - Your code                        │
└─────────────────────────────────────┘
```

### Path Mapping

The `.vscode/launch.json` configuration maps paths:
```json
"pathMappings": [
  {
    "localRoot": "${workspaceFolder}",  // /home/gradrix/repos/center
    "remoteRoot": "/app"                 // Inside container
  }
]
```

This lets VS Code translate breakpoints in your local files to the container paths.

## Debug Configurations

### 1. Python: Attach to Docker (Recommended)
- **Use for**: Debugging tests in Docker (production-like environment)
- **Pros**: Same environment as CI/CD, isolated
- **Cons**: Slightly slower startup

**Steps:**
```bash
# Terminal 1
./scripts/test-debug.sh

# VS Code: Press F5 → "Python: Attach to Docker"
```

### 2. Python: Debug Tests Locally
- **Use for**: Quick debugging iterations
- **Pros**: Fast, no Docker overhead
- **Cons**: Requires local Python setup, may behave differently

**Steps:**
1. Open test file in VS Code
2. Press F5
3. Select "Python: Debug Tests Locally"

## Debugging Workflow

### Basic Debugging

1. **Set a breakpoint** - Click left gutter or press F9
2. **Start debugging** - `./scripts/test-debug.sh` + F5
3. **Wait for hit** - Execution pauses at breakpoint
4. **Inspect state**:
   - Hover over variables
   - Check VARIABLES panel
   - Use DEBUG CONSOLE: `print(variable_name)`

### Step Through Code

- **F5** - Continue (run to next breakpoint)
- **F10** - Step Over (execute current line, don't go into functions)
- **F11** - Step Into (go inside function calls)
- **Shift+F11** - Step Out (exit current function)
- **Shift+F5** - Stop debugging

### Advanced Techniques

#### Conditional Breakpoints
Right-click breakpoint → Edit Breakpoint → Add condition:
```python
iteration > 5  # Only break after 5th iteration
```

#### Logpoints
Right-click in gutter → Add Logpoint:
```python
Current value: {variable_name}
```
Logs without stopping execution.

#### Debug Console
While paused, use Debug Console to:
```python
>>> variable_name
>>> dir(obj)
>>> obj.method()
```

## Debugging Specific Tests

### Run one test file
```bash
./scripts/test-debug.sh neural_engine/tests/test_ollama_client.py
```

### Run specific test function
```bash
./scripts/test-debug.sh -k test_generate_text
```

### Run with markers
```bash
./scripts/test-debug.sh -m integration  # Only integration tests
```

## Troubleshooting

### "Connection refused" on port 5678
**Problem**: Container not exposing port or not running

**Solution**:
```bash
# Check if port is exposed
docker compose ps
docker port <container_name>

# Restart with fresh build
docker compose build tests
./scripts/test-debug.sh
```

### Breakpoints not hitting
**Problem**: Path mapping incorrect or code not matching

**Solution**:
1. Check `.vscode/launch.json` pathMappings
2. Ensure container has mounted source: `volumes: [".:/app"]`
3. Rebuild container: `docker compose build tests`

### "justMyCode" vs library debugging
**Default**: `"justMyCode": false` - debugs library code too
**Change to** `"justMyCode": true` - only your code

Edit `.vscode/launch.json`:
```json
"justMyCode": true  // Skip library code
```

### Tests timeout while debugging
**Problem**: Default pytest timeout while paused at breakpoint

**Solution**: Use longer timeout or disable:
```bash
./scripts/test-debug.sh --timeout=300  # 5 minutes
```

## Performance Tips

### Faster Rebuilds
Use `.dockerignore` to exclude unnecessary files:
```
__pycache__/
*.pyc
.git/
node_modules/
```

### Debug Locally for Speed
For quick iterations without Docker overhead:
```bash
# Ensure services running
docker compose up -d redis ollama

# Debug locally
python -m debugpy --listen 5678 --wait-for-client -m pytest -v
```

Then attach VS Code debugger.

## VS Code Extensions

Recommended extensions:
- **Python** (ms-python.python) - Required
- **Pylance** (ms-python.vscode-pylance) - Better IntelliSense
- **Test Explorer** (hbenl.vscode-test-explorer) - Visual test runner

## Example Session

```bash
# 1. Start debug session
$ ./scripts/test-debug.sh -k test_ollama_generate

🐛 Running Tests in Debug Mode
===============================

📍 Debugger will listen on port 5678
   Attach VS Code debugger after container starts

🐳 Ensuring Redis and Ollama are running...
✅ Redis is ready
✅ Ollama is ready
✅ Services ready

🏗️  Building test container with debug support...
🐛 Starting tests in debug mode...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   1. Container will start and wait for debugger
   2. In VS Code, press F5 or use 'Run > Start Debugging'
   3. Select 'Python: Attach to Docker' configuration
   4. Tests will start running after debugger attaches
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 2. In VS Code: Press F5 → "Python: Attach to Docker"
# 3. Set breakpoints in test file
# 4. Tests run and pause at breakpoints
# 5. Inspect, step through, debug!
```

## Resources

- [VS Code Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [debugpy Documentation](https://github.com/microsoft/debugpy)
- [Docker Debugging Guide](https://code.visualstudio.com/docs/containers/debug-python)
