"""
Integration tests for the Public Pipe (Redis Streams event bus).

These tests verify that neurons can emit and observe events.
"""

import pytest
import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


# Check if we can import public_pipe
try:
    from neural_engine.core.public_pipe import (
        PublicPipe,
        NeuronEvent,
        EventType,
        NeuronExecutionContext,
    )
    PUBLIC_PIPE_AVAILABLE = True
except ImportError as e:
    PUBLIC_PIPE_AVAILABLE = False
    IMPORT_ERROR = str(e)


def check_redis_available() -> bool:
    """Check if Redis is reachable."""
    try:
        import redis
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", 6379))
        r = redis.Redis(host=host, port=port, socket_timeout=2)
        r.ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def redis_available():
    """Skip tests if Redis is not available."""
    if not check_redis_available():
        pytest.skip("Redis not available")
    yield True


@pytest.fixture
def public_pipe(redis_available):
    """Create a PublicPipe instance for testing."""
    if not PUBLIC_PIPE_AVAILABLE:
        pytest.skip(f"PublicPipe not available: {IMPORT_ERROR}")
    
    pipe = PublicPipe()
    # Use test-specific stream key
    pipe.STREAM_KEY = "test:events:public_pipe"
    return pipe


@pytest.fixture
async def clean_pipe(public_pipe):
    """PublicPipe with cleanup after test."""
    yield public_pipe
    # Cleanup: delete test streams
    r = await public_pipe._get_redis()
    keys = await r.keys("test:events:*")
    if keys:
        await r.delete(*keys)


# =============================================================================
# Basic Event Emission Tests
# =============================================================================

class TestEventEmission:
    """Test event emission to Redis streams."""
    
    @pytest.mark.asyncio
    async def test_emit_neuron_started(self, clean_pipe):
        """Test emitting a NEURON_STARTED event."""
        pipe = clean_pipe
        
        event = NeuronEvent(
            event_type=EventType.NEURON_STARTED,
            neuron_type="IntentClassifier",
            goal_id="goal-123",
            data={"input": "test query"},
        )
        
        event_id = await pipe.emit(event)
        
        assert event_id is not None
        assert len(event_id) > 0
    
    @pytest.mark.asyncio
    async def test_emit_neuron_completed(self, clean_pipe):
        """Test emitting a NEURON_COMPLETED event."""
        pipe = clean_pipe
        
        event = NeuronEvent(
            event_type=EventType.NEURON_COMPLETED,
            neuron_type="IntentClassifier",
            goal_id="goal-123",
            data={"output": "classified intent"},
            parent_id="start-event-id",
        )
        
        event_id = await pipe.emit(event)
        
        assert event_id is not None
    
    @pytest.mark.asyncio
    async def test_emit_neuron_failed(self, clean_pipe):
        """Test emitting a NEURON_FAILED event."""
        pipe = clean_pipe
        
        event = NeuronEvent(
            event_type=EventType.NEURON_FAILED,
            neuron_type="CodeGenerator",
            goal_id="goal-456",
            data={"error": "LLM timeout", "retries": 3},
        )
        
        event_id = await pipe.emit(event)
        
        assert event_id is not None
    
    @pytest.mark.asyncio
    async def test_emit_thought(self, clean_pipe):
        """Test emitting a THOUGHT event."""
        pipe = clean_pipe
        
        event = NeuronEvent(
            event_type=EventType.THOUGHT,
            neuron_type="CodeGenerator",
            goal_id="goal-789",
            data={
                "thought": "User wants to create a REST API",
                "confidence": 0.85,
            },
        )
        
        event_id = await pipe.emit(event)
        
        assert event_id is not None
    
    @pytest.mark.asyncio
    async def test_emit_sub_goal(self, clean_pipe):
        """Test emitting a SUB_GOAL event."""
        pipe = clean_pipe
        
        event = NeuronEvent(
            event_type=EventType.SUB_GOAL,
            neuron_type="GoalDecomposer",
            goal_id="goal-main",
            data={
                "sub_goal": "Generate data models",
                "parent_goal": "Create REST API",
            },
        )
        
        event_id = await pipe.emit(event)
        
        assert event_id is not None


# =============================================================================
# Event Reading Tests
# =============================================================================

