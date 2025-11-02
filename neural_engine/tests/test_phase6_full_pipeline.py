"""
Phase 6: Full Pipeline Integration Tests

Tests the complete orchestrated flow from user goal to final result:
User Goal → IntentClassifier → Orchestrator → ToolSelector → CodeGenerator → Sandbox → Result

This validates that all components work together correctly with the message bus
storing intermediate steps and the orchestrator coordinating the flow.
"""

import pytest
import time
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.sandbox import Sandbox
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.key_value_store import KeyValueStore


@pytest.fixture
def message_bus():
    """Message bus for storing intermediate steps."""
    return MessageBus()



@pytest.fixture
def tool_registry():
    """Tool registry with all available tools."""
    registry = ToolRegistry()
    registry.refresh()
    return registry


@pytest.fixture
def sandbox(message_bus):
    """Sandbox for code execution."""
    return Sandbox(message_bus)


@pytest.fixture
def ollama_client():
    """Ollama client for LLM inference."""
    return OllamaClient()


@pytest.fixture
def intent_classifier(message_bus, ollama_client):
    """Intent classifier neuron with isolated cache via environment variables."""
    return IntentClassifierNeuron(message_bus, ollama_client)


@pytest.fixture
def tool_selector(message_bus, ollama_client, tool_registry):
    """Tool selector neuron with isolated cache via environment variables."""
    return ToolSelectorNeuron(message_bus, ollama_client, tool_registry)


@pytest.fixture
def code_generator(message_bus, ollama_client, tool_registry):
    """Code generator neuron."""
    return CodeGeneratorNeuron(message_bus, ollama_client, tool_registry)


@pytest.fixture
def generative_neuron(message_bus, ollama_client):
    """Generative neuron for simple responses."""
    return GenerativeNeuron(message_bus, ollama_client)


@pytest.fixture
def orchestrator(intent_classifier, tool_selector, code_generator, generative_neuron, message_bus, sandbox):
    """Orchestrator that coordinates all neurons."""
    return Orchestrator(
        intent_classifier=intent_classifier,
        tool_selector=tool_selector,
        code_generator=code_generator,
        generative_neuron=generative_neuron,
        message_bus=message_bus,
        sandbox=sandbox
    )


@pytest.fixture
def kv_store():
    """Key-value store for memory operations with isolated storage via environment variables."""
    store = KeyValueStore()  # Will use NEURAL_ENGINE_KV_STORE env var set by conftest
    # Clean up before each test
    try:
        store.delete("test_key")
        store.delete("user_name")
        store.delete("favorite_color")
    except:
        pass
    return store


# ============================================================================
# Basic Pipeline Flow Tests
# ============================================================================

def test_pipeline_simple_greeting(orchestrator, message_bus):
    """Test: Simple greeting goes through generative path."""
    result = orchestrator.process("Hello!")
    
    # Should get a response
    assert result is not None
    assert isinstance(result, dict)
    
    # Check message bus captured the flow
    messages = message_bus.get_all_messages("goal_1")
    assert len(messages) > 0
    
    # Should have intent classification
    intent_messages = [m for m in messages if m.get("neuron") == "intent_classifier"]
    assert len(intent_messages) > 0
    
    # Should be classified as conversational (generative)
    assert intent_messages[0]["data"]["intent"] == "generative"


def test_pipeline_memory_write(orchestrator, message_bus, kv_store):
    """Test: Memory write goes through tool use path."""
    result = orchestrator.process("Remember that my name is Alice")
    
    # Should get confirmation
    assert result is not None
    
    # Check message bus captured complete flow
    messages = message_bus.get_all_messages("goal_1")
    
    # Should have all stages
    neuron_types = [m.get("neuron") for m in messages]
    assert "intent_classifier" in neuron_types
    assert "tool_selector" in neuron_types
    assert "code_generator" in neuron_types
    assert "sandbox" in neuron_types
    
    # Should be classified as tool_use or generative
    intent_messages = [m for m in messages if m.get("neuron") == "intent_classifier"]
    assert len(intent_messages) > 0, "Should have intent classification"
    assert intent_messages[0]["data"]["intent"] in ["tool_use", "generative"]
    
    # Memory should be written (verify the tool was actually called)
    stored_value = kv_store.get("user_name")
    assert stored_value == "Alice"


def test_pipeline_memory_read(orchestrator, message_bus, kv_store):
    """Test: Memory read retrieves stored value."""
    # First store something
    kv_store.set("user_name", "Bob")
    
    # Now read it
    result = orchestrator.process("What is my name?")
    
    # Should get the name back
    assert result is not None
    
    # Check message bus shows processing occurred
    messages = message_bus.get_all_messages("goal_1")
    intent_messages = [m for m in messages if m.get("neuron") == "intent_classifier"]
    
    # Intent may be tool_use or generative depending on LLM interpretation
    assert len(intent_messages) > 0, "Should have intent classification"
    assert intent_messages[0]["data"]["intent"] in ["tool_use", "generative"]
    
    # Verify memory_read_tool was selected
    tool_messages = [m for m in messages if m.get("neuron") == "tool_selector"]
    if tool_messages:
        selected_tools = tool_messages[0]["data"].get("selected_tools", [])
        tool_names = [t.get("name") for t in selected_tools]
        assert "memory_read" in tool_names


