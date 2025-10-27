"""
Test Orchestrator integration with ExecutionStore.
Phase 8b: Verify automatic execution logging.
"""

import pytest
import time
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.sandbox import Sandbox
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.core.ollama_client import OllamaClient


@pytest.fixture
def execution_store():
    """Create ExecutionStore instance."""
    store = ExecutionStore()
    yield store
    store.close()


@pytest.fixture
def orchestrator(execution_store):
    """Create Orchestrator with ExecutionStore."""
    message_bus = MessageBus()
    ollama_client = OllamaClient()
    tool_registry = ToolRegistry()
    
    intent_classifier = IntentClassifierNeuron(message_bus, ollama_client)
    tool_selector = ToolSelectorNeuron(message_bus, ollama_client, tool_registry)
    code_generator = CodeGeneratorNeuron(message_bus, ollama_client, tool_registry)
    generative_neuron = GenerativeNeuron(message_bus, ollama_client)
    sandbox = Sandbox(message_bus)
    
    orchestrator = Orchestrator(
        intent_classifier=intent_classifier,
        tool_selector=tool_selector,
        code_generator=code_generator,
        generative_neuron=generative_neuron,
        message_bus=message_bus,
        sandbox=sandbox,
        execution_store=execution_store
    )
    
    return orchestrator


def test_orchestrator_has_execution_store(orchestrator, execution_store):
    """Test that orchestrator is initialized with execution store."""
    assert orchestrator.execution_store is not None
    assert orchestrator.execution_store == execution_store


def test_generative_execution_logged(orchestrator, execution_store):
    """Test that generative pipeline execution is logged."""
    goal_text = "What is 2 + 2?"
    
    # Get initial execution count
    initial_executions = execution_store.get_recent_executions(limit=1000)
    initial_count = len(initial_executions)
    
    # Process goal
    result = orchestrator.process(goal_text)
    
    # Check that execution was logged
    recent_executions = execution_store.get_recent_executions(limit=1000)
    assert len(recent_executions) == initial_count + 1
    
    # Check execution details
    latest = recent_executions[0]
    assert latest['goal_text'] == goal_text
    # Intent may vary due to LLM, but should be one of the valid intents
    assert latest['intent'] in ['generative', 'tool_use', 'unknown']
    assert 'goal_' in latest['goal_id']
    assert latest['duration_ms'] is not None
    assert latest['duration_ms'] > 0


def test_tool_use_execution_logged(orchestrator, execution_store):
    """Test that tool_use pipeline execution is logged."""
    goal_text = "Say hello using HelloWorldTool"
    
    # Get initial counts
    initial_executions = execution_store.get_recent_executions(limit=1000)
    initial_exec_count = len(initial_executions)
    
    # Process goal
    result = orchestrator.process(goal_text)
    
    # Check that execution was logged
    recent_executions = execution_store.get_recent_executions(limit=1000)
    assert len(recent_executions) == initial_exec_count + 1
    
    # Check execution details
    latest = recent_executions[0]
    assert latest['goal_text'] == goal_text
    # Intent may vary due to LLM, but should be one of the valid intents
    assert latest['intent'] in ['generative', 'tool_use', 'unknown']


def test_execution_metadata_stored(orchestrator, execution_store):
    """Test that execution metadata is properly stored."""
    goal_text = "Calculate 5 factorial"
    
    result = orchestrator.process(goal_text)
    
    # Get the latest execution
    recent = execution_store.get_recent_executions(limit=1)
    assert len(recent) == 1
    
    execution = recent[0]
    assert execution['goal_text'] == goal_text
    assert execution['duration_ms'] > 0
    assert execution['created_at'] is not None


def test_multiple_executions_logged(orchestrator, execution_store):
    """Test that multiple executions are all logged."""
    goals = [
        "What is the capital of France?",
        "Calculate 10 + 20",
        "Tell me a joke"
    ]
    
    initial_count = len(execution_store.get_recent_executions(limit=1000))
    
    # Process multiple goals
    for goal in goals:
        orchestrator.process(goal)
    
    # Check all were logged
    recent = execution_store.get_recent_executions(limit=1000)
    assert len(recent) >= initial_count + len(goals)


