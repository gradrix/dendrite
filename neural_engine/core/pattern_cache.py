"""
Pattern Cache - Learn from successful patterns dynamically.

Stores successful intent/tool selection patterns with embeddings for fast similarity lookup.
This enables the system to learn from real usage without hardcoding examples.
"""

import json
import os
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from sentence_transformers import SentenceTransformer


class PatternCache:
    """
    Stores and retrieves successful patterns using embedding similarity.
    
    Key features:
    - Fast lookup via embedding similarity
    - Learns from successful executions
    - Persistence to disk
    - Usage tracking (patterns used more often = higher confidence)
    """
    
    def __init__(self, cache_file: str = "var/pattern_cache.json", model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize pattern cache.
        
        Args:
            cache_file: Path to cache persistence file
            model_name: Sentence transformer model for embeddings
        """
        self.cache_file = cache_file
        self.patterns: List[Dict[str, Any]] = []
        
        # Initialize statistics first (before loading)
        self.stats = {
            "lookups": 0,
            "hits": 0,
            "misses": 0,
            "stores": 0
        }
        
        # Load sentence transformer (fast, local, no API calls)
        print(f"Loading embedding model '{model_name}'...")
        self.embedder = SentenceTransformer(model_name)
        print(f"✓ Embedding model loaded")
        
        # Load existing patterns from disk
        self._load_from_disk()
    
    def lookup(self, query: str, threshold: float = 0.85) -> Tuple[Optional[Dict], float]:
        """
        Find similar pattern in cache.
        
        Args:
            query: Text to find similar pattern for
            threshold: Minimum similarity score (0.0-1.0)
        
        Returns:
            (decision_data, confidence) or (None, 0.0) if no match
        """
        self.stats["lookups"] += 1
        
        if len(self.patterns) == 0:
            self.stats["misses"] += 1
            return None, 0.0
        
        # Encode query
        query_embedding = self.embedder.encode(query, convert_to_tensor=False)
        
        # Find most similar pattern
        best_similarity = 0.0
        best_pattern = None
        
        for pattern in self.patterns:
            pattern_embedding = np.array(pattern["embedding"])
            similarity = self._cosine_similarity(query_embedding, pattern_embedding)
            
            if similarity > best_similarity and similarity >= threshold:
                best_similarity = similarity
                best_pattern = pattern
        
        if best_pattern:
            self.stats["hits"] += 1
            
            # Adjust confidence based on usage count
            base_confidence = best_pattern["confidence"]
            usage_boost = min(0.15, best_pattern["usage_count"] * 0.01)
            adjusted_confidence = min(0.99, base_confidence + usage_boost)
            
            # Increment usage count
            best_pattern["usage_count"] += 1
            
            return best_pattern["decision"], adjusted_confidence
        else:
            self.stats["misses"] += 1
            return None, 0.0
    
    def store(self, query: str, decision: Dict[str, Any], confidence: float = 0.8, metadata: Optional[Dict] = None):
        """
        Store successful pattern.
        
        Args:
            query: The original query text
            decision: The successful decision data
            confidence: Initial confidence (0.0-1.0)
            metadata: Optional metadata (component, timestamp, etc.)
        """
        self.stats["stores"] += 1
        
        # Encode query
        query_embedding = self.embedder.encode(query, convert_to_tensor=False)
        
        # Check if very similar pattern already exists (avoid duplicates)
        for pattern in self.patterns:
            pattern_embedding = np.array(pattern["embedding"])
            similarity = self._cosine_similarity(query_embedding, pattern_embedding)
            
            if similarity >= 0.90:  # Very similar - update existing (lowered from 0.95)
                # Keep higher confidence
                pattern["confidence"] = max(pattern["confidence"], confidence)
                pattern["usage_count"] += 1
                pattern["last_updated"] = self._get_timestamp()
                if metadata:
                    pattern["metadata"] = metadata
                self._save_to_disk()
                return
        
        # New pattern - add it
        pattern = {
            "query": query,
            "embedding": query_embedding.tolist(),  # Convert to list for JSON
            "decision": decision,
            "confidence": confidence,
            "usage_count": 1,
            "created_at": self._get_timestamp(),
            "last_updated": self._get_timestamp(),
            "metadata": metadata or {}
        }
        
        self.patterns.append(pattern)
        self._save_to_disk()
    
    def get_similar_examples(self, query: str, k: int = 3, min_similarity: float = 0.5) -> List[Tuple[float, Dict, float, int]]:
        """
        Get k most similar patterns for prompt context.
        
        Args:
            query: Text to find similar patterns for
            k: Number of examples to return
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of (similarity, decision, confidence, usage_count) tuples
        """
        if len(self.patterns) == 0:
            return []
        
        # Encode query
        query_embedding = self.embedder.encode(query, convert_to_tensor=False)
        
        # Calculate similarities
        similarities = []
        for pattern in self.patterns:
            pattern_embedding = np.array(pattern["embedding"])
            similarity = self._cosine_similarity(query_embedding, pattern_embedding)
            
            if similarity >= min_similarity:
                similarities.append((
                    similarity,
                    pattern["decision"],
                    pattern["confidence"],
                    pattern["usage_count"]
                ))
        
        # Sort by similarity * usage_count (prefer proven patterns)
        similarities.sort(key=lambda x: x[0] * (1 + x[3] * 0.1), reverse=True)
        
        return similarities[:k]
    
    def get_similar_examples_with_queries(self, query: str, k: int = 3, min_similarity: float = 0.7) -> List[Tuple[str, Dict, float]]:
        """
        Get k most similar patterns WITH original queries for few-shot learning.
        
        This is optimized for chat-based few-shot prompting where we need
        the original query text to construct user/assistant message pairs.
        
        Args:
            query: Text to find similar patterns for
            k: Number of examples to return (keep small: 2-3 max!)
            min_similarity: Minimum similarity threshold (higher = more relevant)
        
        Returns:
            List of (original_query, decision, similarity) tuples
            
        Example:
            [
                ("Calculate 10 + 20", {"intent": "tool_use"}, 0.89),
                ("What's 5 plus 3", {"intent": "tool_use"}, 0.85)
            ]
        """
        if len(self.patterns) == 0:
            return []
        
        # Encode query
        query_embedding = self.embedder.encode(query, convert_to_tensor=False)
        
        # Calculate similarities
        similarities = []
        for pattern in self.patterns:
            pattern_embedding = np.array(pattern["embedding"])
            similarity = self._cosine_similarity(query_embedding, pattern_embedding)
            
            if similarity >= min_similarity:
                similarities.append((
                    pattern["query"],  # Include original query text
                    pattern["decision"],
                    similarity,
                    pattern["usage_count"]
                ))
        
        # Sort by similarity * usage_count (prefer proven patterns)
        similarities.sort(key=lambda x: x[2] * (1 + x[3] * 0.1), reverse=True)
        
        # Return top k as (query, decision, similarity) tuples
        return [(q, d, s) for q, d, s, _ in similarities[:k]]
    
    def clear(self):
        """Clear all patterns."""
        self.patterns = []
        self.stats = {"lookups": 0, "hits": 0, "misses": 0, "stores": 0}
        self._save_to_disk()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hit_rate = self.stats["hits"] / max(1, self.stats["lookups"])
        
        return {
            **self.stats,
            "hit_rate": hit_rate,
            "pattern_count": len(self.patterns),
            "cache_size_mb": self._get_cache_size_mb()
        }
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _load_from_disk(self):
        """Load patterns from disk."""
        if not os.path.exists(self.cache_file):
            print(f"✓ Pattern cache initialized (empty)")
            return
        
        try:
            # Check if file is empty
            if os.path.getsize(self.cache_file) == 0:
                print(f"✓ Pattern cache initialized (empty file)")
                return
                
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                self.patterns = data.get("patterns", [])
                self.stats = data.get("stats", self.stats)
            print(f"✓ Loaded {len(self.patterns)} patterns from cache")
        except Exception as e:
            print(f"⚠️  Failed to load pattern cache: {e}")
            self.patterns = []
    
    def _save_to_disk(self):
        """Save patterns to disk."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        
        try:
            with open(self.cache_file, 'w') as f:
                data = {
                    "patterns": self.patterns,
                    "stats": self.stats
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save pattern cache: {e}")
    
    def _get_cache_size_mb(self) -> float:
        """Get cache file size in MB."""
        if not os.path.exists(self.cache_file):
            return 0.0
        return os.path.getsize(self.cache_file) / (1024 * 1024)
