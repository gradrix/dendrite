# Project Roadmap

> **⚠️ Note**: This document contains the original architectural vision. For current project status, completed phases, and next steps, see **[docs/MASTER_ROADMAP.md](./docs/MASTER_ROADMAP.md)**.

This document outlines the architectural vision and future development direction for the Neural Engine project. It is based on the collaborative design sessions between the developer and the AI agent, Jules.

## Core Philosophy: The "Lego Brick" Approach

The fundamental principle of this project is to create a highly modular, decentralized AI system composed of specialized, single-responsibility "micro-LLMs" called **Neurons**. Each neuron is designed to be an independently testable and composable "Lego brick" that can be chained together into sophisticated pipelines to achieve complex goals. The system is designed for extensibility, testability, and ultimate autonomy.

---

## Key Architectural Concepts

### 1. The Unified Tool Architecture

This is the cornerstone of the agent's capabilities. It treats all tools—whether written by a human developer or the AI itself—as first-class citizens in a single, elegant system.

-   **All Tools are Python Files:** Every tool exists as a standalone Python file in a dedicated `tools/` directory.
-   **Persistent Skillset:** The `tools/` directory is mounted on a persistent volume, ensuring that any tool the AI creates becomes a permanent part of its skillset, surviving reboots and container restarts.
-   **The `ToolRegistry`:** On application startup, this component scans the `tools/` directory, dynamically imports each tool file, and indexes their capabilities into a persistent database (e.g., Redis). This creates a fast, queryable cache of all available skills.
-   **"Smart Tools" with State:** Tools are classes, not just functions. They are "smart" and manage their own state, including authentication tokens. When a tool requires credentials it doesn't have, it raises a specific `AuthenticationRequiredError`.
-   **Self-Healing Authentication:** The `Orchestrator` catches `AuthenticationRequiredError` and triggers a sub-pipeline to acquire the necessary credentials from the user. The tools themselves contain the logic to refresh expired tokens, making them robust and self-sufficient.

### 2. Agentic Consciousness: The Evolving State of Mind

The agent will possess a memory of its own reasoning processes, allowing it to learn and refine its approach over time.

-   **The "Mind Map" (Long-Term Memory):** Every thought (a neuron's input/output) is cached as a node in a tree structure in persistent memory. This creates a complete, queryable "thought tree" for every goal the agent has pursued, forming its long-term memory.
-   **Short-Term Memory Loop:** The `AgenticCoreNeuron` maintains a "short-term memory" or "state of mind" summary. This summary is included in its prompt for the next thinking loop, providing a continuous train of thought and preventing it from starting from a blank slate every time.
-   **Evolving Sub-Goals:** While the agent's main goal is immutable for stability, it is empowered to creatively generate and refine its own sub-goals based on the experiences recorded in its memory.

### 3. The Self-Improving Ecosystem

The agent is part of a larger ecosystem that allows it to monitor its own performance and autonomously improve its own components.

-   **Persistent Prompt Library:** Prompts are stored in a `PromptRegistry` backed by a persistent database. This allows the agent to not just use its prompts, but to analyze and rewrite them to improve performance via a dedicated `PromptTuningNeuron`.
-   **The "Public Pipe" (Event Bus):** Every neuron publishes an event to a Redis stream upon execution, detailing its performance, duration, and outcome.
-   **The `PerformanceMonitorNeuron`:** This is a "meta-agent" that observes the event stream on the "Public Pipe." It analyzes the system's performance to identify inefficiencies or repeated failures and generates new goals to address them, such as "refactor this inefficient tool" or "tune this failing prompt."
-   **The `Scheduler`:** A dedicated service runs scheduled tasks, allowing the agent to manage its own long-term, proactive behavior, such as "check for new Strava activities every hour."

---

## Development Plan

-   [x] **Implement the `ToolRegistry`:** Create the initial version of the `ToolRegistry` that can scan the `tools/` directory, and dynamically load tool files. This is the immediate next step to unblock testing.
-   [ ] **Implement a "Smart Tool":** Create a sample tool (e.g., `strava_tool.py`) that demonstrates state management, raises `AuthenticationRequiredError` when unconfigured, and includes self-healing token refresh logic.
-   [ ] **Implement Orchestrator's Exception Handling:** Update the `Orchestrator` to catch `AuthenticationRequiredError` and launch the dependency resolution sub-pipeline.
-   [ ] **Implement the Persistent `PromptRegistry`:** Build the registry to load, cache, and provide prompts to all neurons.
-   [ ] **Implement the "Mind Map":** Establish the data structure and logic for caching neuron outputs as a thought tree in Redis.
-   [ ] **Implement the Short-Term Memory Loop:** Enhance the `AgenticCoreNeuron` to maintain and utilize its "state of mind" summary.
-   [ ] **Implement the `ToolForgeNeuron`:** Create the neuron capable of writing new Python tool files to the `tools/` directory.
-   [ ] **Implement the "Public Pipe":** Set up the Redis stream for neuron event publishing.
-   [ ] **Implement the `PerformanceMonitorNeuron`:** Create the meta-agent to observe the Public Pipe and generate self-improvement goals.
-   [ ] **Implement the `Scheduler`:** Create the service for managing and executing recurring, long-term goals.

---

## Production Deployment (Added 2024)

### Infrastructure (✅ Created)
- [x] **Production CLI** (`dendrite.py`): Queue/worker pattern for background processing
- [x] **Docker Compose** (`docker-compose.prod.yml`): Production-ready with health checks, restart policies
- [x] **Setup Script** (`scripts/setup-production.sh`): One-command deployment

### Pending Production Tasks
- [ ] **Structured Logging**: Replace print() with JSON logging
- [ ] **Metrics**: Prometheus endpoint for monitoring
- [ ] **HTTP API Mode**: REST server for external integrations
- [ ] **Graceful Shutdown**: Handle SIGTERM in worker processes

### Model Optimization (16GB RAM, No GPU)
Recommended models for constrained environments:

| Model | Size | Use Case |
|-------|------|----------|
| `qwen2.5-1.5b` | 1GB | Minimal, for 8GB RAM |
| `qwen2.5-3b` | 2GB | Best balance for 16GB RAM |
| `qwen2.5-7b` | 4.5GB | High quality, for 32GB RAM |
| `qwen2.5-32b` | 20GB | Maximum quality, for 64GB RAM |

### LLM Backend: llama.cpp

The project uses **llama.cpp** for LLM inference with automatic model management.

**Key files:**
- `start.sh` - One-command startup (idempotent)
- `neural_engine/core/llm_client.py` - Unified LLM client
- `scripts/model-init.sh` - Downloads GGUF model on first run
- `scripts/model-updater.sh` - Background update checker (optional)

**Quick Start:**
```bash
./start.sh          # CPU mode (default)
./start.sh gpu      # GPU mode (NVIDIA)
./start.sh stop     # Stop all
./start.sh status   # Check status
./start.sh test     # Run tests
```

**Change model size:**
```bash
RAM_PROFILE=8gb ./start.sh   # Use smaller model
RAM_PROFILE=32gb ./start.sh  # Use larger model
```

