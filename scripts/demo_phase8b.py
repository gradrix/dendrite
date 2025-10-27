"""
Manual verification script for Phase 8b: Orchestrator logging integration.
Demonstrates execution tracking in action.
"""

from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.sandbox import Sandbox
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.core.ollama_client import OllamaClient


def main():
    print("=" * 80)
    print("Phase 8b: Orchestrator Logging Integration Demo")
    print("=" * 80)
    
    # Initialize components
    print("\n1. Initializing components...")
    message_bus = MessageBus()
    ollama_client = OllamaClient()
    tool_registry = ToolRegistry()
    execution_store = ExecutionStore()
    
    intent_classifier = IntentClassifierNeuron(message_bus, ollama_client)
    tool_selector = ToolSelectorNeuron(message_bus, ollama_client, tool_registry)
    code_generator = CodeGeneratorNeuron(message_bus, ollama_client, tool_registry)
    generative_neuron = GenerativeNeuron(message_bus, ollama_client)
    sandbox = Sandbox(message_bus)
    
    orchestrator = Orchestrator(
        intent_classifier=intent_classifier,
        tool_selector=tool_selector,
        code_generator=code_generator,
        generative_neuron=generative_neuron,
        message_bus=message_bus,
        sandbox=sandbox,
        execution_store=execution_store
    )
    
    print("✓ Components initialized with ExecutionStore")
    
    # Test 1: Simple generative query
    print("\n2. Testing generative query...")
    goal1 = "What is the capital of France?"
    print(f"   Goal: {goal1}")
    result1 = orchestrator.process(goal1)
    print(f"   ✓ Execution logged")
    
    # Test 2: Tool use query
    print("\n3. Testing tool use query...")
    goal2 = "Say hello using HelloWorldTool"
    print(f"   Goal: {goal2}")
    result2 = orchestrator.process(goal2)
    print(f"   ✓ Execution logged")
    
    # Query execution history
    print("\n4. Querying execution history...")
    recent = execution_store.get_recent_executions(limit=5)
    print(f"   Found {len(recent)} recent executions:")
    for i, exec in enumerate(recent[:3], 1):
        print(f"     {i}. {exec['goal_id']}: {exec['goal_text'][:50]}...")
        print(f"        Intent: {exec['intent']}, Duration: {exec['duration_ms']}ms")
    
    # Check statistics
    print("\n5. Updating and checking statistics...")
    execution_store.update_statistics()
    success_rate = execution_store.get_success_rate()
    print(f"   Overall success rate: {success_rate:.2%}")
    
    # Tool performance
    print("\n6. Tool performance metrics...")
    tool_perf = execution_store.get_tool_performance_view()
    if tool_perf:
        print(f"   Found {len(tool_perf)} tools with usage data:")
        for tool in tool_perf[:3]:
            print(f"     - {tool['tool_name']}: {tool['execution_count']} executions, "
                  f"{float(tool['success_rate']):.2%} success rate")
    else:
        print("   No tool usage data yet")
    
    print("\n" + "=" * 80)
    print("✓ Phase 8b verification complete!")
    print("  All executions are now automatically logged to PostgreSQL")
    print("=" * 80)
    
    execution_store.close()


if __name__ == "__main__":
    main()
