from typing import Dict, Optional
from neural_engine.core.neuron import BaseNeuron
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.tool_registry import ToolRegistry

class Orchestrator:
    def __init__(self, intent_classifier=None, tool_selector=None, code_generator=None, 
                 generative_neuron=None, message_bus=None, sandbox=None,
                 neuron_registry: Optional[Dict[str, BaseNeuron]] = None, 
                 tool_registry: Optional[ToolRegistry] = None, 
                 max_depth=10):
        """Initialize Orchestrator with either individual neurons or a neuron registry.
        
        New API (Phase 6+): Pass individual neurons:
            Orchestrator(intent_classifier=..., tool_selector=..., code_generator=..., 
                        generative_neuron=..., message_bus=..., sandbox=...)
        
        Old API (Phases 0-5): Pass neuron_registry and tool_registry:
            Orchestrator(neuron_registry={...}, tool_registry=..., message_bus=...)
        """
        # Support both old and new initialization patterns
        if neuron_registry is not None:
            # Old API
            self.neuron_registry = neuron_registry
            self.tool_registry = tool_registry
            self.message_bus = message_bus
        else:
            # New API - build neuron_registry from individual neurons
            self.intent_classifier = intent_classifier
            self.tool_selector = tool_selector
            self.code_generator = code_generator
            self.generative_neuron = generative_neuron
            self.message_bus = message_bus
            self.sandbox = sandbox
            
            # Create neuron_registry for backward compatibility
            self.neuron_registry = {
                "intent_classifier": intent_classifier,
                "tool_selector": tool_selector,
                "code_generator": code_generator,
                "generative": generative_neuron,
                "sandbox": sandbox
            }
            self.tool_registry = None  # Not used in new API
        
        self.max_depth = max_depth
        self.goal_counter = 0  # Track goals for auto-incrementing goal IDs
    
    def process(self, goal: str, goal_id: Optional[str] = None, depth=0):
        """Process a user goal through the complete pipeline.
        
        Args:
            goal: The user's goal/request as a string
            goal_id: Optional goal ID (will auto-generate if not provided)
            depth: Recursion depth (default 0)
            
        Returns:
            Result from the pipeline (either generative response or tool execution result)
        """
        # Auto-generate goal_id if not provided
        if goal_id is None:
            self.goal_counter += 1
            goal_id = f"goal_{self.goal_counter}"
        
        return self.execute(goal_id, goal, depth)

    def execute(self, goal_id, goal: str, depth=0):
        if depth > self.max_depth:
            return {"error": "Maximum recursion depth exceeded."}

        intent_classifier = self.neuron_registry["intent_classifier"]
        intent_data = intent_classifier.process(goal_id, goal, depth)
        intent = intent_data["intent"]

        if intent == "generative":
            return self._execute_generative_pipeline(goal_id, intent_data, depth)

        elif intent == "tool_use":
            return self._execute_tool_use_pipeline(goal_id, intent_data, depth)

        else:
            return {"error": f"Unknown or unsupported intent: {intent}"}

    def _execute_generative_pipeline(self, goal_id, data, depth):
        return self.neuron_registry["generative"].process(goal_id, data, depth)

    def _execute_tool_use_pipeline(self, goal_id, data, depth):
        # 1. Select the tool
        tool_selector = self.neuron_registry["tool_selector"]
        tool_selection_data = tool_selector.process(goal_id, data['goal'], depth)

        # 2. Generate the code
        code_generator = self.neuron_registry["code_generator"]
        code_generation_data = code_generator.process(goal_id, tool_selection_data, depth)

        # 3. Execute the code in the sandbox
        # Support both "code" and "generated_code" keys
        code = code_generation_data.get("generated_code") or code_generation_data.get("code")
        sandbox = self.neuron_registry["sandbox"]
        execution_result = sandbox.execute(code, goal_id=goal_id, depth=depth)

        return execution_result
