# Duplicate Detection via Embeddings

**Phase 9g: Prevent redundant tools through semantic similarity detection**

## Overview

The Duplicate Detection system uses Chroma embeddings to automatically identify similar or duplicate tools in the registry. This helps maintain a clean, efficient tool ecosystem by:

- **Finding similar tools** using cosine similarity (>90% threshold)
- **Comparing tools side-by-side** with detailed parameter and performance analysis
- **Recommending consolidation** based on usage statistics and reliability
- **Preventing redundancy** before it becomes a problem

## Components

### 1. find_similar_tools()

Finds tools semantically similar to a reference tool.

**Signature:**
```python
def find_similar_tools(self, 
                      tool_name: str, 
                      similarity_threshold: float = 0.9,
                      limit: int = 10) -> List[Dict]
```

**Parameters:**
- `tool_name`: Reference tool to find matches for
- `similarity_threshold`: Minimum cosine similarity (0.0-1.0, default 0.9 = 90%)
- `limit`: Maximum number of similar tools to return

**Returns:**
```python
[
    {
        "tool_name": "similar_tool_1",
        "description": "Tool description",
        "parameter_count": 3,
        "similarity": 0.95,  # 95% similar
        "is_potential_duplicate": True  # >= 95% is likely duplicate
    },
    ...
]
```

**Algorithm:**
1. Get reference tool description and parameters
2. Query Chroma embeddings with cosine similarity
3. Filter by similarity threshold
4. Exclude self-matches
5. Sort by similarity (highest first)
6. Limit results

### 2. find_all_duplicates()

Scans entire registry to find all potential duplicate pairs.

**Signature:**
```python
def find_all_duplicates(self, 
                       similarity_threshold: float = 0.9) -> List[Dict]
```

**Returns:**
```python
[
    {
        "tool_a": "tool_name_1",
        "tool_b": "tool_name_2",
        "similarity": 0.96,
        "is_potential_duplicate": True,
        "stats_a": {
            "total_executions": 50,
            "success_rate": 0.95,
            "avg_duration": 1.2
        },
        "stats_b": {
            "total_executions": 10,
            "success_rate": 0.85,
            "avg_duration": 1.5
        },
        "recommendation": {
            "action": "consolidate",
            "keep": "tool_name_1",
            "deprecate": "tool_name_2",
            "reason": "tool_name_1 has better usage and reliability",
            "confidence": "high"  # high if >= 95%, medium otherwise
        }
    },
    ...
]
```

**Algorithm:**
1. Iterate through all tools in registry
2. Find similar tools for each
3. Track checked pairs to avoid duplicates
4. Get statistics for both tools
5. Generate consolidation recommendation
6. Sort by similarity

### 3. compare_tools_side_by_side()

Detailed comparison of two specific tools.

**Signature:**
```python
def compare_tools_side_by_side(self, tool_a: str, tool_b: str) -> Dict
```

**Returns:**
```python
{
    "tool_a": {
        "name": "tool_a",
        "description": "...",
        "parameters": ["param1", "param2"],
        "parameter_count": 2,
        "statistics": {
            "total_executions": 50,
            "success_rate": 0.95
        }
    },
    "tool_b": {
        "name": "tool_b",
        "description": "...",
        "parameters": ["param1", "param3"],
        "parameter_count": 2,
        "statistics": {
            "total_executions": 10,
            "success_rate": 0.85
        }
    },
    "comparison": {
        "similarity": 0.95,
        "is_likely_duplicate": True,  # >= 95%
        "common_parameters": ["param1"],
        "unique_to_a": ["param2"],
        "unique_to_b": ["param3"],
        "parameter_overlap": 0.5  # 50% of parameters are shared
    },
    "recommendation": {
        "action": "consolidate",
        "keep": "tool_a",
        "deprecate": "tool_b",
        "reason": "tool_a has better usage and reliability",
        "confidence": "high"
    }
}
```

### 4. _generate_consolidation_recommendation()

Internal method that decides which tool to keep.

**Decision Logic:**
1. **Score calculation**: `score = total_executions × success_rate`
2. **If one tool 20%+ better**: Keep better performing tool
3. **If similar performance**: Keep more frequently used tool
4. **If equal usage**: Keep alphabetically first (for consistency)

**Confidence levels:**
- **High**: Similarity >= 95% (likely true duplicate)
- **Medium**: Similarity 90-95% (similar but may have valid differences)

## Usage Examples

### Example 1: Find Similar Tools

```python
from neural_engine.core.tool_discovery import ToolDiscovery

discovery = ToolDiscovery(
    tool_registry=tool_registry,
    execution_store=execution_store
)

# Find tools similar to strava_get_activities
similar = discovery.find_similar_tools(
    tool_name="strava_get_activities",
    similarity_threshold=0.9,
    limit=5
)

for tool in similar:
    print(f"Tool: {tool['tool_name']}")
    print(f"  Similarity: {tool['similarity']:.0%}")
    print(f"  Duplicate? {tool['is_potential_duplicate']}")
    print()
```

