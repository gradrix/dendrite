# Tool Storage & Persistence Strategy

## The Tool Storage Dilemma

### Question: Should AI-generated tools be committed to Git?

**Short Answer**: It depends on your workflow, but I recommend **selective commits with review**.

---

## Strategy Options

### Option 1: Commit Everything (Simple) ✅ RECOMMENDED for MVP
**Pros**:
- Full audit trail
- Easy rollback
- Works with existing bind mount
- No additional infrastructure
- Can review in PR/commits

**Cons**:
- Repo grows over time
- May commit junk/experimental tools
- Git history cluttered

**When to use**: Early stages, learning phase, want full control

**Implementation**:
```bash
# Currently working - no changes needed!
# Tools in neural_engine/tools/ are already in repo
# Bind mount means: container writes → host sees → git tracks
```

---

### Option 2: Gitignore AI Tools, Use Artifact Storage 🎯 RECOMMENDED for Production
**Pros**:
- Repo stays clean
- Admin tools in Git, AI tools in storage
- Can implement versioning/lifecycle policies
- Separate concerns (code vs. generated artifacts)

**Cons**:
- Need additional storage system
- More complexity
- Need tool sync mechanism

**When to use**: Production, many tools, want clean repo

**Implementation**:
```gitignore
# .gitignore
neural_engine/tools/*_ai_generated_*.py
neural_engine/tools/ai_tools/

# Keep admin tools
!neural_engine/tools/hello_world_tool.py
!neural_engine/tools/memory_*.py
!neural_engine/tools/base_tool.py
```

```python
# Tool naming convention
class MyAiGeneratedTool(BaseTool):  # Add marker in name
    """AI-generated on 2025-10-28"""
    ...
```

---

### Option 3: Hybrid (Best of Both) 🌟 RECOMMENDED Long-Term
**Split tools by quality/stability**:
- `neural_engine/tools/core/` → Admin tools, committed
- `neural_engine/tools/experimental/` → AI tools, gitignored initially
- `neural_engine/tools/approved/` → AI tools promoted after testing, committed

**Workflow**:
1. AI creates tool → goes to `experimental/`
2. Tool proves useful → human reviews → promotes to `approved/` → commits
3. Stable approved tools → move to `core/`

**Implementation**:
```python
# Update ToolRegistry to scan multiple directories
class ToolRegistry:
    def __init__(self):
        self.tool_directories = [
            "neural_engine/tools/core",       # Admin tools
            "neural_engine/tools/approved",   # Vetted AI tools
            "neural_engine/tools/experimental"  # AI-generated, may be temporary
        ]
```

```gitignore
# Gitignore experimental AI tools
neural_engine/tools/experimental/

# Commit approved/core tools
!neural_engine/tools/core/
!neural_engine/tools/approved/
```

---

## Tool Lifecycle Management

### Concern: "Wouldn't there be too many tools?"

**Yes, eventually!** Here's how to manage:

### 1. Tool Garbage Collection
```python
class ToolLifecycleManager:
    def cleanup_unused_tools(self, days_unused=30):
        """Remove tools that haven't been used in X days."""
        for tool_name, metadata in self.tool_usage_tracking.items():
            last_used = metadata['last_used']
            if (datetime.now() - last_used).days > days_unused:
                # Archive or delete
                self.archive_tool(tool_name)
```

### 2. Tool Usage Tracking
```python
# In MessageBus or ToolRegistry
class ToolUsageTracker:
    def track_tool_execution(self, tool_name, result):
        """Track which tools are actually useful."""
        self.redis.hincrby("tool_usage", tool_name, 1)
        self.redis.hset(f"tool_last_used:{tool_name}", "timestamp", time.time())
        self.redis.hset(f"tool_success_rate:{tool_name}", "total", 1)
        if result.get("error"):
            self.redis.hincrb(f"tool_success_rate:{tool_name}", "errors", 1)
```

### 3. Tool Quality Scoring
```python
class ToolQualityAnalyzer:
    def score_tool(self, tool_name):
        """Score tool based on usage, success rate, execution time."""
        usage_count = self.get_usage_count(tool_name)
        success_rate = self.get_success_rate(tool_name)
        avg_execution_time = self.get_avg_execution_time(tool_name)
        
        score = (usage_count * 0.4) + (success_rate * 0.4) + (speed_score * 0.2)
        return score
    
    def get_low_quality_tools(self, threshold=0.3):
        """Find tools to deprecate."""
        return [tool for tool in self.all_tools if self.score_tool(tool) < threshold]
```

### 4. Tool Deduplication
```python
class ToolDeduplicator:
    def find_similar_tools(self, tool_name):
        """Find tools with similar functionality."""
        # Use LLM to compare tool descriptions
        # Or use embedding similarity
        tool_def = self.registry.get_tool_definition(tool_name)
        similar = []
        for other_name, other_def in self.registry.get_all_tool_definitions().items():
            similarity = self.compare_descriptions(tool_def['description'], other_def['description'])
            if similarity > 0.8:
                similar.append(other_name)
        return similar
```

---

## My Recommendation for Your Project

**Phase 7 (Current)**: Option 1 - Commit everything
- You're in learning/development phase
- Want full visibility
- Easy rollback
- ~10-50 tools is fine

**Phase 8-9 (Near Future)**: Implement tracking
- Add tool usage metrics
- Track success rates
- See which tools are valuable

**Phase 10+ (Production)**: Option 3 - Hybrid
- Separate experimental from approved
- Implement lifecycle management
- Archive/delete unused tools
- Keep repo clean

---

## Quick Implementation: Add Tool Metadata

Update ToolForge to add tracking metadata:

```python
# In tool_forge_neuron.py
def _write_tool_file(self, code: str, filename: str) -> str:
    """Write tool with metadata header."""
    metadata = f'''"""
AI-Generated Tool
Created: {datetime.now().isoformat()}
Generator: ToolForge v1.0
Status: Experimental
"""

'''
    
    full_code = metadata + code
    
    filepath = os.path.join(self.tools_directory, filename)
    with open(filepath, 'w') as f:
        f.write(full_code)
    
    return filepath
```

---

## Storage Estimates

### Current State:
- Admin tools: ~10 files, ~50KB total
- Each AI tool: ~1-5KB
- 100 AI tools: ~500KB
- 1000 AI tools: ~5MB

**Git can handle this easily.** Only becomes a problem at 10,000+ tools.

### If You Need External Storage Later:

**Option A: S3/Object Storage**
```python
class ToolStorage:
    def save_tool(self, tool_name, code):
        s3.put_object(
            Bucket='my-ai-tools',
            Key=f'tools/{tool_name}.py',
            Body=code
        )
```

**Option B: Database**
```sql
CREATE TABLE ai_tools (
    tool_name VARCHAR PRIMARY KEY,
    code TEXT,
    created_at TIMESTAMP,
    last_used TIMESTAMP,
    usage_count INTEGER,
    success_rate FLOAT
);
```

**Option C: Keep Filesystem, Add Metadata DB**
```python
# Tools on disk (fast loading)
# Metadata in DB (tracking, scoring)
```

---

## Current Architecture is FINE ✅

**For now**:
- Keep tools in Git
- Watch repo size
- When it becomes a problem (~1000 tools), implement Option 3

**The bind mount is perfect**:
- AI writes to container → appears on host → Git sees it
- No rebuild needed
- Human can review/edit
- Version controlled

**Recommendation**: Don't overcomplicate yet. Build fractal architecture, THEN add tool lifecycle management when you actually have tool proliferation problems.

---

## Next: Fractal Architecture

Ready to tackle the orchestration evolution? Or want to implement basic tool tracking first?
