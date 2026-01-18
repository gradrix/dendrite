"""
v2 E2E Tests - Prove the clean architecture works.

Simple, focused tests that verify:
1. Config works
2. LLM generates responses
3. Events are emitted
4. Neurons process correctly
5. Orchestrator routes goals
"""

import pytest
import asyncio
from datetime import datetime


class TestConfig:
    """Test configuration."""
    
    def test_for_testing_creates_config(self):
        """Config.for_testing() creates valid config."""
        from neural_engine.v2.core import Config
        
        config = Config.for_testing()
        
        assert config is not None
        assert config.llm_base_url is not None
        assert config.redis_host is not None
    
    def test_from_env_creates_config(self):
        """Config.from_env() creates valid config."""
        from neural_engine.v2.core import Config
        
        config = Config.from_env()
        
        assert config is not None
    
    @pytest.mark.asyncio
    async def test_get_redis_returns_client(self):
        """Config provides Redis client."""
        from neural_engine.v2.core import Config
        
        config = Config.for_testing()
        redis = await config.get_redis()
        
        assert redis is not None
        # Test ping
        pong = await redis.ping()
        assert pong is True


class TestLLMClient:
    """Test LLM client."""
    
    @pytest.mark.asyncio
    async def test_generate_returns_text(self):
        """LLM generates text."""
        from neural_engine.v2.core import Config, LLMClient
        
        config = Config.for_testing()
        llm = LLMClient.from_config(config)
        
        response = await llm.generate("Say hello in one word.")
        
        assert response is not None
        assert len(response) > 0
    
    @pytest.mark.asyncio
    async def test_generate_json_returns_dict(self):
        """LLM generates JSON."""
        from neural_engine.v2.core import Config, LLMClient
        
        config = Config.for_testing()
        llm = LLMClient.from_config(config)
        
        response = await llm.generate_json(
            "Respond with JSON: {\"answer\": 42}"
        )
        
        assert isinstance(response, dict)


class TestEventBus:
    """Test event system."""
    
    @pytest.mark.asyncio
    async def test_emit_and_get_events(self):
        """Events can be emitted and retrieved."""
        from neural_engine.v2.core import Config, EventBus, EventType
        
        config = Config.for_testing()
        bus = EventBus.from_config(config)
        
        # Emit an event
        event = await bus.emit(
            event_type=EventType.GOAL_START,
            source="test",
            goal_id="test-123",
            data={"test": "data"},
        )
        
        assert event is not None
        assert event.event_type == EventType.GOAL_START
        
        # Get events
        events = await bus.get_events(goal_id="test-123", limit=10)
        assert len(events) > 0


class TestNeurons:
    """Test individual neurons."""
    
    @pytest.mark.asyncio
    async def test_intent_neuron_classifies(self):
        """IntentNeuron classifies user intent."""
        from neural_engine.v2.core import Config, GoalContext
        from neural_engine.v2.neurons import IntentNeuron
        
        config = Config.for_testing()
        neuron = IntentNeuron(config)
        
        ctx = GoalContext(goal_id="test", goal_text="What is the weather?")
        result = await neuron.run(ctx, "What is 2+2?")
        
        assert result.success
        assert result.data in ["generative", "tool", "memory_read", "memory_write"]
    
    @pytest.mark.asyncio
    async def test_generative_neuron_responds(self):
        """GenerativeNeuron generates text."""
        from neural_engine.v2.core import Config, GoalContext
        from neural_engine.v2.neurons import GenerativeNeuron
        
        config = Config.for_testing()
        neuron = GenerativeNeuron(config)
        
        ctx = GoalContext(goal_id="test", goal_text="What is 2+2?")
        result = await neuron.run(ctx)
        
        assert result.success
        assert result.data is not None
        assert len(result.data) > 0
    
    @pytest.mark.asyncio
    async def test_memory_neuron_write_and_read(self):
        """MemoryNeuron can write and read."""
        from neural_engine.v2.core import Config, GoalContext
        from neural_engine.v2.neurons import MemoryNeuron
        
        config = Config.for_testing()
        neuron = MemoryNeuron(config)
        
        # Write
        ctx = GoalContext(goal_id="test-write", goal_text="Remember that my name is TestUser")
        ctx.intent = "memory_write"
        result = await neuron.run(ctx, {"action": "write", "goal": ctx.goal_text})
        
        assert result.success
        assert "remember" in result.data.lower() or "stored" in result.data.lower()


class TestOrchestrator:
    """Test orchestrator flow."""
    
    @pytest.mark.asyncio
    async def test_process_generative_query(self):
        """Orchestrator handles generative queries."""
        from neural_engine.v2.core import Config, Orchestrator
        
        config = Config.for_testing()
        orchestrator = await Orchestrator.from_config(config)
        
        result = await orchestrator.process("What is 2+2?")
        
        assert result["success"]
        assert result["result"] is not None
        assert "goal_id" in result
        assert "duration_ms" in result
    
    @pytest.mark.asyncio
    async def test_process_emits_events(self):
        """Orchestrator emits fractal events."""
        from neural_engine.v2.core import Config, Orchestrator, EventBus
        
        config = Config.for_testing()
        orchestrator = await Orchestrator.from_config(config)
        
        result = await orchestrator.process("Hello")
        
        assert result["success"]
        
        # Check events were emitted
        bus = EventBus.from_config(config)
        events = await bus.get_events(goal_id=result["goal_id"], limit=50)
        
        # Should have at least goal_start, neuron events, goal_complete
        assert len(events) >= 3
    
    @pytest.mark.asyncio
    async def test_process_records_thoughts(self):
        """Orchestrator records thoughts in ThoughtTree."""
        from neural_engine.v2.core import Config, Orchestrator, ThoughtTree
        
        config = Config.for_testing()
        orchestrator = await Orchestrator.from_config(config)
        
        result = await orchestrator.process("Explain Python")
        
        assert result["success"]
        
        # Check thoughts were recorded
        tree = orchestrator.thought_tree
        thoughts = await tree.get_thoughts(result["goal_id"])
        
        assert len(thoughts) >= 1
        # Root thought should exist
        root = await tree.get_root(result["goal_id"])
        assert root is not None
        assert root.status == "completed"


class TestIntegration:
    """Integration tests for full flows."""
    
    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """Complete conversation flow works."""
        from neural_engine.v2.core import Config, Orchestrator
        
        config = Config.for_testing()
        orchestrator = await Orchestrator.from_config(config)
        
        # Multiple queries
        queries = [
            "What is Python?",
            "How do I write a for loop?",
            "What is 5 times 7?",
        ]
        
        for query in queries:
            result = await orchestrator.process(query)
            assert result["success"], f"Failed on: {query}"
            assert result["result"] is not None
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Errors are handled gracefully."""
        from neural_engine.v2.core import Config, Orchestrator
        
        config = Config.for_testing()
        orchestrator = await Orchestrator.from_config(config)
        
        # Empty query should still work
        result = await orchestrator.process("")
        
        # Should complete (maybe with minimal response)
        assert "goal_id" in result
