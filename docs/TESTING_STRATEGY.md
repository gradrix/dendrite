# Testing Strategy for Autonomous Improvement

## Test Hierarchy & Classification

Understanding the different levels of testing in this project:

### 1. Unit Tests (`test_*.py`)
- **Scope**: Single component/class in isolation
- **Mocks**: External dependencies mocked (LLM, database, Redis)
- **Speed**: Fast (< 1 second per test)
- **Location**: `neural_engine/tests/test_<component>.py`
- **Example**: `test_result_validator_neuron.py` - Tests validator tiers independently
- **When to use**: Testing individual neuron logic, data transformations, algorithms

### 2. Integration Tests (`test_*_integration.py`)
- **Scope**: Multiple components working together
- **Mocks**: Some mocking (typically LLM/external services), real internal components
- **Speed**: Medium (1-10 seconds per test)
- **Location**: `neural_engine/tests/test_<feature>_integration.py`
- **Example**: `test_validator_integration.py` - Tests orchestrator + validator interaction
- **When to use**: Testing component interactions, data flow, integration points

### 3. Full System Tests (`it_test_*.py`)
- **Scope**: Complete system with all neurons
- **Mocks**: Minimal mocking (may mock LLM for determinism), real components
- **Speed**: Slow (10-60 seconds per test)
- **Location**: `neural_engine/tests/it_test_full_system_integration.py`
- **Example**: Full orchestrator pipeline from goal → intent → tool → result
- **When to use**: Testing complete features, end-to-end scenarios, system behavior

### 4. End-to-End Tests (`./scripts/run.sh ask`)
- **Scope**: Production-like environment with Docker services
- **Mocks**: None - real Ollama, PostgreSQL, Redis, Chroma
- **Speed**: Very slow (1-10 minutes per test)
- **Location**: Executed via `./scripts/run.sh ask "goal"` or demos
- **Example**: `./scripts/run.sh ask "What is 2 plus 2?"` - Real LLM calls, real caching
- **When to use**: Final validation, user acceptance testing, performance benchmarking

### Testing Decision Matrix

| **Testing Level** | **Use When** | **Pros** | **Cons** |
|-------------------|--------------|----------|----------|
| **Unit** | Developing new neuron | Fast, isolated, easy to debug | Doesn't catch integration issues |
| **Integration** | Connecting components | Tests real interactions | Slower, more setup |
| **Full System** | Major features complete | Tests system behavior | Very slow, harder to isolate failures |
| **E2E** | Release readiness | Production-like, real behavior | Slowest, requires Docker services |

### Test Coverage Goals

- **Unit Tests**: 80%+ coverage of individual neurons
- **Integration Tests**: All major feature interactions
- **Full System Tests**: Key user scenarios (5-10 tests)
- **E2E Tests**: Critical paths (2-3 smoke tests)

### Running Tests

```bash
# Unit tests (fast, run frequently)
docker compose run --rm tests pytest neural_engine/tests/test_result_validator_neuron.py -v

# Integration tests (medium, run before commits)
docker compose run --rm tests pytest neural_engine/tests/test_validator_integration.py -v

# Full system tests (slow, run before merging)
docker compose run --rm tests pytest neural_engine/tests/it_test_full_system_integration.py -v

# End-to-end tests (slowest, run before releases)
./scripts/run.sh ask "What is 2 plus 2?"
./scripts/run.sh demo
```

### Current Test Status

Phase 2.4 (Result Validator) Test Coverage:
- ✅ Unit tests: 26/26 passing (test_result_validator_neuron.py)
- ✅ Integration tests: 9/9 passing (test_validator_integration.py)
- ✅ E2E validation: Successful (run.sh ask test with 70% confidence)

---

## Your Excellent Questions

1. **"If tool fails or regresses - how does the system test if it fixed it?"**
2. **"During goal execution or async in background?"**
3. **"What if some tools are not idempotent and cannot be run multiple times (like write/data change methods)?"**

## Current State (What We Have Now)

### 1. A/B Testing - Currently SIMULATED
```python
def validate_improvement(self, tool_name: str):
    """
    Current implementation:
    - Gets OLD metrics from ExecutionStore (real historical data)
    - SIMULATES NEW metrics (assumes 20% improvement)
    - No actual testing of the improved code!
    """
```

