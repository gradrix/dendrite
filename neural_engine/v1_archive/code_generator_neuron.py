from .neuron import BaseNeuron, fractal_process
from .code_validator_neuron import CodeValidatorNeuron
from .parameter_extractor import ParameterExtractor, MemoryParameterExtractor
from typing import Dict, Tuple
import json

class CodeGeneratorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, tool_registry, enable_validation=True, 
                 max_retries=5, use_parameter_extraction=True):
        super().__init__(message_bus, ollama_client)
        self.tool_registry = tool_registry
        self.enable_validation = enable_validation
        self.use_parameter_extraction = use_parameter_extraction
        self.validator = CodeValidatorNeuron(max_retries=max_retries) if enable_validation else None
        
        # Initialize parameter extractors
        if self.use_parameter_extraction:
            self.param_extractor = ParameterExtractor(ollama_client)
            self.memory_extractor = MemoryParameterExtractor(ollama_client)  # Pass LLM client
        else:
            self.param_extractor = None
            self.memory_extractor = None

    def _load_prompt(self):
        with open("neural_engine/prompts/code_generator_prompt.txt", "r") as f:
            return f.read()

    @fractal_process
    def process(self, goal_id: str, data: dict, depth: int):
        goal = data["goal"]
        
        # Support both old format (selected_tool_name) and new format (selected_tools list)
        if "selected_tools" in data:
            # New format from updated tool_selector
            tools = data["selected_tools"]
            if not tools or len(tools) == 0:
                # No tools selected - cannot generate code
                result_data = {
                    "goal": goal,
                    "error": "No tools selected for code generation",
                    "generated_code": ""
                }
                self.add_message_with_metadata(
                    goal_id=goal_id,
                    message_type="code_generation",
                    data=result_data,
                    depth=depth
                )
                return result_data
            
            tool_name = tools[0]["name"]
            # Handle both module/class and module_name/class_name formats
            module_name = tools[0].get("module") or tools[0].get("module_name")
            class_name = tools[0].get("class") or tools[0].get("class_name")
        else:
            # Old format for backward compatibility
            tool_name = data["selected_tool_name"]
            module_name = data["selected_tool_module"]
            class_name = data["selected_tool_class"]

        # Get full tool definition for parameter info
        tool_definitions = self.tool_registry.get_all_tool_definitions()
        tool_definition = tool_definitions.get(tool_name, {})
        
        # STAGE 1: Extract parameters BEFORE code generation
        extracted_params = None
        param_hints = None
        
        if self.use_parameter_extraction:
            # Get parameter names from tool definition
            params = tool_definition.get("parameters", [])
            param_names = []
            if isinstance(params, list):
                # Check if list contains dicts (tool definition format)
                if params and isinstance(params[0], dict):
                    # Extract parameter names from dicts
                    param_names = [p.get('name', p) for p in params]
                else:
                    # Already list of strings
                    param_names = params
            elif isinstance(params, dict):
                param_names = params.get("required", [])
            
            # Fast path for memory operations (most common)
            if tool_name == "memory_write":
                extracted_params = self.memory_extractor.extract_memory_write_params(goal)
                print(f"🎯 Memory write params extracted: {extracted_params}")
            elif tool_name == "memory_read":
                extracted_params = self.memory_extractor.extract_memory_read_params(goal)
                print(f"🎯 Memory read params extracted: {extracted_params}")
            elif param_names:
                # General extraction for other tools
                tool_desc = tool_definition.get("description", "")
                extracted_params = self.param_extractor.extract_parameters(
                    goal, tool_name, tool_desc, param_names
                )
                print(f"🎯 Params extracted for {tool_name}: {extracted_params}")
            
            # Create hints for code generator
            if extracted_params:
                param_hints = self.param_extractor.create_parameter_hints(extracted_params)

        # Build context for validation
        context = {
            "goal": goal,
            "tool_name": tool_name,
            "tool_module": module_name,
            "tool_class": class_name,
            "tool_definition": tool_definition,
            "extracted_params": extracted_params,  # NEW: Pass extracted params
            "param_hints": param_hints  # NEW: Pass hints
        }

        # Generate code with validation and retry
        if self.enable_validation:
            generated_code, validation_result = self._generate_with_validation(
                goal_id, context, depth
            )
        else:
            # Fallback to original behavior without validation
            generated_code = self._generate_code_once(context)
            validation_result = None

        result_data = {
            "goal": goal,
            "tool_name": tool_name,
            "generated_code": generated_code
        }
        
        # Add extraction metadata if available
        if extracted_params:
            result_data["extracted_params"] = extracted_params
        
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
            message_type="code_generation",
            data=result_data,
            depth=depth
        )
        
        return result_data
    
    def _generate_with_validation(self, goal_id: str, context: Dict, depth: int) -> Tuple[str, Dict]:
        """
        Generate code with validation and retry mechanism.
        
        Attempts up to max_retries times, providing targeted feedback each time.
        
        Returns:
            (generated_code, validation_result)
        """
        attempt = 0
        retry_context = context.copy()
        
        while attempt < self.validator.max_retries:
            attempt += 1
            
            # Generate code
            generated_code = self._generate_code_once(retry_context)
            
            # Validate
            validation_result = self.validator.validate_code(generated_code, context)
            validation_result["attempts"] = attempt
            
            if validation_result["valid"]:
                if attempt > 1:
                    print(f"✅ Code generation successful after {attempt} attempts")
                return generated_code, validation_result
            
            # Code has errors - check if we should retry
            if not self.validator.should_retry(attempt):
                print(f"⚠️  Code validation failed after {attempt} attempts. Returning best effort.")
                return generated_code, validation_result
            
            # Build retry context with targeted feedback
            print(f"🔄 Retry attempt {attempt}/{self.validator.max_retries}: {validation_result['feedback'][:100]}...")
            retry_context = self.validator.get_retry_context(
                validation_result, context, attempt
            )
        
        # Max retries reached
        print(f"⚠️  Max retries ({self.validator.max_retries}) reached. Returning last attempt.")
        return generated_code, validation_result
    
    def _generate_code_once(self, context: Dict) -> str:
        """
        Generate code once (single LLM call).
        
        Args:
            context: May include retry_instruction for feedback-based retry,
                     param_hints for extracted parameter values
        """
        prompt_template = self._load_prompt()
        
        # Add parameter hints if available
        param_hints_text = ""
        if "param_hints" in context and context["param_hints"]:
            param_hints_text = f"\n\n{context['param_hints']}\n"
            param_hints_text += "USE THESE EXACT PARAMETER VALUES IN YOUR CODE.\n"
        
        # Check if this is a retry with feedback
        if "retry_instruction" in context:
            # Prepend retry instruction to prompt
            retry_prefix = f"\n\n{context['retry_instruction']}\n\n"
            prompt = retry_prefix + param_hints_text + prompt_template.format(
                goal=context["goal"],
                tool_name=context["tool_name"],
                tool_module=context["tool_module"],
                tool_class=context["tool_class"],
                tool_definition=json.dumps(context["tool_definition"], indent=2)
            )
        else:
            # Normal first attempt with parameter hints
            prompt = param_hints_text + prompt_template.format(
                goal=context["goal"],
                tool_name=context["tool_name"],
                tool_module=context["tool_module"],
                tool_class=context["tool_class"],
                tool_definition=json.dumps(context["tool_definition"], indent=2)
            )

        # Use temperature=0 for deterministic code generation
        response = self.ollama_client.generate(
            prompt=prompt,
            context="code_generation",
            options={"temperature": 0}
        )
        generated_code = response['response'].strip()

        # Clean up the code if it's wrapped in markdown
        generated_code = self._strip_markdown_fences(generated_code)
        
        return generated_code.strip()
    
    def _strip_markdown_fences(self, code: str) -> str:
        """Strip markdown code fences and handle duplicated code blocks."""
        import re
        
        # Remove leading ```python or ```
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        
        # Remove trailing ```
        if code.endswith("```"):
            code = code[:-3]
        
        # Check for duplicated code blocks (LLM sometimes outputs code twice)
        # Pattern: code block followed by ``` ```python and same code again
        fence_pattern = r'\n*```\s*```python\n*'
        if re.search(fence_pattern, code):
            # Take only the first code block
            parts = re.split(fence_pattern, code)
            code = parts[0].strip()
        
        # Also handle just ``` in the middle (without python marker)
        fence_pattern2 = r'\n*```\s*```\n*'
        if re.search(fence_pattern2, code):
            parts = re.split(fence_pattern2, code)
            code = parts[0].strip()
        
        return code.strip()