def test_failed_execution_logged(orchestrator, execution_store):
    """Test that failed executions are also logged."""
    # This might fail or succeed, but should be logged either way
    goal_text = "Use a nonexistent tool"
    
    initial_count = len(execution_store.get_recent_executions(limit=1000))
    
    try:
        result = orchestrator.process(goal_text)
    except Exception:
        pass  # We don't care if it fails, we just want to verify logging
    
    # Check that execution was logged
    recent = execution_store.get_recent_executions(limit=1000)
    assert len(recent) >= initial_count + 1


def test_goal_id_auto_increment(orchestrator, execution_store):
    """Test that goal IDs are auto-incremented."""
    orchestrator.process("First goal")
    orchestrator.process("Second goal")
    orchestrator.process("Third goal")
    
    recent = execution_store.get_recent_executions(limit=3)
    
    # Check that we got different goal IDs
    goal_ids = [exec['goal_id'] for exec in recent[:3]]
    assert len(set(goal_ids)) >= 3  # At least 3 unique IDs


def test_execution_success_flag(orchestrator, execution_store):
    """Test that success flag is stored correctly."""
    # Simple generative query should succeed
    goal_text = "What is 1 + 1?"
    orchestrator.process(goal_text)
    
    recent = execution_store.get_recent_executions(limit=1)
    execution = recent[0]
    
    # Should have a success field (True or False)
    assert 'success' in execution


def test_orchestrator_without_execution_store():
    """Test that orchestrator works without execution store (backward compatibility)."""
    message_bus = MessageBus()
    ollama_client = OllamaClient()
    tool_registry = ToolRegistry()
    
    intent_classifier = IntentClassifierNeuron(message_bus, ollama_client)
    tool_selector = ToolSelectorNeuron(message_bus, ollama_client, tool_registry)
    code_generator = CodeGeneratorNeuron(message_bus, ollama_client, tool_registry)
    generative_neuron = GenerativeNeuron(message_bus, ollama_client)
    sandbox = Sandbox(message_bus)
    
    # Create orchestrator without execution_store
    orchestrator = Orchestrator(
        intent_classifier=intent_classifier,
        tool_selector=tool_selector,
        code_generator=code_generator,
        generative_neuron=generative_neuron,
        message_bus=message_bus,
        sandbox=sandbox,
        execution_store=None
    )
    
    # Should work but not log anything
    result = orchestrator.process("What is 2 + 2?")
    assert result is not None


def test_execution_duration_reasonable(orchestrator, execution_store):
    """Test that execution duration is in reasonable range."""
    goal_text = "Say hello"
    
    orchestrator.process(goal_text)
    
    recent = execution_store.get_recent_executions(limit=1)
    execution = recent[0]
    
    # Duration should be reasonable (not negative, not too large)
    assert execution['duration_ms'] >= 0
    assert execution['duration_ms'] < 300000  # Less than 5 minutes


def test_statistics_update_after_executions(orchestrator, execution_store):
    """Test that statistics can be updated after executions."""
    # Run a few executions
    for i in range(3):
        orchestrator.process(f"Test query {i}")
    
    # Update statistics
    execution_store.update_statistics()
    
    # Should not raise exception
    stats = execution_store.get_tool_performance_view()
    assert isinstance(stats, list)


def test_success_rate_calculation(orchestrator, execution_store):
    """Test that success rate can be calculated after executions."""
    # Run some executions
    orchestrator.process("Simple question 1")
    orchestrator.process("Simple question 2")
    
    # Calculate success rate
    rate = execution_store.get_success_rate()
    assert 0.0 <= rate <= 1.0


def test_intent_classification_stored(orchestrator, execution_store):
    """Test that intent classification is stored in execution."""
    # Generative query
    orchestrator.process("What is the weather?")
    
    recent = execution_store.get_recent_executions(limit=1)
    execution = recent[0]
    
    # Should have intent stored
    assert execution['intent'] in ['generative', 'tool_use', 'unknown']
