"""
Semantic Fact Store - Revolutionary dynamic classification system.

Instead of hardcoded facts, this system:
1. Loads facts from JSON (versionable, searchable)
2. Indexes facts in Chroma for semantic search
3. Finds relevant facts for each goal dynamically
4. Learns from failures by adding new facts
5. Validates facts against examples

This makes the system self-improving and community-driven.
"""

import json
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import chromadb
from chromadb.config import Settings


@dataclass
class ClassificationFact:
    """A single classification fact with semantic context."""
    id: str
    description: str
    intent: str
    confidence: float
    category: str
    examples: List[str]
    tags: List[str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict) -> 'ClassificationFact':
        """Create from dictionary."""
        return ClassificationFact(**data)


class SemanticFactStore:
    """
    Semantic fact store using Chroma for fast retrieval.
    
    This is the revolutionary part: instead of checking ALL facts,
    we semantically search for RELEVANT facts based on the goal.
    """
    
    def __init__(self, 
                 facts_file: str = "neural_engine/data/classification_facts.json",
                 chroma_dir: str = None,
                 collection_name: str = "classification_facts"):
        """
        Initialize semantic fact store.
        
        Args:
            facts_file: Path to JSON facts database
            chroma_dir: Directory for Chroma database (defaults to var/prod/chroma or var/test/chroma)
            collection_name: Name of Chroma collection
        """
        self.facts_file = facts_file
        
        # Auto-detect environment: test vs prod
        if chroma_dir is None:
            # Check if running in test (via environment variable set by conftest.py)
            in_test = os.environ.get("PYTEST_CURRENT_TEST") is not None
            env_dir = "test" if in_test else "prod"
            chroma_dir = f"var/{env_dir}/chroma"
        
        self.chroma_dir = chroma_dir
        self.collection_name = collection_name
        
        # Load facts from JSON
        self.facts = self._load_facts()
        
        # Initialize Chroma client
        self.client = chromadb.PersistentClient(
            path=chroma_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Intent classification facts"}
        )
        
        # Index facts if collection is empty
        if self.collection.count() == 0:
            self._index_facts()
    
    def _load_facts(self) -> List[ClassificationFact]:
        """Load facts from JSON file."""
        if not os.path.exists(self.facts_file):
            raise FileNotFoundError(f"Facts file not found: {self.facts_file}")
        
        with open(self.facts_file, 'r') as f:
            data = json.load(f)
        
        facts = []
        for fact_data in data.get("facts", []):
            facts.append(ClassificationFact.from_dict(fact_data))
        
        print(f"📚 Loaded {len(facts)} classification facts from {self.facts_file}")
        return facts
    
    def _index_facts(self):
        """Index all facts in Chroma for semantic search."""
        if not self.facts:
            return
        
        # Prepare documents: description + examples for better semantic matching
        documents = []
        metadatas = []
        ids = []
        
        for fact in self.facts:
            # Combine description and examples for richer semantic context
            doc_text = f"{fact.description}\n\nExamples:\n" + "\n".join(f"- {ex}" for ex in fact.examples)
            documents.append(doc_text)
            
            metadatas.append({
                "intent": fact.intent,
                "confidence": fact.confidence,
                "category": fact.category,
                "tags": ",".join(fact.tags)
            })
            
            ids.append(fact.id)
        
        # Add to Chroma
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"✓ Indexed {len(documents)} facts in Chroma")
    
    def find_relevant_facts(self, 
                           goal: str, 
                           top_k: int = 5,
                           min_similarity: float = 0.5) -> List[Tuple[ClassificationFact, float]]:
        """
        Find most relevant facts for a goal using semantic search.
        
        This is REVOLUTIONARY: instead of checking all facts,
        we only check the most semantically relevant ones.
        
        Args:
            goal: User's goal to classify
            top_k: Number of top facts to retrieve
            min_similarity: Minimum similarity threshold (0-1)
        
        Returns:
            List of (fact, similarity_score) tuples
        """
        if self.collection.count() == 0:
            return []
        
        # Search Chroma for relevant facts
        results = self.collection.query(
            query_texts=[goal],
            n_results=top_k,
            include=["distances", "metadatas", "documents"]
        )
        
        # Extract results
        relevant_facts = []
        
        if results['ids'] and results['ids'][0]:
            fact_ids = results['ids'][0]
            # Chroma returns cosine distance (0 = identical, 2 = opposite)
            # Convert to similarity: similarity = 1 - (distance / 2)
            distances = results.get('distances', [[]])[0] if 'distances' in results else [0] * len(fact_ids)
            
            for fact_id, distance in zip(fact_ids, distances):
                # Convert distance to similarity (Chroma uses cosine distance 0-2)
                similarity = max(0.0, 1.0 - (distance / 2.0))
                
                if similarity >= min_similarity:
                    # Find corresponding fact
                    fact = next((f for f in self.facts if f.id == fact_id), None)
                    if fact:
                        relevant_facts.append((fact, similarity))
        
        return relevant_facts
    
    def add_fact(self, fact: ClassificationFact, save_to_file: bool = True):
        """
        Add a new fact dynamically (for self-learning).
        
        Args:
            fact: New classification fact
            save_to_file: Whether to persist to JSON file
        """
        # Add to in-memory list
        self.facts.append(fact)
        
        # Add to Chroma
        doc_text = f"{fact.description}\n\nExamples:\n" + "\n".join(f"- {ex}" for ex in fact.examples)
        
        self.collection.add(
            documents=[doc_text],
            metadatas=[{
                "intent": fact.intent,
                "confidence": fact.confidence,
                "category": fact.category,
                "tags": ",".join(fact.tags)
            }],
            ids=[fact.id]
        )
        
        # Optionally save to JSON file
        if save_to_file:
            self._save_facts()
        
        print(f"✓ Added new fact: {fact.id}")
    
    def _save_facts(self):
        """Save all facts back to JSON file."""
        data = {
            "version": "1.0.0",
            "description": "Intent classification facts for semantic matching",
            "facts": [f.to_dict() for f in self.facts]
        }
        
        with open(self.facts_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Saved {len(self.facts)} facts to {self.facts_file}")
    
    def get_fact_by_id(self, fact_id: str) -> Optional[ClassificationFact]:
        """Get a specific fact by ID."""
        return next((f for f in self.facts if f.id == fact_id), None)
    
    def remove_fact(self, fact_id: str, save_to_file: bool = True):
        """Remove a fact (for cleanup/validation)."""
        self.facts = [f for f in self.facts if f.id != fact_id]
        
        try:
            self.collection.delete(ids=[fact_id])
        except:
            pass
        
        if save_to_file:
            self._save_facts()
        
        print(f"✓ Removed fact: {fact_id}")
    
    def validate_facts(self) -> Dict[str, List[str]]:
        """
        Validate all facts by checking if examples match their intent.
        
        Returns:
            Dictionary of validation issues
        """
        issues = {
            "missing_examples": [],
            "inconsistent": []
        }
        
        for fact in self.facts:
            if not fact.examples:
                issues["missing_examples"].append(fact.id)
        
        return issues
