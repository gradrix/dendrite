# Project Refactoring Analysis

## 1. 🐳 GitHub Workflow - GPU Detection

**Problem:** CI fails because GitHub runners don't have NVIDIA drivers for Ollama GPU support.

**Solution:** Make Ollama GPU support optional in docker-compose.yml

### Changes Needed:

**docker-compose.yml:**
- Create two profiles: `gpu` and `cpu`
- GPU profile: Uses nvidia runtime (local development)
- CPU profile: No GPU requirements (CI/testing)
- Default to CPU-only for compatibility

**Benefit:** 
- CI works without GPU
- Local dev can use GPU with `--profile gpu`
- Automatic fallback to CPU mode

---

## 2. 📁 Scripts Directory Cleanup

**Current Status:** 40+ files in `/scripts` - hard to navigate

### Analysis:

**Categories:**
1. **Docker operations** (7 files):
   - `dev.sh`, `start.sh`, `stop.sh`, `shell.sh`, `reset.sh`, `setup.sh`, `health.sh`
   
2. **Testing** (18 files):
   - `test.sh`, `test-unit.sh`, `test-integration.sh`, `test-watch.sh`, `test-debug.sh`
   - Phase-specific: `test-phase0.sh` through `test-phase9b.sh`
   - `test-local.sh`, `test-failing-19.sh`

3. **Demos** (7 files):
   - `demo_phase8b.py`, `demo_phase8c.py`, `demo_phase8d.py`
   - `demo_phase9a.py`, `demo_phase9b.py`, `demo_phase9c.py`
   - `demo_stage3_integration.py`

4. **Database** (2 files):
   - `init_db.sql`, `init_extensions.sql`

5. **Utilities** (3 files):
   - `logs.sh`, `migrate.sh`, `help.sh`
   - `warm_cache.py`

### Recommended Structure:

```
scripts/
├── docker/           # Docker operations (start, stop, shell, reset, etc.)
├── testing/          # All test scripts
├── demos/            # Demo Python files
├── db/              # Database initialization files
├── utils/           # Utilities (logs, migrate, warm_cache)
└── README.md        # Updated documentation
```

**Alternative:** Single unified script with commands:
```bash
./scripts/run.sh docker start
./scripts/run.sh docker stop
./scripts/run.sh test unit
./scripts/run.sh test phase3
./scripts/run.sh demo phase9a
```

**Recommendation:** Use folder structure (simpler, more maintainable than mega-script)

**Dead Scripts to Remove:**
- Phase-specific test scripts (use `pytest neural_engine/tests/test_phase3*.py` instead)
- `test-failing-19.sh` (temporary debugging script)

---

## 3. 🧠 Core Directory Analysis

**Current Status:** 51 Python files in `neural_engine/core/`

### Dead Code Analysis:

**Likely Dead/Deprecated:**

1. **agentic_core_neuron.py** - Superseded by orchestrator?
2. **classification_facts.py** - Old pattern-based classification (replaced by voting)
3. **intent_decision_aggregator.py** - Old voting aggregator?
4. **memory_operation_detector_neuron.py** - Superseded by memory_operations_specialist?
5. **parallel_voter.py** - Old voting implementation?
6. **simple_voters.py** - Replaced by voting_tool_selector?
7. **semantic_intent_classifier.py** - Superseded by intent_classifier_neuron?
8. **tool_use_detector_neuron.py** - Superseded by domain_router?
9. **tool_selection_validator_neuron.py** - Still used?
10. **thinking_visualizer.py** - Development debug tool?
11. **replay_tester.py**, **shadow_tester.py**, **safe_testing_strategy.py** - Testing infrastructure, still needed?

**Verification Needed:** Run grep to check if these are imported anywhere.

### Recommended Structure:

```
neural_engine/core/
├── orchestration/        # High-level coordination
│   ├── orchestrator.py
│   ├── system_factory.py
│   └── message_bus.py
│
├── neurons/             # Core processing units
│   ├── intent_classifier_neuron.py
│   ├── tool_selector_neuron.py
│   ├── code_generator_neuron.py
│   ├── generative_neuron.py
│   ├── tool_forge_neuron.py
│   ├── error_recovery_neuron.py
│   └── ...
│
├── intelligence/        # Learning & optimization
│   ├── pattern_cache.py
│   ├── neural_pathway_cache.py
│   ├── goal_decomposition_learner.py
│   └── self_learning.py
│
├── autonomous/          # Self-improvement systems
│   ├── autonomous_loop.py
│   ├── autonomous_improvement_neuron.py
│   └── self_investigation_neuron.py
│
├── tools/              # Tool management
│   ├── tool_registry.py
│   ├── tool_discovery.py
│   ├── tool_lifecycle_manager.py
│   └── tool_version_manager.py
│
├── selection/          # Tool selection systems
│   ├── voting_tool_selector.py
│   ├── domain_router.py
│   ├── memory_operations_specialist.py
│   └── task_simplifier.py
│
├── execution/          # Code execution
│   ├── sandbox.py
│   ├── code_validator_neuron.py
│   └── deployment_monitor.py
│
├── storage/            # Data persistence
│   ├── execution_store.py
│   ├── key_value_store.py
│   └── semantic_fact_store.py
│
└── infrastructure/     # Base infrastructure
    ├── neuron.py
    ├── ollama_client.py
    ├── exceptions.py
    ├── parameter_extractor.py
    └── analytics_engine.py
```

