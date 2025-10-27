# Project Roadmap

This document outlines the architectural vision and future development direction for the Neural Engine project. It is based on the collaborative design sessions between the developer and the AI agent, Jules.

## Core Philosophy: The "Lego Brick" Approach

The fundamental principle of this project is to create a highly modular, decentralized AI system composed of specialized, single-responsibility "micro-LLMs" called **Neurons**. Each neuron is designed to be an independently testable and composable "Lego brick" that can be chained together into sophisticated pipelines to achieve complex goals. The system is designed for extensibility, testability, and eventual autonomy.

---

## Key Architectural Concepts

### 1. The Sandbox Execution Environment
- **Concept:** All AI-generated code will be executed within a secure `Sandbox` environment.
- **Purpose:** To decouple AI logic from infrastructure. The Sandbox will be responsible for preparing the execution context (e.g., loading data from Redis handles into simple variables like a `params` dictionary) and capturing the output in a managed way (via a `sandbox.set_result()` function).
- **Benefit:** This provides security, modularity (we can swap backend infrastructure without changing AI prompts), and simplicity for the code-generating neurons.

### 2. "Smart Tool" Architecture & Deferred Instantiation
- **Concept:** Tools are not just simple functions; they are classes. The `ToolRegistry` will discover these tool *classes* but will **not** instantiate them on startup.
- **Purpose:** To support "Smart Tools" that require arguments (like API tokens or other state) during their initialization. Instantiation will be deferred and handled by the AI-generated code within the Sandbox.
- **Benefit:** This allows for tools that can manage their own state and dependencies gracefully.

### 3. Dynamic Dependency Resolution
- **Concept:** When a Smart Tool requires a dependency (e.g., an API token) that it doesn't have, it will raise a specific, custom exception (e.g., `AuthenticationRequiredError`).
- **Purpose:** The `Orchestrator` will catch this specific exception and trigger a new, dedicated sub-pipeline with the goal of resolving that dependency (e.g., by asking the user for the token).
- **Benefit:** This creates a robust, self-healing system that can autonomously handle missing dependencies without crashing.

### 4. Parameter Resolution Pipeline
- **Concept:** For tools that require complex, structured parameters (e.g., a date range), a dedicated multi-neuron pipeline will be invoked *before* the code generation step.
- **Purpose:** This pipeline will first use a neuron to understand the *semantic meaning* of the user's request (e.g., "last 24 hours") and then use another neuron to transform that semantic meaning into the concrete data format the tool expects (e.g., ISO 8601 timestamps).
- **Benefit:** This breaks down the complex problem of parameter analysis into smaller, more reliable and testable steps, increasing the accuracy of tool usage.

### 5. The `ToolForgeNeuron`: A Self-Extending Agent
- **Concept:** A specialized neuron, the `ToolForgeNeuron`, will have the ability to write new tool files (`.py` files) and save them into the `tools/` directory.
- **Purpose:** To allow the agent to autonomously expand its own skillset. The `ToolRegistry` will automatically discover these new tools, making them immediately available for use.
- **Benefit:** This is the cornerstone of a truly learning agent that can acquire new capabilities over time without human intervention.

---

## Development Plan

The features above will be implemented incrementally in the following order:

1.  **[DONE]** - Foundational architecture with a simple, parameterless tool pipeline.
2.  **[NEXT]** - Implement the full "Smart Tool" architecture, including the `ToolRegistry` refactor and deferred instantiation.
3.  **[FUTURE]** - Implement the `AuthenticationRequiredError` and the Orchestrator's dependency resolution logic.
4.  **[FUTURE]** - Design and implement the multi-neuron Parameter Resolution Pipeline.
5.  **[FUTURE]** - Design and implement the `ToolForgeNeuron`.