class TestEventReading:
    """Test reading events from Redis streams."""
    
    @pytest.mark.asyncio
    async def test_read_recent_events(self, clean_pipe):
        """Test reading recent events from stream."""
        pipe = clean_pipe
        
        # Emit several events
        for i in range(5):
            event = NeuronEvent(
                event_type=EventType.NEURON_STARTED,
                neuron_type="TestNeuron",
                goal_id=f"goal-{i}",
                data={"index": i},
            )
            await pipe.emit(event)
        
        # Read recent
        events = await pipe.read_recent(limit=10)
        
        assert len(events) >= 5
        # Events should have goal_ids
        goal_ids = [e.goal_id for e in events if e.goal_id.startswith("goal-")]
        assert len(goal_ids) >= 5
    
    @pytest.mark.asyncio
    async def test_read_recent_with_limit(self, clean_pipe):
        """Test reading with limit."""
        pipe = clean_pipe
        
        # Emit more events
        for i in range(10):
            event = NeuronEvent(
                event_type=EventType.THOUGHT,
                neuron_type="TestNeuron",
                goal_id=f"limit-goal-{i}",
                data={"thought": f"Thought {i}"},
            )
            await pipe.emit(event)
        
        # Read only 3
        events = await pipe.read_recent(limit=3)
        
        assert len(events) == 3
    
    @pytest.mark.asyncio
    async def test_read_by_goal(self, clean_pipe):
        """Test reading events filtered by goal_id."""
        pipe = clean_pipe
        target_goal = "specific-goal-xyz"
        
        # Emit mixed events
        for i in range(3):
            await pipe.emit(NeuronEvent(
                event_type=EventType.NEURON_STARTED,
                neuron_type="TestNeuron",
                goal_id=target_goal,
                data={"index": i},
            ))
            await pipe.emit(NeuronEvent(
                event_type=EventType.NEURON_STARTED,
                neuron_type="TestNeuron",
                goal_id="other-goal",
                data={"index": i},
            ))
        
        # Read only target goal using read_recent with filter
        events = await pipe.read_recent(limit=100, goal_id=target_goal)
        
        assert len(events) >= 3
        for event in events:
            assert event.goal_id == target_goal
    
    @pytest.mark.asyncio
    async def test_read_by_neuron_type(self, clean_pipe):
        """Test reading events filtered by neuron type."""
        pipe = clean_pipe
        
        # Emit from different neurons
        await pipe.emit(NeuronEvent(
            event_type=EventType.NEURON_COMPLETED,
            neuron_type="SpecialNeuron",
            goal_id="goal-1",
            data={"result": "success"},
        ))
        await pipe.emit(NeuronEvent(
            event_type=EventType.NEURON_COMPLETED,
            neuron_type="RegularNeuron",
            goal_id="goal-2",
            data={"result": "also success"},
        ))
        
        # Read only SpecialNeuron events
        events = await pipe.read_recent(limit=100, neuron_type="SpecialNeuron")
        
        assert len(events) >= 1
        for event in events:
            assert event.neuron_type == "SpecialNeuron"


# =============================================================================
# Subscription Tests
# =============================================================================

class TestSubscription:
    """Test real-time subscription to events."""
    
    @pytest.mark.asyncio
    async def test_subscribe_receives_new_events(self, clean_pipe):
        """Test that subscription receives newly emitted events."""
        pipe = clean_pipe
        received_events = []
        
        async def collector():
            """Collect events from subscription."""
            async for event in pipe.subscribe(block_ms=500):
                received_events.append(event)
                if len(received_events) >= 3:
                    break
        
        # Start subscriber in background
        subscriber_task = asyncio.create_task(collector())
        
        # Give subscriber time to start
        await asyncio.sleep(0.1)
        
        # Emit events
        for i in range(3):
            await pipe.emit(NeuronEvent(
                event_type=EventType.THOUGHT,
                neuron_type="Subscriber",
                goal_id=f"sub-goal-{i}",
                data={"thought": f"Thought {i}"},
            ))
        
        # Wait for subscriber to collect
        try:
            await asyncio.wait_for(subscriber_task, timeout=3.0)
        except asyncio.TimeoutError:
            pass
        
        assert len(received_events) >= 1
    
    @pytest.mark.asyncio
    async def test_subscribe_with_local_callback(self, clean_pipe):
        """Test local subscription callback."""
        pipe = clean_pipe
        received_events = []
        
        def callback(event):
            received_events.append(event)
        
        pipe.add_subscriber(callback)
        
        # Emit events
        await pipe.emit(NeuronEvent(
            event_type=EventType.NEURON_STARTED,
            neuron_type="Test",
            goal_id="g1",
            data={},
        ))
        await pipe.emit(NeuronEvent(
            event_type=EventType.NEURON_FAILED,
            neuron_type="Test",
            goal_id="g2",
            data={"error": "test error"},
        ))
        
        # Should have received both events via callback
        assert len(received_events) == 2
        
        pipe.remove_subscriber(callback)


# =============================================================================
# Execution Context Tests
# =============================================================================

