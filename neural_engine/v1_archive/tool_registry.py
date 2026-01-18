import os
import importlib
import inspect
import logging
from neural_engine.tools.base_tool import BaseTool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self, tool_directory="neural_engine/tools"):
        self.tool_directory = tool_directory
        self.tools = {}
        self.refresh()

    def refresh(self):
        self.tools = {}
        self._scan_and_load()

    def _scan_and_load(self):
        for root, _, files in os.walk(self.tool_directory):
            for filename in files:
                if filename.endswith(".py") and filename != "__init__.py" and filename != "base_tool.py":
                    self._load_tool(root, filename)

    def _load_tool(self, root, filename):
        filepath = os.path.join(root, filename)
        module_name = self._get_module_name(filepath)

        try:
            # Use importlib.import_module instead of spec_from_file_location
            # This ensures relative imports work correctly
            module = importlib.import_module(module_name)

            found_tool = False
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                    tool_instance = obj()
                    tool_def = tool_instance.get_tool_definition()
                    tool_name = tool_def.get("name")

                    if not tool_name:
                        logger.warning(f"Tool class {name} in {filepath} is missing a 'name' in its definition. Skipping.")
                        continue

                    if tool_name in self.tools:
                        logger.warning(f"Duplicate tool name '{tool_name}' found in {filepath}. Overwriting existing tool.")

                    # Store module_name and class_name on tool instance for code generation
                    tool_instance._module_name = module_name
                    tool_instance._class_name = name
                    
                    self.tools[tool_name] = tool_instance
                    logger.info(f"Loaded tool: '{tool_name}' from {filepath}")
                    found_tool = True

            if not found_tool:
                logger.warning(f"No valid tool class found in {filepath}")

        except Exception as e:
            logger.error(f"Failed to load tool from {filepath}: {e}")

    def _get_module_name(self, filepath):
        # Remove .py extension first, then replace / with .
        if filepath.endswith(".py"):
            filepath = filepath[:-3]
        return filepath.replace("/", ".")

    def get_tool(self, tool_key):
        return self.tools.get(tool_key)

    def get_all_tools(self):
        return self.tools
    
    def get_all_tool_definitions(self):
        definitions = {}
        for name, tool in self.tools.items():
            tool_def = tool.get_tool_definition()
            # Add stored metadata
            if hasattr(tool, '_module_name'):
                tool_def["module_name"] = tool._module_name
            if hasattr(tool, '_class_name'):
                tool_def["class_name"] = tool._class_name
            definitions[name] = tool_def
        return definitions
