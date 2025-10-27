import os
import importlib
from typing import Dict, List
from ..tools.base_tool import BaseTool

class ToolRegistry:
    def __init__(self, tool_directory="neural_engine/tools"):
        self.tool_directory = tool_directory
        self.tools: Dict[str, BaseTool] = {}
        self.tool_definitions: List[Dict] = []
        self._discover_and_register_tools()

    def _discover_and_register_tools(self):
        for filename in os.listdir(self.tool_directory):
            if filename.endswith("_tool.py"):
                module_name = f"neural_engine.tools.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    for attribute_name in dir(module):
                        attribute = getattr(module, attribute_name)
                        if isinstance(attribute, type) and issubclass(attribute, BaseTool) and attribute is not BaseTool:
                            tool_instance = attribute()
                            tool_name = tool_instance.get_tool_definition()["name"]
                            self.tools[tool_name] = tool_instance
                            self.tool_definitions.append(tool_instance.get_tool_definition())
                except ImportError as e:
                    print(f"Error importing tool {module_name}: {e}")

    def get_tool(self, name: str) -> BaseTool:
        return self.tools.get(name)

    def get_all_tool_definitions(self) -> List[Dict]:
        return self.tool_definitions
