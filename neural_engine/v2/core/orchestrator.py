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
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .config import Config
from .events import EventBus, EventType
from .memory import ThoughtTree, GoalContext
from ..neurons import IntentNeuron, GenerativeNeuron, ToolNeuron, MemoryNeuron

logger = logging.getLogger(__name__)


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
        tool_forge=None,  # Optional ToolForge for dynamic tool creation
    ):
        self.config = config
        self.intent_neuron = intent_neuron
        self.generative_neuron = generative_neuron
        self.tool_neuron = tool_neuron
        self.memory_neuron = memory_neuron
        self.event_bus = event_bus
        self.thought_tree = thought_tree
        self.tool_forge = tool_forge
    
    @classmethod
    async def from_config(cls, config: Config, enable_forge: bool = False) -> 'Orchestrator':
        """Create orchestrator with all dependencies."""
        redis_client = await config.get_redis()
        
        tool_neuron = ToolNeuron(config)
        
        # Optionally create ToolForge
        tool_forge = None
        if enable_forge:
            from ..forge import ToolForge
            tool_forge = ToolForge(config, tool_neuron.registry)
            
            # Load previously saved forge state (restores forged tools)
            tool_forge.load_from_redis()
            
            logger.info("ToolForge enabled - dynamic tool creation available")
        
        return cls(
            config=config,
            intent_neuron=IntentNeuron(config),
            generative_neuron=GenerativeNeuron(config),
            tool_neuron=tool_neuron,
            memory_neuron=MemoryNeuron(config),
            event_bus=EventBus.from_config(config),
            thought_tree=ThoughtTree(redis_client),
            tool_forge=tool_forge,
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
        """Handle tool execution with error recovery."""
        result = await self.tool_neuron.run(ctx, ctx.goal_text)
        
        if not result.success:
            raise Exception(f"Tool execution failed: {result.error}")
        
        # Check for recovery signals
        result_data = result.data
        
        # If tool succeeded with data, interpret the result for the user
        if result_data and not result_data.startswith(("NO_", "TOOL_")):
            interpreted = await self._interpret_tool_result(ctx, result_data)
            if interpreted:
                return interpreted
        
        if result_data.startswith("NO_MATCHING_TOOL:") or result_data.startswith("NO_TOOLS_AVAILABLE"):
            # No tool can handle this - fall back to generative
            ctx.add_message("orchestrator", "fallback", f"No matching tool found, using generative response. Reason: {getattr(ctx, 'recovery_reason', 'unknown')}")
            return await self._handle_generative(ctx)
        
        if result_data.startswith("TOOL_NOT_FOUND:"):
            # Tool suggested but doesn't exist - try to forge it
            if self.tool_forge:
                tool_name = result_data.split(":", 1)[1] if ":" in result_data else "unknown"
                ctx.add_message("orchestrator", "forge", f"Attempting to create tool: {tool_name}")
                
                try:
                    # Use the recovery reason as the capability description
                    capability = getattr(ctx, 'recovery_reason', ctx.goal_text)
                    new_tool = await self.tool_forge.create_tool(
                        capability=capability,
                        request=ctx.goal_text,
                    )
                    
                    if new_tool:
                        # Register the new tool and retry
                        self.tool_neuron.registry.register(new_tool)
                        
                        # Save forge state so tool persists across restarts
                        self.tool_forge.save_to_redis()
                        
                        ctx.add_message("orchestrator", "forge_success", f"Created new tool, retrying")
                        
                        retry_result = await self.tool_neuron.run(ctx, ctx.goal_text)
                        if retry_result.success and not retry_result.data.startswith("TOOL_"):
                            return retry_result.data
                except Exception as e:
                    logger.warning(f"Tool forge failed: {e}")
            
            # Fall back to generative
            ctx.add_message("orchestrator", "fallback", f"Suggested tool not available, using generative response")
            return await self._handle_generative(ctx)
        
        if result_data.startswith("TOOL_ERROR:") or result_data.startswith("TOOL_EXCEPTION:"):
            # Tool failed - check recovery action
            recovery_action = getattr(ctx, 'recovery_action', 'fallback_generative')
            recovery_context = getattr(ctx, 'recovery_context', {})
            
            # Handle request_config - ask user for missing credentials
            if recovery_action == "request_config":
                service = recovery_context.get("service", "the service")
                instructions = recovery_context.get("instructions", "Please provide the required credentials.")
                actual_error = recovery_context.get("error", "Unknown error")
                
                ctx.add_message("orchestrator", "auth_required", f"Authentication needed for {service}")
                
                # Return a helpful message with the actual error details
                return (
                    f"🔐 **Authentication Issue with {service}**\n\n"
                    f"**Error:** `{actual_error}`\n\n"
                    f"This usually means the token is missing, expired, or invalid.\n\n"
                    f"**To fix:**\n{instructions}\n\n"
                    f"Once you've updated the token, try your request again!"
                )
            
            if recovery_action == "retry" and not getattr(ctx, '_retried', False):
                # Retry once with error context
                ctx._retried = True
                ctx.retry_error = result_data.split(":", 1)[1] if ":" in result_data else result_data
                ctx.add_message("orchestrator", "retry", f"Tool failed, retrying with error context")
                
                retry_result = await self.tool_neuron.run(ctx, ctx.goal_text)
                if retry_result.success and not retry_result.data.startswith("TOOL_"):
                    return retry_result.data
            
            if recovery_action == "refine_params" and not getattr(ctx, '_params_refined', False):
                # Try to refine parameters
                ctx._params_refined = True
                ctx.retry_error = result_data.split(":", 1)[1] if ":" in result_data else result_data
                ctx.add_message("orchestrator", "refine", f"Refining parameters and retrying")
                
                retry_result = await self.tool_neuron.run(ctx, ctx.goal_text)
                if retry_result.success and not retry_result.data.startswith("TOOL_"):
                    return retry_result.data
            
            # Fall back to generative
            ctx.add_message("orchestrator", "fallback", f"Tool failed after recovery attempts, using generative response")
            
            # Record failure in forge if available
            if self.tool_forge and hasattr(ctx, 'tool_name'):
                self.tool_forge.record_failure(ctx.tool_name, result_data)
            
            return await self._handle_generative(ctx)
        
        # Success! Record metrics if forge is available
        if self.tool_forge and hasattr(ctx, 'tool_name'):
            duration = ctx.duration_ms or 0
            self.tool_forge.record_success(ctx.tool_name, duration)
        
        return result_data
    
    async def _interpret_tool_result(self, ctx: GoalContext, tool_output: str) -> Optional[str]:
        """
        Interpret tool output into a human-friendly response.
        
        Uses the LLM to transform raw tool data into a natural response
        that directly answers the user's original question.
        """
        try:
            from .llm import LLMClient
            
            llm = LLMClient(
                base_url=self.config.llm_base_url,
                api_key=self.config.llm_api_key,
                model=self.config.llm_model,
            )
            
            prompt = f"""You are a helpful assistant. The user asked: "{ctx.goal_text}"

A tool returned this data:
{tool_output[:8000]}

Format this data as a human-friendly answer.
RULES:
- Use natural language, not JSON
- Include all numbers (distances, times, counts)
- If the data is a list, you MUST show EVERY SINGLE ITEM - never skip or summarize
- Use bullet points for lists"""
            
            response = await llm.generate(prompt, max_tokens=1500)
            
            if response and len(response) > 10:
                ctx.add_message("orchestrator", "interpreted", "Tool result interpreted for user")
                return response
            
        except Exception as e:
            logger.debug(f"Tool interpretation failed: {e}")
        
        # Fall back to raw output if interpretation fails
        return None
    
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
