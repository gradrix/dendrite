# Memory, Validation & Action Indexing Strategy

## Your Questions

1. **Should actions be indexed and saved?** → YES
2. **Graph DB vs Redis?** → Both! Use right tool for job
3. **Is it overkill?** → No, but start simple
4. **What's the use case?** → Let me show you...

---

## The Problem We're Solving

Right now:
- ✅ MessageBus stores execution history in Redis (temporary)
- ✅ Tools write to KeyValueStore (simple key→value)
- ❌ No long-term memory of what worked/failed
- ❌ No relationship tracking (what led to what)
- ❌ No learning from past executions

**We need**: System that learns from experience!

---

## Architecture: Multi-Layer Memory

### Layer 1: Redis (Working Memory) - CURRENT ✅
**What**: Short-term execution state
**Purpose**: Fast, ephemeral, coordination
**TTL**: Minutes to hours

```python
# Already implemented in MessageBus
bus.add_message("goal_1", "intent", {...})  # Expires after execution
```

**Use cases**:
- Current pipeline state
- Inter-neuron communication
- Temporary results

---

### Layer 2: PostgreSQL (Episodic Memory) - RECOMMENDED 🎯
**What**: Structured execution history
**Purpose**: Track what happened, analyze patterns
**TTL**: Weeks to months

```sql
-- Execution history
CREATE TABLE executions (
    execution_id UUID PRIMARY KEY,
    goal_id VARCHAR,
    goal_text TEXT,
    intent VARCHAR,
    selected_tools JSONB,
    generated_code TEXT,
    result JSONB,
    success BOOLEAN,
    error TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP,
    metadata JSONB
);

-- Tool usage stats
CREATE TABLE tool_usage (
    tool_name VARCHAR,
    execution_id UUID REFERENCES executions(execution_id),
    parameters JSONB,
    result JSONB,
    success BOOLEAN,
    duration_ms INTEGER,
    created_at TIMESTAMP
);

-- User feedback (for learning)
CREATE TABLE feedback (
    execution_id UUID REFERENCES executions(execution_id),
    user_rating INTEGER,  -- 1-5
    feedback_text TEXT,
    created_at TIMESTAMP
);
```

**Benefits**:
- SQL queries for analytics
- Efficient indexing
- ACID guarantees
- Standard tooling

**Use cases**:
- "Which tools succeed most often?"
- "What goals lead to errors?"
- "Show me executions similar to this one"
- Performance monitoring
- Usage analytics

---

### Layer 3: Vector DB (Semantic Memory) - FUTURE 🚀
**What**: Embedding-based similarity search
**Purpose**: Find relevant past experiences
**TTL**: Permanent

```python
# Using Qdrant, Weaviate, or Pinecone
class SemanticMemory:
    def store_execution(self, execution):
        """Store execution with embedding."""
        embedding = self.embed(execution['goal_text'])
        
        self.vector_db.upsert(
            id=execution['execution_id'],
            vector=embedding,
            payload=execution
        )
    
    def find_similar_executions(self, goal_text, limit=5):
        """Find similar past executions."""
        query_embedding = self.embed(goal_text)
        
        results = self.vector_db.search(
            vector=query_embedding,
            limit=limit
        )
        
        return results  # Past executions that solved similar problems
```

**Use cases**:
- "We've solved something like this before..."
- Few-shot learning (show LLM similar examples)
- Caching (reuse solutions for similar goals)
- Transfer learning

---

### Layer 4: Graph DB (Causal Memory) - OVERKILL FOR NOW ⚠️
**What**: Relationships between entities
**Purpose**: Track causality, dependencies, evolution
**TTL**: Permanent

```cypher
// Neo4j example
CREATE (g:Goal {text: "Remember my name is Alice"})
CREATE (t:Tool {name: "memory_write"})
CREATE (e:Execution {id: "exec_123", success: true})
CREATE (g)-[:USED_TOOL]->(t)
CREATE (g)-[:RESULTED_IN]->(e)
CREATE (t)-[:CREATED_BY {timestamp: datetime()}]->(a:Agent)
```

**When you need it**:
- Tool evolution tracking (which tools spawned from which)
- Complex dependency analysis
- Debugging causal chains
- Research on system behavior

**For now**: PostgreSQL with JSONB can handle relationships. Use graph DB later if needed.

---

## Recommended Implementation: Start with PostgreSQL

### Why PostgreSQL First?

1. **Structured + Flexible**: SQL + JSONB for semi-structured data
2. **Battle-tested**: Reliable, mature, understood
3. **Good enough**: Handles 90% of use cases
4. **Easy to add later**: Can migrate to graph DB when needed
5. **Docker-friendly**: Add to docker-compose.yml

### Quick Implementation

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: dendrite
      POSTGRES_USER: dendrite
      POSTGRES_PASSWORD: dendrite_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

