# Fractal Architecture Evolution Plan

## Vision: From Centralized to Self-Organizing Neural Swarm

This document outlines the migration path from the current centralized Orchestrator to a fully autonomous, fractal neuron system.

---

## Current State (Phases 0-2) ✅

### Architecture
```
User Goal → Orchestrator (Central Controller)
            ↓
            Picks Neuron → Executes → Returns Result
```

### Characteristics
- ✅ **Works**: Reliable, testable, debuggable
- ✅ **Simple**: Easy to understand and validate
- ❌ **Centralized**: Single point of control
- ❌ **Stateless**: Neurons don't remember
- ❌ **Static**: Manual neuron registration

### Components
- `Orchestrator`: Central dispatcher
- `BaseNeuron`: Stateless processors
- `MessageBus`: Simple key-value storage
- `neuron_registry`: Hardcoded dict

---

## Phase 3-6: Tool Pipeline (Keep Current Architecture) ✅ NEXT

### Goal
Complete the tool execution pipeline while maintaining stability.

### Keep
- Centralized Orchestrator (for now)
- Stateless neurons (for now)
- Focus on **validating the pipeline logic**

### Implement
- Phase 3: Tool Selection (ToolSelectorNeuron)
- Phase 4: Code Generation (CodeGeneratorNeuron)
- Phase 5: Sandbox Execution
- Phase 6: Full pipeline integration

### Why Keep Current Architecture?
- **Stability**: Don't change foundation while building features
- **Testing**: Easy to debug centralized flow
- **Learning**: Understand the full pipeline before decentralizing

---

## Phase 7: Add Neuron Identity & Memory 🎯 CRITICAL MIGRATION START

### Goal
Give neurons persistent identity and memory without changing orchestration.

### Migration Steps

#### 7.1: Add Neuron Identity
```python
# OLD (current)
class BaseNeuron:
    def __init__(self, message_bus, ollama_client):
        self.message_bus = message_bus
        self.ollama_client = ollama_client

# NEW (Phase 7)
class BaseNeuron:
    def __init__(self, neuron_id, message_bus, ollama_client, memory_store):
        self.neuron_id = neuron_id  # Unique identity
        self.message_bus = message_bus
        self.ollama_client = ollama_client
        self.memory = memory_store  # Personal memory
        self.birth_time = time.time()
        self.execution_count = 0
```

#### 7.2: Add Thought Tree Storage
```python
class MemoryGraph:
    """Stores neuron's thought history as a tree"""
    def __init__(self, redis_client, neuron_id):
        self.redis = redis_client
        self.neuron_id = neuron_id
    
    def add_thought(self, goal_id, parent_goal_id, input_data, output_data):
        """Store a thought node in the tree"""
        thought_key = f"thought:{goal_id}"
        self.redis.hset(thought_key, mapping={
            "neuron_id": self.neuron_id,
            "parent_goal_id": parent_goal_id or "",
            "input": json.dumps(input_data),
            "output": json.dumps(output_data),
            "timestamp": time.time(),
            "depth": self._get_depth(parent_goal_id)
        })
        
        # Link to parent
        if parent_goal_id:
            self.redis.sadd(f"thought:{parent_goal_id}:children", goal_id)
    
    def get_thought_chain(self, goal_id):
        """Retrieve entire thought chain from root to this thought"""
        chain = []
        current = goal_id
        while current:
            thought = self.redis.hgetall(f"thought:{current}")
            chain.insert(0, thought)
            current = thought.get("parent_goal_id")
        return chain
    
    def query_similar_thoughts(self, context):
        """Find past thoughts similar to current context (for learning)"""
        # Use semantic search on stored thoughts
        # Returns: List of (goal_id, similarity_score)
        pass
```

#### 7.3: Update BaseNeuron to Use Memory
```python
class BaseNeuron:
    def process(self, goal_id, data, depth=0, parent_goal_id=None):
        # 1. Record input
        self.execution_count += 1
        
        # 2. Check memory for similar past problems
        similar = self.memory.query_similar_thoughts(data)
        
        # 3. Execute (with context from memory)
        result = self._execute(goal_id, data, depth, similar)
        
        # 4. Record output
        self.memory.add_thought(goal_id, parent_goal_id, data, result)
        
        # 5. Publish event (for Phase 8)
        self._publish_execution_event(goal_id, result)
        
        return result
    
    def _execute(self, goal_id, data, depth, similar_thoughts):
        """Subclasses implement this"""
        raise NotImplementedError
```

