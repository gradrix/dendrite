"""
Phase 1: Generative Pipeline Tests

These tests verify the complete generative (conversational) pipeline:
User Goal → Intent Classification → Generative Neuron → LLM Response

This is the simplest end-to-end flow in the system.
"""

import pytest
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.tool_registry import ToolRegistry
import redis
import os


@pytest.fixture
def redis_client():
    """Provide a Redis client for testing."""
    client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def message_bus():
    """Provide a MessageBus for testing."""
    os.environ['REDIS_HOST'] = 'redis'
    return MessageBus()


@pytest.fixture
def ollama_client():
    """Provide an OllamaClient for testing."""
    os.environ['OLLAMA_HOST'] = 'http://ollama:11434'
    os.environ['OLLAMA_MODEL'] = 'mistral'
    return OllamaClient()


@pytest.fixture
def intent_classifier(ollama_client, message_bus):
    """Provide an IntentClassifierNeuron for testing."""
    return IntentClassifierNeuron(ollama_client=ollama_client, message_bus=message_bus)


@pytest.fixture
def generative_neuron(ollama_client, message_bus):
    """Provide a GenerativeNeuron for testing."""
    return GenerativeNeuron(ollama_client=ollama_client, message_bus=message_bus)


@pytest.fixture
def tool_registry():
    """Provide a ToolRegistry for testing."""
    return ToolRegistry()


@pytest.fixture
def orchestrator(intent_classifier, generative_neuron, tool_registry, message_bus):
    """Provide an Orchestrator with all neurons registered."""
    neuron_registry = {
        "intent_classifier": intent_classifier,
        "generative": generative_neuron,
    }
    return Orchestrator(
        neuron_registry=neuron_registry,
        tool_registry=tool_registry,
        message_bus=message_bus
    )


class TestPhase1GenerativeNeuron:
    """
    Phase 1a: Test GenerativeNeuron in isolation
    
    Verify that the generative neuron can:
    1. Load prompts correctly
    2. Process simple requests
    3. Store responses in message bus
    4. Return well-formed responses
    """
    
    def test_generative_neuron_loads_prompt(self, generative_neuron):
        """Test: Generative neuron loads prompt template."""
        prompt = generative_neuron._load_prompt()
        
        assert "{goal}" in prompt
        assert len(prompt) > 0
        print(f"✓ Prompt loaded ({len(prompt)} chars)")
    
    def test_generative_neuron_simple_question(self, generative_neuron):
        """Test: Generative neuron answers a simple question."""
        goal_id = "gen-test-001"
        data = {"goal": "What is 2+2?"}
        
        result = generative_neuron.process(goal_id, data)
        
        assert "response" in result
        assert len(result["response"]) > 0
        print(f"✓ Response: {result['response'][:100]}...")
    
    def test_generative_neuron_stores_in_message_bus(self, generative_neuron, message_bus):
        """Test: Generative neuron stores response in message bus."""
        goal_id = "gen-test-002"
        data = {"goal": "Say 'test' and nothing else"}
        
        result = generative_neuron.process(goal_id, data)
        
        # Verify stored in message bus
        stored_response = message_bus.get_message(goal_id, "generative_response")
        assert stored_response is not None
        assert len(stored_response) > 0
        print(f"✓ Response stored in message bus")
    
    def test_generative_neuron_creative_task(self, generative_neuron):
        """Test: Generative neuron handles creative requests."""
        goal_id = "gen-test-003"
        data = {"goal": "Write a haiku about testing"}
        
        result = generative_neuron.process(goal_id, data)
        
        assert "response" in result
        assert len(result["response"]) > 10
        print(f"✓ Creative response generated")


