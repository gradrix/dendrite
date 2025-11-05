# Dendrite

A modular AI orchestration system with semantic tool discovery, intelligent error recovery, and pattern learning capabilities. Built for production use with PostgreSQL logging, tool lifecycle management, and 100% local execution.

## Current Capabilities ✅

**What Actually Works (Production-Ready):**

- **Intent Classification with Pattern Caching**: Learns from past decisions to speed up repeated queries
- **3-Stage Tool Discovery**: Semantic search (ChromaDB) → Statistical ranking → LLM selection
- **Intelligent Error Recovery**: Automatic retry with exponential backoff, fallback strategies, and adaptation
- **Tool Lifecycle Management**: Detects deleted/modified tools and prevents stale executions
- **PostgreSQL Analytics**: Full execution history, tool statistics, and performance tracking
- **Dynamic Tool Loading**: Tools auto-discovered from filesystem with zero configuration
- **Code Generation & Sandboxed Execution**: Safe Python code execution with controlled namespaces
- **Memory Operations**: Persistent key-value storage for context and state
- **100% Local Execution**: Runs entirely on your infrastructure with Ollama - no cloud APIs

## Roadmap Features 🚧

**Built but Not Yet Integrated** (see [docs/INTEGRATION_AUDIT.md](docs/INTEGRATION_AUDIT.md)):

- Neural Pathway Cache (System 1/2 fast path)
- Goal Decomposition Learning (pattern-based subgoal suggestions)
- Autonomous Loop (continuous self-improvement)
- Tool Forge (dynamic tool creation)
- Parallel Voting Systems (multi-voter consensus)
- Advanced Analytics & Monitoring

**Why separated?** Core system is production-ready and stable. Advanced features are being integrated systematically to maintain quality (see [docs/INTEGRATION_ACTION_PLAN.md](docs/INTEGRATION_ACTION_PLAN.md)).

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB+ RAM (for LLM models)
- (Optional) NVIDIA GPU with drivers for GPU acceleration

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/gradrix/dendrite.git
   cd dendrite
   ```

2. **Start services:**
   ```bash
   # For CPU-only environments (CI, cloud servers)
   docker compose --profile cpu up -d
   
   # For GPU-enabled environments (local with NVIDIA GPU)
   docker compose --profile gpu up -d
   ```

3. **Run setup:**
   ```bash
   ./scripts/setup.sh
   ```

4. **Execute a goal:**
   ```bash
   ./scripts/run.sh ask "Say hello to the world, mate"
   ./scripts/run.sh ask "Remember that my favorite color is blue"
   ./scripts/run.sh ask "What is my favorite color?"
   ```

### Example Output

```
🧠 Neural Engine - Self-Improving AI System
==========================================
🐳 Ensuring services are running...
✅ Redis ready
✅ PostgreSQL ready
✅ Ollama ready
🗄️  Running database migrations...
✅ Database migrations complete
✅ All services ready

🎯 NEW GOAL
================================================================================
Goal: Say hello to the world, mate
Time: 14:23:45
================================================================================

💨 CACHE HIT (System 1 - Fast Path)
   Intent cache hit: generative (confidence: 0.87)

✅ GOAL COMPLETED SUCCESSFULLY
================================================================================
Result: "G'day, world! How's it going, mate? Hope you're having a bonzer day!"

Duration: 2.31s
Steps: 1

📊 Execution Summary:
   Total steps: 1
   Duration: 2.31s
   Intent cache hit: Yes
   Decomposition pattern: No (not integrated)
   Errors: No
```

### Running Tests

```bash
# Run all tests
./scripts/test.sh

# Run specific test suite
pytest neural_engine/tests/test_phase6_full_pipeline.py -v