```python
# neural_engine/core/execution_store.py
import psycopg2
from psycopg2.extras import Json
import uuid
from datetime import datetime

class ExecutionStore:
    """Persistent storage for execution history."""
    
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            database="dendrite",
            user="dendrite",
            password=os.environ.get("POSTGRES_PASSWORD")
        )
    
    def store_execution(self, goal_id, goal_text, intent, tools, code, result, duration_ms):
        """Store execution for later analysis."""
        execution_id = str(uuid.uuid4())
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO executions 
                (execution_id, goal_id, goal_text, intent, selected_tools, 
                 generated_code, result, success, duration_ms, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                execution_id,
                goal_id,
                goal_text,
                intent,
                Json(tools),
                code,
                Json(result),
                not result.get('error'),
                duration_ms,
                datetime.now()
            ))
            self.conn.commit()
        
        return execution_id
    
    def get_successful_executions(self, limit=100):
        """Get recent successful executions for learning."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT goal_text, intent, selected_tools, result
                FROM executions
                WHERE success = true
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
    
    def get_tool_success_rate(self, tool_name):
        """Calculate success rate for a tool."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
                FROM tool_usage
                WHERE tool_name = %s
            """, (tool_name,))
            row = cur.fetchone()
            return row[1] / row[0] if row[0] > 0 else 0
```

---

## Use Cases Unlocked

### 1. Tool Success Tracking ✅
```python
# Which tools actually work?
store.get_tool_success_rate("memory_write")  # → 0.95 (95% success)
store.get_tool_success_rate("ai_generated_broken_tool")  # → 0.12 (12% success)

# Improve ToolForge by learning from failures
```

### 2. Few-Shot Learning ✅
```python
# Show LLM examples of similar successful executions
similar = store.find_similar_executions("Remember my name is Bob")
# → Returns: "Remember my name is Alice" → used memory_write successfully

# Add to prompt:
prompt = f"""
Here are similar goals that worked before:
{similar}

Now solve: {new_goal}
"""
```

### 3. Performance Monitoring ✅
```python
# Track system performance over time
store.get_avg_execution_time_by_intent()
# intent=tool_use: 2.5s
# intent=generative: 0.8s

# Identify bottlenecks
```

### 4. User Feedback Loop ✅
```python
# User rates execution
store.add_feedback(execution_id, rating=5, text="Perfect!")

# ToolForge learns what users like
high_rated_tools = store.get_high_rated_tools()
# Use these as examples when creating new tools
```

### 5. Failure Analysis ✅
```python
# Debug: Why did this goal fail?
failed_executions = store.get_failed_executions(
    goal_pattern="%memory%",
    last_n_days=7
)

# Common error: "Missing parameter: key"
# Fix: Update prompt to extract parameters better
```

---

## Implementation Priority

### Phase 8 (NOW): Add Basic Tracking 🎯
1. Add PostgreSQL to docker-compose
2. Create ExecutionStore class
3. Update Orchestrator to log executions
4. Query execution history for debugging

**Effort**: 2-3 hours
**Value**: HIGH - enables learning and debugging

### Phase 9 (SOON): Add Analytics Dashboard
1. Query successful patterns
2. Track tool success rates
3. Performance metrics
4. Usage analytics

**Effort**: 4-6 hours
**Value**: MEDIUM - nice visibility

### Phase 10+ (LATER): Add Semantic Search
1. Generate embeddings for goals
2. Store in vector DB
3. Find similar past executions
4. Use for few-shot prompting

**Effort**: 1-2 days
**Value**: HIGH - enables true learning

### Maybe Never: Graph DB
Only if you need:
- Complex causal analysis
- Tool evolution tracking over generations
- Research on emergent behavior

**Effort**: 2-3 days
**Value**: LOW unless doing research

---

## My Recommendation

**For Fractal Architecture (Phase 8-10)**:

1. **Add PostgreSQL NOW** - We'll need execution history for self-monitoring
2. **Keep Redis** - Still use for ephemeral pipeline state
3. **Skip Graph DB** - PostgreSQL JSON is sufficient
4. **Add Vector DB Later** - When you have 1000+ executions to learn from

**This gives you**:
- Redis: Pipeline coordination (current)
- PostgreSQL: Long-term memory (new)
- File system: Tool storage (current)
- Vector DB: Semantic search (future)

**Keeps it simple but enables**:
- Neurons can query past executions
- System learns from experience
- Performance monitoring
- Failure analysis
- User feedback integration

---

---

# ADDENDUM: Scaling to Thousands of Tools

## The REAL Problem: Tool Discovery at Scale

### Question: "How would AI know which tool to pick without cluttering small LLM context?"

**Current approach** (works for ~10 tools):
```python
all_tools = registry.get_all_tool_definitions()  # Send ALL to LLM
prompt = f"Tools: {all_tools}\nGoal: {goal}"
```

**Breaks at**: 100+ tools (context window overflow)

### Solution: 3-Stage Tool Discovery 🎯

#### Stage 1: Semantic Search (1000 → 20 tools) ⚡
**Method**: Vector embeddings + similarity search
**Performance**: 10-50ms
**Tool**: Chroma (embedded vector DB)