**Problem**: We're not actually running the improved tool to see if it works!

### 2. When Testing Happens
Currently: **Synchronous** - validate_improvement() is called manually or during autonomous cycle
- NOT running in background
- NOT testing during real goal execution
- No live traffic comparison

### 3. Non-Idempotent Tools
Currently: **No special handling**
- System would blindly test any tool
- Could cause side effects (duplicate writes, data corruption, etc.)

## What We Need (The Solution)

### Phase 1: Safe Testing Framework (IMPLEMENT THIS FIRST)

```python
class SafeTestingStrategy:
    """
    Determines how to safely test an improved tool based on its characteristics.
    """
    
    def classify_tool(self, tool_name: str) -> Dict[str, Any]:
        """
        Analyze tool to determine testing strategy.
        
        Returns:
            {
                'idempotent': bool,  # Can be run multiple times safely?
                'has_side_effects': bool,  # Modifies external state?
                'read_only': bool,  # Only reads data?
                'requires_sandbox': bool,  # Needs isolated environment?
                'testing_strategy': str,  # 'shadow', 'sandbox', 'synthetic', 'manual'
            }
        """
        
    def get_testing_strategy(self, tool_classification: Dict) -> TestingStrategy:
        """
        Choose appropriate testing approach:
        
        1. SHADOW TESTING (safe for read-only tools):
           - Run both old and new versions in parallel
           - Compare outputs
           - No side effects
           
        2. SANDBOX TESTING (for tools with side effects):
           - Run in isolated environment
           - Mock external dependencies
           - Validate behavior without actual changes
           
        3. SYNTHETIC TESTING (for non-idempotent tools):
           - Create synthetic test cases
           - Run against test data
           - Don't use real production calls
           
        4. MANUAL APPROVAL (for high-risk tools):
           - Generate improvement
           - Require human review
           - No automatic deployment
        """
```

### Phase 2: Real A/B Testing (Background Execution)

```python
class LiveABTesting:
    """
    Run A/B tests on actual traffic in background.
    """
    
    def start_ab_test(self, tool_name: str, improved_version: str):
        """
        Deploy improved version in shadow mode:
        
        1. Keep old version as primary
        2. Run new version in parallel (shadow)
        3. Compare results asynchronously
        4. Collect metrics over time
        """
        
    async def monitor_ab_test(self, tool_name: str):
        """
        Background task that:
        - Monitors both versions
        - Collects success/failure rates
        - Detects regressions immediately
        - Auto-rollback if new version fails
        """
        
    def evaluate_ab_test(self, tool_name: str, duration: int = 3600):
        """
        After sufficient time (e.g., 1 hour):
        - Statistical comparison of metrics
        - Confidence intervals
        - Recommendation: deploy/rollback/continue-testing
        """
```

### Phase 3: Regression Detection

```python
class RegressionDetector:
    """
    Continuously monitor deployed improvements for regressions.
    """
    
    def monitor_post_deployment(self, tool_name: str):
        """
        After deployment, monitor for:
        - Success rate drops
        - Increased error rates
        - Performance degradation
        - New error types
        
        If regression detected:
        1. Alert immediately
        2. Auto-rollback if critical
        3. Analyze what went wrong
        4. Add to failure patterns
        """
        
    def compare_sliding_windows(self, tool_name: str):
        """
        Compare metrics:
        - Last 24h BEFORE deployment
        - Last 24h AFTER deployment
        
        Statistical tests:
        - T-test for performance differences
        - Chi-square for error rate changes
        - Confidence intervals
        """
```

## Proposed Implementation Plan

### Step 1: Tool Classification System
```python
# Add to BaseTool:
class BaseTool:
    def get_tool_characteristics(self) -> Dict[str, Any]:
        """
        Tool declares its own characteristics for safe testing.
        
        Returns:
            {
                'idempotent': True/False,
                'side_effects': ['writes_to_db', 'sends_email', 'modifies_file'],
                'safe_for_shadow_testing': True/False,
                'requires_sandbox': True/False,
                'test_data_available': True/False
            }
        """
```

