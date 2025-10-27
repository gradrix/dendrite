import redis
import time

class Sandbox:
    def __init__(self, message_bus):
        self.message_bus = message_bus

    def _prepare_environment(self, data_handles: dict) -> dict:
        """
        Resolves data handles from Redis and prepares the global scope
        for the sandboxed code.
        """
        environment = {}
        for name, handle in data_handles.items():
            # For now, we assume handles are direct keys to string values
            # This can be expanded to handle complex data types
            data = self.message_bus.redis.get(handle)
            if data:
                environment[name] = data.decode('utf-8')
        return environment

    def execute(self, code: str, data_handles: dict = None, goal_id: str = None, depth: int = 0) -> dict:
        """
        Executes the given Python code in a sandboxed environment.
        """
        environment = {
            'sandbox': self
        }
        if data_handles:
            environment.update(self._prepare_environment(data_handles))

        self._result = None

        try:
            exec(code, environment)
            result = {"success": True, "result": self._result, "error": None}
        except Exception as e:
            result = {"success": False, "result": None, "error": str(e)}
        
        # Store execution result in message bus if goal_id provided
        if goal_id:
            message = {
                "goal_id": goal_id,
                "neuron": "sandbox",
                "message_type": "execution",
                "timestamp": time.time(),
                "depth": depth,
                "data": result
            }
            self.message_bus.add_message(goal_id, "execution", message)
        
        return result

    def set_result(self, result):
        """
        A function that is exposed to the sandboxed code to allow it
        to return a value.
        """
        self._result = result
