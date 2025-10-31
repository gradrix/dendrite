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
        
        Phase 10d: Now with intelligent error recovery!
        If execution fails and error_recovery is available, attempts to recover.
        """
        environment = {
            'sandbox': self
        }
        if data_handles:
            environment.update(self._prepare_environment(data_handles))

        self._result = None
        attempt_history = []

        try:
            exec(code, environment)
            result = {"success": True, "result": self._result, "error": None}
        except Exception as e:
            # Phase 10d: Attempt error recovery if available
            if hasattr(self, 'error_recovery') and self.error_recovery and hasattr(self, 'error_recovery_context'):
                print(f"\n⚠️  Tool execution failed: {e}")
                print(f"🔄 Attempting error recovery...")
                
                # Attempt recovery
                recovery_result = self.error_recovery.recover(
                    error=e,
                    tool_name=self.error_recovery_context.get('tool_name', 'unknown'),
                    parameters={},  # Parameters are embedded in code, hard to extract
                    context=self.error_recovery_context,
                    attempt_history=attempt_history
                )
                
                if recovery_result['success']:
                    print(f"✅ Recovery successful via {recovery_result['strategy']} strategy")
                    result = {
                        "success": True,
                        "result": recovery_result['result'],
                        "error": None,
                        "recovered": True,
                        "recovery_strategy": recovery_result['strategy'],
                        "recovery_explanation": recovery_result['explanation']
                    }
                else:
                    print(f"❌ Recovery failed: {recovery_result['explanation']}")
                    result = {
                        "success": False,
                        "result": None,
                        "error": str(e),
                        "recovery_attempted": True,
                        "recovery_strategy": recovery_result['strategy'],
                        "recovery_explanation": recovery_result['explanation']
                    }
            else:
                # No error recovery available - return error as before
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
