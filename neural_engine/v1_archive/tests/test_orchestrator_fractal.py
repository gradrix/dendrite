"""
Unit tests for Orchestrator fractal architecture integration.

Tests the Public Pipe and Mind Map integration in the Orchestrator.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


class TestOrchestratorFractalInit:
    """Test fractal initialization in Orchestrator."""
    
    def test_orchestrator_initializes_with_fractal_disabled(self):
        """Test that fractal can be disabled."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            enable_fractal=False,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        assert orch.enable_fractal == False
        assert orch.public_pipe is None
        assert orch.mind_map is None
    
    def test_orchestrator_accepts_custom_public_pipe(self):
        """Test that custom PublicPipe can be injected."""
        from neural_engine.core.orchestrator import Orchestrator
        from neural_engine.core.public_pipe import PublicPipe
        
        mock_pipe = MagicMock(spec=PublicPipe)
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            public_pipe=mock_pipe,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        assert orch.public_pipe == mock_pipe
    
    def test_orchestrator_accepts_custom_mind_map(self):
        """Test that custom MindMap can be injected."""
        from neural_engine.core.orchestrator import Orchestrator
        from neural_engine.core.mind_map import MindMap
        
        mock_map = MagicMock(spec=MindMap)
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        assert orch.mind_map == mock_map
    
    def test_orchestrator_enables_fractal_on_neurons(self):
        """Test that fractal is enabled on neurons during init."""
        from neural_engine.core.orchestrator import Orchestrator
        
        mock_neuron = MagicMock()
        mock_neuron.enable_fractal = MagicMock()
        
        neuron_registry = {
            "intent_classifier": mock_neuron,
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        mock_pipe = MagicMock()
        mock_map = MagicMock()
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        # Verify enable_fractal was called on the neuron
        mock_neuron.enable_fractal.assert_called_once_with(mock_pipe, mock_map)


class TestOrchestratorFractalTracking:
    """Test fractal tracking during goal processing."""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create an orchestrator with mocked fractal components."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        # Mock intent classifier to return generative intent
        neuron_registry["intent_classifier"].process.return_value = {
            "intent": "generative",
            "goal": "test goal"
        }
        neuron_registry["generative"].process.return_value = {
            "response": "Test response",
            "success": True
        }
        
        mock_pipe = MagicMock()
        mock_pipe.emit = AsyncMock()
        
        mock_map = MagicMock()
        mock_map.create_root = AsyncMock(return_value=MagicMock(node_id="root_test"))
        mock_map.complete_goal = AsyncMock()
        mock_map.fail_goal = AsyncMock()
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        return orch
    
    def test_process_emits_goal_started_event(self, mock_orchestrator):
        """Test that processing a goal emits a started event."""
        orch = mock_orchestrator
        
        # Process a goal
        result = orch.process("Test goal")
        
        # Verify emit was called with NEURON_STARTED
        assert orch.public_pipe.emit.called
        calls = orch.public_pipe.emit.call_args_list
        
        # First call should be NEURON_STARTED
        first_call = calls[0]
        event = first_call[0][0]
        assert event.event_type.value == "neuron_started"
        assert event.neuron_type == "Orchestrator"
    
    def test_process_creates_mind_map_root(self, mock_orchestrator):
        """Test that processing a goal creates a root node."""
        orch = mock_orchestrator
        
        # Process a goal
        result = orch.process("Test goal", goal_id="test-123")
        
        # Verify create_root was called
        orch.mind_map.create_root.assert_called_once()
        call_kwargs = orch.mind_map.create_root.call_args
        assert call_kwargs[1]["goal_id"] == "test-123"
        assert "Test goal" in call_kwargs[1]["goal_text"]
    
    def test_process_completes_goal_on_success(self, mock_orchestrator):
        """Test that successful processing completes the goal."""
        orch = mock_orchestrator
        
        # Process a goal
        result = orch.process("Test goal", goal_id="test-success")
        
        # Verify complete_goal was called
        orch.mind_map.complete_goal.assert_called_once()
        call_args = orch.mind_map.complete_goal.call_args
        assert call_args[0][0] == "test-success"
    
    def test_process_fails_goal_on_error(self, mock_orchestrator):
        """Test that error result fails the goal."""
        orch = mock_orchestrator
        
        # Make the generative neuron return an error
        orch.neuron_registry["generative"].process.return_value = {
            "error": "Test error",
            "success": False
        }
        
        # Process a goal
        result = orch.process("Test goal", goal_id="test-fail")
        
        # Verify fail_goal was called
        orch.mind_map.fail_goal.assert_called_once()
        call_args = orch.mind_map.fail_goal.call_args
        assert call_args[0][0] == "test-fail"
        assert "Test error" in call_args[1]["error"]
    
    def test_process_emits_completed_event(self, mock_orchestrator):
        """Test that processing emits a completed event."""
        orch = mock_orchestrator
        
        # Process a goal
        result = orch.process("Test goal")
        
        # Verify emit was called with NEURON_COMPLETED
        calls = orch.public_pipe.emit.call_args_list
        
        # Last call should be NEURON_COMPLETED
        last_call = calls[-1]
        event = last_call[0][0]
        assert event.event_type.value == "neuron_completed"
        assert event.neuron_type == "Orchestrator"


class TestOrchestratorFractalHelpers:
    """Test fractal helper methods."""
    
    def test_run_async_executes_coroutine(self):
        """Test that _run_async properly executes async code."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            enable_fractal=False,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        async def test_coro():
            return "async_result"
        
        result = orch._run_async(test_coro())
        assert result == "async_result"
    
    @pytest.mark.asyncio
    async def test_start_goal_tracking_emits_and_creates(self):
        """Test _start_goal_tracking creates root and emits event."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        mock_pipe = MagicMock()
        mock_pipe.emit = AsyncMock()
        
        mock_map = MagicMock()
        mock_root = MagicMock()
        mock_root.node_id = "root_node_123"
        mock_map.create_root = AsyncMock(return_value=mock_root)
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        root_id = await orch._start_goal_tracking("goal-abc", "Test goal text")
        
        assert root_id == "root_node_123"
        mock_pipe.emit.assert_called_once()
        mock_map.create_root.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_complete_goal_tracking_on_success(self):
        """Test _complete_goal_tracking marks goal complete."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        mock_pipe = MagicMock()
        mock_pipe.emit = AsyncMock()
        
        mock_map = MagicMock()
        mock_map.complete_goal = AsyncMock()
        mock_map.fail_goal = AsyncMock()
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        await orch._complete_goal_tracking(
            "goal-xyz",
            {"success": True, "result": "data"},
            150,
            success=True
        )
        
        mock_map.complete_goal.assert_called_once()
        mock_map.fail_goal.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_complete_goal_tracking_on_failure(self):
        """Test _complete_goal_tracking marks goal failed."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        mock_pipe = MagicMock()
        mock_pipe.emit = AsyncMock()
        
        mock_map = MagicMock()
        mock_map.complete_goal = AsyncMock()
        mock_map.fail_goal = AsyncMock()
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        await orch._complete_goal_tracking(
            "goal-fail",
            {"error": "Something went wrong"},
            200,
            success=False
        )
        
        mock_map.fail_goal.assert_called_once()
        mock_map.complete_goal.assert_not_called()
        
        # Verify error message was passed
        call_kwargs = mock_map.fail_goal.call_args
        assert "Something went wrong" in call_kwargs[1]["error"]


class TestOrchestratorFractalGracefulDegradation:
    """Test that orchestrator works when fractal components fail."""
    
    def test_process_works_without_redis(self):
        """Test that processing still works if Redis is unavailable."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        neuron_registry["intent_classifier"].process.return_value = {
            "intent": "generative",
            "goal": "test"
        }
        neuron_registry["generative"].process.return_value = {
            "response": "Works!",
            "success": True
        }
        
        # Explicitly disable fractal
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            enable_fractal=False,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        # Should work without any fractal components
        result = orch.process("Test goal")
        
        assert result["response"] == "Works!"
    
    def test_process_continues_if_fractal_emit_fails(self):
        """Test that processing continues even if emit fails."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        neuron_registry["intent_classifier"].process.return_value = {
            "intent": "generative",
            "goal": "test"
        }
        neuron_registry["generative"].process.return_value = {
            "response": "Works despite errors!",
            "success": True
        }
        
        # Create pipe that fails on emit
        mock_pipe = MagicMock()
        mock_pipe.emit = AsyncMock(side_effect=Exception("Redis connection lost"))
        
        mock_map = MagicMock()
        mock_map.create_root = AsyncMock(side_effect=Exception("Redis down"))
        mock_map.complete_goal = AsyncMock()
        
        orch = Orchestrator(
            neuron_registry=neuron_registry,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        # Should still work even though fractal components fail
        result = orch.process("Test goal")
        
        assert result["response"] == "Works despite errors!"
