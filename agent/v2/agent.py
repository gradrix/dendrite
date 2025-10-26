"""
V2 Agent: Top-down planning and sequential execution

Architecture:
1. Planning Phase: Analyze goal with multiple LLM calls
2. Execution Phase: Execute pre-planned neurons sequentially
"""

import logging
from typing import Dict, Any
from .planner import GoalPlanner, ExecutionPlan
from .executor import PlanExecutor

logger = logging.getLogger(__name__)


class V2Agent:
    """V2 Agent with planning and sequential execution."""

    def __init__(self, ollama_client, tool_registry):
        self.ollama = ollama_client
        self.tool_registry = tool_registry

        self.planner = GoalPlanner(ollama_client, tool_registry)
        self.executor = PlanExecutor(ollama_client, tool_registry)

    def execute_goal(self, goal: str, context: Dict = None) -> Dict[str, Any]:
        """Execute a goal using v2 architecture."""

        logger.info(f"🎯 V2 Agent starting goal: {goal[:100]}...")

        try:
            # Phase 1: Planning
            logger.info("📋 Phase 1: Planning...")
            plan = self.planner.create_plan(goal, context)

            # Phase 2: Execution
            logger.info("🚀 Phase 2: Execution...")
            result = self.executor.execute_plan(plan)

            # Add planning info to result
            result["plan"] = {
                "total_steps": plan.total_steps,
                "estimated_complexity": plan.estimated_complexity,
                "data_requirements": plan.data_requirements,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "goal": s.goal,
                        "depends_on": s.depends_on,
                        "neuron_type": s.neuron_type
                    }
                    for s in plan.steps
                ]
            }

            logger.info(f"✅ V2 Agent completed: {result['success']}")
            return result

        except Exception as e:
            logger.error(f"💥 V2 Agent failed: {e}")
            # Return a proper error result structure
            return {
                "success": False,
                "error": str(e),
                "original_goal": goal,
                "completed_steps": 0,
                "total_steps": 0,
                "results": {},
                "errors": {"planning": str(e)},
                "debug_info": {}
            }

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debugging information."""
        return {
            "executor_debug": self.executor._get_debug_info()
        }