class TestExecutionContext:
    """Test the NeuronExecutionContext context manager."""
    
    @pytest.mark.asyncio
    async def test_context_emits_start_and_complete(self, clean_pipe):
        """Test that context manager emits start and complete events."""
        pipe = clean_pipe
        goal_id = "context-test-goal"
        
        async with NeuronExecutionContext(
            pipe=pipe,
            neuron_type="ContextTestNeuron",
            goal_id=goal_id,
            input_data={"query": "test"},
        ) as ctx:
            # Do some work
            ctx.set_result({"result": "success"})
        
        # Check events were emitted
        events = await pipe.read_goal_events(goal_id)
        event_types = [e.event_type for e in events]
        
        assert EventType.NEURON_STARTED in event_types
        assert EventType.NEURON_COMPLETED in event_types
    
    @pytest.mark.asyncio
    async def test_context_emits_failed_on_exception(self, clean_pipe):
        """Test that context manager emits failed event on exception."""
        pipe = clean_pipe
        goal_id = "context-fail-goal"
        
        with pytest.raises(ValueError):
            async with NeuronExecutionContext(
                pipe=pipe,
                neuron_type="FailingNeuron",
                goal_id=goal_id,
                input_data={},
            ):
                raise ValueError("Intentional test error")
        
        # Check failed event was emitted
        events = await pipe.read_goal_events(goal_id)
        event_types = [e.event_type for e in events]
        
        assert EventType.NEURON_STARTED in event_types
        assert EventType.NEURON_FAILED in event_types
    
    @pytest.mark.asyncio
    async def test_context_records_thought(self, clean_pipe):
        """Test that context can record thoughts."""
        pipe = clean_pipe
        goal_id = "context-thought-goal"
        
        async with NeuronExecutionContext(
            pipe=pipe,
            neuron_type="ThinkingNeuron",
            goal_id=goal_id,
            input_data={},
        ) as ctx:
            await ctx.thought("This is my reasoning")
            ctx.set_result("done")
        
        # Check thought event was emitted
        events = await pipe.read_goal_events(goal_id)
        event_types = [e.event_type for e in events]
        
        assert EventType.THOUGHT in event_types


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_emit_with_large_data(self, clean_pipe):
        """Test emitting event with large data payload."""
        pipe = clean_pipe
        
        large_data = {
            "code": "x" * 10000,  # 10KB of data
            "metadata": {"nested": {"deep": {"value": list(range(100))}}},
        }
        
        event = NeuronEvent(
            event_type=EventType.NEURON_COMPLETED,
            neuron_type="LargeDataNeuron",
            goal_id="large-data-goal",
            data=large_data,
        )
        
        event_id = await pipe.emit(event)
        assert event_id is not None
        
        # Verify we can read it back
        events = await pipe.read_goal_events("large-data-goal")
        assert len(events) >= 1
        assert len(events[0].data.get("code", "")) == 10000
    
    @pytest.mark.asyncio
    async def test_emit_with_special_characters(self, clean_pipe):
        """Test emitting event with special characters in data."""
        pipe = clean_pipe
        
        event = NeuronEvent(
            event_type=EventType.THOUGHT,
            neuron_type="SpecialCharsNeuron",
            goal_id="special-chars-goal",
            data={
                "thought": "User wants: 'quotes', \"double quotes\", \n newlines \t tabs",
                "unicode": "🎉 émojis and ñ accents",
            },
        )
        
        event_id = await pipe.emit(event)
        assert event_id is not None
    
    @pytest.mark.asyncio
    async def test_read_empty_stream(self, clean_pipe):
        """Test reading from stream with no matching events."""
        pipe = clean_pipe
        
        # Read from a goal that doesn't exist
        events = await pipe.read_goal_events("nonexistent-goal-xyz")
        
        # Should return empty list, not error
        assert events == []


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_emit_many_events_quickly(self, clean_pipe):
        """Test emitting many events in rapid succession."""
        pipe = clean_pipe
        
        start_time = datetime.now(timezone.utc)
        
        # Emit 100 events
        for i in range(100):
            event = NeuronEvent(
                event_type=EventType.THOUGHT,
                neuron_type="PerfTestNeuron",
                goal_id="perf-test-goal",
                data={"index": i},
            )
            await pipe.emit(event)
        
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        # Should complete in reasonable time (< 5 seconds for 100 events)
        assert elapsed < 5.0
        
        # Verify all events were stored
        events = await pipe.read_goal_events("perf-test-goal")
        assert len(events) >= 100


# =============================================================================
# Stats Tests
# =============================================================================

class TestStats:
    """Test statistics functionality."""
    
    @pytest.mark.asyncio
    async def test_get_stats(self, clean_pipe):
        """Test getting pipe statistics."""
        pipe = clean_pipe
        
        # Emit some events first
        for i in range(5):
            await pipe.emit(NeuronEvent(
                event_type=EventType.THOUGHT,
                neuron_type="StatsTest",
                goal_id=f"stats-goal-{i}",
                data={},
            ))
        
        stats = await pipe.get_stats()
        
        assert "length" in stats
        assert stats["length"] >= 5
        assert "max_length" in stats
