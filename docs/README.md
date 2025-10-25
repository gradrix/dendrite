# Dendrite Documentation# Documentation



Complete documentation for the self-organizing neuron-based AI agent.This folder contains detailed documentation for the Center AI Agent project.



## 📚 Core Documentation## 📚 Core Documentation



### Getting Started### Model Management

- **[MODEL_MANAGEMENT_SUMMARY.md](MODEL_MANAGEMENT_SUMMARY.md)** - Complete model selection system

- **[SETUP.md](SETUP.md)** - Complete setup guide  - Hardware detection and resource-aware selection

  - Prerequisites and installation  - Model profiles (3B to 32B parameters)

  - Strava API configuration  - Configuration and usage examples

  - Model selection and GPU setup  

  - Troubleshooting- **[MODEL_QUICK_REF.md](MODEL_QUICK_REF.md)** - Quick reference guide

  - Command cheat sheet

### Understanding the System  - Model recommendations by system specs

  - Troubleshooting

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - How Dendrite works

  - Neuron-based execution model### Agent Architecture

  - Micro-prompting strategy- **[NEURON_AGENT_SUMMARY.md](NEURON_AGENT_SUMMARY.md)** - Self-organizing execution engine

  - Automatic dendrite spawning  - Micro-prompt architecture

  - Smart data compaction  - Dendrite spawning (parallel execution)

  - Error reflection & self-correction  - Error reflection system

  - Performance characteristics  

- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - Recent project reorganization

### Using Dendrite  - Documentation consolidation

  - Smart data storage system

- **[USAGE.md](USAGE.md)** - Usage patterns and best practices  - File structure changes

  - Running goals and instructions

  - Monitoring execution## 🔧 Setup Guides

  - Advanced patterns

  - Extending with new tools- **[STRAVA_TOKEN_SETUP.md](STRAVA_TOKEN_SETUP.md)** - Initial Strava OAuth setup

  - Configuration reference- **[AUTO_TOKEN_REFRESH.md](AUTO_TOKEN_REFRESH.md)** - Automatic token refresh system

  - Examples and troubleshooting- **[WSL_GPU_SETUP.md](WSL_GPU_SETUP.md)** - GPU detection in WSL2



## 🎯 Quick Links## 📋 Quick References



### For First-Time Users- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Token management and query commands

1. Read [SETUP.md](SETUP.md) to get Dendrite running

2. Try a simple goal: `./start-agent.sh --goal "How many activities this week?"`## 📦 Archive

3. Check [USAGE.md](USAGE.md) for more examples

Old/outdated documentation is kept in `archive/` folder for reference:

### For Developers- Session notes and implementation logs

1. Understand the architecture in [ARCHITECTURE.md](ARCHITECTURE.md)- Superseded token documentation

2. Learn how to add tools in [USAGE.md#extending-dendrite](USAGE.md#extending-dendrite)- Old project summaries

3. Explore the codebase: `agent/neuron_agent.py`, `agent/tool_registry.py`


### For Researchers
- [ARCHITECTURE.md](ARCHITECTURE.md) explains the novel concepts:
  - Recursive micro-prompting
  - Emergent decomposition
  - Context compaction
  - Error reflection

## 📂 Additional Resources

### Archive

The `archive/` directory contains:
- Old session summaries and debugging notes
- Proposals for future features
- Historical refactoring notes

These are kept for reference but not actively maintained.

## 🔗 External References

- **Ollama Documentation**: https://github.com/ollama/ollama
- **Strava API**: https://developers.strava.com/
- **Docker Documentation**: https://docs.docker.com/

## 🤝 Contributing

Found a bug or have a suggestion? Feel free to:
1. Open an issue on GitHub
2. Submit a pull request
3. Improve documentation

When contributing documentation:
- Keep it clear and concise
- Include practical examples
- Test instructions before committing
- Use proper Markdown formatting

## 📋 Documentation Standards

- **Code blocks**: Always specify language (```bash, ```python, etc.)
- **File paths**: Use backticks for paths (`agent/neuron_agent.py`)
- **Commands**: Show actual runnable examples
- **Outputs**: Include example outputs when helpful
- **Links**: Use relative links for internal docs

## 🗂️ File Organization

```
docs/
├── README.md              # This file - documentation overview
├── SETUP.md              # Installation and configuration
├── ARCHITECTURE.md       # System design and internals
├── USAGE.md              # How to use Dendrite
└── archive/              # Historical notes (reference only)
    └── session_summaries/  # AI-generated debugging sessions
```

## ❓ Need Help?

1. **Setup issues**: Check [SETUP.md](SETUP.md) troubleshooting section
2. **Usage questions**: See examples in [USAGE.md](USAGE.md)
3. **Architecture questions**: Read [ARCHITECTURE.md](ARCHITECTURE.md)
4. **Still stuck**: Open a GitHub issue with:
   - What you tried
   - What happened
   - Relevant logs (`./scripts/logs.sh`)
