from typing import Dict, Optional
import time
from neural_engine.core.neuron import BaseNeuron
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore

class Orchestrator:
    def __init__(self, intent_classifier=None, tool_selector=None, code_generator=None, 
                 generative_neuron=None, message_bus=None, sandbox=None,
                 neuron_registry: Optional[Dict[str, BaseNeuron]] = None, 
                 tool_registry: Optional[ToolRegistry] = None,
                 execution_store: Optional[ExecutionStore] = None,
                 max_depth=10):
        """Initialize Orchestrator with either individual neurons or a neuron registry.
        
        New API (Phase 6+): Pass individual neurons:
            Orchestrator(intent_classifier=..., tool_selector=..., code_generator=..., 
                        generative_neuron=..., message_bus=..., sandbox=..., 
                        execution_store=...)
        
        Old API (Phases 0-5): Pass neuron_registry and tool_registry:
            Orchestrator(neuron_registry={...}, tool_registry=..., message_bus=...)
        
        Args:
            execution_store: Optional ExecutionStore for logging executions.
                           If None and PostgreSQL is available, creates one automatically.
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
        
        # Initialize ExecutionStore for logging
        self.execution_store = execution_store
        if self.execution_store is None:
            try:
                self.execution_store = ExecutionStore()
            except Exception as e:
                # If PostgreSQL is not available, continue without logging
                print(f"Warning: ExecutionStore not available: {e}")
                self.execution_store = None
    
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
        
        # Track execution timing
        start_time = time.time()
        
        # Execute the pipeline
        result = self.execute(goal_id, goal, depth)
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log execution to database if available
        if self.execution_store:
            try:
                self._log_execution(goal_id, goal, result, duration_ms, depth)
            except Exception as e:
                print(f"Warning: Failed to log execution: {e}")
        
        return result

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
    
    def _log_execution(self, goal_id: str, goal_text: str, result: Dict, duration_ms: int, depth: int):
        """Log execution to ExecutionStore.
        
        Args:
            goal_id: The goal identifier
            goal_text: Original user request
            result: Pipeline result dictionary
            duration_ms: Execution duration in milliseconds
            depth: Recursion depth
        """
        # Extract key information from result
        intent = result.get('intent', 'unknown')
        success = result.get('success', False)
        error = result.get('error')
        
        # Store main execution
        execution_id = self.execution_store.store_execution(
            goal_id=goal_id,
            goal_text=goal_text,
            intent=intent,
            success=success,
            error=error,
            duration_ms=duration_ms,
            metadata={
                'depth': depth,
                'result': result,
                'timestamp': time.time()
            }
        )
        
        # If tool was used, log tool execution
        if intent == "tool_use" and 'selected_tools' in result:
            selected_tools = result['selected_tools']
            if isinstance(selected_tools, str):
                selected_tools = [selected_tools]
            
            for tool_name in selected_tools:
                # Extract tool-specific data
                tool_params = result.get('tool_parameters', {})
                tool_result = result.get('execution_result')
                tool_success = result.get('success', False)
                tool_error = result.get('error')
                
                self.execution_store.store_tool_execution(
                    execution_id=execution_id,
                    tool_name=tool_name,
                    parameters=tool_params,
                    result=tool_result,
                    success=tool_success,
                    error=tool_error,
                    duration_ms=None  # Individual tool timing not tracked yet
                )
        
        return execution_id