**Recommendation:** Start by identifying dead code, then gradually restructure if needed. Flat structure isn't bad with 51 files, but categories help.

---

## 4. 🔐 Strava Auth Flow Testing

**Current Gap:** No tests verify the auth token flow when credentials are missing.

### Test Scenarios Needed:

1. **Missing credentials → User prompt flow**
   ```python
   def test_strava_missing_credentials_prompts_user():
       # Clear any existing Strava credentials
       # Execute goal: "Show me my recent runs"
       # Should detect missing credentials
       # Should prompt user to provide token
       # Should NOT crash
   ```

2. **Invalid/expired token → Refresh flow**
   ```python
   def test_strava_expired_token_handling():
       # Set invalid token
       # Execute Strava goal
       # Should detect 401/403 error
       # Should prompt for new credentials
   ```

3. **Successful auth → Store & reuse**
   ```python
   def test_strava_successful_auth_stores_credentials():
       # Provide valid credentials
       # Execute Strava goal
       # Verify credentials stored in KV store
       # Second execution should reuse stored credentials
   ```

### Should You Use Real Credentials?

**Option 1: Real Strava Token (Recommended for E2E testing)**
- Pros: Tests actual Strava API integration
- Cons: Requires manual token rotation, can't run in CI
- **Use case:** Manual integration testing before deployment

**Option 2: Mock Strava Responses (Recommended for CI)**
- Pros: Deterministic, no real credentials needed
- Cons: Doesn't test actual API
- **Use case:** Automated testing in CI

**Recommendation:**
- Add both types of tests
- Use `pytest.mark.integration` and `pytest.mark.requires_auth` markers
- Document how to run auth tests with real credentials locally
- Mock for CI, real for manual validation

---

## 5. 📚 Documentation Cleanup

**Current Issues:**
- README.md outdated (references old architecture)
- 20+ docs files with overlapping info
- Looks like "AI-generated documentation dump"
- Phase completion summaries not useful for users

### Analysis of ./docs:

**Useful Documents (Keep & Update):**
1. `DEBUGGING.md` - Practical troubleshooting
2. `DEVELOPMENT_PLAN.md` - Architecture overview (if updated)
3. `TESTING_STRATEGY.md` - Test organization
4. `QUICKSTART_DEBUGGING.md` - Getting started

**Phase Summaries (Archive or Delete):**
- `PHASE0_SUCCESS.md`, `PHASE3_SUCCESS.md`, `PHASE6_PROGRESS.md`, etc.
- These are development logs, not user docs

**Architecture Deep Dives (Consolidate):**
- `FRACTAL_ARCHITECTURE_EVOLUTION.md`
- `AUTONOMOUS_LOOP_FRACTAL.md`
- `TOOL_LOADING_ARCHITECTURE.md`
- Merge into single `ARCHITECTURE.md`

**Strategy Documents (Consolidate):**
- `MEMORY_STRATEGY.md`
- `ERROR_HANDLING_STRATEGY.md`
- `TOOL_STORAGE_STRATEGY.md`
- Merge into implementation docs

### Recommended Documentation Structure:

```
docs/
├── README.md                    # Project overview (user-facing)
├── GETTING_STARTED.md          # Quick setup & first steps
├── ARCHITECTURE.md             # System design & components
├── DEVELOPMENT.md              # Contributing guide
├── TESTING.md                  # How to run tests
├── DEPLOYMENT.md               # Production setup
├── API.md                      # API reference
├── TROUBLESHOOTING.md          # Common issues
└── archive/                    # Historical phase documents
    └── phase-summaries/
```

### Main README.md Structure:

```markdown
# Neural Engine

AI-powered tool orchestration system with autonomous learning and self-improvement.

## Features
- Voting-based tool selection
- Autonomous tool creation & improvement
- Self-monitoring & health checks
- Redis-backed message bus
- PostgreSQL analytics

## Quick Start
[Installation steps - clear, concise]

## Architecture
[High-level overview with diagram]

## Testing
[How to run tests]

## Documentation
[Links to detailed docs]
```

**Remove "AI-ness":**
- Change "Phase X Success" → Feature descriptions
- Remove LLM prompt examples from user docs (move to DEVELOPMENT.md)
- Focus on **what it does**, not **how it was built**
- Professional tone, not chatty
- Remove "🎉 Revolutionary Architecture" language

---

## Priority Recommendations:

**HIGH PRIORITY:**
1. ✅ Fix GitHub CI workflow (GPU detection)
2. ✅ Clean up documentation (outdated README, consolidate docs)

**MEDIUM PRIORITY:**
3. ⚠️ Identify and remove dead code from core/
4. ⚠️ Add Strava auth flow tests

**LOW PRIORITY:**
5. 📦 Reorganize scripts/ (works fine as-is, just messy)

Would you like me to implement any of these changes?