# Run with coverage
pytest --cov=neural_engine --cov-report=html
```

## Architecture

### Active Components (Currently Integrated)

**Orchestrator**  
Central coordinator routing goals through generative or tool-use pipelines.

**Intent Classifier** (with Pattern Cache)  
Determines intent (generative vs tool_use) and learns from past decisions for faster classification.

**Tool Selector** (3-Stage Process)  
1. **Semantic Search**: ChromaDB vector search (1000+ tools → ~10 candidates)
2. **Statistical Ranking**: Performance-based filtering (10 → 5 top tools)
3. **LLM Selection**: Final intelligent choice from top candidates

**Code Generator**  
Generates executable Python code using selected tools with proper parameters.

**Sandbox**  
Isolated Python execution with namespace control, timeout protection, and result handling.

**Tool Discovery**  
ChromaDB-backed semantic search indexing tool descriptions for relevant matches.

**Tool Lifecycle Manager**  
Monitors filesystem for tool changes, detects deleted tools, prevents stale executions.

**Error Recovery Neuron**  
Implements retry with exponential backoff, fallback strategies, and adaptive error handling.

**Execution Store** (PostgreSQL)  
Logs all executions, tool statistics, performance metrics, and analytics data.

**Tool Registry**  
Dynamic tool loading from filesystem with automatic discovery and indexing.

**Message Bus** (Redis)  
Event-driven communication between components with pub/sub messaging.

### Data Flow

```
User Goal
    ↓
Intent Classifier (+ Pattern Cache) → [generative] → Generative Neuron → Response
    ↓
[tool_use]
    ↓
Tool Discovery (Semantic Search)
    ↓
Tool Selector (3-stage)
    ↓
Code Generator
    ↓
Sandbox Execution (+ Error Recovery)
    ↓
Execution Store (PostgreSQL Logging)
    ↓
Result
```

### Future Components (Not Yet Integrated)

See [docs/INTEGRATION_AUDIT.md](docs/INTEGRATION_AUDIT.md) for details on:
- Neural Pathway Cache (System 1 fast path)
- Goal Decomposition Learner (pattern learning)
- Autonomous Loop (self-improvement)
- Tool Forge (dynamic tool creation)
- Voting Systems (parallel consensus)
- Advanced Analytics

## Configuration

### Docker Profiles

**CPU Profile** (default, for CI and GPU-less environments):
```bash
docker compose --profile cpu up -d
```

**GPU Profile** (for NVIDIA GPU acceleration):
```bash
docker compose --profile gpu up -d
```

### Environment Variables

Key environment variables in docker-compose.yml:

- `OLLAMA_HOST`: Ollama API endpoint (default: http://ollama:11434)
- `OLLAMA_MODEL`: LLM model to use (default: mistral)
- `REDIS_HOST`: Redis server for message bus (default: redis)
- `REDIS_DB`: Redis database number (0 for production, 1 for tests)
- `POSTGRES_HOST`: PostgreSQL for analytics storage

### Models

Tested with:
- `mistral` (default, good balance)
- `llama3.1:8b` (higher quality)
- `llama3.2:3b` (faster, lower memory)

Change model:
```bash
docker compose exec ollama-cpu ollama pull llama3.1:8b
# Update OLLAMA_MODEL in docker-compose.yml
```

## Project Structure

```
.
├── neural_engine/
│   ├── core/              # Core neurons and orchestration
│   ├── tools/             # Available tool implementations
│   ├── tests/             # Test suites
│   └── prompts/           # LLM prompt templates
├── scripts/               # Utility scripts
├── docs/                  # Documentation
├── .github/workflows/     # CI configuration
└── docker-compose.yml     # Service orchestration
```

## Development

### Adding a New Tool

1. Create tool file in `neural_engine/tools/`:
   ```python
   from neural_engine.tools.base_tool import BaseTool
   
   class MyCustomTool(BaseTool):
       def get_tool_definition(self):
           return {
               "name": "my_custom_tool",
               "description": "What this tool does",
               "parameters": [
                   {"name": "param1", "type": "string", "description": "...", "required": True}
               ]
           }
       
       def execute(self, **kwargs):
           param1 = kwargs.get('param1')
           # Your logic here
           return {"result": "success"}
   ```

2. Tool is automatically discovered by registry on startup

3. Test your tool:
   ```bash
   pytest neural_engine/tests/test_tool_registry.py
   python run_goal.py "Use my custom tool with param1 as test"
   ```

### Running in Development Mode

```bash
# Start with live code reloading
./scripts/dev.sh

