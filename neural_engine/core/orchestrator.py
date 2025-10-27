from typing import Dict
from .neuron import BaseNeuron
from .intent_classifier_neuron import IntentClassifierNeuron
from .generative_neuron import GenerativeNeuron
from ..tools.python_script_tool import PythonScriptTool
from .tool_registry import ToolRegistry

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
        # ... (pipeline execution with depth passed to each neuron)
        return {"status": "success", "message": "Tool use pipeline executed."}