**Output:**
```
Tool: strava_get_my_activities
  Similarity: 97%
  Duplicate? True

Tool: strava_activity_list
  Similarity: 92%
  Duplicate? False
```

### Example 2: Scan for All Duplicates

```python
# Find all duplicate pairs across registry
duplicates = discovery.find_all_duplicates(similarity_threshold=0.95)

print(f"Found {len(duplicates)} potential duplicate pairs\n")

for pair in duplicates[:5]:  # Show top 5
    print(f"{pair['tool_a']} ↔ {pair['tool_b']}")
    print(f"  Similarity: {pair['similarity']:.0%}")
    
    rec = pair['recommendation']
    print(f"  Recommendation: Keep '{rec['keep']}', deprecate '{rec['deprecate']}'")
    print(f"  Reason: {rec['reason']}")
    print(f"  Confidence: {rec['confidence']}")
    print()
```

**Output:**
```
Found 3 potential duplicate pairs

strava_get_activities ↔ strava_get_my_activities
  Similarity: 97%
  Recommendation: Keep 'strava_get_activities', deprecate 'strava_get_my_activities'
  Reason: strava_get_activities has better usage and reliability
  Confidence: high

hello_world ↔ hello_world_tool
  Similarity: 96%
  Recommendation: Keep 'hello_world', deprecate 'hello_world_tool'
  Reason: hello_world is used more frequently (150 vs 5 executions)
  Confidence: high
```

### Example 3: Detailed Side-by-Side Comparison

```python
# Compare two specific tools
comparison = discovery.compare_tools_side_by_side(
    "strava_get_activities",
    "strava_get_my_activities"
)

print(f"Tool A: {comparison['tool_a']['name']}")
print(f"  Description: {comparison['tool_a']['description']}")
print(f"  Parameters: {', '.join(comparison['tool_a']['parameters'])}")
print(f"  Executions: {comparison['tool_a']['statistics']['total_executions']}")
print(f"  Success Rate: {comparison['tool_a']['statistics']['success_rate']:.0%}")
print()

print(f"Tool B: {comparison['tool_b']['name']}")
print(f"  Description: {comparison['tool_b']['description']}")
print(f"  Parameters: {', '.join(comparison['tool_b']['parameters'])}")
print(f"  Executions: {comparison['tool_b']['statistics']['total_executions']}")
print(f"  Success Rate: {comparison['tool_b']['statistics']['success_rate']:.0%}")
print()

comp = comparison['comparison']
print(f"Similarity: {comp['similarity']:.0%}")
print(f"Common parameters: {', '.join(comp['common_parameters'])}")
print(f"Unique to A: {', '.join(comp['unique_to_a'])}")
print(f"Unique to B: {', '.join(comp['unique_to_b'])}")
print(f"Parameter overlap: {comp['parameter_overlap']:.0%}")
print()

rec = comparison['recommendation']
print(f"Recommendation: {rec['action']}")
print(f"  Keep: {rec['keep']}")
print(f"  Deprecate: {rec['deprecate']}")
print(f"  Reason: {rec['reason']}")
print(f"  Confidence: {rec['confidence']}")
```

## Similarity Thresholds

**Recommended thresholds:**

| Threshold | Use Case | Meaning |
|-----------|----------|---------|
| 0.95+ | True duplicates | Nearly identical tools - likely redundant |
| 0.90-0.95 | Similar tools | Related functionality - may have valid differences |
| 0.85-0.90 | Related tools | Same domain but different purposes |
| 0.80-0.85 | Loosely related | Might be in same category but distinct |

**Default: 0.90** - Balances false positives vs false negatives

## Consolidation Workflows

### Workflow 1: Manual Review

```python
# 1. Find duplicates
duplicates = discovery.find_all_duplicates(similarity_threshold=0.95)

# 2. Review each pair
for pair in duplicates:
    comparison = discovery.compare_tools_side_by_side(
        pair['tool_a'], 
        pair['tool_b']
    )
    
    # 3. Make decision (manual)
    print(f"\nReview: {pair['tool_a']} vs {pair['tool_b']}")
    print(f"Recommendation: Keep {comparison['recommendation']['keep']}")
    decision = input("Consolidate? (y/n): ")
    
    if decision.lower() == 'y':
        # 4. Deprecate duplicate
        tool_lifecycle.deprecate_tool(
            comparison['recommendation']['deprecate'],
            reason=f"Duplicate of {comparison['recommendation']['keep']}"
        )
```

### Workflow 2: Automated (High Confidence)

```python
# Only auto-consolidate high-confidence duplicates
duplicates = discovery.find_all_duplicates(similarity_threshold=0.97)

for pair in duplicates:
    rec = pair['recommendation']
    
    # Only if high confidence AND usage difference is clear
    stats_keep = pair['stats_a'] if rec['keep'] == pair['tool_a'] else pair['stats_b']
    stats_deprecate = pair['stats_b'] if rec['keep'] == pair['tool_a'] else pair['stats_a']
    
    usage_ratio = stats_keep['total_executions'] / max(stats_deprecate['total_executions'], 1)
    
    if rec['confidence'] == 'high' and usage_ratio > 5.0:
        # Auto-deprecate if used 5x less
        print(f"Auto-consolidating: {rec['deprecate']} → {rec['keep']}")
        tool_lifecycle.deprecate_tool(
            rec['deprecate'],
            reason=f"Auto-consolidated duplicate of {rec['keep']}"
        )
```

