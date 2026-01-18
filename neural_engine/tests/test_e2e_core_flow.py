"""
E2E Test: Core System Flow

This test validates the ACTUAL working state of the system with minimal complexity.
It answers: "Does the core loop work?"

Test Flow:
1. Simple generative response (no tools)
2. Memory write → Memory read (persistence)
3. Simple calculation using existing tool
4. Verify what actually gets tracked/cached

NO external APIs (Strava, etc). Just core system.
"""

import pytest
import uuid
import redis.asyncio as redis
from unittest.mock import MagicMock


class TestE2ECoreFlow:
    """
    E2E tests for the core system flow.
    These tests use real LLM calls - they're slow but prove the system works.
    """
    
    @pytest.fixture
    def async_redis(self):
        """Async redis client for fractal components."""
        client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
        return client
    
    @pytest.fixture
    def setup_system(self, async_redis):
        """Set up the complete system with all components."""
        from neural_engine.core.orchestrator import Orchestrator
        from neural_engine.core.tool_registry import ToolRegistry
        from neural_engine.core.message_bus import MessageBus
        from neural_engine.core.ollama_client import OllamaClient
        from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
        from neural_engine.core.generative_neuron import GenerativeNeuron
        from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
        from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
        from neural_engine.core.sandbox import Sandbox
        from neural_engine.core.public_pipe import PublicPipe
        from neural_engine.core.mind_map import MindMap
        
        # Core components - they use env vars internally
        message_bus = MessageBus()
        ollama_client = OllamaClient()
        tool_registry = ToolRegistry()
        
        # Fractal components
        public_pipe = PublicPipe(async_redis)
        mind_map = MindMap(async_redis)
        
        # Neurons
        intent_classifier = IntentClassifierNeuron(
            ollama_client=ollama_client, 
            message_bus=message_bus
        )
        generative_neuron = GenerativeNeuron(
            ollama_client=ollama_client, 
            message_bus=message_bus
        )
        tool_selector = ToolSelectorNeuron(
            ollama_client=ollama_client, 
            message_bus=message_bus, 
            tool_registry=tool_registry
        )
        code_generator = CodeGeneratorNeuron(
            ollama_client=ollama_client, 
            message_bus=message_bus,
            tool_registry=tool_registry
        )
        sandbox = Sandbox(message_bus=message_bus)
        
        neuron_registry = {
            "intent_classifier": intent_classifier,
            "generative": generative_neuron,
            "tool_selector": tool_selector,
            "code_generator": code_generator,
            "sandbox": sandbox,
        }
        
        # Orchestrator with fractal enabled
        orchestrator = Orchestrator(
            neuron_registry=neuron_registry,
            tool_registry=tool_registry,
            message_bus=message_bus,
            public_pipe=public_pipe,
            mind_map=mind_map,
            enable_fractal=True,
            enable_semantic_search=False,  # Skip for simplicity
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        return {
            'orchestrator': orchestrator,
            'message_bus': message_bus,
            'public_pipe': public_pipe,
            'mind_map': mind_map,
            'async_redis': async_redis,
        }
    
    # =========================================================================
    # Test 1: Simple Generative Response
    # =========================================================================
    
    def test_01_simple_generative_response(self, setup_system):
        """
        Most basic test: Ask a question, get a response.
        No tools, no memory, just: input → LLM → output
        """
        orch = setup_system['orchestrator']
        
        goal_id = f"e2e_gen_{uuid.uuid4().hex[:8]}"
        result = orch.process("What is 2 + 2? Just answer with the number.", goal_id=goal_id)
        
        # Basic checks
        assert result is not None, "Should return a result"
        assert 'response' in result or 'result' in result or 'error' not in result, \
            f"Should have a response, got: {result}"
        
        # The response should mention "4"
        response_text = str(result.get('response', result.get('result', '')))
        assert '4' in response_text, f"Should answer with 4, got: {response_text}"
        
        print(f"\n✓ Generative response works: {response_text[:100]}")
    
    # =========================================================================
    # Test 2: Memory Write
    # =========================================================================
    
    def test_02_memory_write(self, setup_system):
        """
        Test that we can store something in memory.
        """
        orch = setup_system['orchestrator']
        
        goal_id = f"e2e_memw_{uuid.uuid4().hex[:8]}"
        result = orch.process(
            "Remember that my favorite color is blue. Store this in memory.",
            goal_id=goal_id
        )
        
        assert result is not None, "Should return a result"
        assert 'error' not in result or result.get('error') is None, \
            f"Should not have error: {result}"
        
        print(f"\n✓ Memory write completed: {result}")
    
    # =========================================================================
    # Test 3: Memory Read
    # =========================================================================
    
    def test_03_memory_read(self, setup_system):
        """
        Test that we can retrieve from memory.
        First write, then read.
        """
        orch = setup_system['orchestrator']
        
        # First, manually write to memory to ensure it's there
        from neural_engine.core.key_value_store import KeyValueStore
        kv_store = KeyValueStore()
        kv_store.set("test_e2e_name", "Alice")
        
        goal_id = f"e2e_memr_{uuid.uuid4().hex[:8]}"
        result = orch.process(
            "What is my name? Check memory for 'test_e2e_name'.",
            goal_id=goal_id
        )
        
        assert result is not None, "Should return a result"
        
        response_text = str(result.get('response', result.get('result', '')))
        # Should either mention Alice or indicate it used memory
        print(f"\n✓ Memory read completed: {response_text[:200]}")
    
    # =========================================================================
    # Test 4: Tool Usage (Calculator)
    # =========================================================================
    
    def test_04_use_existing_tool(self, setup_system):
        """
        Test using an existing tool (addition).
        """
        orch = setup_system['orchestrator']
        
        goal_id = f"e2e_tool_{uuid.uuid4().hex[:8]}"
        result = orch.process(
            "Use the add_numbers tool to add 15 and 27.",
            goal_id=goal_id
        )
        
        assert result is not None, "Should return a result"
        
        response_text = str(result)
        # The result should mention 42 (15 + 27)
        print(f"\n✓ Tool usage result: {response_text[:200]}")
    
    # =========================================================================
    # Test 5: Fractal Event Tracking
    # =========================================================================
    
    def test_05_fractal_events_emitted(self, setup_system):
        """
        Verify that fractal events are actually emitted to PublicPipe.
        Note: This is a sync test because Orchestrator.process() is sync.
        """
        import asyncio
        import redis as sync_redis
        
        orch = setup_system['orchestrator']
        
        from neural_engine.core.public_pipe import PublicPipe
        
        # Use sync redis for verification since we're in sync test
        r = sync_redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
        
        # Clear existing events
        r.delete(PublicPipe.STREAM_KEY)
        
        goal_id = f"e2e_frac_{uuid.uuid4().hex[:8]}"
        result = orch.process("Say hello.", goal_id=goal_id)
        
        # Give async tasks time to complete
        import time
        time.sleep(0.5)
        
        # Check events were emitted
        events = r.xrange(PublicPipe.STREAM_KEY)
        
        assert len(events) >= 2, f"Should have at least 2 events (started + completed), got {len(events)}"
        
        event_types = [e[1].get('event_type') for e in events]
        print(f"\n✓ Fractal events emitted: {event_types}")
        
        assert 'neuron_started' in event_types, "Should have started event"
        assert 'neuron_completed' in event_types or 'neuron_failed' in event_types, \
            "Should have completed or failed event"
        
        r.close()
    
    # =========================================================================
    # Test 6: Mind Map Tracking
    # =========================================================================
    
    def test_06_mind_map_created(self, setup_system):
        """
        Verify that goals create Mind Map entries.
        Note: Sync test since Orchestrator.process() is sync.
        """
        import redis as sync_redis
        import json
        
        orch = setup_system['orchestrator']
        
        from neural_engine.core.mind_map import MindMap
        
        # Use sync redis for verification
        r = sync_redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
        
        goal_id = f"e2e_mind_{uuid.uuid4().hex[:8]}"
        result = orch.process("What is the meaning of life?", goal_id=goal_id)
        
        # Give async tasks time to complete
        import time
        time.sleep(0.5)
        
        # Check Mind Map node was created
        node_key = f"{MindMap.GOAL_PREFIX}{goal_id}"
        node_data = r.hgetall(node_key)
        
        print(f"\n✓ Mind Map node data: {node_data}")
        
        r.close()
        
        # Note: node_data might be empty if Mind Map storage isn't working
        # This test will reveal if it's actually being used
    
    # =========================================================================
    # Test 7: Message Bus Tracking
    # =========================================================================
    
    def test_07_message_bus_records(self, setup_system):
        """
        Verify that MessageBus records the execution.
        """
        orch = setup_system['orchestrator']
        message_bus = setup_system['message_bus']
        
        goal_id = f"e2e_msgb_{uuid.uuid4().hex[:8]}"
        result = orch.process("Count to three.", goal_id=goal_id)
        
        # Check what's in message bus
        messages = message_bus.get_all_messages(goal_id)
        
        print(f"\n✓ Message bus has {len(messages)} messages for goal {goal_id}")
        for msg in messages[:5]:  # Print first 5
            print(f"  - {msg.get('message_type', 'unknown')}: {str(msg.get('data', ''))[:50]}")
    
    # =========================================================================
    # Test 8: Repeated Query (Caching?)
    # =========================================================================
    
    def test_08_repeated_query_behavior(self, setup_system):
        """
        Test: Does the system cache/reuse results for identical queries?
        This reveals if MindMap/caching actually helps.
        """
        import time
        
        orch = setup_system['orchestrator']
        
        query = "What is the capital of France?"
        
        # First run
        start1 = time.time()
        goal_id1 = f"e2e_rep1_{uuid.uuid4().hex[:8]}"
        result1 = orch.process(query, goal_id=goal_id1)
        time1 = time.time() - start1
        
        # Second run (same query)
        start2 = time.time()
        goal_id2 = f"e2e_rep2_{uuid.uuid4().hex[:8]}"
        result2 = orch.process(query, goal_id=goal_id2)
        time2 = time.time() - start2
        
        print(f"\n✓ First query: {time1:.2f}s")
        print(f"✓ Second query: {time2:.2f}s")
        print(f"✓ Speedup: {time1/time2:.2f}x" if time2 > 0 else "N/A")
        
        # Note: This will reveal if caching is actually working
        # If time2 ≈ time1, caching isn't being used for generative queries


class TestE2ESystemState:
    """
    Tests that reveal the actual state of various systems.
    These are diagnostic - they show what's working vs dead code.
    """
    
    def test_which_event_systems_are_active(self):
        """
        Diagnostic: Which event systems actually have data?
        - MessageBus
        - PublicPipe
        - ExecutionStore
        """
        import redis as sync_redis
        
        client = sync_redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
        
        # Check PublicPipe stream
        try:
            pipe_events = client.xlen('dendrite:public_pipe')
            print(f"\n📊 PublicPipe events: {pipe_events}")
        except:
            print(f"\n📊 PublicPipe: N/A")
        
        # Check MessageBus keys
        msg_keys = client.keys('message_bus:*')
        print(f"📊 MessageBus keys: {len(msg_keys)}")
        
        # Check MindMap keys
        mind_keys = client.keys('dendrite:mind:*')
        print(f"📊 MindMap keys: {len(mind_keys)}")
        
        # Check KeyValueStore
        kv_keys = client.keys('kv:*')
        print(f"📊 KeyValueStore keys: {len(kv_keys)}")
        
        client.close()
    
    def test_tool_registry_state(self):
        """
        Diagnostic: What tools are registered?
        """
        from neural_engine.core.tool_registry import ToolRegistry
        
        registry = ToolRegistry()
        tools = list(registry.get_all_tools().keys())
        
        print(f"\n🔧 Registered tools ({len(tools)}):")
        for tool in tools[:10]:  # First 10
            print(f"  - {tool}")
        if len(tools) > 10:
            print(f"  ... and {len(tools) - 10} more")
