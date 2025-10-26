"""
V2 Executor: Executes pre-planned neurons sequentially

No spawning during execution - retries happen within neurons.
"""

import logging
from typing import Dict, Any, List
from .neuron import Neuron
from .planner import ExecutionPlan, ExecutionStep

logger = logging.getLogger(__name__)


class PlanExecutor:
    """Executes a pre-planned execution plan."""

    def __init__(self, ollama_client, tool_registry):
        self.ollama = ollama_client
        self.tool_registry = tool_registry
        self.execution_context: Dict[str, Any] = {}
        self.completed_steps: Dict[str, Any] = {}

    def execute_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute the entire plan sequentially."""

        logger.info(f"🚀 Executing plan with {plan.total_steps} steps (complexity: {plan.estimated_complexity})")

        self.execution_context = {"original_goal": plan.original_goal}
        self.completed_steps = {}

        # Execute steps in dependency order
        remaining_steps = plan.steps.copy()
        executed_step_ids = set()

        while remaining_steps:
            # Find steps that can be executed (all dependencies met)
            executable_steps = [
                step for step in remaining_steps
                if all(dep in executed_step_ids for dep in step.depends_on)
            ]

            if not executable_steps:
                logger.error("❌ Circular dependency or missing dependencies detected")
                break

            # Execute the first executable step
            step = executable_steps[0]
            logger.info(f"📍 Executing step {step.step_id}: {step.goal[:50]}...")

            # Prepare input data for this step
            input_data = self._prepare_step_input(step)

            # Create and execute neuron
            neuron = Neuron(step.goal, self.ollama, self.tool_registry)
            result = neuron.execute(input_data, self.execution_context)

            # Store result
            self.completed_steps[step.step_id] = {
                "result": result,
                "neuron": neuron,
                "step": step
            }

            # Update context with step output
            if result.success:
                self.execution_context[step.step_id] = result.data
                executed_step_ids.add(step.step_id)
                logger.info(f"✅ Step {step.step_id} completed")
            else:
                logger.error(f"❌ Step {step.step_id} failed: {result.error}")
                # Continue with other steps if possible, but mark failure

            # Remove from remaining
            remaining_steps.remove(step)

        # Prepare final result
        final_result = {
            "success": all(
                step_result["result"].success
                for step_result in self.completed_steps.values()
            ),
            "original_goal": plan.original_goal,
            "completed_steps": len(self.completed_steps),
            "total_steps": plan.total_steps,
            "results": {
                step_id: step_result["result"].data
                for step_id, step_result in self.completed_steps.items()
                if step_result["result"].success
            },
            "errors": {
                step_id: step_result["result"].error
                for step_id, step_result in self.completed_steps.items()
                if not step_result["result"].success
            },
            "debug_info": self._get_debug_info()
        }

        logger.info(f"🏁 Plan execution complete: {final_result['completed_steps']}/{plan.total_steps} steps successful")
        return final_result

    def _prepare_step_input(self, step: ExecutionStep) -> Dict[str, Any]:
        """Prepare input data for a step based on its dependencies."""

        input_data = {}

        # Add parameters from dependencies
        for dep_id in step.depends_on:
            if dep_id in self.completed_steps:
                dep_result = self.completed_steps[dep_id]["result"]
                if dep_result.success:
                    input_data[dep_id] = dep_result.data

        # Add any specific parameters needed
        for param in step.parameters_needed:
            if param in self.execution_context:
                input_data[param] = self.execution_context[param]

        return input_data

    def _get_debug_info(self) -> Dict[str, Any]:
        """Get debugging information about the execution."""

        debug_info = {}

        for step_id, step_data in self.completed_steps.items():
            neuron = step_data["neuron"]
            result = step_data["result"]

            debug_info[step_id] = {
                "goal": neuron.goal,
                "success": result.success,
                "error": result.error,
                "prompt_used": result.prompt_used,
                "response_received": result.response_received,
                "validation_errors": result.validation_errors,
                "retry_count": result.retry_count,
                "execution_history": len(neuron.execution_history)
            }

        return debug_info