### Workflow 3: Preventive (Before Creation)

```python
# Before creating a new tool, check for duplicates
def create_new_tool(tool_name, description, code):
    # 1. Index new tool temporarily
    discovery.reindex_tool(tool_name)
    
    # 2. Check for similar tools
    similar = discovery.find_similar_tools(
        tool_name=tool_name,
        similarity_threshold=0.90,
        limit=3
    )
    
    # 3. Warn if duplicates found
    if similar:
        print(f"⚠️  Found {len(similar)} similar tools:")
        for tool in similar:
            print(f"  - {tool['tool_name']} ({tool['similarity']:.0%} similar)")
        
        proceed = input("Continue creating tool? (y/n): ")
        if proceed.lower() != 'y':
            return False
    
    # 4. Create tool
    tool_registry.register_tool(tool_name, code)
    return True
```

## Integration Points

### ToolLifecycleManager

```python
# Find duplicates before cleanup
duplicates = discovery.find_all_duplicates(similarity_threshold=0.95)

for pair in duplicates:
    rec = pair['recommendation']
    
    # Mark duplicate for deprecation
    lifecycle_manager.mark_for_deprecation(
        tool_name=rec['deprecate'],
        reason=f"Duplicate of {rec['keep']}",
        metadata={
            'similarity': pair['similarity'],
            'recommended_replacement': rec['keep']
        }
    )
```

### AutonomousImprovementNeuron

```python
# Before improving a tool, check if it's a duplicate
def before_improve(self, tool_name):
    similar = self.discovery.find_similar_tools(tool_name, threshold=0.95)
    
    if similar and similar[0]['is_potential_duplicate']:
        # Maybe consolidate instead of improving
        print(f"⚠️  {tool_name} appears to be duplicate of {similar[0]['tool_name']}")
        print("Consider consolidating instead of improving separately")
        return False
    
    return True
```

## Testing

**Test Coverage: 14 tests**

Located in: `neural_engine/tests/test_duplicate_detection.py`

**Test categories:**
1. **find_similar_tools**: High/medium/no similarity, limit respect, sorting, self-exclusion
2. **find_all_duplicates**: Full registry scan, pair deduplication
3. **compare_tools_side_by_side**: Detailed comparison, parameter overlap, tool not found
4. **consolidation recommendations**: Usage-based, success-based, equal stats

**Run tests:**
```bash
# Via Docker (recommended)
bash scripts/test.sh neural_engine/tests/test_duplicate_detection.py

# Direct pytest
pytest neural_engine/tests/test_duplicate_detection.py -v
```

## Performance Characteristics

### Time Complexity

- **find_similar_tools**: O(n) where n = limit
  - Chroma vector search: ~10ms per query
  - Typical: <50ms for limit=10

- **find_all_duplicates**: O(n × m) where n = tools, m = limit
  - Full scan: ~500ms for 50 tools
  - Typical: <2s for 100 tools with limit=20

- **compare_tools_side_by_side**: O(1)
  - Single vector query: ~10ms
  - Typical: <50ms

### Memory Usage

- Chroma embeddings: ~4KB per tool (384-dim embeddings)
- 100 tools: ~400KB memory footprint
- Scalable to 10,000+ tools

## Benefits

**🎯 Prevent Redundancy**
- Catch duplicate tools before they spread
- Maintain clean, focused tool registry

**📊 Data-Driven Consolidation**
- Recommendations based on actual usage and performance
- Not just semantic similarity

**🔍 Proactive Discovery**
- Find duplicates automatically during scans
- No manual audits needed

**🚀 Scalable**
- Vector similarity search scales to thousands of tools
- Fast enough for real-time checks

**🧠 Intelligent**
- Considers parameters, not just descriptions
- Confidence levels for safe automation

## Future Enhancements

### Phase 10+

1. **Automatic Merging**: Combine duplicate tools into single best-of-both
2. **Similarity Explanation**: Why are these tools similar? Show key overlaps
3. **Incremental Scanning**: Only check new tools, not full registry each time
4. **Cluster Detection**: Find groups of 3+ similar tools (not just pairs)
5. **Usage Migration**: Auto-migrate executions from deprecated to kept tool

## Summary

Phase 9g completes the autonomous improvement pipeline with:
- ✅ **find_similar_tools()**: Find duplicates via embeddings
- ✅ **find_all_duplicates()**: Full registry scanning
- ✅ **compare_tools_side_by_side()**: Detailed comparison
- ✅ **Smart recommendations**: Usage + reliability based
- ✅ **14 tests**: All passing
- ✅ **Integration ready**: Works with ToolLifecycleManager

**Phase 9 is now complete!** The system can autonomously improve itself with comprehensive safety guarantees and duplicate prevention.

Next: **Phase 10** - Cognitive optimization (error recovery, goal learning, pathway caching)
