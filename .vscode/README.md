# VS Code Testing and Debugging

This directory contains VS Code configurations for debugging tests.

## Debug Configurations

### 1. Python: Debug Tests in Docker ⭐ **RECOMMENDED**
Press F5 and select this - it automatically starts Docker container with tests!

**Usage:**
1. Open any test file (or just be in the workspace)
2. Press **F5**
3. Select "Python: Debug Tests in Docker"
4. Set breakpoints and debug!

**What it does:**
- Automatically runs `./scripts/test-debug.sh`
- Waits for container to start
- Attaches debugger when ready
- All in one step!

### 2. Python: Debug Current Test File in Docker
Same as above but only runs the currently open test file.

**Usage:**
1. Open a specific test file (e.g., `test_ollama_client.py`)
2. Press **F5**
3. Select "Python: Debug Current Test File in Docker"
4. Only that file's tests will run!

### 3. Python: Attach to Docker (manual)
For when you've already started tests with `./scripts/test-debug.sh` manually.

**Usage:**
```bash
# Terminal 1: Start tests in debug mode
./scripts/test-debug.sh

# VS Code: Press F5 and select "Python: Attach to Docker (manual)"
```

### 4. Python: Debug Tests Locally
Run and debug tests locally (faster, but requires local Python setup).

**Usage:**
1. Open a test file
2. Press F5
3. Select "Python: Debug Tests Locally"

## How It Works

### Docker Debugging (debugpy)
- Test container exposes port 5678 for debugging
- VS Code connects to this port
- Path mappings translate between local files and container paths
- Set breakpoints in VS Code, they work in the container!

### Local Debugging
- Runs pytest directly on your machine
- Requires local Python environment with dependencies
- Faster iteration but needs Redis/Ollama running

## Tips

**Set breakpoints:**
- Click left gutter in VS Code to set breakpoints
- Or add `breakpoint()` in your Python code

**View variables:**
- Hover over variables while debugging
- Use Debug Console to evaluate expressions

**Step through code:**
- F10: Step Over
- F11: Step Into
- Shift+F11: Step Out
- F5: Continue

**Debug specific tests:**
```bash
./scripts/test-debug.sh -k test_specific_name
```