#### 7.4: Update Orchestrator to Pass Neuron IDs
```python
class Orchestrator:
    def __init__(self, message_bus, max_depth=10):
        self.message_bus = message_bus
        self.max_depth = max_depth
        
        # Create neurons with unique IDs
        self.neurons = {
            "intent_classifier": IntentClassifierNeuron(
                neuron_id="intent-001",
                message_bus=message_bus,
                ollama_client=OllamaClient(),
                memory_store=MemoryGraph(message_bus.redis, "intent-001")
            ),
            "generative": GenerativeNeuron(
                neuron_id="generative-001",
                message_bus=message_bus,
                ollama_client=OllamaClient(),
                memory_store=MemoryGraph(message_bus.redis, "generative-001")
            ),
            # ...
        }
```

### Tests for Phase 7
- Test neuron has unique ID
- Test thoughts stored in tree structure
- Test thought chain retrieval
- Test memory survives neuron restart
- Test similar thought queries

### Why This Phase?
- **Backward compatible**: Orchestrator still works
- **Foundation**: Enables learning from past executions
- **Incremental**: No big-bang migration

---

## Phase 8: Event Stream (Public Pipe) 🌟

### Goal
Replace key-value MessageBus with event stream for observability.

### Migration Steps

#### 8.1: Add EventBus (Keep MessageBus for Now)
```python
class EventBus:
    """Redis Streams-based event publishing"""
    def __init__(self, redis_client):
        self.redis = redis_client
        self.stream_name = "neuron_events"
    
    def publish(self, event_type, neuron_id, data):
        """Publish event to stream"""
        self.redis.xadd(self.stream_name, {
            "event_type": event_type,
            "neuron_id": neuron_id,
            "timestamp": time.time(),
            "data": json.dumps(data)
        })
    
    def subscribe(self, consumer_group, consumer_id, last_id="0"):
        """Subscribe to event stream"""
        # Create consumer group if not exists
        try:
            self.redis.xgroup_create(self.stream_name, consumer_group, id="0", mkstream=True)
        except redis.exceptions.ResponseError:
            pass  # Group already exists
        
        # Read from stream
        events = self.redis.xreadgroup(
            consumer_group,
            consumer_id,
            {self.stream_name: ">"},
            count=10,
            block=1000
        )
        return events
```

#### 8.2: Update Neurons to Publish Events
```python
class BaseNeuron:
    def _publish_execution_event(self, goal_id, result):
        """Publish execution telemetry"""
        self.event_bus.publish(
            event_type="neuron.executed",
            neuron_id=self.neuron_id,
            data={
                "goal_id": goal_id,
                "success": result.get("success", True),
                "duration_ms": result.get("duration_ms"),
                "execution_count": self.execution_count
            }
        )
```

#### 8.3: Add PerformanceMonitorNeuron
```python
class PerformanceMonitorNeuron(BaseNeuron):
    """Meta-agent that observes system performance"""
    
    def start_monitoring(self):
        """Run in background, watching event stream"""
        while True:
            events = self.event_bus.subscribe(
                consumer_group="performance_monitor",
                consumer_id=self.neuron_id
            )
            
            for event in events:
                self._analyze_event(event)
    
    def _analyze_event(self, event):
        """Analyze neuron performance"""
        data = json.loads(event["data"])
        
        # Detect slow neurons
        if data.get("duration_ms", 0) > 5000:
            self._spawn_optimization_goal(
                f"Optimize {data['neuron_id']} - slow execution"
            )
        
        # Detect failure patterns
        if not data.get("success"):
            self._track_failure(data["neuron_id"], data["goal_id"])
    
    def _spawn_optimization_goal(self, goal_description):
        """Create new goal to optimize system"""
        goal_id = self.message_bus.get_new_goal_id()
        self.message_bus.add_message(goal_id, "goal", goal_description)
        # This feeds back into orchestrator
```

### Tests for Phase 8
- Test events published to stream
- Test multiple consumers can read events
- Test PerformanceMonitor detects slow neurons
- Test PerformanceMonitor spawns optimization goals

---

## Phase 9: Decentralized Goal Claiming 🚀

### Goal
Replace centralized orchestrator with pub/sub goal broadcasting.

### Migration Steps

#### 9.1: Add Goal Broadcasting
```python
class NeuronSwarm:
    """Replaces Orchestrator - manages goal pub/sub"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.goal_stream = "goals"
    
    def publish_goal(self, goal_id, goal_text, depth=0, parent_goal_id=None):
        """Broadcast goal to all neurons"""
        self.redis.xadd(self.goal_stream, {
            "goal_id": goal_id,
            "goal": goal_text,
            "depth": depth,
            "parent_goal_id": parent_goal_id or "",
            "status": "pending",
            "timestamp": time.time()
        })
    
    def claim_goal(self, goal_id, neuron_id):
        """Neuron claims a goal (atomic operation)"""
        # Use Redis transaction to ensure only one neuron claims
        with self.redis.pipeline() as pipe:
            try:
                pipe.watch(f"goal:{goal_id}:status")
                status = pipe.get(f"goal:{goal_id}:status")
                
                if status == b"pending":
                    pipe.multi()
                    pipe.set(f"goal:{goal_id}:status", "claimed")
                    pipe.set(f"goal:{goal_id}:claimed_by", neuron_id)
                    pipe.execute()
                    return True
                else:
                    return False  # Already claimed
            except redis.WatchError:
                return False  # Race condition, try again
```

