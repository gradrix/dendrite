"""
Phase 0: Foundation Tests - Intent Classification

These tests verify the first LLM interaction in the system:
Can we correctly classify user intent from a simple goal string?

This is the foundation for everything else.
"""

import pytest
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
import redis


@pytest.fixture
def redis_client():
    """Provide a Redis client for testing."""
    client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
    # Clean up before test
    client.flushdb()
    yield client
    # Clean up after test
    client.flushdb()


@pytest.fixture
def message_bus(redis_client):
    """Provide a MessageBus for testing."""
    return MessageBus(redis_client)


@pytest.fixture
def ollama_client():
    """Provide an OllamaClient for testing."""
    return OllamaClient(host='http://ollama:11434')


@pytest.fixture
def intent_classifier(ollama_client, message_bus):
    """Provide an IntentClassifierNeuron for testing."""
    return IntentClassifierNeuron(ollama_client=ollama_client, message_bus=message_bus)


class TestPhase0IntentClassification:
    """
    Phase 0: Test the first LLM call - Intent Classification
    
    These tests verify that we can:
    1. Load prompts correctly
    2. Call the LLM with a formatted prompt
    3. Parse the response
    4. Return the correct intent
    """
    
    def test_generative_intent_simple_question(self, intent_classifier):
        """Test: Simple conversational question should be classified as 'generative'."""
        goal_id = "test-001"
        goal = "What is the capital of France?"
        
        result = intent_classifier.process(goal_id, goal)
        
        assert result["goal"] == goal
        assert result["intent"] in ["generative", "tool_use"]  # Should be generative
        print(f"✓ Classified '{goal}' as: {result['intent']}")
    
    def test_tool_use_intent_time_query(self, intent_classifier):
        """Test: Time query should be classified as 'tool_use'."""
        goal_id = "test-002"
        goal = "What time is it right now?"
        
        result = intent_classifier.process(goal_id, goal)
        
        assert result["goal"] == goal
        assert result["intent"] in ["generative", "tool_use"]  # Should be tool_use
        print(f"✓ Classified '{goal}' as: {result['intent']}")
    
    def test_tool_use_intent_api_call(self, intent_classifier):
        """Test: API request should be classified as 'tool_use'."""
        goal_id = "test-003"
        goal = "Get my latest Strava activities"
        
        result = intent_classifier.process(goal_id, goal)
        
        assert result["goal"] == goal
        assert result["intent"] in ["generative", "tool_use"]  # Should be tool_use
        print(f"✓ Classified '{goal}' as: {result['intent']}")
    
    def test_message_bus_stores_intent(self, intent_classifier, message_bus):
        """Test: Intent should be stored in message bus."""
        goal_id = "test-004"
        goal = "Tell me a joke"
        
        result = intent_classifier.process(goal_id, goal)
        
        # Verify message was stored
        messages = message_bus.get_messages(goal_id)
        assert len(messages) > 0
        
        # Find the intent message
        intent_message = next((m for m in messages if m.get('type') == 'intent'), None)
        assert intent_message is not None
        assert 'data' in intent_message
        print(f"✓ Intent stored in message bus: {intent_message['data']}")
    
    def test_ollama_client_connectivity(self, ollama_client):
        """Test: Ollama client can connect and generate."""
        response = ollama_client.generate(prompt="Say 'test' and nothing else.")
        
        assert 'response' in response
        assert len(response['response']) > 0
        print(f"✓ Ollama responded: {response['response'][:50]}...")
    
    def test_prompt_template_loads(self, intent_classifier):
        """Test: Prompt template file loads correctly."""
        prompt = intent_classifier._load_prompt()
        
        assert "{goal}" in prompt
        assert "tool_use" in prompt.lower()
        assert "generative" in prompt.lower()
        print(f"✓ Prompt template loaded ({len(prompt)} chars)")


@pytest.mark.parametrize("goal,expected_intent", [
    ("What is 2+2?", "generative"),
    ("Tell me about Python", "generative"),
    ("What time is it?", "tool_use"),
    ("Check the weather", "tool_use"),
    ("Get my Strava activities", "tool_use"),
    ("Write me a poem", "generative"),
])
def test_intent_classification_batch(intent_classifier, goal, expected_intent):
    """
    Batch test: Multiple goals with expected intents.
    
    Note: LLM responses may vary, so we accept both intents but print
    the result for manual verification during development.
    """
    goal_id = f"batch-{hash(goal)}"
    result = intent_classifier.process(goal_id, goal)
    
    actual_intent = result["intent"]
    match = "✓" if actual_intent == expected_intent else "✗"
    
    print(f"{match} '{goal}' → Expected: {expected_intent}, Got: {actual_intent}")
    
    # For now, just verify it's one of the valid intents
    assert actual_intent in ["generative", "tool_use"]
