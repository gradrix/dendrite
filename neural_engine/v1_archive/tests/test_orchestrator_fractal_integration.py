"""
Integration tests for Orchestrator fractal architecture.

Tests the integration between Orchestrator and fractal components.
Since PublicPipe and MindMap are already tested with real Redis,
these tests verify the integration wiring works correctly.
"""

import pytest
import uuid
import time
from unittest.mock import MagicMock, AsyncMock, patch


class TestOrchestratorFractalIntegration:
    """Integration tests verifying Orchestrator properly integrates with fractal components."""
    
    @pytest.fixture
    def mock_neurons(self):
        """Create mock neurons with predictable behavior."""
        neurons = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        
        # Default: return generative intent
        neurons["intent_classifier"].process.return_value = {
            "intent": "generative",
            "goal": "test goal"
        }
        neurons["generative"].process.return_value = {
            "response": "Integration test response",
            "success": True
        }
        
        return neurons
    
    @pytest.fixture
    def mock_public_pipe(self):
        """Create a mock PublicPipe that tracks calls."""
        mock = MagicMock()
        mock.emit = AsyncMock(return_value="event_123")
        return mock
    
    @pytest.fixture
    def mock_mind_map(self):
        """Create a mock MindMap that tracks calls."""
        mock = MagicMock()
        mock_node = MagicMock()
        mock_node.node_id = f"root_{uuid.uuid4().hex[:8]}"
        mock.create_root = AsyncMock(return_value=mock_node)
        mock.complete_goal = AsyncMock()
        mock.fail_goal = AsyncMock()
        mock.get_node = AsyncMock(return_value=mock_node)
        return mock
    
    def test_full_success_pipeline(self, mock_neurons, mock_public_pipe, mock_mind_map):
        """Test complete success path creates events and Mind Map entries."""
        from neural_engine.core.orchestrator import Orchestrator
        
        orch = Orchestrator(
            neuron_registry=mock_neurons,
            public_pipe=mock_public_pipe,
            mind_map=mock_mind_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        goal_id = f"success_test_{uuid.uuid4().hex[:8]}"
        result = orch.process("Complete success pipeline test", goal_id=goal_id)
        
        # Verify success response
        assert result["response"] == "Integration test response"
        
        # Verify Public Pipe emitted started and completed events
        emit_calls = mock_public_pipe.emit.call_args_list
        assert len(emit_calls) >= 2
        
        # First event should be started
        first_event = emit_calls[0][0][0]
        assert first_event.event_type.value == "neuron_started"
        assert first_event.neuron_type == "Orchestrator"
        
        # Last event should be completed
        last_event = emit_calls[-1][0][0]
        assert last_event.event_type.value == "neuron_completed"
        assert last_event.neuron_type == "Orchestrator"
        
        # Verify Mind Map was created
        mock_mind_map.create_root.assert_called_once()
        create_call = mock_mind_map.create_root.call_args
        assert create_call[1]["goal_id"] == goal_id
        
        # Verify Mind Map was marked complete
        mock_mind_map.complete_goal.assert_called_once()
        complete_call = mock_mind_map.complete_goal.call_args
        assert complete_call[0][0] == goal_id
    
    def test_full_failure_pipeline(self, mock_neurons, mock_public_pipe, mock_mind_map):
        """Test complete failure path creates events and marks failure."""
        from neural_engine.core.orchestrator import Orchestrator
        
        # Configure for failure
        mock_neurons["generative"].process.return_value = {
            "error": "Simulated failure",
            "success": False
        }
        
        orch = Orchestrator(
            neuron_registry=mock_neurons,
            public_pipe=mock_public_pipe,
            mind_map=mock_mind_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        goal_id = f"failure_test_{uuid.uuid4().hex[:8]}"
        result = orch.process("Test failure path", goal_id=goal_id)
        
        # Verify error response
        assert result.get("error") == "Simulated failure"
        
        # Verify Public Pipe emitted started and completed events
        emit_calls = mock_public_pipe.emit.call_args_list
        assert len(emit_calls) >= 2
        
        # Last event should be failed for failure cases
        last_event = emit_calls[-1][0][0]
        assert last_event.event_type.value == "neuron_failed"
        
        # Verify Mind Map was marked failed
        mock_mind_map.fail_goal.assert_called_once()
        fail_call = mock_mind_map.fail_goal.call_args
        assert fail_call[0][0] == goal_id
        assert "Simulated failure" in fail_call[1]["error"]
    
    def test_tool_use_pipeline(self, mock_neurons, mock_public_pipe, mock_mind_map):
        """Test tool use path integrates with fractal components."""
        from neural_engine.core.orchestrator import Orchestrator
        
        # Configure for tool use
        mock_neurons["intent_classifier"].process.return_value = {
            "intent": "tool_use",
            "goal": "use a tool"
        }
        mock_neurons["tool_selector"].process.return_value = {
            "tool": "test_tool",
            "result": "Tool executed successfully",
            "success": True
        }
        
        orch = Orchestrator(
            neuron_registry=mock_neurons,
            public_pipe=mock_public_pipe,
            mind_map=mock_mind_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        goal_id = f"tool_test_{uuid.uuid4().hex[:8]}"
        result = orch.process("Use a tool for this", goal_id=goal_id)
        
        # Verify events were emitted
        emit_calls = mock_public_pipe.emit.call_args_list
        assert len(emit_calls) >= 2
        
        # Verify Mind Map was created and completed
        mock_mind_map.create_root.assert_called_once()
        mock_mind_map.complete_goal.assert_called_once()
    
    def test_event_contains_goal_context(self, mock_neurons, mock_public_pipe, mock_mind_map):
        """Test that events include goal context."""
        from neural_engine.core.orchestrator import Orchestrator
        
        orch = Orchestrator(
            neuron_registry=mock_neurons,
            public_pipe=mock_public_pipe,
            mind_map=mock_mind_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        goal_id = f"context_test_{uuid.uuid4().hex[:8]}"
        result = orch.process("Test context in events", goal_id=goal_id)
        
        # Check started event has goal_id
        started_event = mock_public_pipe.emit.call_args_list[0][0][0]
        assert started_event.goal_id == goal_id
        
        # Check completed event has goal_id
        completed_event = mock_public_pipe.emit.call_args_list[-1][0][0]
        assert completed_event.goal_id == goal_id
    
    def test_completed_event_has_duration(self, mock_neurons, mock_public_pipe, mock_mind_map):
        """Test that completed events include duration."""
        from neural_engine.core.orchestrator import Orchestrator
        
        orch = Orchestrator(
            neuron_registry=mock_neurons,
            public_pipe=mock_public_pipe,
            mind_map=mock_mind_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        result = orch.process("Test duration tracking")
        
        # Check completed event has duration
        completed_event = mock_public_pipe.emit.call_args_list[-1][0][0]
        assert completed_event.duration_ms is not None
        assert completed_event.duration_ms >= 0
    
    def test_mind_map_receives_result_context(self, mock_neurons, mock_public_pipe, mock_mind_map):
        """Test that Mind Map completion includes result context."""
        from neural_engine.core.orchestrator import Orchestrator
        
        mock_neurons["generative"].process.return_value = {
            "response": "Detailed response content",
            "success": True,
            "tokens_used": 150
        }
        
        orch = Orchestrator(
            neuron_registry=mock_neurons,
            public_pipe=mock_public_pipe,
            mind_map=mock_mind_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        goal_id = f"result_ctx_{uuid.uuid4().hex[:8]}"
        result = orch.process("Test result context", goal_id=goal_id)
        
        # Verify complete_goal was called with result info
        complete_call = mock_mind_map.complete_goal.call_args
        assert "result" in complete_call[1] or len(complete_call[0]) > 1
    
    def test_multiple_goals_tracked_independently(self, mock_neurons, mock_public_pipe, mock_mind_map):
        """Test that multiple goals create independent tracking."""
        from neural_engine.core.orchestrator import Orchestrator
        
        orch = Orchestrator(
            neuron_registry=mock_neurons,
            public_pipe=mock_public_pipe,
            mind_map=mock_mind_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        goal_ids = [f"multi_{i}_{uuid.uuid4().hex[:8]}" for i in range(3)]
        
        for i, goal_id in enumerate(goal_ids):
            result = orch.process(f"Goal number {i}", goal_id=goal_id)
        
        # Verify create_root was called for each goal
        assert mock_mind_map.create_root.call_count == 3
        
        # Verify each call had a different goal_id
        called_ids = [call[1]["goal_id"] for call in mock_mind_map.create_root.call_args_list]
        assert set(called_ids) == set(goal_ids)
        
        # Verify complete_goal was called for each
        assert mock_mind_map.complete_goal.call_count == 3


class TestOrchestratorFractalNeuronPropagation:
    """Test that fractal components propagate to neurons."""
    
    def test_enable_fractal_propagates_to_neurons(self):
        """Test that neurons with enable_fractal receive components."""
        from neural_engine.core.orchestrator import Orchestrator
        from neural_engine.core.neuron import BaseNeuron
        from unittest.mock import MagicMock
        
        class TestableNeuron(BaseNeuron):
            def process(self, goal_id, data, depth=0):
                return {"processed": True}
        
        # Create a real neuron that can receive fractal
        mock_bus = MagicMock()
        mock_ollama = MagicMock()
        real_neuron = TestableNeuron(mock_bus, mock_ollama)
        
        neurons = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock(),
            "testable": real_neuron
        }
        
        neurons["intent_classifier"].process.return_value = {"intent": "generative", "goal": "test"}
        neurons["generative"].process.return_value = {"response": "ok", "success": True}
        
        mock_pipe = MagicMock()
        mock_map = MagicMock()
        
        orch = Orchestrator(
            neuron_registry=neurons,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        # Verify the real neuron received fractal components
        assert real_neuron._public_pipe == mock_pipe
        assert real_neuron._mind_map == mock_map
    
    def test_neurons_without_enable_fractal_are_skipped(self):
        """Test that neurons without enable_fractal method are handled gracefully."""
        from neural_engine.core.orchestrator import Orchestrator
        
        # Plain mock without enable_fractal method
        neurons = {
            "intent_classifier": MagicMock(spec=["process"]),  # No enable_fractal
            "generative": MagicMock(spec=["process"]),
            "tool_selector": MagicMock(spec=["process"]),
            "code_generator": MagicMock(spec=["process"]),
            "sandbox": MagicMock(spec=["process"])
        }
        
        neurons["intent_classifier"].process.return_value = {"intent": "generative", "goal": "test"}
        neurons["generative"].process.return_value = {"response": "ok", "success": True}
        
        mock_pipe = MagicMock()
        mock_map = MagicMock()
        
        # Should not raise even though neurons don't have enable_fractal
        orch = Orchestrator(
            neuron_registry=neurons,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        # Processing should still work
        result = orch.process("Test handling neurons without enable_fractal")
        assert result["response"] == "ok"


class TestOrchestratorFractalEdgeCases:
    """Test edge cases in fractal integration."""
    
    def test_no_goal_id_generates_one(self):
        """Test that processing without goal_id still works."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neurons = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        neurons["intent_classifier"].process.return_value = {"intent": "generative", "goal": "test"}
        neurons["generative"].process.return_value = {"response": "ok", "success": True}
        
        mock_pipe = MagicMock()
        mock_pipe.emit = AsyncMock()
        mock_map = MagicMock()
        mock_map.create_root = AsyncMock(return_value=MagicMock(node_id="root"))
        mock_map.complete_goal = AsyncMock()
        
        orch = Orchestrator(
            neuron_registry=neurons,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        # Process without providing goal_id
        result = orch.process("Test without explicit goal_id")
        
        # Should still work and track
        assert mock_pipe.emit.called
        assert mock_map.create_root.called
    
    def test_empty_goal_string(self):
        """Test handling of empty goal string."""
        from neural_engine.core.orchestrator import Orchestrator
        
        neurons = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        neurons["intent_classifier"].process.return_value = {"intent": "generative", "goal": ""}
        neurons["generative"].process.return_value = {"response": "handled empty", "success": True}
        
        mock_pipe = MagicMock()
        mock_pipe.emit = AsyncMock()
        mock_map = MagicMock()
        mock_map.create_root = AsyncMock(return_value=MagicMock(node_id="root"))
        mock_map.complete_goal = AsyncMock()
        
        orch = Orchestrator(
            neuron_registry=neurons,
            public_pipe=mock_pipe,
            mind_map=mock_map,
            enable_fractal=True,
            enable_semantic_search=False,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        # Should handle empty string gracefully
        result = orch.process("")
        
        assert result["response"] == "handled empty"