#### 9.2: Update Neurons to Watch Goal Stream
```python
class BaseNeuron:
    def start_listening(self):
        """Listen for goals this neuron can handle"""
        while True:
            goals = self.swarm.get_pending_goals(
                consumer_group=self.__class__.__name__,
                consumer_id=self.neuron_id
            )
            
            for goal in goals:
                if self._can_handle(goal):
                    if self.swarm.claim_goal(goal["goal_id"], self.neuron_id):
                        self._handle_goal(goal)
    
    def _can_handle(self, goal):
        """Does this neuron's capabilities match the goal?"""
        # Check if goal matches this neuron's expertise
        # Could use semantic similarity, keywords, etc.
        raise NotImplementedError
```

#### 9.3: Add Capability Registry
```python
class NeuronRegistry:
    """Tracks which neurons exist and their capabilities"""
    
    def register_neuron(self, neuron_id, capabilities, neuron_class):
        """Neuron announces itself to the swarm"""
        self.redis.hset(f"neuron:{neuron_id}", mapping={
            "class": neuron_class,
            "capabilities": json.dumps(capabilities),
            "status": "active",
            "registered_at": time.time()
        })
        
        # Set expiry - neuron must heartbeat
        self.redis.expire(f"neuron:{neuron_id}", 60)
    
    def heartbeat(self, neuron_id):
        """Neuron proves it's still alive"""
        self.redis.expire(f"neuron:{neuron_id}", 60)
    
    def find_neurons_for_capability(self, capability):
        """Find all neurons that can handle this capability"""
        # Scan all registered neurons
        # Return list of neuron_ids
        pass
```

#### 9.4: Migration Strategy (Hybrid Mode)
```python
class HybridOrchestrator:
    """Transition period: supports both modes"""
    
    def execute(self, goal_id, goal, mode="centralized"):
        if mode == "centralized":
            # OLD: Direct neuron invocation
            return self._centralized_execute(goal_id, goal)
        else:
            # NEW: Pub/sub goal claiming
            return self._decentralized_execute(goal_id, goal)
    
    def _centralized_execute(self, goal_id, goal):
        """Current orchestrator logic"""
        neuron = self.neurons["intent_classifier"]
        return neuron.process(goal_id, goal)
    
    def _decentralized_execute(self, goal_id, goal):
        """New swarm logic"""
        self.swarm.publish_goal(goal_id, goal)
        # Wait for a neuron to claim and execute
        return self._wait_for_result(goal_id, timeout=30)
```

### Tests for Phase 9
- Test goal broadcast to stream
- Test neuron claims goal atomically
- Test only one neuron claims a goal
- Test capability matching
- Test hybrid mode (backward compatibility)

---

## Phase 10: Dynamic Neuron Spawning 🌌

### Goal
Neurons can spawn specialized child neurons.

### Migration Steps

#### 10.1: Add NeuronSpawner
```python
class NeuronSpawner:
    """Factory for creating new neurons at runtime"""
    
    def spawn(self, parent_neuron_id, neuron_class, specialization, prompt_override=None):
        """Spawn a new neuron instance"""
        neuron_id = f"{neuron_class.__name__}-{uuid.uuid4().hex[:8]}"
        
        # Create memory store
        memory = MemoryGraph(self.redis, neuron_id)
        
        # Create neuron instance
        neuron = neuron_class(
            neuron_id=neuron_id,
            message_bus=self.message_bus,
            ollama_client=self.ollama_client,
            memory_store=memory
        )
        
        # Override prompt if specified
        if prompt_override:
            neuron._prompt = prompt_override
        
        # Register in swarm
        capabilities = self._extract_capabilities(neuron, specialization)
        self.registry.register_neuron(neuron_id, capabilities, neuron_class.__name__)
        
        # Start listening for goals
        threading.Thread(target=neuron.start_listening, daemon=True).start()
        
        # Record lineage
        self.redis.sadd(f"neuron:{parent_neuron_id}:children", neuron_id)
        self.redis.set(f"neuron:{neuron_id}:parent", parent_neuron_id)
        
        return neuron_id
    
    def kill_neuron(self, neuron_id):
        """Gracefully shut down a neuron"""
        # Mark as inactive
        self.redis.hset(f"neuron:{neuron_id}", "status", "terminated")
        # Neuron's listening loop will exit
```

