from .neuron import BaseNeuron
from .code_validator_neuron import CodeValidatorNeuron
from typing import Dict, Tuple
import json

class CodeGeneratorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, tool_registry, enable_validation=True, max_retries=5):
        super().__init__(message_bus, ollama_client)
        self.tool_registry = tool_registry
        self.enable_validation = enable_validation
        self.validator = CodeValidatorNeuron(max_retries=max_retries) if enable_validation else None

    def _load_prompt(self):
        with open("neural_engine/prompts/code_generator_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id: str, data: dict, depth: int):
        goal = data["goal"]
        
        # Support both old format (selected_tool_name) and new format (selected_tools list)
        if "selected_tools" in data:
            # New format from updated tool_selector
            tools = data["selected_tools"]
            tool_name = tools[0]["name"]
            module_name = tools[0]["module"]
            class_name = tools[0]["class"]
        else:
            # Old format for backward compatibility
            tool_name = data["selected_tool_name"]
            module_name = data["selected_tool_module"]
            class_name = data["selected_tool_class"]

        # Get full tool definition for parameter info
        tool_definitions = self.tool_registry.get_all_tool_definitions()
        tool_definition = tool_definitions.get(tool_name, {})

        # Build context for validation
        context = {
            "goal": goal,
            "tool_name": tool_name,
            "tool_module": module_name,
            "tool_class": class_name,
            "tool_definition": tool_definition
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
            context: May include retry_instruction for feedback-based retry
        """
        prompt_template = self._load_prompt()
        
        # Check if this is a retry with feedback
        if "retry_instruction" in context:
            # Prepend retry instruction to prompt
            retry_prefix = f"\n\n{context['retry_instruction']}\n\n"
            prompt = retry_prefix + prompt_template.format(
                goal=context["goal"],
                tool_name=context["tool_name"],
                tool_module=context["tool_module"],
                tool_class=context["tool_class"],
                tool_definition=json.dumps(context["tool_definition"], indent=2)
            )
        else:
            # Normal first attempt
            prompt = prompt_template.format(
                goal=context["goal"],
                tool_name=context["tool_name"],
                tool_module=context["tool_module"],
                tool_class=context["tool_class"],
                tool_definition=json.dumps(context["tool_definition"], indent=2)
            )

        # Use temperature=0 for deterministic code generation
        response = self.ollama_client.client.generate(
            model=self.ollama_client.model,
            prompt=prompt,
            options={"temperature": 0}
        )
        generated_code = response['response'].strip()

        # Clean up the code if it's wrapped in markdown
        if generated_code.startswith("```python"):
            generated_code = generated_code[9:]
        if generated_code.startswith("```"):
            generated_code = generated_code[3:]
        if generated_code.endswith("```"):
            generated_code = generated_code[:-3]
        
        return generated_code.strip()
