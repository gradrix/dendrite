from .message_bus import MessageBus
from .ollama_client import OllamaClient
import time
import uuid
import asyncio
import functools
from typing import Optional, Dict, Any, List


def fractal_process(func):
    """
    Decorator that wraps a neuron's process method to emit fractal events.
    
    When fractal is enabled on the neuron, this will:
    1. Emit NEURON_STARTED before processing
    2. Emit NEURON_COMPLETED on success
    3. Emit NEURON_FAILED on exception
    4. Record to Mind Map
    """
    @functools.wraps(func)
    def wrapper(self, goal_id, *args, **kwargs):
        # If fractal not enabled, just run normally
        if not self._public_pipe:
            return func(self, goal_id, *args, **kwargs)
        
        # Extract data for events
        data = args[0] if args else kwargs.get('data', kwargs.get('goal', {}))
        depth = kwargs.get('depth', args[1] if len(args) > 1 else 0)
        
        start_time = time.time()
        self._new_neuron_id()
        
        try:
            # Emit started event
            self._run_fractal_async(self._emit_started(goal_id, {"data": data, "depth": depth}))
            
            # Run the actual process
            result = func(self, goal_id, *args, **kwargs)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Emit completed event
            self._run_fractal_async(self._emit_completed(goal_id, result, duration_ms))
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Emit failed event
            self._run_fractal_async(self._emit_failed(goal_id, str(e), duration_ms))
            
            raise
    
    return wrapper


