from .neuron import BaseNeuron
from .task_simplifier import TaskSimplifier
from .pattern_cache import PatternCache
from .parallel_voter import ParallelVoter
from .simple_voters import create_intent_voters
from typing import Optional, List, Tuple, Dict

class IntentClassifierNeuron(BaseNeuron):
    def __init__(self, *args, 
                 use_simplifier=True, 
                 simplifier_threshold=0.8,
                 use_pattern_cache=True,
                 use_parallel_voting=True,  # NEW: True parallel voting with multiple simple neurons
                 cache_threshold=0.80,
                 cache_file=None,
                 pattern_cache: Optional[PatternCache] = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.use_simplifier = use_simplifier
        self.simplifier_threshold = simplifier_threshold
        self.use_pattern_cache = use_pattern_cache
        self.use_parallel_voting = use_parallel_voting
        self.cache_threshold = cache_threshold
        
        if self.use_simplifier:
            self.simplifier = TaskSimplifier()
        
        # Parallel voting system - multiple simple neurons vote simultaneously
        if self.use_parallel_voting:
            self.parallel_voter = ParallelVoter(self.ollama_client, max_workers=8)
            self.voters = create_intent_voters(self.ollama_client)
        else:
            self.parallel_voter = None
            self.voters = None
        
        # Pattern cache for adaptive learning
        # Default path uses environment variable or falls back to var/intent_cache.json
        if self.use_pattern_cache:
            if cache_file is None:
                import os
                cache_file = os.environ.get("NEURAL_ENGINE_INTENT_CACHE", "var/intent_cache.json")
            self.pattern_cache = pattern_cache or PatternCache(cache_file=cache_file)
        else:
            self.pattern_cache = None
    
    def _load_prompt(self):
        with open("neural_engine/prompts/intent_classifier_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, goal: str, depth=0):
        # Stage 1: Check pattern cache (fastest - learned patterns)
        if self.use_pattern_cache and self.pattern_cache:
            cached_decision, cache_confidence = self.pattern_cache.lookup(
                goal, 
                threshold=self.cache_threshold
            )
            
            if cached_decision:
                intent = cached_decision["intent"]
                print(f"✓ Pattern cache hit: '{goal}' → {intent} (confidence: {cache_confidence:.2f})")
                
                self.add_message_with_metadata(
                    goal_id=goal_id,
                    message_type="intent",
                    data={
                        "intent": intent,
                        "goal": goal,
                        "method": "pattern_cache",
                        "confidence": cache_confidence
                    },
                    depth=depth
                )
                
                return {"goal": goal, "intent": intent}
        
        # Stage 2: Parallel voting system (8 simple neurons vote simultaneously)
        # This runs BEFORE simplifier - it's more accurate and scales better
        if self.use_parallel_voting and self.parallel_voter and self.voters:
            vote_result = self.parallel_voter.vote(goal, self.voters)
            
            intent = vote_result["winner"]
            confidence = vote_result["confidence"]
            
            print(f"🗳️  Parallel voting: '{goal}' → {intent} ({vote_result['num_votes']} votes, {confidence:.0%} agreement)")
            
            # Debug: Show individual votes
            if vote_result.get("votes"):
                for v in vote_result["votes"]:
                    print(f"     • {v['label']} (conf:{v['confidence']:.1f}) - {v.get('question', '')[:50]}...")
            
            # Store in cache for future use
            if self.use_pattern_cache and self.pattern_cache:
                self.pattern_cache.store(
                    goal,
                    {"intent": intent},
                    confidence=confidence
                )
            
            self.add_message_with_metadata(
                goal_id=goal_id,
                message_type="intent",
                data={
                    "intent": intent,
                    "goal": goal,
                    "method": "parallel_voting",
                    "confidence": confidence,
                    "num_votes": vote_result["num_votes"]
                },
                depth=depth
            )
            
            return {"goal": goal, "intent": intent}
        
        # Stage 3: Try keyword simplifier (fallback - rule-based)
        if self.use_simplifier:
            simplified = self.simplifier.simplify_for_intent_classification(goal)
            
            # If high confidence, use it directly
            if simplified["confidence"] >= self.simplifier_threshold:
                intent = simplified["intent"]
                
                # Store successful simplifier result in cache for future
                if self.use_pattern_cache and self.pattern_cache:
                    self.pattern_cache.store(
                        goal,
                        {"intent": intent},
                        confidence=simplified["confidence"],
                        metadata={"method": "simplifier", "keyword": simplified.get("keyword_matched")}
                    )
                
                self.add_message_with_metadata(
                    goal_id=goal_id,
                    message_type="intent",
                    data={
                        "intent": intent, 
                        "goal": goal,
                        "method": "simplifier",
                        "confidence": simplified["confidence"],
                        "keyword_matched": simplified.get("keyword_matched")
                    },
                    depth=depth
                )
                
                return {"goal": goal, "intent": intent}
        
        # Stage 4: Fall back to LLM with focused few-shot examples
        # Get similar examples from cache (only highly relevant ones!)
        similar_examples = []
        if self.use_pattern_cache and self.pattern_cache:
            # Use higher threshold (0.7) to only get truly relevant examples
            # Limit to 2 examples max to avoid bloating prompt
            similar_examples = self.pattern_cache.get_similar_examples_with_queries(
                goal, k=2, min_similarity=0.7
            )
        
        # Use chat API with few-shot if we have good examples
        if similar_examples:
            intent = self._classify_with_fewshot(goal, similar_examples)
        else:
            # Zero-shot: no good examples available
            intent = self._classify_zeroshot(goal)
        
        # Validate intent
        if intent not in ["generative", "tool_use"]:
            print(f"⚠️  Invalid intent '{intent}', defaulting to 'generative'")
            intent = "generative"
        
        # NOTE: Pattern cache storage moved to orchestrator AFTER execution validation
        # This ensures we only cache patterns that actually worked in practice

        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="intent",
            data={
                "intent": intent, 
                "goal": goal,
                "method": "llm_fewshot" if similar_examples else "llm_zeroshot",
                "confidence": 0.75,
                "fewshot_examples_count": len(similar_examples)
            },
            depth=depth
        )

        return {"goal": goal, "intent": intent}
    
    def _classify_with_fewshot(self, goal: str, examples: List[Tuple[str, Dict, float]]) -> str:
        """
        Classify intent using chat API with few-shot examples.
        
        Args:
            goal: The goal to classify
            examples: List of (query, decision, similarity) tuples
        
        Returns:
            Intent classification ("generative" or "tool_use")
        """
        # Build chat messages with few-shot examples
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an intent classifier. Classify user goals as either:\n"
                    "- 'generative' (creative writing, stories, poems, general knowledge)\n"
                    "- 'tool_use' (calculations, data retrieval, API calls, specific actions)\n\n"
                    "Respond with only the intent name."
                )
            }
        ]
        
        # Add few-shot examples (only 2-3 most relevant!)
        for query, decision, similarity in examples[:2]:  # MAX 2 examples
            intent = decision.get("intent", "generative")
            messages.append({"role": "user", "content": query})
            messages.append({"role": "assistant", "content": intent})
        
        # Add actual query
        messages.append({"role": "user", "content": goal})
        
        # Call chat API
        response = self.ollama_client.chat(messages)
        intent = response['message']['content'].strip().lower()
        
        # Validate
        if intent not in ["generative", "tool_use"]:
            # Try to extract from response
            if "tool" in intent or "tool_use" in intent:
                intent = "tool_use"
            elif "gen" in intent or "creative" in intent:
                intent = "generative"
            else:
                print(f"⚠️  Invalid intent '{intent}' from few-shot, defaulting to 'generative'")
                intent = "generative"
        
        return intent
    
    def _classify_zeroshot(self, goal: str) -> str:
        """
        Classify intent using chat API without examples (zero-shot).
        
        Args:
            goal: The goal to classify
        
        Returns:
            Intent classification ("generative" or "tool_use")
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an intent classifier. Classify user goals as either:\n"
                    "- 'generative' (creative writing, stories, poems, general knowledge)\n"
                    "- 'tool_use' (calculations, data retrieval, API calls, specific actions)\n\n"
                    "Respond with only the intent name."
                )
            },
            {"role": "user", "content": goal}
        ]
        
        response = self.ollama_client.chat(messages)
        intent = response['message']['content'].strip().lower()
        
        # Validate
        if intent not in ["generative", "tool_use"]:
            if "tool" in intent or "tool_use" in intent:
                intent = "tool_use"
            elif "gen" in intent or "creative" in intent:
                intent = "generative"
            else:
                print(f"⚠️  Invalid intent '{intent}' from zero-shot, defaulting to 'generative'")
                intent = "generative"
        
        return intent
    
    def _build_focused_prompt(self, goal: str, similar_examples: list) -> str:
        """
        Build focused prompt with similar examples from cache.
        
        Args:
            goal: The goal to classify
            similar_examples: List of (similarity, decision, confidence, usage_count)
        
        Returns:
            Focused prompt string
        """
        prompt_template = self._load_prompt()
        base_prompt = prompt_template.format(goal=goal)
        
        # Add similar examples if available (dynamic, not hardcoded!)
        if similar_examples:
            examples_text = "\n\nSimilar examples from successful past classifications:\n"
            for similarity, decision, confidence, usage_count in similar_examples[:3]:
                intent = decision.get("intent", "unknown")
                examples_text += f"- Similar goal → {intent} (used {usage_count}x, {similarity:.0%} similar)\n"
            
            # Insert examples before the final "Intent:" line
            base_prompt = base_prompt.replace("\nIntent:", examples_text + "\nIntent:")
        
        return base_prompt
