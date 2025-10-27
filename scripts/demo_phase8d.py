"""
Demo script for Phase 8d: Tool Discovery with Semantic Search.
Demonstrates 3-stage filtering: Semantic → Ranking → LLM (Stage 3 in ToolSelectorNeuron).
"""

from neural_engine.core.tool_discovery import ToolDiscovery
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore


def print_section(title):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def main():
    print_section("Phase 8d: Tool Discovery with Semantic Search")
    
    # Initialize components
    print("\n1. Initializing components...")
    tool_registry = ToolRegistry()
    execution_store = ExecutionStore()
    discovery = ToolDiscovery(
        tool_registry=tool_registry,
        execution_store=execution_store,
        chroma_path="/tmp/chroma_test"
    )
    print(f"   ✓ Tool registry loaded: {len(tool_registry.get_all_tools())} tools")
    print("   ✓ Semantic search engine initialized")
    
    # Index all tools
    print_section("Indexing Tools for Semantic Search")
    count = discovery.index_all_tools()
    print(f"   ✓ Indexed {count} tools with embeddings")
    
    # Check index stats
    print_section("Index Statistics")
    stats = discovery.get_index_stats()
    print(f"   Indexed tools: {stats['indexed_tools']}")
    print(f"   Registry tools: {stats['registry_tools']}")
    print(f"   Coverage: {stats['coverage']:.1%}")
    if stats['not_indexed']:
        print(f"   Not indexed: {stats['not_indexed']}")
    if stats['stale_indexed']:
        print(f"   Stale: {stats['stale_indexed']}")
    
    # Test semantic search
    print_section("Stage 1: Semantic Search")
    test_queries = [
        "Check if a number is prime",
        "Get my Strava activities",
        "Say hello to the user",
        "Calculate the sum of two numbers"
    ]
    
    for query in test_queries:
        print(f"\n   Query: '{query}'")
        candidates = discovery.semantic_search(query, n_results=5)
        print(f"   Candidates ({len(candidates)}):")
        for i, tool_name in enumerate(candidates, 1):
            print(f"     {i}. {tool_name}")
    
    # Test statistical ranking
    print_section("Stage 2: Statistical Ranking")
    query = "Check if a number is prime"
    print(f"   Query: '{query}'")
    
    # Get semantic candidates
    candidates = discovery.semantic_search(query, n_results=10)
    print(f"   Semantic candidates: {len(candidates)} tools")
    
    # Rank by statistics
    ranked = discovery.statistical_ranking(candidates, limit=5)
    print(f"\n   Top 5 ranked tools:")
    for i, tool in enumerate(ranked, 1):
        if tool['success_rate'] is not None:
            print(f"     {i}. {tool['tool_name']}")
            print(f"        Score: {tool['score']:.3f}")
            print(f"        Success rate: {tool['success_rate']:.1%}")
            print(f"        Executions: {tool['executions']}")
            print(f"        Recency factor: {tool['recency_factor']:.2f}")
        else:
            print(f"     {i}. {tool['tool_name']}")
            print(f"        Score: {tool['score']:.3f} (new tool, no stats yet)")
    
    # Complete discovery pipeline
    print_section("Complete Discovery Pipeline (Stages 1+2)")
    test_goals = [
        "I want to check if 17 is a prime number",
        "Show me my recent Strava activities",
        "Add two numbers: 42 and 58"
    ]
    
    for goal in test_goals:
        print(f"\n   Goal: '{goal}'")
        discovered = discovery.discover_tools(goal, semantic_limit=10, ranking_limit=3)
        print(f"   Discovered {len(discovered)} tools:")
        for i, tool in enumerate(discovered, 1):
            print(f"     {i}. {tool['tool_name']} (score: {tool['score']:.3f})")
    
    # Test search by description
    print_section("Search by Description (UI Feature)")
    search_queries = ["strava", "calculate", "hello"]
    
    for query in search_queries:
        print(f"\n   Search: '{query}'")
        results = discovery.search_by_description(query, limit=3)
        for i, tool in enumerate(results, 1):
            print(f"     {i}. {tool['tool_name']}")
            print(f"        Description: {tool['description']}")
            print(f"        Relevance: {tool['relevance']:.2f}")
    
    # Test index sync
    print_section("Index Synchronization")
    discovery.sync_index()
    
    # Final stats
    print_section("Summary")
    final_stats = discovery.get_index_stats()
    print(f"   ✓ Phase 8d: Tool Discovery operational")
    print(f"   ✓ Indexed {final_stats['indexed_tools']} tools")
    print(f"   ✓ 3-stage filtering ready:")
    print(f"      1. Semantic Search (Chroma) - O(log n) speed")
    print(f"      2. Statistical Ranking (PostgreSQL) - Performance-based")
    print(f"      3. LLM Selection (ToolSelectorNeuron) - Context-aware")
    print(f"\n   System can scale to thousands of tools efficiently!")
    print("=" * 80)
    
    # Cleanup
    discovery.close()


if __name__ == "__main__":
    main()
