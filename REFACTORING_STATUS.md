# Refactoring Implementation Summary

## ✅ COMPLETED: GitHub CI Workflow Fix

### Problem
GitHub CI runners don't have NVIDIA GPU drivers, causing Ollama service to fail.

### Solution Implemented
Created dual-profile docker-compose setup:

**CPU Profile (default for CI):**
- Service: `ollama-cpu` (no GPU requirements)
- Services: `tests`, `app`
- Command: `docker compose --profile cpu up`

**GPU Profile (local development):**
- Service: `ollama` (with nvidia runtime)
- Services: `tests-gpu`, `app-gpu`  
- Command: `docker compose --profile gpu up`

### Changes Made:

1. **docker-compose.yml:**
   - Split `ollama` into `ollama` (GPU) and `ollama-cpu` (CPU only)
   - Split `app` into `app` (CPU) and `app-gpu` (GPU)
   - Split `tests` into `tests` (CPU) and `tests-gpu` (GPU)
   - Added profile tags to enable/disable services

2. **.github/workflows/main.yml:**
   - Changed to use `--profile cpu` for all operations
   - Updated service name references: `ollama` → `ollama-cpu`
   - Tests now run without GPU requirements

### Usage:

**CI (automatic):**
```bash
docker compose --profile cpu up -d
```

**Local Development (GPU):**
```bash
docker compose --profile gpu up -d
```

**Local Development (CPU):**
```bash
docker compose --profile cpu up -d
```

### Benefits:
- ✅ CI tests run without GPU
- ✅ Local dev can still use GPU
- ✅ Automatic fallback to CPU
- ✅ No code changes needed
- ✅ Backwards compatible

---

## 🔍 ANALYZED: Dead Code Detection

### Potentially Dead Files:
1. `agentic_core_neuron.py` - ❓ Not imported (check if orchestrator replaced it)
2. `classification_facts.py` - ❓ Not imported (old pattern-based system?)
3. `intent_decision_aggregator.py` - ❓ Not imported (old voting?)
4. `memory_operation_detector_neuron.py` - ❓ Not imported (replaced by specialist?)
5. `parallel_voter.py` - ❓ Not imported (old voting?)
6. `simple_voters.py` - ❓ Not imported (replaced by voting_tool_selector?)
7. `semantic_intent_classifier.py` - ⚠️ Used in docs only
8. `tool_use_detector_neuron.py` - ❓ Not imported (replaced by domain_router?)
9. `tool_selection_validator_neuron.py` - ❓ Not imported

### Still Used:
- `thinking_visualizer.py` - Used in `run_goal.py` and demos
- `replay_tester.py` - Used in `autonomous_loop.py`
- `shadow_tester.py` - Used in `autonomous_loop.py`
- `safe_testing_strategy.py` - Might be used by test infrastructure

### Recommendation:
**Before deletion, run full test suite to ensure nothing breaks.**

---

## 📚 TODO: Documentation Cleanup

### High Priority:
1. **Update README.md:**
   - Remove outdated architecture references
   - Add clear quick start
   - Professional tone (remove AI-generated feel)
   - Current feature list
   - Docker profiles documentation

2. **Consolidate docs/**
   - Keep: DEBUGGING.md, TESTING.md, TROUBLESHOOTING.md
   - Archive: All PHASE*_SUCCESS.md files
   - Merge: Architecture documents into ARCHITECTURE.md
   - Delete: Redundant summaries

3. **Create:**
   - GETTING_STARTED.md (clear setup guide)
   - ARCHITECTURE.md (consolidated system design)
   - API.md (tool and neuron APIs)

### Current Status:
- 📝 Analysis complete (REFACTORING_ANALYSIS.md)
- ⏳ Implementation pending user approval

---

## 📁 TODO: Scripts Directory Cleanup

### Recommended Actions:

**Move to folders:**
```
scripts/
├── docker/        # start.sh, stop.sh, shell.sh, reset.sh, dev.sh, health.sh
├── testing/       # All test-*.sh files
├── demos/         # All demo_*.py files
├── db/           # init_db.sql, init_extensions.sql
└── utils/        # logs.sh, migrate.sh, warm_cache.py, help.sh
```

**Delete obsolete:**
- `test-phase*.sh` (use pytest directly)
- `test-failing-19.sh` (temporary debug script)

**Benefits:**
- Easier navigation
- Clear categorization
- Reduced clutter

### Current Status:
- 📝 Analysis complete
- ⏳ Implementation pending user approval

---

## 🧪 TODO: Strava Auth Flow Tests

### Test Cases Needed:

1. **test_strava_missing_credentials_prompts_user**
   - Clear KV store credentials
   - Execute Strava goal
   - Verify graceful error handling
   - Verify user prompt for credentials

2. **test_strava_expired_token_handling**
   - Set invalid token
   - Execute Strava goal  
   - Verify 401 detection
   - Verify re-auth prompt

3. **test_strava_successful_auth_flow**
   - Provide valid credentials
   - Execute Strava goal
   - Verify credentials stored
   - Verify subsequent requests reuse credentials

### Implementation Options:

**Option A: Real Credentials (E2E)**
```python
@pytest.mark.integration
@pytest.mark.requires_strava_auth
def test_strava_real_auth():
    # Use real token from environment
    # Actually call Strava API
```

**Option B: Mocked Responses (CI)**
```python
@pytest.mark.unit
def test_strava_auth_flow_mocked():
    # Mock Strava API responses
    # Test credential handling logic
```

**Recommendation:** Implement both with appropriate markers

### Current Status:
- 📝 Analysis complete
- ⏳ Implementation pending user approval

---

## 🗂️ TODO: Core Directory Restructure

### Proposed Structure:
```
neural_engine/core/
├── orchestration/    # High-level coordination
├── neurons/          # Core processing units
├── intelligence/     # Learning & optimization
├── autonomous/       # Self-improvement
├── tools/           # Tool management
├── selection/       # Tool selection systems
├── execution/       # Code execution
├── storage/         # Data persistence
└── infrastructure/  # Base infrastructure
```

### Benefits:
- Clearer organization
- Easier to navigate
- Logical grouping
- Scalable structure

### Risks:
- Import path changes
- Requires updating all imports
- Potential breakage if not careful

### Recommendation:
- Low priority (flat structure works fine for 51 files)
- Only do if causing real problems
- If done, use automated refactoring tools

### Current Status:
- 📝 Analysis complete
- ⏳ Implementation pending user approval

---

## Next Steps

**Immediate (Done):**
- ✅ Fixed GitHub CI workflow with CPU/GPU profiles

**User Decision Required:**
1. Should I update README.md and consolidate docs/?
2. Should I reorganize scripts/ directory?
3. Should I create Strava auth flow tests?
4. Should I identify and remove dead code from core/?
5. Should I restructure core/ directory?

**My Recommendation:**
- **Do now:** Documentation cleanup (README + docs consolidation)
- **Do soon:** Remove confirmed dead code (after verification)
- **Do later:** Scripts reorganization (low priority)
- **Do later:** Core restructure (only if needed)
- **Do later:** Strava auth tests (good to have, not critical)
