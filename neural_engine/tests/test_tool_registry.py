import unittest
import os
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.tools.base_tool import BaseTool

class TestToolRegistry(unittest.TestCase):
    def setUp(self):
        self.test_tools_dir = "neural_engine/tests/test_tools"
        os.makedirs(self.test_tools_dir, exist_ok=True)
        self.create_test_tools()

    def tearDown(self):
        for root, dirs, files in os.walk(self.test_tools_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.test_tools_dir)

    def create_test_tools(self):
        # Create a valid tool
        with open(os.path.join(self.test_tools_dir, "test_tool.py"), "w") as f:
            f.write("""
from neural_engine.tools.base_tool import BaseTool
class TestTool(BaseTool):
    def get_tool_definition(self):
        return {"name": "test_tool"}
    def execute(self, **kwargs):
        return {"status": "success"}
""")

        # Create a file with multiple tools
        with open(os.path.join(self.test_tools_dir, "multi_tool.py"), "w") as f:
            f.write("""
from neural_engine.tools.base_tool import BaseTool
class MultiTool1(BaseTool):
    def get_tool_definition(self):
        return {"name": "multi_tool_1"}
    def execute(self, **kwargs):
        return {"status": "multi_success_1"}
class MultiTool2(BaseTool):
    def get_tool_definition(self):
        return {"name": "multi_tool_2"}
    def execute(self, **kwargs):
        return {"status": "multi_success_2"}
""")

        # Create an invalid python file
        with open(os.path.join(self.test_tools_dir, "invalid_tool.py"), "w") as f:
            f.write("this is not a valid tool")

        # Create a non-python file
        with open(os.path.join(self.test_tools_dir, "data.txt"), "w") as f:
            f.write("some data")

    def test_tool_loading(self):
        registry = ToolRegistry(tool_directory=self.test_tools_dir)
        tools = registry.get_all_tools()
        self.assertIn("test_tool", tools)
        self.assertIn("multi_tool_1", tools)
        self.assertIn("multi_tool_2", tools)
        self.assertEqual(len(tools), 3)

    def test_get_tool(self):
        registry = ToolRegistry(tool_directory=self.test_tools_dir)
        tool = registry.get_tool("test_tool")
        self.assertIsNotNone(tool)
        self.assertTrue(isinstance(tool, BaseTool))

        multi_tool = registry.get_tool("multi_tool_1")
        self.assertIsNotNone(multi_tool)
        self.assertTrue(isinstance(multi_tool, BaseTool))

    def test_tool_execution(self):
        registry = ToolRegistry(tool_directory=self.test_tools_dir)
        tool = registry.get_tool("test_tool")
        result = tool.execute()
        self.assertEqual(result, {"status": "success"})

        multi_tool_2 = registry.get_tool("multi_tool_2")
        result = multi_tool_2.execute()
        self.assertEqual(result, {"status": "multi_success_2"})

if __name__ == "__main__":
    unittest.main()
