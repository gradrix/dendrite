"""
V2 Planner: Analyzes goals and creates execution plans

Uses multiple LLM micro-prompts to understand:
- What data is needed
- Filtering requirements
- Parameters to pass
- Number of neuron steps
"""

import logging
import json
from typing import List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""
    step_id: str
    goal: str
    depends_on: List[str]  # Step IDs this depends on
    expected_output: str
    parameters_needed: List[str]
    neuron_type: str = "generic"  # generic, data_processing, api_call, etc.


@dataclass
class ExecutionPlan:
    """Complete execution plan for a goal."""
    original_goal: str
    steps: List[ExecutionStep]
    data_requirements: List[str]
    estimated_complexity: str  # simple, medium, complex
    total_steps: int


class GoalPlanner:
    """Plans execution by analyzing goals with multiple LLM calls."""

    def __init__(self, ollama_client, tool_registry):
        self.ollama = ollama_client
        self.tool_registry = tool_registry

    def create_plan(self, goal: str, context: Dict = None) -> ExecutionPlan:
        """Create an execution plan for the given goal."""

        logger.info(f"📋 Planning execution for goal: {goal[:100]}...")

        # Step 1: Analyze goal requirements
        requirements = self._analyze_requirements(goal, context)

        # Step 2: Determine data needs
        data_needs = self._analyze_data_needs(goal, requirements, context)

        # Step 3: Plan execution steps
        steps = self._plan_execution_steps(goal, requirements, data_needs)

        # Step 4: Validate and refine plan
        refined_steps = self._refine_plan(steps, goal)

        plan = ExecutionPlan(
            original_goal=goal,
            steps=refined_steps,
            data_requirements=data_needs,
            estimated_complexity=self._estimate_complexity(refined_steps),
            total_steps=len(refined_steps)
        )

        logger.info(f"✅ Created execution plan with {len(refined_steps)} steps")
        return plan

    def _analyze_requirements(self, goal: str, context: Dict) -> Dict:
        """Analyze what the goal requires."""

        context_summary = ""
        if context:
            available_keys = [k for k in context.keys() if not k.startswith('_')]
            if available_keys:
                context_summary = f"\n\nAvailable context data: {available_keys[:10]}"

        prompt = f"""Analyze this goal and determine what is required to achieve it.

Goal: {goal}{context_summary}

Available tools: {[tool.name + ': ' + tool.description[:50] for tool in self.tool_registry.list_tools()][:20]}

Determine:
1. What type of data is needed (API calls, calculations, filtering, etc.)
2. What tools or operations are required
3. Any specific parameters or conditions mentioned
4. Expected output format

Output JSON:
{{
  "data_types": ["api_data", "calculations", "filtering", "aggregation"],
  "required_tools": ["tool_name1", "tool_name2"],
  "parameters": ["param1", "param2"],
  "conditions": ["condition1", "condition2"],
  "output_format": "description of expected result"
}}"""

        response = self.ollama.generate(prompt, system="Analyze goal requirements.", temperature=0.1)
        try:
            return json.loads(response)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse requirements JSON: {e}. Response: {response[:200]}...")
            # Fallback: return basic requirements
            return {
                "data_types": ["api_data"],
                "required_tools": ["getMyActivities"],
                "parameters": [],
                "conditions": [],
                "output_format": "List of activities with kudos information"
            }

    def _analyze_data_needs(self, goal: str, requirements: Dict, context: Dict) -> List[str]:
        """Analyze what data sources are needed."""

        prompt = f"""Based on the goal and requirements, what data sources are needed?

Goal: {goal}
Requirements: {json.dumps(requirements, indent=2)}

Available context: {list(context.keys()) if context else []}

List the specific data sources needed:
- API endpoints to call
- Context data to retrieve
- Calculations to perform
- Files to read

Output as a list of data source descriptions."""

        response = self.ollama.generate(prompt, system="Identify data sources.", temperature=0.1)

        # Parse response into list
        lines = [line.strip('- ').strip() for line in response.split('\n') if line.strip().startswith('-')]
        return lines if lines else [response.strip()]

    def _plan_execution_steps(self, goal: str, requirements: Dict, data_needs: List[str]) -> List[ExecutionStep]:
        """Plan the individual execution steps."""

        prompt = f"""Create a detailed execution plan for this goal.

Goal: {goal}

Requirements: {json.dumps(requirements, indent=2)}
Data Needs: {data_needs}

Create a sequence of execution steps. Each step should be:
- A single, atomic action
- Have clear inputs and outputs
- Be executable by one neuron

Format as JSON array:
[{{
  "step_id": "step_1",
  "goal": "Fetch user activities from Strava API",
  "depends_on": [],
  "expected_output": "List of activities",
  "parameters_needed": ["after_unix", "before_unix"],
  "neuron_type": "api_call"
}},
{{
  "step_id": "step_2",
  "goal": "Filter activities that have kudos",
  "depends_on": ["step_1"],
  "expected_output": "Filtered list of activities with kudos",
  "parameters_needed": ["activities_list"],
  "neuron_type": "data_processing"
}}]"""

        response = self.ollama.generate(prompt, system="Plan execution steps.", temperature=0.2)
        try:
            steps_data = json.loads(response)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse execution steps JSON: {e}. Response: {response[:200]}...")
            # Fallback: create basic steps
            steps_data = [
                {
                    "step_id": "step_1",
                    "goal": "Get current timestamp to calculate date range",
                    "depends_on": [],
                    "expected_output": "Current Unix timestamp",
                    "parameters_needed": [],
                    "neuron_type": "timestamp_calculation"
                },
                {
                    "step_id": "step_2",
                    "goal": "Fetch Strava activities from the last 7 days using the timestamp",
                    "depends_on": ["step_1"],
                    "expected_output": "List of activities from last 7 days",
                    "parameters_needed": ["current_timestamp"],
                    "neuron_type": "api_call"
                },
                {
                    "step_id": "step_3", 
                    "goal": "For each activity with kudos, get the names of people who gave kudos",
                    "depends_on": ["step_2"],
                    "expected_output": "List of activities with kudos giver names",
                    "parameters_needed": ["activities"],
                    "neuron_type": "data_processing"
                }
            ]

        steps = []
        for step_data in steps_data:
            step = ExecutionStep(
                step_id=step_data["step_id"],
                goal=step_data["goal"],
                depends_on=step_data.get("depends_on", []),
                expected_output=step_data.get("expected_output", ""),
                parameters_needed=step_data.get("parameters_needed", []),
                neuron_type=step_data.get("neuron_type", "generic")
            )
            steps.append(step)

        return steps

    def _refine_plan(self, steps: List[ExecutionStep], goal: str) -> List[ExecutionStep]:
        """Refine and validate the execution plan."""

        prompt = f"""Review and refine this execution plan for the goal.

Goal: {goal}

Current Plan:
{json.dumps([{
    "step_id": s.step_id,
    "goal": s.goal,
    "depends_on": s.depends_on,
    "neuron_type": s.neuron_type
} for s in steps], indent=2)}

Check for:
1. Missing dependencies
2. Unnecessary steps
3. Better ordering
4. Missing parameters

Output the refined plan as JSON array with the same format."""

        response = self.ollama.generate(prompt, system="Refine execution plan.", temperature=0.1)
        try:
            refined_data = json.loads(response)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse refined plan JSON: {e}. Response: {response[:200]}...")
            # Fallback: return original steps
            return steps

        refined_steps = []
        for step_data in refined_data:
            step = ExecutionStep(
                step_id=step_data["step_id"],
                goal=step_data["goal"],
                depends_on=step_data.get("depends_on", []),
                expected_output=step_data.get("expected_output", ""),
                parameters_needed=step_data.get("parameters_needed", []),
                neuron_type=step_data.get("neuron_type", "generic")
            )
            refined_steps.append(step)

        return refined_steps

    def _estimate_complexity(self, steps: List[ExecutionStep]) -> str:
        """Estimate the complexity of the plan."""

        total_steps = len(steps)
        api_calls = sum(1 for s in steps if s.neuron_type == "api_call")
        data_processing = sum(1 for s in steps if s.neuron_type == "data_processing")

        if total_steps <= 3 and api_calls <= 1:
            return "simple"
        elif total_steps <= 6 and api_calls <= 3:
            return "medium"
        else:
            return "complex"