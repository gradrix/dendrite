try:
    from neural_engine.core.tool_registry import ToolRegistry
    print("Successfully imported ToolRegistry")
except ImportError as e:
    print(f"Failed to import ToolRegistry: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
