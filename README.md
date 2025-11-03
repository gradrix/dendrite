# Dendrite

An autonomous AI orchestration system with self-learning capabilities, voting-based tool selection, and intelligent error recovery.

## Features

- **Voting-Based Architecture**: Domain router and tool selector use LLM voting for intelligent decision-making
- **Autonomous Learning**: Pattern caching and neural pathway optimization improve performance over time
- **Self-Improvement**: Autonomous loop detects underperforming tools and generates improvements
- **Tool Discovery**: Semantic search with ChromaDB for relevant tool selection from large toolsets
- **Error Recovery**: Intelligent retry, fallback, and strategy adaptation for robust execution
- **Memory Operations**: Smart key-value storage with pattern-based memory operation detection
- **Analytics**: Performance monitoring, health checks, and detailed execution tracking
- **Tool Forge**: Dynamic tool creation and validation system
- **100% Local**: Runs entirely on your infrastructure with Ollama - no cloud API required

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
   python run_goal.py "Remember that my favorite color is blue"
   python run_goal.py "What is my favorite color?"
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

### Core Components

**Orchestrator**  
Central coordination system that routes goals through the appropriate processing pipeline (generative vs tool-use).

**Intent Classifier**  
Determines whether a goal requires tool execution or can be answered directly by the LLM.

**Domain Router**  
Uses per-domain LLM voting to detect specialized domains (memory, Strava, calculator) and route to specialist systems.

**Tool Selector**  
Three-stage selection process:
1. Semantic search (1000+ tools → 10 candidates)
2. Statistical ranking (10 candidates → 5 top performers)
3. LLM voting (5 candidates → best tool)

**Code Generator**  
Generates Python code to execute selected tools with extracted parameters.

**Sandbox**  
Isolated Python execution environment with controlled namespaces and result handling.

**Memory Specialist**  
Pattern-based detection for memory operations (read/write/delete) with high-confidence classification.

**Tool Discovery**  
ChromaDB-backed semantic search for finding relevant tools in large tool repositories.

**Autonomous Loop**  
Background monitoring system that:
- Detects failing or underperforming tools
- Generates improvement suggestions
- Validates improvements with shadow testing
- Automatically deploys successful improvements

### Data Flow

```
User Goal
    ↓
Intent Classifier → [generative] → Generative Neuron → Response
    ↓
[tool_use]
    ↓
Domain Router → Memory Specialist (if memory domain)
    ↓              ↓
Tool Discovery → Tool Selector (voting-based)
    ↓
Parameter Extractor
    ↓
Code Generator
    ↓
Sandbox Execution
    ↓
Result
```

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

Current test results: **578/586 passing (98.6%)**

Optimization features:
- Pattern caching reduces LLM calls for repeated goals
- Neural pathway caching stores successful execution paths
- Tool discovery limits candidates to prevent token overflow
- Statistical ranking prioritizes high-performing tools
- Memory specialist uses pattern matching for instant classification

## Strava Integration

The system includes Strava API tools for activity tracking:
- Get recent activities
- Fetch activity kudos
- Give kudos to activities
- Update activity details
- Get dashboard feed

Configure Strava authentication:
1. Obtain session cookies and CSRF token from Strava web app
2. Store in key-value store:
   ```python
   from neural_engine.core.key_value_store import KeyValueStore
   kv = KeyValueStore()
   kv.set("strava_cookies", "your_cookies_here")
   kv.set("strava_token", "your_csrf_token")
   ```

## Troubleshooting

### Common Issues

**Ollama not responding:**
```bash
# Check if Ollama is running
docker compose ps

# Check Ollama logs
docker compose logs ollama-cpu  # or ollama for GPU

# Restart Ollama
docker compose restart ollama-cpu
```

**Tests failing with "Model not available":**
```bash
# Pull the required model
docker compose exec ollama-cpu ollama pull mistral
```

**Redis connection errors:**
```bash
# Verify Redis is running
docker compose exec redis redis-cli ping
# Should return: PONG
```

**GPU not detected (local development):**
```bash
# Verify NVIDIA drivers
nvidia-smi

# Use GPU profile
docker compose --profile gpu up -d
```

## Documentation

- [Architecture Details](docs/ARCHITECTURE.md) - In-depth system design
- [Testing Strategy](docs/TESTING.md) - Test organization and coverage
- [Debugging Guide](docs/DEBUGGING.md) - Troubleshooting tips
- [Development Plan](docs/DEVELOPMENT.md) - Roadmap and future features

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass: `./scripts/test.sh`
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Status

**Production Ready**: Core functionality is stable with 98.6% test coverage. Autonomous improvement features are in active development.

Key achievements:
- ✅ Voting-based architecture (no hardcoded patterns)
- ✅ Redis database isolation (production safety)
- ✅ Global test isolation
- ✅ Tool discovery with semantic search
- ✅ Autonomous loop with self-improvement
- ✅ Error recovery and fallback strategies
- ✅ CI/CD with GitHub Actions
