from .neuron import BaseNeuron
from .tool_discovery import ToolDiscovery
from .tool_selection_validator_neuron import ToolSelectionValidatorNeuron
from .task_simplifier import TaskSimplifier
from typing import Optional, Dict, List, Tuple
import json

class ToolSelectorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, tool_registry, 
                 tool_discovery: Optional[ToolDiscovery] = None,
                 enable_validation: bool = False,  # Disabled by default - mostly LLM quality issues
                 use_simplifier: bool = True,  # Use TaskSimplifier to help small LLM
                 max_retries: int = 3):  # Reduced to 3 to avoid test timeouts
        super().__init__(message_bus, ollama_client)
        self.tool_registry = tool_registry
        self.tool_discovery = tool_discovery
        self.enable_validation = enable_validation
        self.use_simplifier = use_simplifier
        self.validator = ToolSelectionValidatorNeuron(max_retries=max_retries) if enable_validation else None
        self.simplifier = TaskSimplifier() if use_simplifier else None
        
        # Track usage for performance comparison
        self.selection_stats = {
            "semantic_enabled": tool_discovery is not None,
            "simplifier_enabled": use_simplifier,
            "total_selections": 0,
            "avg_candidates_considered": 0,
            "simplifier_narrowing_count": 0
        }

    def _load_prompt(self):
        with open("neural_engine/prompts/tool_selector_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id: str, goal: str, depth: int):
        # Stage 3: LLM Selection from top candidates
        if self.tool_discovery:
            # Use 3-stage filtering (Stages 1+2 already done in discover_tools)
            discovered_tools = self.tool_discovery.discover_tools(
                goal_text=goal,
                semantic_limit=20,  # Stage 1: 1000+ → 20 candidates
                ranking_limit=5      # Stage 2: 20 → 5 top performers
            )
            
            # Build tool definitions for top 5 candidates only
            tool_definitions = {}
            for tool_info in discovered_tools:
                tool_name = tool_info['tool_name']
                tool = self.tool_registry.get_tool(tool_name)
                if tool:
                    tool_def = tool.get_tool_definition()
                    # Add metadata from registry
                    if hasattr(tool, '_module_name'):
                        tool_def["module_name"] = tool._module_name
                    if hasattr(tool, '_class_name'):
                        tool_def["class_name"] = tool._class_name
                    # Add performance score from Stage 2
                    tool_def["performance_score"] = tool_info.get('score', 0.5)
                    tool_def["success_rate"] = tool_info.get('success_rate')
                    tool_definitions[tool_name] = tool_def
            
            self.selection_stats["avg_candidates_considered"] = len(tool_definitions)
        else:
            # Fallback: Use all tools (original behavior)
            tool_definitions = self.tool_registry.get_all_tool_definitions()
            self.selection_stats["avg_candidates_considered"] = len(tool_definitions)
        
        # NEW: Try TaskSimplifier to narrow tools before LLM
        narrowed_tools = tool_definitions
        simplifier_hint = None
        simplifier_confidence = 0.0
        
        if self.simplifier and len(tool_definitions) > 3:
            # Get tool names
            available_tool_names = list(tool_definitions.keys())
            
            # Ask simplifier to narrow down
            simplified = self.simplifier.simplify_for_tool_selection(goal, available_tool_names)
            
            # If confident, use narrowed list
            if simplified["confidence"] > 0.6:
                narrowed_tool_names = simplified["narrowed_tools"]
                narrowed_tools = {
                    name: tool_definitions[name] 
                    for name in narrowed_tool_names 
                    if name in tool_definitions
                }
                simplifier_hint = simplified["explicit_hint"]
                simplifier_confidence = simplified["confidence"]
                
                self.selection_stats["simplifier_narrowing_count"] += 1
                print(f"🎯 TaskSimplifier: {len(tool_definitions)} tools → {len(narrowed_tools)} tools (confidence: {simplifier_confidence:.2f})")
        
        self.selection_stats["total_selections"] += 1
        
        # Build context for validation
        context = {
            "goal": goal,
            "available_tools": narrowed_tools,  # Use narrowed tools
            "simplifier_hint": simplifier_hint  # Pass hint to LLM
        }
        
        # Select tool with validation and retry
        if self.enable_validation:
            selected_tools, validation_result = self._select_with_validation(
                goal_id, context, depth, narrowed_tools
            )
        else:
            # Fallback to original behavior without validation
            selected_tools = self._select_tool_once(context, narrowed_tools)
            validation_result = None
        
        result_data = {
            "goal": goal,
            "selected_tools": selected_tools
        }
        
        # Add simplifier metadata if used
        if simplifier_hint:
            result_data["simplifier"] = {
                "narrowed_from": len(tool_definitions),
                "narrowed_to": len(narrowed_tools),
                "confidence": simplifier_confidence
            }
        
        # Add validation metadata if available
        if validation_result:
            result_data["validation"] = {
                "valid": validation_result["valid"],
                "attempts": validation_result.get("attempts", 1),
                "had_errors": len(validation_result.get("errors", [])) > 0
            }
        
        # Use new metadata-rich message format
        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="tool_selection",
            data=result_data,
            depth=depth
        )
        
        return result_data
    
    def _select_with_validation(self, goal_id: str, context: Dict, depth: int, tool_definitions: Dict) -> Tuple[List[Dict], Dict]:
        """
        Select tool with validation and retry mechanism.
        
        Returns:
            (selected_tools, validation_result)
        """
        attempt = 0
        retry_context = context.copy()
        
        while attempt < self.validator.max_retries:
            attempt += 1
            
            # Select tool
            selected_tools = self._select_tool_once(retry_context, tool_definitions)
            
            # Validate
            validation_result = self.validator.validate_selection(selected_tools, context)
            validation_result["attempts"] = attempt
            validation_result["previous_selection"] = selected_tools
            
            if validation_result["valid"]:
                if attempt > 1:
                    print(f"✅ Tool selection successful after {attempt} attempts")
                return selected_tools, validation_result
            
            # Selection has errors - check if we should retry
            if not self.validator.should_retry(attempt):
                print(f"⚠️  Tool selection validation failed after {attempt} attempts. Using best effort.")
                return selected_tools, validation_result
            
            # Build retry context with targeted feedback
            print(f"🔄 Retry attempt {attempt}/{self.validator.max_retries}: {validation_result['feedback'][:100]}...")
            retry_context = self.validator.get_retry_context(
                validation_result, context, attempt
            )
        
        # Max retries reached
        print(f"⚠️  Max retries ({self.validator.max_retries}) reached. Using last attempt.")
        return selected_tools, validation_result
    
    def _select_tool_once(self, context: Dict, tool_definitions: Dict) -> List[Dict]:
        """
        Select tool once (single LLM call).
        
        Args:
            context: May include retry_instruction for feedback-based retry,
                     and simplifier_hint for task simplification
            tool_definitions: Available tools (may be narrowed by simplifier)
        
        Returns:
            List of selected tools
        """
        prompt_template = self._load_prompt()
        
        # Build prompt with optional hints
        prompt_parts = []
        
        # Add simplifier hint if available (helps small LLM understand task)
        if "simplifier_hint" in context and context["simplifier_hint"]:
            prompt_parts.append(f"HINT: {context['simplifier_hint']}\n\n")
        
        # Add retry instruction if this is a retry
        if "retry_instruction" in context:
            prompt_parts.append(f"{context['retry_instruction']}\n\n")
        
        # Add main prompt
        prompt_parts.append(prompt_template.format(
            goal=context["goal"],
            tools=json.dumps(tool_definitions, indent=2)
        ))
        
        prompt = "".join(prompt_parts)

        response = self.ollama_client.generate(prompt=prompt)
        
        try:
            # Parse LLM response
            response_json = json.loads(response['response'].strip())
            selected_tool_name = response_json["tool_name"]

            tool = self.tool_registry.get_tool(selected_tool_name)
            if not tool:
                raise ValueError(f"Tool '{selected_tool_name}' not found in registry.")

            # Get enriched tool definition from registry
            tool_info = tool_definitions[selected_tool_name]
            
            return [{
                "name": selected_tool_name,
                "module": tool_info["module_name"],
                "class": tool_info["class_name"]
            }]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Failed to parse response - return empty list
            print(f"⚠️  Failed to parse tool selection: {e}")
            return []
