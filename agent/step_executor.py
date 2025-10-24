"""
Step Executor - Execute Individual Steps with Fresh LLM Context

Each step gets its own fresh LLM context, making it simple for small models.
"""

import logging
from typing import Any, Dict, List, Optional

from agent.instruction_parser_v2 import StepDefinition
from agent.ollama_client import OllamaClient
from agent.template_engine import TemplateEngine
from agent.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class StepExecutor:
    """
    Executes individual instruction steps with fresh LLM context.
    
    Each step execution is independent and focused, making it suitable
    for small language models.
    """
    
    def __init__(
        self,
        ollama: OllamaClient,
        registry: ToolRegistry,
        template_engine: Optional[TemplateEngine] = None
    ):
        """
        Initialize step executor.
        
        Args:
            ollama: Ollama client for LLM calls
            registry: Tool registry for executing tools
            template_engine: Optional template engine (creates new if None)
        """
        self.ollama = ollama
        self.registry = registry
        self.template = template_engine or TemplateEngine()
        self.step_results: Dict[str, Any] = {}
    
    def execute_step(
        self,
        step: StepDefinition,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a single step with fresh LLM context.
        
        Args:
            step: Step definition to execute
            dry_run: If True, don't actually execute tools
            
        Returns:
            Dict with: success, result, error
        """
        logger.info(f"Executing step: {step.id} ({step.description})")
        
        try:
            # Check if this is a loop step
            if step.is_loop_step():
                return self._execute_loop_step(step, dry_run)
            
            # Check if this is an LLM reasoning step
            elif step.is_llm_step():
                return self._execute_llm_step(step, dry_run)
            
            # Regular tool execution step
            else:
                return self._execute_tool_step(step, dry_run)
        
        except Exception as e:
            logger.error(f"Step {step.id} failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "step_id": step.id
            }
    
    def _execute_tool_step(
        self,
        step: StepDefinition,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute a regular tool step."""
        
        # Get tool
        tool = self.registry.get(step.tool)
        if not tool:
            return {
                "success": False,
                "error": f"Tool {step.tool} not found",
                "step_id": step.id
            }
        
        # Determine parameters
        if step.params_template:
            # Extract params using LLM if template contains variables
            params = self._extract_parameters(step, tool)
        elif step.params:
            # Use static params
            params = step.params
        else:
            # No params
            params = {}
        
        if params is None:
            return {
                "success": False,
                "error": "Failed to extract parameters",
                "step_id": step.id
            }
        
        logger.info(f"  Tool: {step.tool}")
        logger.info(f"  Params: {params}")
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would execute {step.tool} with {params}")
            return {
                "success": True,
                "result": {"dry_run": True},
                "step_id": step.id
            }
        
        # Execute tool
        try:
            result = tool.execute(**params)
            
            # Save result if save_as is specified
            if step.save_as:
                self.step_results[step.save_as] = result
                self.template.set_context({step.save_as: result})
                logger.info(f"  Saved result as: {step.save_as}")
            
            logger.info(f"  ✅ Step {step.id} completed successfully")
            
            return {
                "success": True,
                "result": result,
                "step_id": step.id,
                "params": params
            }
        
        except Exception as e:
            logger.error(f"  ❌ Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "step_id": step.id,
                "params": params
            }
    
    def _execute_loop_step(
        self,
        step: StepDefinition,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute a step that loops over an array."""
        
        # Get array to loop over
        loop_array = self.template.get_loop_array(step.loop)
        
        if not loop_array:
            logger.warning(f"  Loop array is empty for step {step.id}")
            return {
                "success": True,
                "result": [] if step.aggregate else {},
                "step_id": step.id,
                "loop_count": 0
            }
        
        logger.info(f"  Loop: {len(loop_array)} iterations")
        
        # Get tool
        tool = self.registry.get(step.tool)
        if not tool:
            return {
                "success": False,
                "error": f"Tool {step.tool} not found",
                "step_id": step.id
            }
        
        # Execute for each item
        results = []
        errors = []
        
        for idx, item in enumerate(loop_array):
            # Set loop context
            self.template.set_loop_context(item, idx)
            
            # Render parameters for this iteration
            params = self.template.render_params(step.params_template)
            
            logger.info(f"  Iteration {idx + 1}/{len(loop_array)}: {params}")
            
            if dry_run:
                logger.info(f"    [DRY RUN] Would execute {step.tool}")
                results.append({"dry_run": True, "iteration": idx})
                continue
            
            # Execute tool
            try:
                result = tool.execute(**params)
                results.append(result)
                logger.info(f"    ✅ Iteration {idx + 1} completed")
            
            except Exception as e:
                logger.error(f"    ❌ Iteration {idx + 1} failed: {e}")
                errors.append({
                    "iteration": idx,
                    "error": str(e),
                    "params": params
                })
        
        # Clear loop context
        self.template.clear_loop_context()
        
        # Aggregate or return all results
        if step.aggregate:
            final_result = results
        else:
            final_result = {
                "results": results,
                "errors": errors,
                "total": len(loop_array),
                "successful": len(results),
                "failed": len(errors)
            }
        
        # Save result
        if step.save_as:
            self.step_results[step.save_as] = final_result
            self.template.set_context({step.save_as: final_result})
        
        logger.info(f"  ✅ Loop step {step.id} completed: {len(results)}/{len(loop_array)} successful")
        
        return {
            "success": len(errors) == 0,
            "result": final_result,
            "step_id": step.id,
            "loop_count": len(loop_array),
            "errors": errors if errors else None
        }
    
    def _execute_llm_step(
        self,
        step: StepDefinition,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute an LLM reasoning step."""
        
        # Get input data
        input_data = self.template.render_value(step.input) if step.input else None
        
        # Build prompt
        prompt = step.context or step.description
        
        if input_data:
            import json
            prompt += f"\n\nInput data:\n{json.dumps(input_data, indent=2)}"
        
        if step.output_format:
            import json
            prompt += f"\n\nRequired output format:\n{json.dumps(step.output_format, indent=2)}"
        
        prompt += "\n\nRespond ONLY with valid JSON matching the required format."
        
        logger.info(f"  LLM reasoning step")
        logger.info(f"  Context length: {len(prompt)} chars")
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would call LLM for reasoning")
            return {
                "success": True,
                "result": {"dry_run": True},
                "step_id": step.id
            }
        
        # Call LLM
        try:
            system_context = "You are a helpful assistant that analyzes data and returns structured JSON."
            response = self.ollama.generate(prompt, system=system_context)
            
            # Try to parse JSON from response
            import json
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {"raw_response": response}
            
            # Save result
            if step.save_as:
                self.step_results[step.save_as] = result
                self.template.set_context({step.save_as: result})
            
            logger.info(f"  ✅ LLM step {step.id} completed")
            
            return {
                "success": True,
                "result": result,
                "step_id": step.id
            }
        
        except Exception as e:
            logger.error(f"  ❌ LLM step failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "step_id": step.id
            }
    
    def _extract_parameters(
        self,
        step: StepDefinition,
        tool
    ) -> Optional[Dict[str, Any]]:
        """
        Extract parameters using LLM if needed, or render template directly.
        
        Args:
            step: Step definition
            tool: Tool to execute
            
        Returns:
            Parameters dict or None if extraction fails
        """
        # First try direct template rendering
        params = self.template.render_params(step.params_template)
        
        # Check if all values are resolved (no None values from missing variables)
        if self._all_values_resolved(params):
            return params
        
        # If some values are None, we need LLM to help extract them
        logger.info(f"  Some parameters not resolved, using LLM extraction")
        
        # Build prompt for parameter extraction
        tool_dict = tool.to_dict()
        param_info = tool_dict.get('parameters', [])
        
        prompt = f"""Task: {step.description}

Tool: {step.tool}
Parameters needed:"""
        
        for p in param_info:
            param_name = p.get('name', 'unknown')
            param_type = p.get('type', 'any')
            required = p.get('required', False)
            param_desc = p.get('description', '')
            req_str = "(required)" if required else "(optional)"
            prompt += f"\n  - {param_name} ({param_type}) {req_str}: {param_desc}"
        
        # Add context from dependencies if available
        if step.depends_on:
            prompt += "\n\nAvailable data from previous steps:"
            for dep_id in step.depends_on:
                if dep_id in self.step_results:
                    import json
                    result_summary = self._summarize_result(self.step_results[dep_id])
                    prompt += f"\n  {dep_id}: {json.dumps(result_summary, indent=2)}"
        
        prompt += "\n\nDetermine the parameters for this tool call."
        prompt += "\n\nRespond ONLY with valid JSON:"
        prompt += '\n{"params": {"param_name": "value"}}'
        
        # Call LLM
        try:
            system_context = "You are a parameter extractor. Output ONLY valid JSON."
            response = self.ollama.generate(prompt, system=system_context)
            
            # Parse JSON
            import json
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                param_data = json.loads(json_match.group())
                extracted_params = param_data.get('params', {})
                
                # Merge with template params (template takes precedence)
                final_params = {**extracted_params, **{k: v for k, v in params.items() if v is not None}}
                
                return final_params
            else:
                logger.error(f"Could not parse parameters from LLM response")
                return None
        
        except Exception as e:
            logger.error(f"Parameter extraction failed: {e}")
            return None
    
    def _all_values_resolved(self, params: Dict[str, Any]) -> bool:
        """Check if all parameter values are resolved (no None values)."""
        for value in params.values():
            if value is None:
                return False
            if isinstance(value, dict):
                if not self._all_values_resolved(value):
                    return False
        return True
    
    def _summarize_result(self, result: Any, max_items: int = 3) -> Any:
        """Summarize a result for inclusion in LLM prompt."""
        if isinstance(result, list):
            if len(result) <= max_items:
                return result
            else:
                return result[:max_items] + [f"... and {len(result) - max_items} more"]
        elif isinstance(result, dict):
            # Keep structure but summarize nested lists
            return {k: self._summarize_result(v, max_items) for k, v in result.items()}
        else:
            return result
    
    def get_result(self, step_id: str) -> Optional[Any]:
        """Get result of a previously executed step."""
        return self.step_results.get(step_id)
    
    def get_all_results(self) -> Dict[str, Any]:
        """Get all step results."""
        return self.step_results.copy()
    
    def clear_results(self):
        """Clear all step results."""
        self.step_results.clear()
        self.template.set_context({})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("StepExecutor module loaded successfully")
    print("Run tests with actual Ollama client and tools")
