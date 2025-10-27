import argparse
import uuid
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
from neural_engine.core.sandbox import Sandbox
import redis

def main():
    parser = argparse.ArgumentParser(description="Neural Engine CLI")
    parser.add_argument("--goal", type=str, required=True, help="The goal for the Neural Engine to execute.")
    args = parser.parse_args()

    goal_id = str(uuid.uuid4())
    print(f"Executing goal: {args.goal} (ID: {goal_id})")

    # Basic setup of dependencies
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    message_bus = MessageBus(redis_client)
    ollama_client = OllamaClient(host='http://localhost:11434')
    tool_registry = ToolRegistry(redis_client=redis_client)

    # Instantiate neurons
    intent_classifier = IntentClassifierNeuron(ollama_client=ollama_client, message_bus=message_bus)
    generative_neuron = GenerativeNeuron(ollama_client=ollama_client, message_bus=message_bus)
    tool_selector = ToolSelectorNeuron(ollama_client=ollama_client, message_bus=message_bus, tool_registry=tool_registry)
    code_generator = CodeGeneratorNeuron(ollama_client=ollama_client, message_bus=message_bus)
    sandbox = Sandbox() # Assuming sandbox has a simpler setup for now

    neuron_registry = {
        "intent_classifier": intent_classifier,
        "generative": generative_neuron,
        "tool_selector": tool_selector,
        "code_generator": code_generator,
        "sandbox": sandbox,
    }

    # Instantiate and run the orchestrator
    orchestrator = Orchestrator(
        neuron_registry=neuron_registry,
        tool_registry=tool_registry,
        message_bus=message_bus
    )

    result = orchestrator.execute(goal_id, args.goal)
    print("\n--- Execution Result ---")
    print(result)

if __name__ == "__main__":
    main()