def test_pipeline_hello_world(orchestrator, message_bus):
    """Test: Hello world tool execution."""
    result = orchestrator.process("Say hello world")
    
    # Should execute (either tool or generative response)
    assert result is not None
    
    messages = message_bus.get_all_messages("goal_1")
    
    # Intent classification may vary - "Say hello world" is ambiguous
    intent_messages = [m for m in messages if m.get("neuron") == "intent_classifier"]
    assert len(intent_messages) > 0
    assert intent_messages[0]["data"]["intent"] in ["tool_use", "generative"]
    
    # If tool_use intent, verify tool selector ran
    # NOTE: Specific tool selection depends on LLM interpretation and semantic matching
    # The important thing is the system completes successfully
    if intent_messages[0]["data"]["intent"] == "tool_use":
        tool_messages = [m for m in messages if m.get("neuron") == "tool_selector"]
        assert len(tool_messages) > 0, "Tool selector should run for tool_use intent"
        selected_tools = tool_messages[0]["data"].get("selected_tools", [])
        assert len(selected_tools) > 0, "At least one tool should be selected"


# ============================================================================
# Multiple Goals in Sequence
# ============================================================================

def test_pipeline_multiple_goals_sequential(orchestrator, message_bus, kv_store):
    """Test: Multiple goals processed one after another."""
    # Goal 1: Write to memory
    result1 = orchestrator.process("Remember that my favorite color is blue")
    assert result1 is not None
    
    # Give message bus time to process
    time.sleep(0.1)
    
    # Goal 2: Read from memory
    result2 = orchestrator.process("What is my favorite color?")
    assert result2 is not None
    
    # Both goals should have separate message histories
    messages_goal1 = message_bus.get_all_messages("goal_1")
    messages_goal2 = message_bus.get_all_messages("goal_2")
    
    assert len(messages_goal1) > 0
    assert len(messages_goal2) > 0
    
    # Goal 1 should have written to memory
    stored_color = kv_store.get("favorite_color")
    assert stored_color == "blue"


def test_pipeline_mixed_intents(orchestrator, message_bus):
    """Test: Mix of conversational and tool use intents."""
    # Conversational
    result1 = orchestrator.process("Hello there!")
    assert result1 is not None
    
    time.sleep(0.1)
    
    # Tool use
    result2 = orchestrator.process("Say hello world")
    assert result2 is not None
    
    time.sleep(0.1)
    
    # Conversational
    result3 = orchestrator.process("Thanks!")
    assert result3 is not None
    
    # Check all three goals were processed
    messages_goal1 = message_bus.get_all_messages("goal_1")
    messages_goal2 = message_bus.get_all_messages("goal_2")
    messages_goal3 = message_bus.get_all_messages("goal_3")
    
    assert len(messages_goal1) > 0
    assert len(messages_goal2) > 0
    assert len(messages_goal3) > 0


# ============================================================================
# Depth Tracking
# ============================================================================

def test_pipeline_depth_tracking(orchestrator, message_bus):
    """Test: Depth parameter is tracked through pipeline."""
    result = orchestrator.process("Say hello world")
    
    messages = message_bus.get_all_messages("goal_1")
    
    # All messages should have depth field
    for msg in messages:
        assert "depth" in msg
        # All should be at depth 0 (no recursion yet)
        assert msg["depth"] == 0


def test_pipeline_depth_increments(intent_classifier, tool_selector, code_generator, message_bus):
    """Test: Depth increments when neurons call each other."""
    # Simulate intent classifier at depth 0
    intent_classifier.process("goal_1", "Say hello", depth=0)
    
    # Simulate tool selector at depth 1 (called by orchestrator after intent)
    tool_selector.process("goal_1", {"goal": "Say hello"}, depth=1)
    
    # Simulate code generator at depth 2
    code_generator.process("goal_1", {"goal": "Say hello", "selected_tools": []}, depth=2)
    
    messages = message_bus.get_all_messages("goal_1")
    
    # Should have messages at different depths
    depths = [m["depth"] for m in messages]
    assert 0 in depths
    assert 1 in depths
    assert 2 in depths


# ============================================================================
# Error Handling
# ============================================================================

def test_pipeline_handles_invalid_tool_selection(orchestrator, message_bus):
    """Test: Pipeline handles case where no suitable tool is found."""
    result = orchestrator.process("Calculate the nth Fibonacci number where n is 1000")
    
    # Should still get a result (might be generative fallback or error message)
    assert result is not None
    
    messages = message_bus.get_all_messages("goal_1")
    assert len(messages) > 0


def test_pipeline_handles_code_generation_error(orchestrator, message_bus):
    """Test: Pipeline handles code generation errors gracefully."""
    # This should trigger tool use but might have issues with code generation
    result = orchestrator.process("Do something with quantum entanglement matrices")
    
    # Should handle gracefully (generative fallback or error)
    assert result is not None


