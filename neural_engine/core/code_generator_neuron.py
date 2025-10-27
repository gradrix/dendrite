from .neuron import BaseNeuron
import json

class CodeGeneratorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, tool_registry):
        super().__init__(message_bus, ollama_client)
        self.tool_registry = tool_registry

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

        prompt_template = self._load_prompt()
        prompt = prompt_template.format(
            goal=goal,
            tool_name=tool_name,
            tool_module=module_name,
            tool_class=class_name,
            tool_definition=json.dumps(tool_definition, indent=2)
        )

        response = self.ollama_client.generate(prompt=prompt)
        generated_code = response['response'].strip()

        # Clean up the code if it's wrapped in markdown
        if generated_code.startswith("```python"):
            generated_code = generated_code[9:]
        if generated_code.startswith("```"):
            generated_code = generated_code[3:]
        if generated_code.endswith("```"):
            generated_code = generated_code[:-3]
        
        generated_code = generated_code.strip()

        result_data = {
            "goal": goal,
            "tool_name": tool_name,
            "generated_code": generated_code
        }
        
        # Use new metadata-rich message format
        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="code_generation",
            data=result_data,
            depth=depth
        )
        
        return result_data