#### 10.2: Add Neuron Specialization
```python
class GenerativeNeuron(BaseNeuron):
    def spawn_specialist(self, specialization):
        """Spawn a specialized version of self"""
        
        # Example: Spawn poetry specialist
        if specialization == "poetry":
            prompt = """You are a specialized poetry generator.
            Your role is to create beautiful, evocative poems.
            You only handle poetry-related goals."""
            
            child_id = self.spawner.spawn(
                parent_neuron_id=self.neuron_id,
                neuron_class=GenerativeNeuron,
                specialization="poetry",
                prompt_override=prompt
            )
            
            return child_id
```

#### 10.3: Add ToolForgeNeuron (Self-Generating Code)
```python
class ToolForgeNeuron(BaseNeuron):
    """Neuron that writes new tools"""
    
    def _can_handle(self, goal):
        """Handle goals about creating new tools"""
        return "create tool" in goal["goal"].lower() or \
               "write tool" in goal["goal"].lower()
    
    def _handle_goal(self, goal):
        """Generate a new tool file"""
        # 1. Analyze goal to understand what tool to create
        tool_spec = self._analyze_tool_requirements(goal["goal"])
        
        # 2. Generate Python code for tool
        tool_code = self._generate_tool_code(tool_spec)
        
        # 3. Write to tools/ directory
        tool_path = f"neural_engine/tools/{tool_spec['name']}_tool.py"
        with open(tool_path, "w") as f:
            f.write(tool_code)
        
        # 4. Trigger ToolRegistry refresh
        self.tool_registry.refresh()
        
        # 5. Test the new tool
        test_result = self._test_new_tool(tool_spec['name'])
        
        return {
            "success": True,
            "tool_name": tool_spec['name'],
            "tool_path": tool_path,
            "test_result": test_result
        }
```

### Tests for Phase 10
- Test spawning specialized neuron
- Test child neuron inherits memory access
- Test child neuron registers independently
- Test ToolForgeNeuron generates valid Python
- Test newly forged tools work immediately

---

## Migration Timeline

### ✅ NOW (Phase 0-2): Foundation Complete
- Neurons work
- Message bus works
- Tool registry works

### 🎯 NEXT (Phase 3-6): 2-3 weeks
- Complete tool pipeline
- Keep centralized architecture
- Focus on functionality

### 🚀 THEN (Phase 7-8): 2-3 weeks
- Add neuron identity & memory
- Add event stream
- Still centralized, but instrumented

### 🌟 AFTER (Phase 9): 2-3 weeks
- Migrate to pub/sub orchestration
- Hybrid mode for safety
- Gradual transition

### 🌌 FUTURE (Phase 10+): Ongoing
- Dynamic spawning
- Self-improvement loop
- True autonomy

---

## Rollback Strategy

Each phase maintains backward compatibility:

### Phase 7: Memory
- If problems: Use `memory=None` flag, neurons work without memory
- No breaking changes to existing code

### Phase 8: Events
- If problems: Disable event publishing, system still works
- EventBus runs alongside MessageBus

### Phase 9: Decentralization
- If problems: Use `mode="centralized"` in HybridOrchestrator
- Can switch between modes with config flag

### Phase 10: Spawning
- If problems: Disable spawning, use manual registration
- Static neuron set still works

---

## Success Metrics

### Phase 7
- ✅ Every neuron has unique ID
- ✅ Thoughts stored in Redis graph
- ✅ Can query thought history

### Phase 8
- ✅ All executions publish events
- ✅ PerformanceMonitor running
- ✅ System generates self-improvement goals

### Phase 9
- ✅ Goals broadcast to stream
- ✅ Neurons claim goals autonomously
- ✅ Zero central coordination needed

### Phase 10
- ✅ Neurons spawn children
- ✅ ToolForge generates working tools
- ✅ System evolves without human intervention

---

## Final Vision

```
                    🌐 Goal Stream (Redis)
                           ↓
        [Goal: "Write a poem about AI"]
                           ↓
        ┌──────────────────┴──────────────────┐
        ↓                                      ↓
    Neuron-A                              Neuron-B
    "I handle poetry!"                    "Not my thing"
        ↓                                      (ignores)
    CLAIMS GOAL
        ↓
    Spawns specialist child
        ↓
    Poetry-Specialist-001
        ↓
    Generates poem
        ↓
    Publishes result event
        ↓
    🎉 DONE

Meanwhile, PerformanceMonitor watches and thinks:
"Hmm, poetry goals are common. Should I spawn a permanent poetry specialist?"
```

**No central orchestrator. Self-organizing. Fractal. Autonomous.** 🌟
