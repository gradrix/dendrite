"""
Semantic Intent Classifier - Revolutionary self-learning system.

Key innovations:
1. Semantic fact retrieval (not checking ALL facts)
2. Dynamic fact learning from failures
3. Validation and self-correction
4. Community-driven fact database
"""

from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from .semantic_fact_store import SemanticFactStore, ClassificationFact


class SemanticIntentClassifier:
    """
    Intent classifier using semantic fact retrieval.
    
    Revolutionary features:
    - Only checks RELEVANT facts (semantic search)
    - Self-learns from failures
    - No prompt engineering needed
    - Human-readable fact database
    """
    
    def __init__(self, 
                 ollama_client,
                 fact_store: Optional[SemanticFactStore] = None,
                 facts_file: str = "neural_engine/data/classification_facts.json",
                 top_k_facts: int = 5,
                 max_workers: int = 5):
        """
        Initialize semantic classifier.
        
        Args:
            ollama_client: Ollama client for LLM calls
            fact_store: Optional pre-initialized fact store
            facts_file: Path to JSON facts database
            top_k_facts: Number of relevant facts to check per goal
            max_workers: Parallel fact checking threads
        """
        self.ollama_client = ollama_client
        self.fact_store = fact_store or SemanticFactStore(facts_file=facts_file)
        self.top_k_facts = top_k_facts
        self.max_workers = max_workers
    
    def classify(self, 
                 goal: str,
                 confidence_threshold: float = 0.70,
                 debug: bool = False) -> Dict[str, any]:
        """
        Classify goal using keyword-enhanced semantic retrieval + voting.
        
        Revolutionary workflow:
        1. Extract keywords: Ask LLM what keywords describe this goal
        2. Multi-angle search: Search facts using keywords + original goal
        3. Parallel check: Ask LLM if goal matches each relevant fact
        4. Vote aggregation: Strongest matches win
        5. Learn: If low confidence, flag for human review/learning
        
        Args:
            goal: User's goal to classify
            confidence_threshold: Minimum confidence to accept result
            debug: Print debugging information
        
        Returns:
            {
                "intent": str,
                "confidence": float,
                "keywords": List[str],
                "relevant_facts": List[str],
                "matched_facts": List[Dict],
                "needs_learning": bool
            }
        """
        # Step 1: Extract keywords from goal using LLM
        keywords = self._extract_keywords(goal)
        
        if debug:
            print(f"\n🔍 Goal: '{goal}'")
            print(f"   Keywords: {', '.join(keywords)}")
        
        # Step 2: Multi-angle semantic search (goal + each keyword)
        all_relevant_facts = {}  # fact_id -> (fact, max_similarity)
        
        # Search with original goal
        goal_facts = self.fact_store.find_relevant_facts(
            goal, 
            top_k=self.top_k_facts,
            min_similarity=0.3
        )
        for fact, similarity in goal_facts:
            if fact.id not in all_relevant_facts or similarity > all_relevant_facts[fact.id][1]:
                all_relevant_facts[fact.id] = (fact, similarity)
        
        # Search with each keyword (multi-angle approach!)
        for keyword in keywords[:3]:  # Top 3 keywords to avoid explosion
            keyword_facts = self.fact_store.find_relevant_facts(
                keyword,
                top_k=3,
                min_similarity=0.3
            )
            for fact, similarity in keyword_facts:
                if fact.id not in all_relevant_facts or similarity > all_relevant_facts[fact.id][1]:
                    all_relevant_facts[fact.id] = (fact, similarity)
        
        relevant_facts = list(all_relevant_facts.values())
        
        if debug:
            print(f"   Found {len(relevant_facts)} unique relevant facts")
            for fact, similarity in relevant_facts[:5]:
                print(f"      {similarity:.2f}: [{fact.category}] {fact.description[:50]}...")
        
        if not relevant_facts:
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "keywords": keywords,
                "relevant_facts": [],
                "matched_facts": [],
                "needs_learning": True,
                "reason": "No relevant facts found"
            }
        
        # Step 3: Parallel fact checking (only relevant ones!)
        matches = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._check_fact, fact, goal): (fact, similarity)
                for fact, similarity in relevant_facts
            }
            
            for future in as_completed(futures):
                fact, semantic_similarity = futures[future]
                try:
                    is_match, match_confidence = future.result()
                    if is_match:
                        matches.append({
                            "fact_id": fact.id,
                            "fact": fact.description,
                            "intent": fact.intent,
                            "base_confidence": fact.confidence,
                            "match_confidence": match_confidence,
                            "semantic_similarity": semantic_similarity,
                            "total_confidence": fact.confidence * match_confidence
                        })
                except Exception as e:
                    if debug:
                        print(f"⚠️  Fact check failed for {fact.id}: {e}")
        
        # Step 4: Vote aggregation
        intent, confidence, breakdown = self._aggregate_matches(matches)
        
        if debug:
            print(f"   Matched {len(matches)} facts")
            print(f"   → {intent} ({confidence:.0%})")
            for intent_name, score in breakdown.items():
                print(f"      {intent_name}: {score:.2f}")
        
        return {
            "intent": intent,
            "confidence": confidence,
            "keywords": keywords,
            "relevant_facts": [f"{f.id}({s:.2f})" for f, s in relevant_facts],
            "matched_facts": matches,
            "needs_learning": confidence < confidence_threshold,
            "num_relevant": len(relevant_facts),
            "num_matched": len(matches)
        }
    
    def _extract_keywords(self, goal: str) -> List[str]:
        """
        Extract keywords that describe the goal's intent.
        
        This is KEY: helps semantic search find better matches!
        """
        prompt = f"""Extract 3-5 keywords that best describe this user request's intent.

User request: "{goal}"

Think about:
- What ACTION is the user trying to do? (print, calculate, store, retrieve, explain)
- What DOMAIN is it about? (memory, math, creative, knowledge, api)
- What VERBS or NOUNS describe it? (output, display, time, joke, code)

Return ONLY the keywords, comma-separated, nothing else.
Example: "output, display, command, print"
"""
        
        response = self.ollama_client.generate(
            prompt=prompt,
            context="semantic_keyword_extraction",
            options={"temperature": 0.3}  # Slight creativity for keyword variety
        )
        
        keywords_text = response['response'].strip()
        # Parse comma-separated keywords
        keywords = [k.strip().lower() for k in keywords_text.split(',') if k.strip()]
        
        return keywords[:5]  # Max 5 keywords
    
    def _check_fact(self, fact: ClassificationFact, goal: str) -> Tuple[bool, float]:
        """
        Check if a fact matches the goal using LLM.
        
        Returns:
            (is_match, confidence)
        """
        prompt = f"""Does this goal match this classification rule?

Goal: "{goal}"

Rule: {fact.description}

Examples of goals that match this rule:
{chr(10).join(f'- {ex}' for ex in fact.examples[:3])}

Answer YES if the goal matches this rule, NO if it doesn't.
Consider the semantic meaning, not just keywords.
"""
        
        response = self.ollama_client.generate(
            prompt=prompt,
            context="semantic_fact_check",
            options={"temperature": 0}
        )
        
        answer = response['response'].strip().upper()
        
        if "YES" in answer:
            return True, 0.9
        elif "NO" in answer:
            return False, 0.0
        else:
            # Unclear - low confidence match
            return True, 0.3
    
    def _aggregate_matches(self, matches: List[Dict]) -> Tuple[str, float, Dict[str, float]]:
        """
        Aggregate matched facts to determine final classification.
        
        Returns:
            (intent, confidence, intent_breakdown)
        """
        if not matches:
            return "unknown", 0.0, {}
        
        # Sum confidence per intent
        intent_scores = {}
        for match in matches:
            intent = match["intent"]
            confidence = match["total_confidence"]
            
            if intent not in intent_scores:
                intent_scores[intent] = 0.0
            
            intent_scores[intent] += confidence
        
        # Find winner
        winner = max(intent_scores, key=intent_scores.get)
        total_confidence = sum(intent_scores.values())
        
        # Normalize (what % of votes did winner get?)
        confidence = intent_scores[winner] / total_confidence if total_confidence > 0 else 0.0
        
        return winner, confidence, intent_scores
    
    def learn_from_failure(self, 
                          goal: str, 
                          expected_intent: str,
                          actual_intent: str,
                          category: str = "learned",
                          auto_save: bool = False) -> ClassificationFact:
        """
        Learn from a classification failure by creating a new fact.
        
        This is the REVOLUTIONARY PART: system improves itself!
        
        Args:
            goal: The goal that was misclassified
            expected_intent: What it should have been
            actual_intent: What the system classified it as
            category: Category for the new fact
            auto_save: Whether to auto-save to JSON (or flag for human review)
        
        Returns:
            New ClassificationFact created from this failure
        """
        # Generate unique ID
        fact_id = f"{category}_{len(self.fact_store.facts) + 1:03d}"
        
        # Create description based on the goal
        description = f"user says something like '{goal}'"
        
        # Create new fact
        new_fact = ClassificationFact(
            id=fact_id,
            description=description,
            intent=expected_intent,
            confidence=0.85,  # Lower confidence for learned facts
            category=category,
            examples=[goal],
            tags=["learned", "auto-generated"]
        )
        
        # Add to fact store
        self.fact_store.add_fact(new_fact, save_to_file=auto_save)
        
        print(f"📖 Learned new fact from failure:")
        print(f"   Goal: '{goal}'")
        print(f"   Expected: {expected_intent}, Got: {actual_intent}")
        print(f"   Created fact: {fact_id}")
        
        return new_fact
