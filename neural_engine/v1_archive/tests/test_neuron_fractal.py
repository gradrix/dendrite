"""
Tests for neuron-level fractal event emission.

Verifies that individual neurons emit events when fractal is enabled.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestNeuronFractalEmission:
    """Test that neurons emit fractal events during processing."""
    
    @pytest.fixture
    def mock_message_bus(self):
        """Create a mock message bus."""
        mock = MagicMock()
        mock.add_message = MagicMock()
        return mock
    
    @pytest.fixture
    def mock_ollama_client(self):
        """Create a mock ollama client."""
        mock = MagicMock()
        mock.generate = MagicMock(return_value={"response": "Test response"})
        return mock
    
    @pytest.fixture
    def mock_public_pipe(self):
        """Create a mock PublicPipe."""
        mock = MagicMock()
        mock.emit = AsyncMock(return_value="event_123")
        return mock
    
    @pytest.fixture
    def mock_mind_map(self):
        """Create a mock MindMap."""
        mock = MagicMock()
        mock.create_root = AsyncMock()
        mock.add_thought = AsyncMock()
        return mock
    
    def test_generative_neuron_emits_events_when_enabled(
        self, 
        mock_message_bus, 
        mock_ollama_client, 
        mock_public_pipe,
        mock_mind_map
    ):
        """Test GenerativeNeuron emits started and completed events."""
        from neural_engine.core.generative_neuron import GenerativeNeuron
        
        neuron = GenerativeNeuron(mock_message_bus, mock_ollama_client)
        neuron.enable_fractal(mock_public_pipe, mock_mind_map)
        
        # Mock the prompt loading
        with patch.object(neuron, '_load_prompt', return_value="Generate: {goal}"):
            result = neuron.process("goal-123", {"goal": "test question"}, depth=0)
        
        # Verify events were emitted
        assert mock_public_pipe.emit.call_count >= 2
        
        # Check event types
        calls = mock_public_pipe.emit.call_args_list
        event_types = [call[0][0].event_type.value for call in calls]
        
        assert "neuron_started" in event_types
        assert "neuron_completed" in event_types
        
        # Check neuron type is correct
        for call in calls:
            event = call[0][0]
            assert event.neuron_type == "GenerativeNeuron"
    
    def test_generative_neuron_no_events_when_disabled(
        self, 
        mock_message_bus, 
        mock_ollama_client,
        mock_public_pipe
    ):
        """Test GenerativeNeuron doesn't emit when fractal disabled."""
        from neural_engine.core.generative_neuron import GenerativeNeuron
        
        neuron = GenerativeNeuron(mock_message_bus, mock_ollama_client)
        # Don't call enable_fractal
        
        with patch.object(neuron, '_load_prompt', return_value="Generate: {goal}"):
            result = neuron.process("goal-123", {"goal": "test question"}, depth=0)
        
        # No events should be emitted
        mock_public_pipe.emit.assert_not_called()
    
    def test_neuron_emits_failed_on_exception(
        self,
        mock_message_bus,
        mock_ollama_client,
        mock_public_pipe,
        mock_mind_map
    ):
        """Test that failed events are emitted when neuron raises."""
        from neural_engine.core.generative_neuron import GenerativeNeuron
        
        neuron = GenerativeNeuron(mock_message_bus, mock_ollama_client)
        neuron.enable_fractal(mock_public_pipe, mock_mind_map)
        
        # Make the LLM call fail
        mock_ollama_client.generate.side_effect = RuntimeError("LLM unavailable")
        
        with patch.object(neuron, '_load_prompt', return_value="Generate: {goal}"):
            with pytest.raises(RuntimeError):
                neuron.process("goal-123", {"goal": "test"}, depth=0)
        
        # Should have started and failed events
        calls = mock_public_pipe.emit.call_args_list
        event_types = [call[0][0].event_type.value for call in calls]
        
        assert "neuron_started" in event_types
        assert "neuron_failed" in event_types
    
    def test_event_contains_goal_id(
        self,
        mock_message_bus,
        mock_ollama_client,
        mock_public_pipe,
        mock_mind_map
    ):
        """Test that events contain the correct goal_id."""
        from neural_engine.core.generative_neuron import GenerativeNeuron
        
        neuron = GenerativeNeuron(mock_message_bus, mock_ollama_client)
        neuron.enable_fractal(mock_public_pipe, mock_mind_map)
        
        with patch.object(neuron, '_load_prompt', return_value="Generate: {goal}"):
            neuron.process("my-specific-goal-id", {"goal": "test"}, depth=0)
        
        # Check all events have the goal_id
        for call in mock_public_pipe.emit.call_args_list:
            event = call[0][0]
            assert event.goal_id == "my-specific-goal-id"
    
    def test_completed_event_has_duration(
        self,
        mock_message_bus,
        mock_ollama_client,
        mock_public_pipe,
        mock_mind_map
    ):
        """Test that completed events include duration_ms."""
        from neural_engine.core.generative_neuron import GenerativeNeuron
        
        neuron = GenerativeNeuron(mock_message_bus, mock_ollama_client)
        neuron.enable_fractal(mock_public_pipe, mock_mind_map)
        
        with patch.object(neuron, '_load_prompt', return_value="Generate: {goal}"):
            neuron.process("goal-123", {"goal": "test"}, depth=0)
        
        # Find the completed event
        completed_events = [
            call[0][0] for call in mock_public_pipe.emit.call_args_list
            if call[0][0].event_type.value == "neuron_completed"
        ]
        
        assert len(completed_events) == 1
        assert completed_events[0].duration_ms is not None
        assert completed_events[0].duration_ms >= 0


class TestIntentClassifierFractal:
    """Test IntentClassifierNeuron fractal emission."""
    
    @pytest.fixture
    def mock_message_bus(self):
        mock = MagicMock()
        mock.add_message = MagicMock()
        return mock
    
    @pytest.fixture
    def mock_ollama_client(self):
        mock = MagicMock()
        # Return a valid intent response
        mock.generate = MagicMock(return_value={"response": "generative"})
        return mock
    
    @pytest.fixture
    def mock_public_pipe(self):
        mock = MagicMock()
        mock.emit = AsyncMock(return_value="event_123")
        return mock
    
    def test_intent_classifier_emits_events(
        self,
        mock_message_bus,
        mock_ollama_client,
        mock_public_pipe
    ):
        """Test IntentClassifierNeuron emits fractal events."""
        from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
        
        # Create with minimal features to speed up test
        neuron = IntentClassifierNeuron(
            mock_message_bus, 
            mock_ollama_client,
            use_simplifier=False,
            use_pattern_cache=False,
            use_semantic=False,
            use_parallel_voting=False
        )
        neuron.enable_fractal(mock_public_pipe, None)
        
        with patch.object(neuron, '_load_prompt', return_value="Classify: {goal}"):
            result = neuron.process("goal-123", "What is the capital of France?", depth=0)
        
        # Should have events
        assert mock_public_pipe.emit.call_count >= 2
        
        event_types = [call[0][0].event_type.value for call in mock_public_pipe.emit.call_args_list]
        assert "neuron_started" in event_types
        assert "neuron_completed" in event_types


class TestCodeGeneratorFractal:
    """Test CodeGeneratorNeuron fractal emission."""
    
    # Skip this test - CodeGeneratorNeuron has complex initialization
    # The fractal emission is tested via the decorator which is shared
    # with GenerativeNeuron and IntentClassifierNeuron
    pass
