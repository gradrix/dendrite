"""
Warm up pattern caches with successful executions.
This creates execution-validated cache entries that improve future performance.
"""

from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.key_value_store import KeyValueStore
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.sandbox import Sandbox
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron

# Create orchestrator with specialists enabled
mb = MessageBus()
kv = KeyValueStore()
tr = ToolRegistry()
tr.refresh()
sb = Sandbox(mb)
oc = OllamaClient()

intent_classifier = IntentClassifierNeuron(mb, oc, use_pattern_cache=True)
tool_selector = ToolSelectorNeuron(mb, oc, tr, use_pattern_cache=True, use_specialists=True)
code_generator = CodeGeneratorNeuron(mb, oc, tr)

orchestrator = Orchestrator(
    intent_classifier=intent_classifier,
    tool_selector=tool_selector,
    code_generator=code_generator,
    generative_neuron=None,
    message_bus=mb,
    sandbox=sb,
    enable_semantic_search=False,
    enable_lifecycle_sync=False,
    enable_error_recovery=False
)

# Test goals that should work and cache successfully
test_goals = [
    ("Say hello", "hello_world"),
    ("Add 5 and 3", "addition"),
    ("Remember my name is Alice", "memory_write"),
    ("Remember my favorite color is blue", "memory_write"),
    ("Calculate 10 + 5", "add"),
]

print("Warming cache with successful executions...")
print("=" * 60)

for i, (goal, expected_tool) in enumerate(test_goals, 1):
    print(f"\n{i}. Testing: {goal}")
    print(f"   Expected tool: {expected_tool}")
    
    try:
        result = orchestrator.process(goal)
        
        if result.get('success'):
            print(f"   ✓ SUCCESS")
        else:
            print(f"   ✗ FAILED: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ✗ EXCEPTION: {e}")

print("\n" + "=" * 60)
print("Cache warming complete!")
print(f"\nIntent classifier stats: {intent_classifier.stats}")
print(f"Tool selector stats: {tool_selector.stats}")
