# Dendrite Documentation# Dendrite Documentation# Documentation



> **New to Dendrite?** Start with the **[main README](../README.md)** for an overview.



Complete documentation for the self-organizing neuron-based AI agent.Complete documentation for the self-organizing neuron-based AI agent.This folder contains detailed documentation for the Center AI Agent project.



## 📚 Documentation Files



### 🚀 [SETUP.md](SETUP.md)## 📚 Core Documentation## 📚 Core Documentation

**Complete setup and configuration guide**



Get Dendrite running on your machine:

- Prerequisites and Docker setup### Getting Started### Model Management

- **Strava API authentication** (BOTH token + cookies required!)

- Model selection and auto-detection- **[MODEL_MANAGEMENT_SUMMARY.md](MODEL_MANAGEMENT_SUMMARY.md)** - Complete model selection system

- GPU support (Linux, WSL)

- Troubleshooting common issues- **[SETUP.md](SETUP.md)** - Complete setup guide  - Hardware detection and resource-aware selection



👉 **Start here if this is your first time!**  - Prerequisites and installation  - Model profiles (3B to 32B parameters)



---  - Strava API configuration  - Configuration and usage examples



### 🏗️ [ARCHITECTURE.md](ARCHITECTURE.md)  - Model selection and GPU setup  

**Deep dive into how Dendrite works**

  - Troubleshooting- **[MODEL_QUICK_REF.md](MODEL_QUICK_REF.md)** - Quick reference guide

Understand the neuron-based system:

- Biological neural network metaphor (neurons, dendrites, axons)  - Command cheat sheet

- Micro-prompting strategy (50-200 tokens per prompt)

- Automatic dendrite spawning (pre & post-execution)### Understanding the System  - Model recommendations by system specs

- Smart data compaction (disk caching at >5KB)

- Error reflection & self-correction  - Troubleshooting

- Memory overseer (intelligent context loading)

- Performance characteristics and comparisons- **[ARCHITECTURE.md](ARCHITECTURE.md)** - How Dendrite works



👉 **Read this to understand how it thinks!**  - Neuron-based execution model### Agent Architecture



---  - Micro-prompting strategy- **[NEURON_AGENT_SUMMARY.md](NEURON_AGENT_SUMMARY.md)** - Self-organizing execution engine



### 🚀 [USAGE.md](USAGE.md)  - Automatic dendrite spawning  - Micro-prompt architecture

**How to use Dendrite effectively**

  - Smart data compaction  - Dendrite spawning (parallel execution)

Practical guide for using the agent:

- Running goals (natural language queries)  - Error reflection & self-correction  - Error reflection system

- Creating instruction files

- Monitoring execution (logs, state, resources)  - Performance characteristics  

- Advanced patterns (multi-step, accumulation, analysis)

- Extending Dendrite (adding new tools)- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - Recent project reorganization

- Authentication management (token + cookie refresh)

- Best practices and troubleshooting### Using Dendrite  - Documentation consolidation



👉 **Your day-to-day reference!**  - Smart data storage system



---- **[USAGE.md](USAGE.md)** - Usage patterns and best practices  - File structure changes



## 🎯 Quick Navigation  - Running goals and instructions



**First time setup:**  - Monitoring execution## 🔧 Setup Guides

1. [Prerequisites](SETUP.md#prerequisites) → [Docker setup](SETUP.md#quick-start) → [Strava auth](SETUP.md#strava-api-authentication-setup)

  - Advanced patterns

**Understanding the system:**

1. [Core concepts](ARCHITECTURE.md#core-concepts) → [Execution flow](ARCHITECTURE.md#example-execution-flow) → [Design patterns](ARCHITECTURE.md#key-design-patterns)  - Extending with new tools- **[STRAVA_TOKEN_SETUP.md](STRAVA_TOKEN_SETUP.md)** - Initial Strava OAuth setup



**Daily usage:**  - Configuration reference- **[AUTO_TOKEN_REFRESH.md](AUTO_TOKEN_REFRESH.md)** - Automatic token refresh system

1. [Running goals](USAGE.md#running-goals) → [Monitoring](USAGE.md#monitoring-execution) → [Examples](USAGE.md#examples-collection)

  - Examples and troubleshooting- **[WSL_GPU_SETUP.md](WSL_GPU_SETUP.md)** - GPU detection in WSL2

---



## 📂 Additional Resources

## 🎯 Quick Links## 📋 Quick References

### Archive



The `archive/` directory contains:

- Old session summaries and debugging notes### For First-Time Users- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Token management and query commands

- Proposals for future features

- Historical refactoring notes1. Read [SETUP.md](SETUP.md) to get Dendrite running



These are kept for reference but not actively maintained.2. Try a simple goal: `./start-agent.sh --goal "How many activities this week?"`## 📦 Archive



---3. Check [USAGE.md](USAGE.md) for more examples



## 🔗 External ReferencesOld/outdated documentation is kept in `archive/` folder for reference:



- **Ollama Documentation**: https://github.com/ollama/ollama### For Developers- Session notes and implementation logs

- **Strava API**: https://developers.strava.com/

- **Docker Documentation**: https://docs.docker.com/1. Understand the architecture in [ARCHITECTURE.md](ARCHITECTURE.md)- Superseded token documentation



---2. Learn how to add tools in [USAGE.md#extending-dendrite](USAGE.md#extending-dendrite)- Old project summaries



## 🤝 Contributing3. Explore the codebase: `agent/neuron_agent.py`, `agent/tool_registry.py`



Found a bug or have a suggestion? Feel free to:

1. Open an issue on GitHub### For Researchers

2. Submit a pull request- [ARCHITECTURE.md](ARCHITECTURE.md) explains the novel concepts:

3. Improve documentation  - Recursive micro-prompting

  - Emergent decomposition

When contributing documentation:  - Context compaction

- Keep it clear and concise  - Error reflection

- Include practical examples

- Test instructions before committing## 📂 Additional Resources

- Use proper Markdown formatting

### Archive

---

The `archive/` directory contains:

## 📋 Documentation Standards- Old session summaries and debugging notes

- Proposals for future features

- **Code blocks**: Always specify language (```bash, ```python, etc.)- Historical refactoring notes

- **File paths**: Use backticks for paths (`agent/neuron_agent.py`)

- **Commands**: Show actual runnable examplesThese are kept for reference but not actively maintained.

- **Outputs**: Include example outputs when helpful

- **Links**: Use relative links for internal docs## 🔗 External References



---- **Ollama Documentation**: https://github.com/ollama/ollama

- **Strava API**: https://developers.strava.com/

## ❓ Need Help?- **Docker Documentation**: https://docs.docker.com/



1. **Setup issues**: Check [SETUP.md](SETUP.md) troubleshooting section## 🤝 Contributing

2. **Usage questions**: See examples in [USAGE.md](USAGE.md)

3. **Architecture questions**: Read [ARCHITECTURE.md](ARCHITECTURE.md)Found a bug or have a suggestion? Feel free to:

4. **Still stuck**: Open a GitHub issue with:1. Open an issue on GitHub

   - What you tried2. Submit a pull request

   - What happened3. Improve documentation

   - Relevant logs (`./scripts/logs.sh`)

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
