"""
System Factory: Create fully initialized Neural Engine system.

Simplifies system initialization for production use.
"""

import redis
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
from neural_engine.core.sandbox import Sandbox
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.core.tool_discovery import ToolDiscovery
from neural_engine.core.error_recovery_neuron import ErrorRecoveryNeuron
from neural_engine.core.neural_pathway_cache import NeuralPathwayCache
from neural_engine.core.goal_decomposition_learner import GoalDecompositionLearner


def create_neural_engine(
    enable_all_features: bool = True
) -> Orchestrator:
    """
    Create a fully initialized Neural Engine system.
    
    Uses environment variables for configuration:
    - REDIS_HOST: Redis hostname (default: redis)
    - OLLAMA_HOST: Ollama API host (default: http://ollama:11434)
    - OLLAMA_MODEL: Model to use (default: mistral)
    
    Args:
        enable_all_features: Enable all Phase 9 & 10 features
    
    Returns:
        Fully initialized Orchestrator with all components
    """
    print("🧠 Initializing Neural Engine...")
    
    # Core dependencies (use environment variables)
    message_bus = MessageBus()  # Creates its own redis client
    ollama_client = OllamaClient()  # Uses OLLAMA_HOST env var
    tool_registry = ToolRegistry()
    
    print(f"   ✓ Loaded {len(tool_registry.get_all_tools())} tools")
    
    # Execution store (PostgreSQL)
    try:
        execution_store = ExecutionStore()
        print("   ✓ Connected to PostgreSQL")
    except Exception as e:
        print(f"   ⚠️  PostgreSQL not available: {e}")
        execution_store = None
    
    # Create neurons
    intent_classifier = IntentClassifierNeuron(
        ollama_client=ollama_client,
        message_bus=message_bus
    )
    
    generative_neuron = GenerativeNeuron(
        ollama_client=ollama_client,
        message_bus=message_bus
    )
    
    tool_selector = ToolSelectorNeuron(
        ollama_client=ollama_client,
        message_bus=message_bus,
        tool_registry=tool_registry
    )
    
    code_generator = CodeGeneratorNeuron(
        ollama_client=ollama_client,
        message_bus=message_bus,
        tool_registry=tool_registry
    )
    
    sandbox = Sandbox(message_bus=message_bus)
    
    print("   ✓ Initialized all neurons")
    
    # Create orchestrator
    orchestrator = Orchestrator(
        intent_classifier=intent_classifier,
        tool_selector=tool_selector,
        code_generator=code_generator,
        generative_neuron=generative_neuron,
        message_bus=message_bus,
        sandbox=sandbox,
        tool_registry=tool_registry,
        execution_store=execution_store,
        enable_semantic_search=enable_all_features,
        enable_lifecycle_sync=enable_all_features,
        enable_error_recovery=enable_all_features
    )
    
    if enable_all_features:
        print("   ✓ Error recovery enabled")
        print("   ✓ Tool discovery enabled")
        print("   ✓ Lifecycle management enabled")
    
    # Add pathway cache and goal learner if available
    if execution_store and enable_all_features:
        try:
            # Pathway cache needs chroma client
            import chromadb
            chroma_client = chromadb.PersistentClient(path="./chroma_data")
            orchestrator.pathway_cache = NeuralPathwayCache(
                execution_store=execution_store,
                chroma_client=chroma_client
            )
            print("   ✓ Neural pathway cache enabled")
        except Exception as e:
            print(f"   ⚠️  Pathway cache not available: {e}")
        
        try:
            orchestrator.goal_learner = GoalDecompositionLearner(execution_store)
            print("   ✓ Goal decomposition learning enabled")
        except Exception as e:
            print(f"   ⚠️  Goal learner not available: {e}")
    
    print("\n✅ Neural Engine ready!\n")
    
    return orchestrator
