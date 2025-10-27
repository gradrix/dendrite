from typing import Dict
from neural_engine.core.neuron import BaseNeuron
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.tool_registry import ToolRegistry

class Orchestrator:
    def __init__(self, neuron_registry: Dict[str, BaseNeuron], tool_registry: ToolRegistry, message_bus, max_depth=10):
        self.neuron_registry = neuron_registry
        self.tool_registry = tool_registry
        self.message_bus = message_bus
        self.max_depth = max_depth

    def execute(self, goal_id, goal: str, depth=0):
        if depth > self.max_depth:
            return {"error": "Maximum recursion depth exceeded."}

        intent_classifier = self.neuron_registry["intent_classifier"]
        intent_data = intent_classifier.process(goal_id, goal, depth)
        intent = intent_data["intent"]

        if intent == "generative":
            return self.neuron_registry["generative"].process(goal_id, intent_data)

        elif intent == "tool_use":
            return self._execute_tool_use_pipeline(goal_id, intent_data, depth)

        else:
            return {"error": f"Unknown or unsupported intent: {intent}"}

    def _execute_tool_use_pipeline(self, goal_id, data, depth):
        # 1. Select the tool
        tool_selector = self.neuron_registry["tool_selector"]
        tool_selection_data = tool_selector.process(goal_id, data['goal'], depth)

        # 2. Generate the code
        code_generator = self.neuron_registry["code_generator"]
        code_generation_data = code_generator.process(goal_id, tool_selection_data, depth)

        # 3. Execute the code in the sandbox
        sandbox = self.neuron_registry["sandbox"]
        execution_result = sandbox.execute(code_generation_data["code"])

        return execution_result
