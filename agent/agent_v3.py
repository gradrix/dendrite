"""
V3 Agent: Self-Correcting Exploratory Execution

Philosophy:
- Natural language goals (no YAML)
- Small LLM contexts (each decision isolated)
- Self-correcting (try → fail → analyze → fix → retry)
- Tool introspection (analyze signatures, responses)
- Adaptive parameter adjustment

Architecture:
1. Goal → Plan (break into steps)
2. Execute each step:
   - Try tool call
   - If error: analyze error + fix params → retry
   - If success: extract needed data
3. Move to next step with extracted data
"""

import logging
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from agent.ollama_client import OllamaClient
from agent.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""
    step_number: int
    description: str
    tool_name: Optional[str] = None
    params: Dict[str, Any] = None
    requires_data_from: Optional[int] = None  # Which previous step provides data
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}


@dataclass
class StepResult:
    """Result of executing a step."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    attempts: int = 1


class AgentV3:
    """
    Self-correcting exploratory agent.
    
    Uses multiple small LLM calls instead of one big context:
    - Planning: goal → steps
    - Execution: step → tool params
    - Error fixing: error → corrected params
    - Data extraction: response → needed fields
    """
    
    def __init__(
        self,
        ollama: OllamaClient,
        tool_registry: ToolRegistry,
        max_retries: int = 3
    ):
        self.ollama = ollama
        self.tools = tool_registry
        self.max_retries = max_retries
        self.execution_results: Dict[int, StepResult] = {}
    
    def execute_goal(self, goal: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute a natural language goal through exploration and self-correction.
        
        Args:
            goal: Natural language description (e.g., "List my private activities from last 24h")
            dry_run: If True, don't actually execute tools
            
        Returns:
            Dict with final results and execution summary
        """
        logger.info(f"🎯 Goal: {goal}")
        
        # Phase 1: Create execution plan (small LLM call)
        logger.info("📋 Phase 1: Planning...")
        plan = self._create_plan(goal)
        logger.info(f"   Generated {len(plan)} steps")
        for step in plan:
            logger.info(f"   Step {step.step_number}: {step.description}")
        
        # Phase 2: Execute each step with self-correction
        logger.info("🔧 Phase 2: Executing...")
        for step in plan:
            logger.info(f"\n{'='*60}")
            logger.info(f"Step {step.step_number}/{len(plan)}: {step.description}")
            logger.info(f"{'='*60}")
            
            result = self._execute_step_with_retry(step, dry_run)
            self.execution_results[step.step_number] = result
            
            if not result.success:
                logger.error(f"❌ Step {step.step_number} failed after {result.attempts} attempts")
                logger.error(f"   Error: {result.error}")
                # Continue anyway - later steps might not need this
            else:
                logger.info(f"✅ Step {step.step_number} completed (attempts: {result.attempts})")
        
        # Phase 3: Format final output (small LLM call)
        logger.info("\n📊 Phase 3: Formatting results...")
        final_output = self._format_final_output(goal, plan)
        
        return {
            "success": True,
            "goal": goal,
            "steps_completed": len([r for r in self.execution_results.values() if r.success]),
            "steps_total": len(plan),
            "output": final_output
        }
    
    def _create_plan(self, goal: str) -> List[ExecutionStep]:
        """
        Break goal into execution steps (small LLM context).
        
        Uses tool signatures to understand what's available.
        """
        # Get tool information
        tool_info = self._get_tool_signatures()
        
        prompt = f"""Break this goal into MINIMAL steps using available tools.

GOAL: {goal}

AVAILABLE TOOLS:
{tool_info}

RULES:
1. Use FEWEST steps possible
2. Each step uses ONE tool OR analyzes data
3. Only get time if goal explicitly mentions time ranges (e.g., "last 24 hours")
4. For simple goals like "List my last X", use just ONE step
5. Use tool "analyze_data" if you need to filter/format results

Examples:
- "List my last 3 activities" → [{{"step": 1, "description": "Get last 3 activities", "tool": "getMyActivities", "needs_data_from": null}}]
- "Show private activities from last 24h" → [{{"step": 1, "description": "Get current time", "tool": "getCurrentDateTime", "needs_data_from": null}}, {{"step": 2, "description": "Get activities from 24h ago", "tool": "getMyActivities", "needs_data_from": 1}}, {{"step": 3, "description": "Filter only private activities", "tool": "analyze_data", "needs_data_from": 2}}]

Output ONLY valid JSON array with minimal steps."""

        response = self.ollama.generate(
            prompt,
            system="You are a planning assistant. Output ONLY valid JSON."
        )
        
        # Parse JSON
        try:
            # Extract JSON from response
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0].strip()
            
            steps_data = json.loads(json_str)
            
            # Convert to ExecutionStep objects
            steps = []
            for item in steps_data:
                steps.append(ExecutionStep(
                    step_number=item['step'],
                    description=item['description'],
                    tool_name=item.get('tool'),
                    requires_data_from=item.get('needs_data_from')
                ))
            
            return steps
            
        except Exception as e:
            logger.error(f"Failed to parse plan: {e}")
            logger.error(f"Response was: {response}")
            # Fallback: simple single-step plan
            return [ExecutionStep(
                step_number=1,
                description="Execute goal directly",
                tool_name="getMyActivities"
            )]
    
    def _execute_step_with_retry(
        self,
        step: ExecutionStep,
        dry_run: bool
    ) -> StepResult:
        """
        Execute a step with self-correction retry loop.
        
        Try → Fail → Analyze error → Fix params → Retry
        """
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"   Attempt {attempt}/{self.max_retries}")
            
            try:
                # Special case: analyze_data (LLM reasoning)
                if step.tool_name == "analyze_data":
                    return self._analyze_data_step(step)
                
                # Regular tool execution
                # Phase A: Determine parameters (small LLM call)
                params = self._determine_parameters(step, attempt)
                logger.info(f"   Parameters: {params}")
                
                if dry_run:
                    logger.info(f"   [DRY RUN] Would call {step.tool_name}")
                    return StepResult(
                        success=True,
                        data={"dry_run": True},
                        attempts=attempt
                    )
                
                # Phase B: Execute tool
                tool = self.tools.get(step.tool_name)
                if not tool:
                    return StepResult(
                        success=False,
                        error=f"Tool '{step.tool_name}' not found",
                        attempts=attempt
                    )
                
                result = tool.execute(**params)
                
                # Phase C: Extract needed data (small LLM call)
                extracted = self._extract_needed_data(step, result)
                
                return StepResult(
                    success=True,
                    data=extracted,
                    attempts=attempt
                )
                
            except Exception as e:
                logger.warning(f"   Attempt {attempt} failed: {e}")
                
                if attempt < self.max_retries:
                    # Phase D: Analyze error and prepare retry (small LLM call)
                    step.params = self._fix_parameters_from_error(
                        step,
                        error=str(e),
                        previous_params=params if 'params' in locals() else {}
                    )
                else:
                    # Final attempt failed
                    return StepResult(
                        success=False,
                        error=str(e),
                        attempts=attempt
                    )
        
        return StepResult(success=False, error="Max retries exceeded", attempts=self.max_retries)
    
    def _determine_parameters(
        self,
        step: ExecutionStep,
        attempt: int
    ) -> Dict[str, Any]:
        """
        Determine parameters for tool call (small LLM context).
        
        Uses:
        - Tool signature (what params it accepts)
        - Previous step results (if step depends on them)
        - Step description (what we're trying to do)
        """
        # Get tool signature
        tool = self.tools.get(step.tool_name)
        if not tool:
            return {}
        
        tool_sig = self._format_tool_signature(tool)
        
        # Get data from previous steps if needed
        previous_data = ""
        if step.requires_data_from:
            prev_result = self.execution_results.get(step.requires_data_from)
            if prev_result and prev_result.success:
                previous_data = f"\nData from step {step.requires_data_from}:\n{json.dumps(prev_result.data, indent=2)}"
        
        # If we have params from error correction, use those
        if step.params:
            return step.params
        
        prompt = f"""Determine parameters for tool call.

TASK: {step.description}
TOOL: {step.tool_name}
{tool_sig}
{previous_data}

IMPORTANT FOR TIME FILTERING:
- "last 24 hours" means activities AFTER (now - 24h) → use after_unix with past timestamp
- "before yesterday" means activities BEFORE (yesterday) → use before_unix
- "activities after X" → use after_unix
- "activities before X" → use before_unix

What parameters should we pass?
Output ONLY valid JSON object with parameters.
If no parameters needed, output: {{}}
Examples:
{{"per_page": 10}}
{{"hours": 24}}
{{"after_unix": 1234567890, "per_page": 100}}"""

        response = self.ollama.generate(
            prompt,
            system="You are a parameter assistant. Output ONLY valid JSON object."
        )
        
        # Parse JSON
        try:
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0].strip()
            
            # Handle empty braces
            if json_str == '{}' or json_str == '':
                return {}
            
            params = json.loads(json_str)
            return params
            
        except Exception as e:
            logger.warning(f"Failed to parse parameters: {e}")
            return {}
    
    def _fix_parameters_from_error(
        self,
        step: ExecutionStep,
        error: str,
        previous_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze error and suggest fixed parameters (small LLM context).
        """
        tool = self.tools.get(step.tool_name)
        tool_sig = self._format_tool_signature(tool) if tool else ""
        
        prompt = f"""Fix tool call parameters based on error.

TASK: {step.description}
TOOL: {step.tool_name}
{tool_sig}

PREVIOUS PARAMETERS THAT FAILED: {json.dumps(previous_params)}
ERROR MESSAGE: {error}

IMPORTANT:
- If error says "unexpected keyword argument 'X'", REMOVE parameter 'X' completely
- If error says "missing required argument 'X'", ADD parameter 'X'
- If tool accepts NO parameters, return empty object: {{}}
- Read the tool signature carefully to see what parameters are actually accepted

Output ONLY valid JSON object with corrected parameters.
If no parameters needed, output: {{}}"""

        response = self.ollama.generate(
            prompt,
            system="You are an error-fixing assistant. Output ONLY valid JSON object."
        )
        
        try:
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0].strip()
            
            fixed_params = json.loads(json_str)
            logger.info(f"   Fixed parameters: {fixed_params}")
            return fixed_params
            
        except Exception as e:
            logger.warning(f"Failed to parse fixed parameters: {e}")
            return previous_params
    
    def _extract_needed_data(
        self,
        step: ExecutionStep,
        raw_result: Any
    ) -> Any:
        """
        Extract only the data needed from tool response (small LLM context).
        
        Instead of keeping entire response, extract what's relevant.
        """
        # If result is simple, keep as-is
        if not isinstance(raw_result, dict) or len(json.dumps(raw_result)) < 500:
            return raw_result
        
        prompt = f"""Extract relevant data from tool response.

TASK: {step.description}
TOOL RESPONSE: {json.dumps(raw_result, indent=2)[:2000]}

What data do we need from this response?
Keep only relevant fields for the task.
Output valid JSON.

Examples:
- If listing activities, extract: activities array
- If getting time, extract: timestamp/datetime
- If checking count, extract: count field"""

        response = self.ollama.generate(
            prompt,
            system="You are a data extraction assistant. Output ONLY valid JSON."
        )
        
        try:
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0].strip()
            
            extracted = json.loads(json_str)
            return extracted
            
        except Exception as e:
            logger.warning(f"Failed to extract data: {e}, using raw result")
            return raw_result
    
    def _analyze_data_step(self, step: ExecutionStep) -> StepResult:
        """
        Execute a data analysis/filtering step using LLM.
        
        This is for steps that need reasoning, not tool calls.
        """
        # Get data from previous step
        if not step.requires_data_from:
            return StepResult(
                success=False,
                error="Analysis step needs data from previous step"
            )
        
        prev_result = self.execution_results.get(step.requires_data_from)
        if not prev_result or not prev_result.success:
            return StepResult(
                success=False,
                error=f"Previous step {step.requires_data_from} has no data"
            )
        
        prompt = f"""Perform data analysis.

TASK: {step.description}
DATA: {json.dumps(prev_result.data, indent=2)}

Analyze the data and output result as valid JSON.
Examples:
- Filter items matching criteria
- Extract specific fields
- Count or summarize

Output ONLY valid JSON."""

        response = self.ollama.generate(
            prompt,
            system="You are a data analysis assistant. Output ONLY valid JSON."
        )
        
        try:
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0].strip()
            
            result = json.loads(json_str)
            return StepResult(success=True, data=result, attempts=1)
            
        except Exception as e:
            logger.error(f"Failed to analyze data: {e}")
            return StepResult(success=False, error=str(e), attempts=1)
    
    def _format_final_output(
        self,
        goal: str,
        plan: List[ExecutionStep]
    ) -> str:
        """
        Format all results into user-friendly output (small LLM context).
        """
        # Collect all successful results
        results_summary = []
        for step_num, result in self.execution_results.items():
            step = next((s for s in plan if s.step_number == step_num), None)
            if step and result.success:
                results_summary.append({
                    "step": step_num,
                    "description": step.description,
                    "data": result.data
                })
        
        prompt = f"""Format execution results for user.

ORIGINAL GOAL: {goal}

RESULTS:
{json.dumps(results_summary, indent=2)}

Create a concise, user-friendly summary.
Focus on what the user asked for.
Use plain text or simple formatting."""

        response = self.ollama.generate(
            prompt,
            system="You are a results formatter. Create clear, concise summaries."
        )
        
        return response.strip()
    
    def _get_tool_signatures(self) -> str:
        """Get formatted list of available tools with signatures."""
        lines = []
        for name, tool in self.tools.tools.items():
            # Skip pseudo-tools (documentation only)
            if name == "llm_analyze_pseudo":
                continue
            desc = tool.description
            params_info = ""
            if tool.parameters:
                params = [f"{p.get('name', '?')}:{p.get('type', 'any')}" for p in tool.parameters]
                params_info = f" ({', '.join(params)})"
            lines.append(f"- {name}{params_info}: {desc}")
        return "\n".join(lines)
    
    def _format_tool_signature(self, tool: Any) -> str:
        """Format single tool signature for LLM."""
        desc = tool.description
        params_info = ""
        if tool.parameters and len(tool.parameters) > 0:
            params = [f"{p.get('name', '?')}: {p.get('type', 'any')} - {p.get('description', 'N/A')}" 
                     for p in tool.parameters]
            params_info = f"\nParameters:\n  " + "\n  ".join(params)
        else:
            params_info = "\nParameters: NONE (call with no parameters)"
        return f"Description: {desc}{params_info}"