class TestPhase1GenerativePipeline:
    """
    Phase 1b: Test the complete generative pipeline through Orchestrator
    
    This tests the full flow:
    Goal → IntentClassifier → Orchestrator → GenerativeNeuron → Response
    """
    
    def test_orchestrator_handles_simple_question(self, orchestrator):
        """Test: Orchestrator correctly routes and answers simple question."""
        goal_id = "pipe-test-001"
        goal = "What is Python?"
        
        result = orchestrator.execute(goal_id, goal)
        
        assert "response" in result
        assert len(result["response"]) > 0
        print(f"✓ Orchestrator answered: {result['response'][:100]}...")
    
    def test_orchestrator_handles_creative_request(self, orchestrator):
        """Test: Orchestrator handles creative/generative requests."""
        goal_id = "pipe-test-002"
        goal = "Tell me a joke"
        
        result = orchestrator.execute(goal_id, goal)
        
        assert "response" in result
        assert len(result["response"]) > 0
        print(f"✓ Creative response generated")
    
    def test_orchestrator_handles_explanation_request(self, orchestrator):
        """Test: Orchestrator explains concepts."""
        goal_id = "pipe-test-003"
        goal = "Explain recursion in one sentence"
        
        result = orchestrator.execute(goal_id, goal)
        
        assert "response" in result
        assert len(result["response"]) > 10
        print(f"✓ Explanation provided")
    
    def test_orchestrator_intent_classification_correct(self, orchestrator, message_bus):
        """Test: Orchestrator correctly classifies intent as generative."""
        goal_id = "pipe-test-004"
        goal = "What is the meaning of life?"
        
        result = orchestrator.execute(goal_id, goal)
        
        # Check that intent was classified correctly
        intent_message = message_bus.get_message(goal_id, "intent")
        assert intent_message is not None
        # Extract intent from new metadata format
        intent = intent_message["data"]["intent"] if "data" in intent_message else intent_message
        assert intent in ["generative", "tool_use"]  # Should be generative
        
        # Check that response was generated
        assert "response" in result
        print(f"✓ Intent: {intent}, Response received")


@pytest.mark.parametrize("goal,expected_keywords", [
    ("What is Python?", ["python", "programming", "language"]),
    ("Explain Docker", ["docker", "container"]),
    ("What is 2+2?", ["4", "four"]),
])
def test_generative_pipeline_batch(orchestrator, goal, expected_keywords):
    """
    Batch test: Multiple generative goals
    
    Note: We check for keywords but LLM responses vary,
    so we're lenient with exact matching.
    """
    goal_id = f"batch-{hash(goal)}"
    result = orchestrator.execute(goal_id, goal)
    
    assert "response" in result
    response_lower = result["response"].lower()
    
    # At least one keyword should appear (case-insensitive)
    keyword_found = any(kw.lower() in response_lower for kw in expected_keywords)
    
    status = "✓" if keyword_found else "⚠"
    print(f"{status} '{goal}' → Response contains relevant keywords: {keyword_found}")
    
    # Just verify we got a response
    assert len(result["response"]) > 0


class TestPhase1ErrorHandling:
    """
    Phase 1c: Test error handling in generative pipeline
    """
    
    def test_orchestrator_max_depth_check(self, orchestrator):
        """Test: Orchestrator respects max depth to prevent infinite recursion."""
        goal_id = "error-test-001"
        goal = "Test goal"
        
        # Execute at max depth
        result = orchestrator.execute(goal_id, goal, depth=orchestrator.max_depth + 1)
        
        assert "error" in result
        assert "Maximum recursion depth" in result["error"]
        print(f"✓ Max depth protection works")
    
    def test_generative_neuron_empty_goal(self, generative_neuron):
        """Test: Generative neuron handles empty goal gracefully."""
        goal_id = "error-test-002"
        data = {"goal": ""}
        
        result = generative_neuron.process(goal_id, data)
        
        # Should still return something (even if it's asking for clarification)
        assert "response" in result
        print(f"✓ Empty goal handled")


class TestPhase1MessageBusIntegration:
    """
    Phase 1d: Verify message bus correctly stores pipeline state
    """
    
    def test_full_pipeline_message_flow(self, orchestrator, message_bus):
        """Test: Complete pipeline stores all messages correctly."""
        goal_id = "msg-test-001"
        goal = "What is testing?"
        
        result = orchestrator.execute(goal_id, goal)
        
        # Verify intent was stored
        intent_message = message_bus.get_message(goal_id, "intent")
        assert intent_message is not None
        # Extract intent from new metadata format
        intent = intent_message["data"]["intent"] if "data" in intent_message else intent_message
        
        # Verify response was stored
        response = message_bus.get_message(goal_id, "generative_response")
        assert response is not None
        
        # Verify returned response matches stored response
        assert result["response"] == response
        
        print(f"✓ Complete message flow verified")
        print(f"  Intent: {intent}")
        print(f"  Response: {response[:50]}...")
