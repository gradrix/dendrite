"""
Edge Case Tests - Test error handling and boundary conditions.

Tests:
- LLM failures and timeouts
- Invalid JSON responses
- Empty/malformed queries
- Redis connection issues
- Neuron processing errors
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock


class TestLLMEdgeCases:
    """Test LLM client error handling."""
    
    @pytest.mark.asyncio
    async def test_llm_timeout_handling(self):
        """LLM timeout should raise appropriate error."""
        from neural_engine.v2.core import Config, LLMClient
        
        config = Config.for_testing()
        llm = LLMClient.from_config(config)
        
        # Mock the sync method to raise timeout
        with patch.object(llm, '_generate_sync') as mock_gen:
            mock_gen.side_effect = TimeoutError("Request timed out")
            
            with pytest.raises(TimeoutError):
                await llm.generate("test")
    
    @pytest.mark.asyncio
    async def test_llm_connection_error(self):
        """LLM connection error should propagate."""
        from neural_engine.v2.core import Config, LLMClient
        from openai import APIConnectionError
        
        config = Config.for_testing()
        llm = LLMClient.from_config(config)
        
        with patch.object(llm, '_generate_sync') as mock_gen:
            mock_gen.side_effect = Exception("Connection refused")
            
            with pytest.raises(Exception) as exc_info:
                await llm.generate("test")
            assert "Connection" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_json_with_invalid_response(self):
        """Invalid JSON should return error dict."""
        from neural_engine.v2.core import Config, LLMClient
        
        config = Config.for_testing()
        llm = LLMClient.from_config(config)
        
        with patch.object(llm, '_generate_sync') as mock_gen:
            mock_gen.return_value = "This is not JSON at all"
            
            result = await llm.generate_json("test")
            
            assert "error" in result
            assert result["raw"] == "This is not JSON at all"
    
    @pytest.mark.asyncio
    async def test_generate_json_with_markdown_code_block(self):
        """Should extract JSON from markdown code blocks."""
        from neural_engine.v2.core import Config, LLMClient
        
        config = Config.for_testing()
        llm = LLMClient.from_config(config)
        
        with patch.object(llm, '_generate_sync') as mock_gen:
            mock_gen.return_value = '```json\n{"key": "value"}\n```'
            
            result = await llm.generate_json("test")
            
            assert result == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_generate_json_with_plain_code_block(self):
        """Should extract JSON from plain code blocks."""
        from neural_engine.v2.core import Config, LLMClient
        
        config = Config.for_testing()
        llm = LLMClient.from_config(config)
        
        with patch.object(llm, '_generate_sync') as mock_gen:
            mock_gen.return_value = '```\n{"answer": 42}\n```'
            
            result = await llm.generate_json("test")
            
            assert result == {"answer": 42}


class TestEventBusEdgeCases:
    """Test event bus error handling."""
    
    @pytest.mark.asyncio
    async def test_emit_without_required_fields(self):
        """Emit without required fields should raise error."""
        from neural_engine.v2.core import Config, EventBus
        
        config = Config.for_testing()
        bus = EventBus.from_config(config)
        
        with pytest.raises(ValueError) as exc_info:
            await bus.emit()  # No arguments
        
        assert "Must provide event" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_events_with_no_matches(self):
        """Getting events for non-existent goal returns empty list."""
        from neural_engine.v2.core import Config, EventBus
        
        config = Config.for_testing()
        bus = EventBus.from_config(config)
        
        events = await bus.get_events(goal_id="non-existent-goal-12345")
        
        assert events == []
    
    @pytest.mark.asyncio
    async def test_event_with_large_metadata(self):
        """Large metadata should be handled."""
        from neural_engine.v2.core import Config, EventBus, EventType
        
        config = Config.for_testing()
        bus = EventBus.from_config(config)
        
        large_data = {"items": ["x" * 100 for _ in range(100)]}
        
        event = await bus.emit(
            event_type=EventType.THOUGHT,
            source="test",
            goal_id="large-metadata-test",
            data=large_data,
        )
        
        assert event is not None


class TestNeuronEdgeCases:
    """Test neuron error handling."""
    
    @pytest.mark.asyncio
    async def test_intent_with_empty_query(self):
        """Intent neuron should handle empty query."""
        from neural_engine.v2.core import Config, GoalContext
        from neural_engine.v2.neurons import IntentNeuron
        
        config = Config.for_testing()
        neuron = IntentNeuron(config)
        
        ctx = GoalContext(goal_id="test", goal_text="")
        result = await neuron.run(ctx, "")
        
        # Should still classify (likely as generative)
        assert result.success
        assert result.data in ["generative", "tool", "memory_read", "memory_write"]
    
    @pytest.mark.asyncio
    async def test_generative_with_very_long_query(self):
        """Generative neuron should handle long queries."""
        from neural_engine.v2.core import Config, GoalContext
        from neural_engine.v2.neurons import GenerativeNeuron
        
        config = Config.for_testing()
        neuron = GenerativeNeuron(config)
        
        long_query = "Explain " + "very " * 100 + "complex topic"
        ctx = GoalContext(goal_id="test", goal_text=long_query)
        result = await neuron.run(ctx)
        
        assert result.success
        assert result.data is not None
    
    @pytest.mark.asyncio
    async def test_neuron_records_error_in_context(self):
        """Neuron errors should be recorded in context."""
        from neural_engine.v2.core import Config, GoalContext
        from neural_engine.v2.neurons import GenerativeNeuron
        
        config = Config.for_testing()
        neuron = GenerativeNeuron(config)
        
        ctx = GoalContext(goal_id="test", goal_text="test")
        
        # Mock LLM to fail
        with patch.object(neuron.llm, '_generate_sync') as mock_gen:
            mock_gen.side_effect = Exception("LLM failed")
            
            result = await neuron.run(ctx)
            
            assert not result.success
            assert "LLM failed" in result.error
            # Check error was recorded in context
            assert len(ctx.messages) > 0
            assert any("error" in m["type"] for m in ctx.messages)


class TestOrchestratorEdgeCases:
    """Test orchestrator error handling."""
    
    @pytest.mark.asyncio
    async def test_process_with_whitespace_only(self):
        """Should handle whitespace-only input."""
        from neural_engine.v2.core import Config, Orchestrator
        
        config = Config.for_testing()
        orchestrator = await Orchestrator.from_config(config)
        
        result = await orchestrator.process("   \n\t   ")
        
        # Should complete (gracefully)
        assert "goal_id" in result
    
    @pytest.mark.asyncio
    async def test_process_with_special_characters(self):
        """Should handle special characters."""
        from neural_engine.v2.core import Config, Orchestrator
        
        config = Config.for_testing()
        orchestrator = await Orchestrator.from_config(config)
        
        result = await orchestrator.process("What is 2 + 2? @#$%^&*()")
        
        assert "goal_id" in result
    
    @pytest.mark.asyncio
    async def test_orchestrator_handles_neuron_failure(self):
        """Orchestrator should handle neuron failures gracefully."""
        from neural_engine.v2.core import Config, Orchestrator
        
        config = Config.for_testing()
        orchestrator = await Orchestrator.from_config(config)
        
        # Mock intent neuron to fail
        with patch.object(orchestrator.intent_neuron, 'run') as mock_run:
            mock_run.return_value = MagicMock(success=False, error="Intent failed")
            
            result = await orchestrator.process("test")
            
            assert not result["success"]
            assert "Intent" in result["error"]


class TestGoalContextEdgeCases:
    """Test GoalContext edge cases."""
    
    def test_duration_ms_before_completion(self):
        """Duration should be None before completion."""
        from neural_engine.v2.core import GoalContext
        
        ctx = GoalContext(goal_id="test", goal_text="test")
        
        assert ctx.duration_ms is None
    
    def test_duration_ms_after_completion(self):
        """Duration should be calculated after completion."""
        from neural_engine.v2.core import GoalContext
        import time
        
        ctx = GoalContext(goal_id="test", goal_text="test")
        time.sleep(0.01)  # 10ms
        ctx.complete("result")
        
        assert ctx.duration_ms is not None
        assert ctx.duration_ms >= 10
    
    def test_add_message_accumulates(self):
        """Messages should accumulate."""
        from neural_engine.v2.core import GoalContext
        
        ctx = GoalContext(goal_id="test", goal_text="test")
        
        ctx.add_message("neuron1", "start", {"foo": "bar"})
        ctx.add_message("neuron2", "result", "success")
        
        assert len(ctx.messages) == 2
        assert ctx.messages[0]["neuron"] == "neuron1"
        assert ctx.messages[1]["neuron"] == "neuron2"


class TestThoughtTreeEdgeCases:
    """Test ThoughtTree edge cases."""
    
    @pytest.mark.asyncio
    async def test_get_root_for_nonexistent_goal(self):
        """Getting root for nonexistent goal returns None."""
        from neural_engine.v2.core import Config, ThoughtTree
        
        config = Config.for_testing()
        redis_client = await config.get_redis()
        tree = ThoughtTree(redis_client)
        
        root = await tree.get_root("nonexistent-goal-xyz")
        
        assert root is None
    
    @pytest.mark.asyncio
    async def test_get_thoughts_for_nonexistent_goal(self):
        """Getting thoughts for nonexistent goal returns empty list."""
        from neural_engine.v2.core import Config, ThoughtTree
        
        config = Config.for_testing()
        redis_client = await config.get_redis()
        tree = ThoughtTree(redis_client)
        
        thoughts = await tree.get_thoughts("nonexistent-goal-abc")
        
        assert thoughts == []
    
    @pytest.mark.asyncio
    async def test_complete_nonexistent_goal(self):
        """Completing nonexistent goal should not error."""
        from neural_engine.v2.core import Config, ThoughtTree
        
        config = Config.for_testing()
        redis_client = await config.get_redis()
        tree = ThoughtTree(redis_client)
        
        # Should not raise
        await tree.complete("nonexistent-goal-123", "result")
    
    @pytest.mark.asyncio
    async def test_thought_chain(self):
        """Thoughts should form a chain."""
        from neural_engine.v2.core import Config, ThoughtTree
        import uuid
        
        config = Config.for_testing()
        redis_client = await config.get_redis()
        tree = ThoughtTree(redis_client)
        
        # Use unique goal ID to avoid pollution from other tests
        goal_id = f"chain-test-{uuid.uuid4()}"
        
        # Create chain: root → thought1 → thought2
        root = await tree.create_root(goal_id, "Test goal")
        t1 = await tree.add_thought(root.thought_id, "Step 1", "reasoning", goal_id)
        t2 = await tree.add_thought(t1.thought_id, "Step 2", "action", goal_id)
        
        thoughts = await tree.get_thoughts(goal_id)
        
        assert len(thoughts) == 3
        # Verify parent chain exists
        t2_found = next((t for t in thoughts if t.content == "Step 2"), None)
        assert t2_found is not None
        assert t2_found.parent_id == t1.thought_id
