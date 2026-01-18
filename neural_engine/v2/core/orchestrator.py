"""
Orchestrator - Thin coordinator that routes goals through neurons.

Simple flow:
1. Create goal context
2. Classify intent
3. Route to appropriate neurons
4. Return result

That's it. No complex state machines.
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .config import Config
from .events import EventBus, EventType
from .memory import ThoughtTree, GoalContext
from ..neurons import IntentNeuron, GenerativeNeuron, ToolNeuron, MemoryNeuron


class Orchestrator:
    """
    Orchestrator - Routes goals through neurons.
    
    Flow:
        goal → intent → [generative|tool|memory] → result
    
    Usage:
        orchestrator = Orchestrator.from_config(config)
        result = await orchestrator.process("What is 2+2?")
    
    The orchestrator is thin - neurons do the work.
    """
    
    def __init__(
        self,
        config: Config,
        intent_neuron: IntentNeuron,
        generative_neuron: GenerativeNeuron,
        tool_neuron: ToolNeuron,
        memory_neuron: MemoryNeuron,
        event_bus: EventBus,
        thought_tree: ThoughtTree,
    ):
        self.config = config
        self.intent_neuron = intent_neuron
        self.generative_neuron = generative_neuron
        self.tool_neuron = tool_neuron
        self.memory_neuron = memory_neuron
        self.event_bus = event_bus
        self.thought_tree = thought_tree
    
    @classmethod
    async def from_config(cls, config: Config) -> 'Orchestrator':
        """Create orchestrator with all dependencies."""
        redis_client = await config.get_redis()
        
        return cls(
            config=config,
            intent_neuron=IntentNeuron(config),
            generative_neuron=GenerativeNeuron(config),
            tool_neuron=ToolNeuron(config),
            memory_neuron=MemoryNeuron(config),
            event_bus=EventBus.from_config(config),
            thought_tree=ThoughtTree(redis_client),
        )
    
    async def process(self, goal: str) -> Dict[str, Any]:
        """
        Process a goal end-to-end.
        
        Args:
            goal: Natural language goal/query
        
        Returns:
            Dict with result, success, and metadata
        """
        goal_id = str(uuid.uuid4())
        
        # Create context
        ctx = GoalContext(goal_id=goal_id, goal_text=goal)
        
        # Create root thought
        await self.thought_tree.create_root(goal_id, goal)
        
        # Emit goal start
        await self.event_bus.emit(
            event_type=EventType.GOAL_START,
            source="orchestrator",
            goal_id=goal_id,
            data={"goal": goal},
        )
        
        try:
            # Step 1: Classify intent
            intent_result = await self.intent_neuron.run(ctx, goal)
            
            if not intent_result.success:
                return self._error_response(ctx, f"Intent classification failed: {intent_result.error}")
            
            intent = intent_result.data
            ctx.intent = intent
            
            # Step 2: Route based on intent
            if intent == "generative":
                result = await self._handle_generative(ctx)
            elif intent == "tool":
                result = await self._handle_tool(ctx)
            elif intent == "memory_read":
                result = await self._handle_memory_read(ctx)
            elif intent == "memory_write":
                result = await self._handle_memory_write(ctx)
            else:
                # Default to generative
                result = await self._handle_generative(ctx)
            
            # Complete
            ctx.complete(result)
            await self.thought_tree.complete(goal_id, result)
            
            await self.event_bus.emit(
                event_type=EventType.GOAL_COMPLETE,
                source="orchestrator",
                goal_id=goal_id,
                data={"result": result[:200] if result else None, "duration_ms": ctx.duration_ms},
            )
            
            return {
                "success": True,
                "goal_id": goal_id,
                "goal": goal,
                "intent": intent,
                "result": result,
                "duration_ms": ctx.duration_ms,
                "messages": ctx.messages,
            }
            
        except Exception as e:
            return self._error_response(ctx, str(e))
    
    async def _handle_generative(self, ctx: GoalContext) -> str:
        """Handle generative/chat queries."""
        result = await self.generative_neuron.run(ctx, ctx.goal_text)
        
        if not result.success:
            raise Exception(f"Generation failed: {result.error}")
        
        return result.data
    
    async def _handle_tool(self, ctx: GoalContext) -> str:
        """Handle tool execution."""
        result = await self.tool_neuron.run(ctx, ctx.goal_text)
        
        if not result.success:
            raise Exception(f"Tool execution failed: {result.error}")
        
        return result.data
    
    async def _handle_memory_read(self, ctx: GoalContext) -> str:
        """Handle memory read."""
        result = await self.memory_neuron.run(ctx, {"action": "read", "goal": ctx.goal_text})
        
        if not result.success:
            raise Exception(f"Memory read failed: {result.error}")
        
        return result.data
    
    async def _handle_memory_write(self, ctx: GoalContext) -> str:
        """Handle memory write."""
        result = await self.memory_neuron.run(ctx, {"action": "write", "goal": ctx.goal_text})
        
        if not result.success:
            raise Exception(f"Memory write failed: {result.error}")
        
        return result.data
    
    def _error_response(self, ctx: GoalContext, error: str) -> Dict[str, Any]:
        """Build error response."""
        ctx.fail(error)
        return {
            "success": False,
            "goal_id": ctx.goal_id,
            "goal": ctx.goal_text,
            "intent": ctx.intent,
            "error": error,
            "duration_ms": ctx.duration_ms,
            "messages": ctx.messages,
        }
