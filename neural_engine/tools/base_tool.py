from abc import ABC, abstractmethod

class BaseTool(ABC):
    @abstractmethod
    def get_tool_definition(self):
        pass

    @abstractmethod
    def execute(self, **kwargs):
        pass
