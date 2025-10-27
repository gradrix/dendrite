import redis

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

    def execute(self, code: str, data_handles: dict = None) -> dict:
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
            return {"result": self._result, "error": None}
        except Exception as e:
            return {"result": None, "error": str(e)}

    def set_result(self, result):
        """
        A function that is exposed to the sandboxed code to allow it
        to return a value.
        """
        self._result = result
