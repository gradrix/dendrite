"""
Tests for PatternCache - Dynamic pattern learning and retrieval.
"""

import pytest
import os
import json
import tempfile
from neural_engine.core.pattern_cache import PatternCache


@pytest.fixture
def temp_cache_file():
    """Create temporary cache file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        cache_file = f.name
    yield cache_file
    # Cleanup
    if os.path.exists(cache_file):
        os.remove(cache_file)


@pytest.fixture
def pattern_cache(temp_cache_file):
    """Provide a PatternCache instance for testing."""
    return PatternCache(cache_file=temp_cache_file)


class TestPatternCacheBasics:
    """Test basic pattern cache functionality."""
    
    def test_cache_initialization(self, pattern_cache):
        """Cache should initialize with empty patterns."""
        assert len(pattern_cache.patterns) == 0
        assert pattern_cache.embedder is not None
        print("✓ Cache initialized")
    
    def test_store_new_pattern(self, pattern_cache):
        """Should store new pattern."""
        query = "Say hello"
        decision = {"intent": "generative"}
        
        pattern_cache.store(query, decision, confidence=0.9)
        
        assert len(pattern_cache.patterns) == 1
        assert pattern_cache.patterns[0]["query"] == query
        assert pattern_cache.patterns[0]["decision"] == decision
        assert pattern_cache.patterns[0]["confidence"] == 0.9
        assert pattern_cache.patterns[0]["usage_count"] == 1
        print("✓ Pattern stored")
    
    def test_lookup_exact_match(self, pattern_cache):
        """Should find exact match with high confidence."""
        query = "Say hello"
        decision = {"intent": "generative"}
        
        # Store pattern
        pattern_cache.store(query, decision, confidence=0.9)
        
        # Lookup same query
        found_decision, confidence = pattern_cache.lookup(query, threshold=0.85)
        
        assert found_decision is not None
        assert found_decision["intent"] == "generative"
        assert confidence > 0.89  # Should be at least base confidence
        print(f"✓ Exact match found (confidence: {confidence:.2f})")
    
    def test_lookup_similar_match(self, pattern_cache):
        """Should find similar patterns."""
        # Store pattern
        pattern_cache.store("Say hello", {"intent": "generative"}, confidence=0.9)
        
        # Lookup similar query
        found_decision, confidence = pattern_cache.lookup("Tell me hello", threshold=0.70)
        
        # Similar queries should match with lower confidence
        assert found_decision is not None
        assert found_decision["intent"] == "generative"
        print(f"✓ Similar match found (confidence: {confidence:.2f})")
    
    def test_lookup_miss(self, pattern_cache):
        """Should return None for dissimilar queries."""
        # Store pattern
        pattern_cache.store("Say hello", {"intent": "generative"}, confidence=0.9)
        
        # Lookup very different query
        found_decision, confidence = pattern_cache.lookup("Calculate prime numbers", threshold=0.85)
        
        assert found_decision is None
        assert confidence == 0.0
        print("✓ Miss handled correctly")
    
    def test_usage_count_boosts_confidence(self, pattern_cache):
        """Patterns used more should have higher confidence."""
        query = "Say hello"
        decision = {"intent": "generative"}
        
        pattern_cache.store(query, decision, confidence=0.8)
        
        # First lookup
        _, conf1 = pattern_cache.lookup(query)
        
        # Second lookup (usage count increased)
        _, conf2 = pattern_cache.lookup(query)
        
        # Third lookup
        _, conf3 = pattern_cache.lookup(query)
        
        # Confidence should increase with usage
        assert conf2 > conf1
        assert conf3 > conf2
        print(f"✓ Confidence progression: {conf1:.3f} → {conf2:.3f} → {conf3:.3f}")


class TestPatternCacheDuplicates:
    """Test duplicate pattern handling."""
    
    def test_very_similar_patterns_merged(self, pattern_cache):
        """Very similar patterns should update existing, not create new."""
        # Store first pattern
        pattern_cache.store("Say hello", {"intent": "generative"}, confidence=0.8)
        
        # Store very similar pattern
        pattern_cache.store("Say hello!", {"intent": "generative"}, confidence=0.9)
        
        # Should only have one pattern (merged)
        assert len(pattern_cache.patterns) == 1
        # Should keep higher confidence
        assert pattern_cache.patterns[0]["confidence"] == 0.9
        # Usage count should be 2
        assert pattern_cache.patterns[0]["usage_count"] == 2
        print("✓ Similar patterns merged")
    
    def test_different_patterns_stored_separately(self, pattern_cache):
        """Different patterns should be stored separately."""
        pattern_cache.store("Say hello", {"intent": "generative"}, confidence=0.9)
        pattern_cache.store("Calculate 2+2", {"intent": "tool_use"}, confidence=0.9)
        
        assert len(pattern_cache.patterns) == 2
        print("✓ Different patterns stored separately")


class TestPatternCacheSimilarExamples:
    """Test retrieval of similar examples for prompts."""
    
    def test_get_similar_examples(self, pattern_cache):
        """Should return k most similar examples."""
        # Store several patterns
        patterns = [
            ("Say hello", {"intent": "generative"}),
            ("Tell me hi", {"intent": "generative"}),
            ("Calculate sum", {"intent": "tool_use"}),
            ("Add numbers", {"intent": "tool_use"}),
        ]
        
        for query, decision in patterns:
            pattern_cache.store(query, decision, confidence=0.9)
        
        # Get similar to "Greet me"
        examples = pattern_cache.get_similar_examples("Greet me", k=2)
        
        assert len(examples) <= 2
        # Should prioritize greeting-related patterns
        for similarity, decision, confidence, usage_count in examples:
            assert similarity > 0.5
            print(f"  Example: {decision} (sim: {similarity:.2f}, usage: {usage_count})")
        
        print("✓ Similar examples retrieved")
    
    def test_get_similar_examples_empty_cache(self, pattern_cache):
        """Should handle empty cache gracefully."""
        examples = pattern_cache.get_similar_examples("test", k=3)
        assert len(examples) == 0
        print("✓ Empty cache handled")
    
    def test_similar_examples_prefer_high_usage(self, pattern_cache):
        """Should prefer patterns with higher usage."""
        # Store two similar patterns
        pattern_cache.store("Say hello", {"intent": "generative", "id": 1}, confidence=0.9)
        pattern_cache.store("Tell hello", {"intent": "generative", "id": 2}, confidence=0.9)
        
        # Use first pattern multiple times
        for _ in range(5):
            pattern_cache.lookup("Say hello")
        
        # Get examples - should prefer the frequently used one
        examples = pattern_cache.get_similar_examples("Greet me", k=2)
        
        # First example should be the one used more (id: 1)
        if len(examples) > 0:
            top_example = examples[0]
            _, decision, _, usage_count = top_example
            assert usage_count >= 5  # Should be the frequently used one
            print(f"✓ High-usage pattern preferred (usage: {usage_count})")


class TestPatternCachePersistence:
    """Test saving and loading patterns."""
    
    def test_save_to_disk(self, temp_cache_file):
        """Should save patterns to disk."""
        cache = PatternCache(cache_file=temp_cache_file)
        cache.store("Say hello", {"intent": "generative"}, confidence=0.9)
        
        # File should exist
        assert os.path.exists(temp_cache_file)
        
        # File should contain pattern
        with open(temp_cache_file, 'r') as f:
            data = json.load(f)
            assert len(data["patterns"]) == 1
            assert data["patterns"][0]["query"] == "Say hello"
        
        print("✓ Patterns saved to disk")
    
    def test_load_from_disk(self, temp_cache_file):
        """Should load patterns from disk."""
        # Create cache and store pattern
        cache1 = PatternCache(cache_file=temp_cache_file)
        cache1.store("Say hello", {"intent": "generative"}, confidence=0.9)
        
        # Create new cache instance (should load from disk)
        cache2 = PatternCache(cache_file=temp_cache_file)
        
        assert len(cache2.patterns) == 1
        assert cache2.patterns[0]["query"] == "Say hello"
        print("✓ Patterns loaded from disk")
    
    def test_clear_cache(self, pattern_cache):
        """Should clear all patterns."""
        pattern_cache.store("Say hello", {"intent": "generative"}, confidence=0.9)
        pattern_cache.store("Calculate", {"intent": "tool_use"}, confidence=0.9)
        
        assert len(pattern_cache.patterns) == 2
        
        pattern_cache.clear()
        
        assert len(pattern_cache.patterns) == 0
        assert pattern_cache.stats["lookups"] == 0
        print("✓ Cache cleared")


class TestPatternCacheStatistics:
    """Test cache statistics and performance tracking."""
    
    def test_stats_tracking(self, pattern_cache):
        """Should track lookups, hits, misses."""
        # Store pattern
        pattern_cache.store("Say hello", {"intent": "generative"}, confidence=0.9)
        
        # Hit
        pattern_cache.lookup("Say hello", threshold=0.85)
        
        # Miss
        pattern_cache.lookup("Calculate prime", threshold=0.85)
        
        stats = pattern_cache.get_stats()
        
        assert stats["lookups"] == 2
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["stores"] == 1
        assert 0.0 <= stats["hit_rate"] <= 1.0
        assert stats["pattern_count"] == 1
        
        print(f"✓ Stats: {stats}")
    
    def test_hit_rate_calculation(self, pattern_cache):
        """Should calculate hit rate correctly."""
        pattern_cache.store("Say hello", {"intent": "generative"}, confidence=0.9)
        
        # 3 hits
        for _ in range(3):
            pattern_cache.lookup("Say hello")
        
        # 1 miss
        pattern_cache.lookup("Unknown query", threshold=0.99)
        
        stats = pattern_cache.get_stats()
        
        assert stats["hit_rate"] == 0.75  # 3 hits / 4 lookups
        print(f"✓ Hit rate: {stats['hit_rate']:.2%}")


class TestPatternCacheIntegration:
    """Integration tests for real-world usage."""
    
    def test_intent_classification_learning(self, pattern_cache):
        """Simulate learning intent classification patterns."""
        # User asks greetings multiple times
        greetings = [
            "Say hello",
            "Tell me hi",
            "Greet the user",
            "Say hi there"
        ]
        
        for greeting in greetings:
            pattern_cache.store(greeting, {"intent": "generative"}, confidence=0.9)
        
        # New greeting should match (lower threshold for real embeddings)
        decision, conf = pattern_cache.lookup("Hello world", threshold=0.50)
        
        assert decision is not None
        assert decision["intent"] == "generative"
        assert conf > 0.5
        print(f"✓ Intent learning works (confidence: {conf:.2f})")
    
    def test_tool_selection_learning(self, pattern_cache):
        """Simulate learning tool selection patterns."""
        # User requests memory operations
        memory_ops = [
            ("Store my name", {"tool": "memory_write"}),
            ("Save this info", {"tool": "memory_write"}),
            ("Remember this data", {"tool": "memory_write"}),
            ("Keep this value", {"tool": "memory_write"}),
        ]
        
        for query, decision in memory_ops:
            pattern_cache.store(query, decision, confidence=0.9)
        
        # New memory write should match (similar phrasing)
        decision, conf = pattern_cache.lookup("Save my data", threshold=0.50)
        
        assert decision is not None
        assert decision["tool"] == "memory_write"
        print(f"✓ Tool selection learning works (confidence: {conf:.2f})")
    
    def test_cold_start_to_warmed_cache(self, pattern_cache):
        """Test cache warming up over time."""
        queries = [
            "Say hello",
            "Calculate sum", 
            "Store data",
            "Say hello",  # Repeat
            "Calculate sum",  # Repeat
        ]
        
        decisions = [
            {"intent": "generative"},
            {"intent": "tool_use"},
            {"intent": "tool_use"},
            {"intent": "generative"},
            {"intent": "tool_use"},
        ]
        
        hits = 0
        misses = 0
        
        for query, decision in zip(queries, decisions):
            found, _ = pattern_cache.lookup(query, threshold=0.85)
            
            if found:
                hits += 1
            else:
                misses += 1
                # Learn from miss
                pattern_cache.store(query, decision, confidence=0.9)
        
        # First 3 should be misses, last 2 should be hits
        assert misses == 3
        assert hits == 2
        
        stats = pattern_cache.get_stats()
        print(f"✓ Cache warmed up: {hits} hits, {misses} misses")
        print(f"  Final stats: {stats['pattern_count']} patterns, {stats['hit_rate']:.1%} hit rate")