### Step 2: Shadow Testing for Read-Only Tools
```python
def shadow_test_improvement(self, tool_name: str, num_samples: int = 20):
    """
    For READ-ONLY tools (safe to run multiple times):
    
    1. Get recent successful executions from ExecutionStore
    2. Replay same inputs through improved version
    3. Compare outputs
    4. Calculate agreement rate
    
    If outputs match >= 95%: SAFE to deploy
    If outputs differ: REVIEW differences
    """
```

### Step 3: Synthetic Testing for Non-Idempotent Tools
```python
def synthetic_test_improvement(self, tool_name: str):
    """
    For NON-IDEMPOTENT tools (dangerous to run multiple times):
    
    1. Tool provides test_cases in its definition
    2. Run improved version against test cases
    3. Verify expected outputs
    4. Check error handling
    
    Example test_cases:
    [
        {
            'input': {'action': 'write', 'data': 'test'},
            'expected_output': {'success': True},
            'should_raise': None
        },
        {
            'input': {'action': 'write', 'data': None},
            'expected_output': None,
            'should_raise': ValueError
        }
    ]
    """
```

### Step 4: Background Monitoring (Async)
```python
async def autonomous_improvement_loop(self):
    """
    Background task that runs continuously:
    
    1. Every N minutes:
       - Detect improvement opportunities
       - Generate improvements
       
    2. For each improvement:
       - Classify tool (read-only vs side-effects)
       - Choose testing strategy
       - Run appropriate tests
       
    3. If tests pass:
       - Start shadow deployment (run both versions)
       - Monitor for H hours
       - If no regressions: full deployment
       
    4. After deployment:
       - Continue monitoring for 24h
       - If regression: auto-rollback
    """
```

## Decision Matrix

| Tool Type | Testing Strategy | Deployment | Monitoring |
|-----------|------------------|------------|------------|
| **Read-only** (queries, gets) | Shadow testing on real traffic | Automatic if tests pass | Real-time comparison |
| **Idempotent** (safe to retry) | Replay historical executions | Automatic if match rate > 95% | Success rate tracking |
| **Side-effects** (writes) | Sandbox + synthetic tests | Manual approval required | Post-deployment monitoring |
| **Critical** (destructive) | Human review only | Manual approval + staged rollout | 24h intensive monitoring |

## Example: Strava Tools Classification

```python
# READ-ONLY - Safe for shadow testing
- strava_get_my_activities
- strava_get_activity_kudos
- strava_get_dashboard_feed

# IDEMPOTENT - Safe to retry
- strava_give_kudos (giving kudos twice is safe)

# SIDE-EFFECTS - Needs sandbox
- strava_update_activity (modifies data)

# Testing Strategy:
strava_get_my_activities:
  - Shadow test: Run improved version on same date ranges
  - Compare activity counts, data structure
  - Deploy if 100% agreement
  
strava_update_activity:
  - Synthetic test: Create test activities in sandbox
  - Verify updates work correctly
  - Require manual approval for deployment
```

## Summary of Answers

### Q1: "How does the system test if it fixed it?"

**Answer**: Currently it doesn't! We need to add:
1. **Shadow testing** for read-only tools (run both versions, compare)
2. **Synthetic testing** for side-effect tools (test cases)
3. **Regression detection** after deployment (monitor metrics)

### Q2: "During goal execution or async in background?"

**Answer**: Should be **BOTH**:
- **Synchronous**: When manually triggered (validate_improvement)
- **Async Background**: Continuous monitoring + shadow testing
- **During Execution**: Shadow mode runs both versions simultaneously

### Q3: "What about non-idempotent tools?"

**Answer**: **Never blindly test them!** Use:
1. **Classification system** - tools declare if they're safe to test
2. **Synthetic test cases** - tool provides test inputs
3. **Sandbox environment** - isolated testing
4. **Manual approval** - for critical/destructive operations

## Next Steps for Demo

Before we build the end-to-end demo, we should add:

1. ✅ **Tool classification** to BaseTool
2. ✅ **Shadow testing** for read-only tools  
3. ✅ **Replay testing** using historical ExecutionStore data
4. ✅ **Regression detection** after deployment

This will make the demo much more realistic and production-ready!

**Should we implement these enhancements first, or do you want to see the basic demo and then enhance it?**
