"""
Fact-Based Classification System

Instead of asking LLMs to interpret goals, we maintain a database of classification facts.
Small LLMs check if a goal matches each fact using semantic similarity.

Example:
    Fact: "user asks about their stored name"
    Goal: "What is my name?"
    Match? YES → classification: memory_read, confidence: 0.95

This approach:
- Is parallelizable (check all facts at once)
- Scales better (add more facts without bloating prompts)
- More explicit (facts are human-readable rules)
- Faster (small yes/no questions instead of complex reasoning)
"""

from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


@dataclass
class ClassificationFact:
    """
    A single fact for classification.
    
    Attributes:
        description: Human-readable description of when this applies
        intent: The classification result (tool_use, generative, etc.)
        confidence: Base confidence if this fact matches (0.0 to 1.0)
        category: Optional category for organizing facts
    """
    description: str
    intent: str
    confidence: float
    category: str = "general"
    
    def to_question(self) -> str:
        """Convert fact to a yes/no question for LLM."""
        return f"Does the user goal match this: {self.description}?"


class FactBasedClassifier:
    """
    Classifies user goals by matching against a fact database.
    
    Each fact is checked in parallel by small LLMs. Facts that match
    vote for their intent. The intent with highest total confidence wins.
    """
    
    def __init__(self, ollama_client, facts: List[ClassificationFact], max_workers: int = 10):
        """
        Initialize fact-based classifier.
        
        Args:
            ollama_client: OllamaClient for LLM calls
            facts: List of classification facts
            max_workers: Max parallel fact checks
        """
        self.ollama_client = ollama_client
        self.facts = facts
        self.max_workers = max_workers
    
    def classify(self, goal: str, early_exit_threshold: float = 0.90) -> Dict[str, any]:
        """
        Classify goal by checking facts in parallel with early exit optimization.
        
        Args:
            goal: User's goal to classify
            early_exit_threshold: Stop checking if we reach this confidence (0.0-1.0)
        
        Returns:
            {
                "intent": str,
                "confidence": float,
                "matched_facts": List[str],
                "all_matches": List[Dict],
                "early_exit": bool
            }
        """
        # Sort facts by confidence (check high-confidence facts first)
        sorted_facts = sorted(self.facts, key=lambda f: f.confidence, reverse=True)
        
        matches = []
        facts_checked = 0
        early_exit = False
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._check_fact, fact, goal): fact 
                for fact in sorted_facts
            }
            
            for future in as_completed(futures):
                fact = futures[future]
                facts_checked += 1
                
                try:
                    is_match, match_confidence = future.result()
                    if is_match:
                        matches.append({
                            "fact": fact.description,
                            "intent": fact.intent,
                            "base_confidence": fact.confidence,
                            "match_confidence": match_confidence,
                            "total_confidence": fact.confidence * match_confidence
                        })
                        
                        # Early exit: if we have strong match, compute current confidence
                        if match_confidence >= early_exit_threshold:
                            # Quick check: if this fact's intent dominates, we can stop
                            intent, confidence = self._aggregate_matches(matches)
                            if confidence >= early_exit_threshold:
                                early_exit = True
                                # Cancel remaining futures
                                for f in futures:
                                    if not f.done():
                                        f.cancel()
                                break
                                
                except Exception as e:
                    print(f"⚠️  Fact check failed: {e}")
        
        # Final aggregation
        intent, confidence = self._aggregate_matches(matches)
        
        return {
            "intent": intent,
            "confidence": confidence,
            "matched_facts": [m["fact"] for m in matches],
            "all_matches": matches,
            "num_facts_checked": facts_checked,
            "num_matches": len(matches),
            "early_exit": early_exit
        }
    
    def _check_fact(self, fact: ClassificationFact, goal: str) -> Tuple[bool, float]:
        """
        Check if a fact matches the goal using LLM.
        
        Returns:
            (is_match, confidence) tuple
        """
        question = fact.to_question()
        prompt = f"{question}\n\nGoal: {goal}\n\nAnswer (YES or NO):"
        
        response = self.ollama_client.client.generate(
            model=self.ollama_client.model,
            prompt=prompt,
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
    
    def _aggregate_matches(self, matches: List[Dict]) -> Tuple[str, float]:
        """
        Aggregate matched facts to determine final classification.
        
        Sums total_confidence per intent, winner is highest sum.
        """
        if not matches:
            return "unknown", 0.0
        
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
        
        return winner, confidence