def test_pipeline_handles_sandbox_execution_error(code_generator, sandbox, message_bus, tool_registry):
    """Test: Pipeline handles sandbox execution errors."""
    # Generate code that will fail
    code_generator.process(
        "goal_1",
        {
            "goal": "Cause an error",
            "selected_tools": []
        },
        depth=0
    )
    
    messages = message_bus.get_all_messages("goal_1")
    code_messages = [m for m in messages if m.get("neuron") == "code_generator"]
    
    if code_messages:
        generated_code = code_messages[0]["data"].get("generated_code", "")
        
        # Force an error by injecting bad code
        bad_code = "this will cause a syntax error @#$"
        
        result = sandbox.execute(bad_code)
        
        # Should get error info
        assert result is not None
        assert "error" in result or "success" in result


# ============================================================================
# Message Bus Integration
# ============================================================================

def test_pipeline_message_bus_stores_all_steps(orchestrator, message_bus):
    """Test: Message bus stores every step of the pipeline."""
    result = orchestrator.process("Say hello world")
    
    messages = message_bus.get_all_messages("goal_1")
    
    # Should have multiple messages (one from each neuron)
    assert len(messages) >= 2  # At minimum: intent + one other step
    
    # Each message should have required fields
    for msg in messages:
        assert "goal_id" in msg
        assert "neuron" in msg
        assert "timestamp" in msg
        assert "depth" in msg
        assert "data" in msg


def test_pipeline_message_bus_goal_isolation(orchestrator, message_bus):
    """Test: Messages from different goals are isolated."""
    result1 = orchestrator.process("First goal")
    time.sleep(0.1)
    result2 = orchestrator.process("Second goal")
    
    messages_goal1 = message_bus.get_all_messages("goal_1")
    messages_goal2 = message_bus.get_all_messages("goal_2")
    
    # Both should have messages
    assert len(messages_goal1) > 0
    assert len(messages_goal2) > 0
    
    # All goal_1 messages should have goal_id="goal_1"
    for msg in messages_goal1:
        assert msg["goal_id"] == "goal_1"
    
    # All goal_2 messages should have goal_id="goal_2"
    for msg in messages_goal2:
        assert msg["goal_id"] == "goal_2"


def test_pipeline_message_bus_chronological_order(orchestrator, message_bus):
    """Test: Messages are stored in chronological order."""
    result = orchestrator.process("Say hello world")
    
    messages = message_bus.get_all_messages("goal_1")
    
    # Check timestamps are increasing
    timestamps = [msg["timestamp"] for msg in messages]
    assert timestamps == sorted(timestamps)


# ============================================================================
# End-to-End Integration
# ============================================================================

def test_full_pipeline_end_to_end(orchestrator, message_bus, kv_store):
    """Test: Complete end-to-end flow with memory write and read."""
    # Step 1: Write to memory
    result1 = orchestrator.process("Remember that my name is Charlie")
    assert result1 is not None
    
    time.sleep(0.2)
    
    # Step 2: Read from memory
    result2 = orchestrator.process("What is my name?")
    assert result2 is not None
    
    time.sleep(0.2)
    
    # Step 3: Update memory
    result3 = orchestrator.process("Actually, my name is David")
    assert result3 is not None
    
    time.sleep(0.2)
    
    # Step 4: Read again
    result4 = orchestrator.process("What is my name now?")
    assert result4 is not None
    
    # Verify memory operations worked
    final_name = kv_store.get("user_name")
    assert final_name == "David"
    
    # Verify all goals were tracked
    assert len(message_bus.get_all_messages("goal_1")) > 0
    assert len(message_bus.get_all_messages("goal_2")) > 0
    assert len(message_bus.get_all_messages("goal_3")) > 0
    assert len(message_bus.get_all_messages("goal_4")) > 0


def test_full_pipeline_with_tool_chaining(orchestrator, message_bus, kv_store):
    """Test: Pipeline can handle goals that require multiple tools."""
    # This goal might need both memory_write and hello_world
    result = orchestrator.process("Say hello and remember that you did")
    
    assert result is not None
    
    messages = message_bus.get_all_messages("goal_1")
    
    # Should have gone through tool use path
    intent_messages = [m for m in messages if m.get("neuron") == "intent_classifier"]
    assert len(intent_messages) > 0
    
    # Tool selector should have been called
    tool_messages = [m for m in messages if m.get("neuron") == "tool_selector"]
    assert len(tool_messages) > 0


def test_full_pipeline_conversational_to_tool_transition(orchestrator, message_bus, kv_store):
    """Test: Seamless transition from conversation to tool use."""
    # Start conversational
    result1 = orchestrator.process("Hi, how are you?")
    assert result1 is not None
    
    time.sleep(0.1)
    
    # Switch to tool use
    result2 = orchestrator.process("Can you remember my email is test@example.com?")
    assert result2 is not None
    
    time.sleep(0.1)
    
    # Back to conversational
    result3 = orchestrator.process("Thanks!")
    assert result3 is not None
    
    # All three should have been processed
    assert len(message_bus.get_all_messages("goal_1")) > 0
    assert len(message_bus.get_all_messages("goal_2")) > 0
    assert len(message_bus.get_all_messages("goal_3")) > 0