```python
class ToolDiscovery:
    def search_tools(self, goal, top_k=20):
        """Semantic search: Find 20 relevant candidates from 1000 tools."""
        goal_embedding = self.embed(goal)  # Use Ollama embeddings
        
        results = self.chroma_collection.query(
            query_embeddings=[goal_embedding],
            n_results=top_k
        )
        
        return results['metadatas'][0]  # 20 candidates
```

#### Stage 2: Statistical Ranking (20 → 5 tools) 📊
**Method**: Historical success data
**Performance**: ~100ms
**Tool**: PostgreSQL queries

```python
class ToolRanker:
    def rank_tools(self, candidates, goal):
        """Rank by: success rate + usage count + similar goal success."""
        scored = []
        for tool in candidates:
            score = (
                self.get_success_rate(tool) * 0.3 +
                self.get_usage_frequency(tool) * 0.2 +
                self.get_recency_score(tool) * 0.2 +
                self.get_similar_goal_success(tool, goal) * 0.3
            )
            scored.append((tool, score))
        
        return sorted(scored, key=lambda x: x[1], reverse=True)[:5]
```

#### Stage 3: LLM Selection (5 → 1 tool) 🤖
**Method**: Existing ToolSelectorNeuron
**Performance**: ~500ms
**Context**: Only 5 tools (efficient!)

```python
# LLM sees only 5 highly relevant tools
top_5_tools = ranking_stage_output
prompt = f"Goal: {goal}\n\nTop 5 tools: {top_5_tools}\n\nPick best one."
```

**Total time**: ~600ms even with 1000 tools! ✅

---

## Updated Technology Stack

### Why PostgreSQL (not MySQL)?
1. **Better JSON**: JSONB faster than MySQL JSON
2. **pgvector**: Native vector similarity search
3. **Better analytics**: Window functions, CTEs, mature
4. **Truly open source**: MySQL owned by Oracle
5. **Battle-tested**: Powers massive systems

### Why Not Graph DB?
- **Overkill**: Tool relationships aren't complex enough
- **PostgreSQL JSONB**: Can store relationships
- **Adds complexity**: Without clear benefit
- **Use later**: Only if you need complex graph queries

### Recommended Stack:

```yaml
services:
  redis:          # Short-term pipeline state (hours)
  postgres:       # Long-term analytics & history (forever)
  # Chroma:       # Embedded! No separate service needed
```

**Storage responsibilities**:
- **Chroma** (embedded): Tool embeddings for semantic search (~1MB for 1000 tools)
- **PostgreSQL**: Execution history, success rates, user feedback
- **Redis**: Current pipeline state (ephemeral)
- **Filesystem**: Tool code (Git-tracked)

---

## Persistence Strategy

### Tier 1: Forever (PostgreSQL)
- Tool execution history
- Success/failure rates
- User feedback
- Performance metrics

### Tier 2: Medium-term (30-90 days)
- Goal embeddings
- Generated code samples
- Detailed execution traces

### Tier 3: Short-term (hours - Redis)
- Pipeline state
- Inter-neuron messages
- Temporary results

### Tier 4: Ephemeral (in-memory)
- Tool registry cache
- Loaded tool instances

---

## Learning Strategy

### Real-time Learning (After Every Execution)
```python
def after_execution(execution_result):
    # 1. Store execution (PostgreSQL)
    store.save_execution(execution_result)
    
    # 2. Update tool statistics
    store.increment_tool_usage(tool_name)
    if success:
        store.increment_tool_success(tool_name)
    
    # 3. Index new tools (Chroma)
    if new_tool_created:
        discovery.index_tool(tool_name, definition)
    
    # 4. Detect low-quality tools
    if success_rate < 0.3:
        mark_for_review(tool_name)
```

### Batch Learning (Daily Maintenance)
```python
def daily_maintenance():
    # 1. Recalculate tool rankings
    # 2. Archive old executions (90+ days)
    # 3. Update embeddings
    # 4. Generate performance reports
    # 5. Cleanup low-quality tools
```

---

## Implementation Timeline

### Phase 8a: PostgreSQL (2 hours)
- Add to docker-compose
- Create ExecutionStore class
- Log executions in Orchestrator
- Test queries

### Phase 8b: Chroma Discovery (3 hours)
- Add chromadb dependency
- Create ToolDiscovery class
- Index existing tools
- Update ToolSelectorNeuron with 3-stage filtering

### Phase 8c: Learning Loop (2 hours)
- Create LearningLoop class
- Hook into post-execution
- Add daily maintenance task

**Total**: ~7 hours for production-ready scaling architecture

---

## Next Steps

Want me to:
1. **Implement PostgreSQL + Chroma** (7 hours work, let's start!) 🎯
2. **Just PostgreSQL** (2 hours) - Add Chroma later
3. **Skip to Fractal** - Add scaling later

I recommend option 1 - You asked the right questions. This architecture will scale to 10,000+ tools!