# Access shell in container
./scripts/shell.sh

# Watch logs
./scripts/logs.sh
```

## Testing

Test suite organization:
- `test_phase0_*.py` - Intent classification
- `test_phase1_*.py` - Generative pipeline
- `test_phase2_*.py` - Tool registry
- `test_phase3_*.py` - Tool selection
- `test_phase4_*.py` - Code generation
- `test_phase5_*.py` - Sandbox execution
- `test_phase6_*.py` - Full pipeline integration
- `test_phase7_*.py` - Tool forge
- `test_phase9*.py` - Analytics and autonomous systems
- `test_tool_discovery.py` - Semantic tool search
- `test_autonomous_*.py` - Self-improvement systems

Run specific test categories:
```bash
# Core pipeline tests
pytest neural_engine/tests/test_phase{0..6}*.py -v

# Autonomous systems
pytest neural_engine/tests/test_autonomous*.py -v

# Tool discovery
pytest neural_engine/tests/test_tool_discovery.py -v
```

## Performance

**Current Status:**
- Core pipeline: ✅ Production-ready
- Test coverage: 98%+ on active components
- Pattern cache: 75% similarity threshold for good hit rate
- Model caching: Docker volumes prevent re-downloads
- Error recovery: Automatic retry with fallback

**Optimizations:**
- Intent pattern caching reduces repeated LLM calls
- Semantic search limits tool candidates (prevents token overflow)
- Statistical ranking prioritizes proven tools
- Database migrations run automatically
- Tool lifecycle prevents stale executions

**Performance Metrics** (on second run with cache):
- Simple goals: ~2-3s (cache hit)
- Tool-based goals: ~5-10s (with semantic search)
- First run: +40-50s (model loading, now cached in Docker volumes)

## Documentation

### Core Documentation
- **[INTEGRATION_AUDIT.md](docs/INTEGRATION_AUDIT.md)** - What's integrated vs what's built
- **[INTEGRATION_ACTION_PLAN.md](docs/INTEGRATION_ACTION_PLAN.md)** - Integration roadmap and priorities
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design details
- [TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md) - Test organization

### Integration Guides
- [TOOL_LIFECYCLE_MANAGEMENT.md](docs/TOOL_LIFECYCLE_MANAGEMENT.md) - Tool lifecycle system
- [TOOL_LOADING_ARCHITECTURE.md](docs/TOOL_LOADING_ARCHITECTURE.md) - Dynamic tool loading
- [DEBUGGING.md](docs/DEBUGGING.md) - Troubleshooting guide

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass: `./scripts/test.sh`
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Status

**Production Ready**: Core orchestration pipeline is stable with 98%+ test coverage on active components.

**What's Working:**
- ✅ Intent classification with pattern learning
- ✅ 3-stage semantic tool discovery
- ✅ Intelligent error recovery
- ✅ Tool lifecycle management
- ✅ PostgreSQL analytics and logging
- ✅ Dynamic tool loading
- ✅ Redis message bus
- ✅ 100% local execution (no cloud APIs)

**What's Next** (see [docs/INTEGRATION_ACTION_PLAN.md](docs/INTEGRATION_ACTION_PLAN.md)):
- 🚧 Neural Pathway Cache (Phase 2.1)
- 🚧 Goal Decomposition Learner (Phase 2.2)
- 🚧 Voting fallback for ambiguous decisions (Phase 2.4)
- 🔮 Autonomous Loop (Phase 3.1) - The big vision!
- 🔮 Tool Forge for dynamic tool creation (Phase 3.2)

**Architecture Philosophy:**
We maintain a clean separation between production-ready core features and experimental advanced capabilities. This ensures stability while enabling innovation.