class BaseNeuron:
    def __init__(self, message_bus: MessageBus, ollama_client: OllamaClient):
        self.message_bus = message_bus
        self.ollama_client = ollama_client
        # Get neuron class name for logging
        self.neuron_name = self.__class__.__name__.replace("Neuron", "").lower()
        # Convert CamelCase to snake_case for neuron name
        import re
        self.neuron_name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', self.__class__.__name__).lower().replace("_neuron", "")
        
        # Fractal architecture: optional Public Pipe and Mind Map
        self._public_pipe = None
        self._mind_map = None
        self._neuron_id: Optional[str] = None
        self._parent_neuron_id: Optional[str] = None
        self._current_thoughts: List[str] = []

    def add_message_with_metadata(self, goal_id, message_type, data, depth=0):
        """Add a message with full metadata for tracking."""
        message = {
            "goal_id": goal_id,
            "neuron": self.neuron_name,
            "message_type": message_type,
            "timestamp": time.time(),
            "depth": depth,
            "data": data
        }
        self.message_bus.add_message(goal_id, message_type, message)

    def process(self, goal_id, data, depth=0):
        raise NotImplementedError
    
    # =========================================================================
    # Fractal Architecture: Public Pipe and Mind Map integration
    # =========================================================================
    
    def enable_fractal(self, public_pipe, mind_map):
        """
        Enable fractal architecture features.
        
        Call this to connect the neuron to the Public Pipe and Mind Map.
        This allows the neuron to emit events and record thoughts.
        """
        self._public_pipe = public_pipe
        self._mind_map = mind_map
    
    def set_parent(self, parent_neuron_id: str):
        """Set the parent neuron ID for tree structure."""
        self._parent_neuron_id = parent_neuron_id
    
    def _run_fractal_async(self, coro):
        """Run an async coroutine from sync context (for fractal events)."""
        if coro is None:
            return None
        try:
            # Check if there's already a running loop
            try:
                loop = asyncio.get_running_loop()
                # Loop is running - use nest_asyncio pattern or schedule in existing loop
                # Create a task and let it run (fire-and-forget for non-blocking)
                task = loop.create_task(coro)
                # For now, we don't wait - let it complete async
                return None
            except RuntimeError:
                # No running loop - safe to use asyncio.run
                return asyncio.run(coro)
        except Exception:
            # Silently ignore fractal failures - don't break the neuron
            pass

    def _new_neuron_id(self) -> str:
        """Generate a new neuron instance ID."""
        self._neuron_id = str(uuid.uuid4())[:8]
        self._current_thoughts = []
        return self._neuron_id
    
    async def _emit_started(self, goal_id: str, input_data: Dict[str, Any]):
        """Emit a NEURON_STARTED event to the Public Pipe."""
        if not self._public_pipe:
            return
        
        from neural_engine.core.public_pipe import NeuronEvent, EventType
        
        await self._public_pipe.emit(NeuronEvent(
            event_type=EventType.NEURON_STARTED,
            neuron_type=self.__class__.__name__,
            goal_id=goal_id,
            neuron_id=self._neuron_id or self._new_neuron_id(),
            parent_id=self._parent_neuron_id,
            data={"input": input_data}
        ))
    
    async def _emit_completed(
        self,
        goal_id: str,
        result: Any,
        duration_ms: float
    ):
        """Emit a NEURON_COMPLETED event to the Public Pipe."""
        if not self._public_pipe:
            return
        
        from neural_engine.core.public_pipe import NeuronEvent, EventType
        
        await self._public_pipe.emit(NeuronEvent(
            event_type=EventType.NEURON_COMPLETED,
            neuron_type=self.__class__.__name__,
            goal_id=goal_id,
            neuron_id=self._neuron_id,
            parent_id=self._parent_neuron_id,
            duration_ms=duration_ms,
            data={"result": result, "thoughts": self._current_thoughts}
        ))
    
    async def _emit_failed(
        self,
        goal_id: str,
        error: str,
        duration_ms: float
    ):
        """Emit a NEURON_FAILED event to the Public Pipe."""
        if not self._public_pipe:
            return
        
        from neural_engine.core.public_pipe import NeuronEvent, EventType
        
        await self._public_pipe.emit(NeuronEvent(
            event_type=EventType.NEURON_FAILED,
            neuron_type=self.__class__.__name__,
            goal_id=goal_id,
            neuron_id=self._neuron_id,
            parent_id=self._parent_neuron_id,
            duration_ms=duration_ms,
            data={"error": error, "thoughts": self._current_thoughts}
        ))
    
    async def think(self, goal_id: str, thought: str):
        """
        Record an intermediate thought.
        
        Use this to emit reasoning steps to the Public Pipe.
        These thoughts will be included in the Mind Map.
        """
        self._current_thoughts.append(thought)
        
        if not self._public_pipe:
            return
        
        from neural_engine.core.public_pipe import NeuronEvent, EventType
        
        await self._public_pipe.emit(NeuronEvent(
            event_type=EventType.THOUGHT,
            neuron_type=self.__class__.__name__,
            goal_id=goal_id,
            neuron_id=self._neuron_id,
            parent_id=self._parent_neuron_id,
            data={"content": thought}
        ))
    
    async def record_to_mind_map(
        self,
        goal_id: str,
        parent_node_id: str,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        status: str = "completed",
        error: Optional[str] = None
    ) -> Optional[str]:
        """
        Record this neuron's execution to the Mind Map.
        
        Returns the node ID for use as parent_node_id by child neurons.
        """
        if not self._mind_map:
            return None
        
        node = await self._mind_map.add_thought(
            goal_id=goal_id,
            parent_id=parent_node_id,
            neuron_type=self.__class__.__name__,
            neuron_id=self._neuron_id or self._new_neuron_id(),
            input_data=input_data,
            output_data=output_data,
            thoughts=self._current_thoughts,
            duration_ms=duration_ms,
            status=status,
            error=error
        )
        
        return node.node_id
    
    async def get_short_term_memory(self, goal_id: str) -> str:
        """
        Get short-term memory context for this goal.
        
        Use this to maintain continuity across neuron invocations.
        """
        if not self._mind_map:
            return ""
        
        return await self._mind_map.get_short_term_memory(goal_id)
    
    def process_with_fractal(self, goal_id: str, data: Any, parent_node_id: str, depth: int = 0):
        """
        Process with full fractal integration (sync wrapper for async).
        
        This is a convenience method that handles the async integration.
        Override _process_async for the actual implementation.
        """
        # For neurons that want to opt-in to fractal tracking
        # but maintain sync interface, run in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - create task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._process_with_fractal_async(goal_id, data, parent_node_id, depth)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self._process_with_fractal_async(goal_id, data, parent_node_id, depth)
                )
        except RuntimeError:
            # No event loop - create one
            return asyncio.run(
                self._process_with_fractal_async(goal_id, data, parent_node_id, depth)
            )
    
    async def _process_with_fractal_async(
        self,
        goal_id: str,
        data: Any,
        parent_node_id: str,
        depth: int = 0
    ) -> Any:
        """
        Async process with fractal tracking.
        
        Override this in subclasses for full async support.
        """
        start_time = time.time()
        self._new_neuron_id()
        
        try:
            await self._emit_started(goal_id, {"data": data, "depth": depth})
            
            # Call the regular sync process
            result = self.process(goal_id, data, depth)
            
            duration_ms = (time.time() - start_time) * 1000
            
            await self._emit_completed(goal_id, result, duration_ms)
            await self.record_to_mind_map(
                goal_id=goal_id,
                parent_node_id=parent_node_id,
                input_data={"data": data, "depth": depth},
                output_data={"result": result},
                duration_ms=duration_ms,
                status="completed"
            )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            await self._emit_failed(goal_id, str(e), duration_ms)
            await self.record_to_mind_map(
                goal_id=goal_id,
                parent_node_id=parent_node_id,
                input_data={"data": data, "depth": depth},
                duration_ms=duration_ms,
                status="failed",
                error=str(e)
            )
            
            raise

