from .neuron import BaseNeuron, fractal_process
from .task_simplifier import TaskSimplifier
from .pattern_cache import PatternCache
from .parallel_voter import ParallelVoter
from .simple_voters import create_intent_voters
from .semantic_intent_classifier import SemanticIntentClassifier
from .domain_router import DomainRouter
from .logging import get_logger
from typing import Optional, List, Tuple, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import SystemConfig

logger = get_logger(__name__)


class IntentClassifierNeuron(BaseNeuron):
    
    @classmethod
    def from_config(cls, config: 'SystemConfig') -> 'IntentClassifierNeuron':
        """
        Create IntentClassifierNeuron from a SystemConfig.
        
        No optional params - everything comes from config.
        """
        return cls(
            config.message_bus,
            config.llm_client,
            use_pattern_cache=config.enable_pattern_cache,
            pattern_cache=config.pattern_cache,
            use_simplifier=True,
            use_semantic=False,
            use_parallel_voting=False
        )
    
    def __init__(self, *args, 
                 use_simplifier=True, 
                 simplifier_threshold=0.8,
                 use_pattern_cache=True,
                 use_semantic=False,  # Revolutionary keyword-enhanced semantic classification
                 use_parallel_voting=False,  # Voting system for ambiguous cases
                 semantic_confidence_threshold=0.60,  # Fall back to voting if below this
                 cache_threshold=0.80,
                 cache_file=None,
                 pattern_cache: Optional[PatternCache] = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.use_simplifier = use_simplifier
        self.simplifier_threshold = simplifier_threshold
        self.use_pattern_cache = use_pattern_cache
        self.use_semantic = use_semantic
        self.use_parallel_voting = use_parallel_voting
        self.semantic_confidence_threshold = semantic_confidence_threshold
        self.cache_threshold = cache_threshold
        self.visualizer = None  # Optional visualizer for cache hit tracking
        
        if self.use_simplifier:
            self.simplifier = TaskSimplifier()
        
        # Semantic classification system (REVOLUTIONARY - keyword-enhanced!)
        if self.use_semantic:
            self.semantic_classifier = SemanticIntentClassifier(
                self.ollama_client,
                top_k_facts=5
            )
        else:
            self.semantic_classifier = None
        
        # Parallel voting system - multiple simple neurons vote simultaneously (fallback)
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
        
        # Domain router for memory detection (override LLM mistakes)
        self.domain_router = DomainRouter(self.ollama_client)
    
    def _load_prompt(self):
        with open("neural_engine/prompts/intent_classifier_prompt.txt", "r") as f:
            return f.read()

    @fractal_process
    def process(self, goal_id, goal: str, depth=0):
        # Stage 0: Domain-based override (memory domain always needs tools)
        domain = self.domain_router.detect_domain(goal)
        if domain == "memory":
            # Memory operations ALWAYS require tools (memory_read/memory_write)
            intent = "tool_use"
            logger.info("Memory domain detected", goal=goal, intent=intent, method="domain_override")
            
            self.add_message_with_metadata(
                goal_id=goal_id,
                message_type="intent",
                data={
                    "intent": intent,
                    "goal": goal,
                    "method": "domain_override",
                    "domain": domain,
                    "confidence": 0.99
                },
                depth=depth
            )
            
            return {"goal": goal, "intent": intent}
        
        # Stage 1: Check pattern cache (fastest - learned patterns)
        if self.use_pattern_cache and self.pattern_cache:
            cached_decision, cache_confidence = self.pattern_cache.lookup(
                goal, 
                threshold=self.cache_threshold
            )
            
            if cached_decision:
                intent = cached_decision["intent"]
                logger.debug("Pattern cache hit", goal=goal, intent=intent, confidence=cache_confidence)
                
                # Notify visualizer if available
                if self.visualizer:
                    self.visualizer.show_cache_check({
                        'intent': intent,
                        'confidence': cache_confidence,
                        'similarity': cache_confidence,
                        'cache_type': 'pattern'
                    })
                
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
            else:
                # Notify visualizer of cache miss
                if self.visualizer:
                    self.visualizer.show_cache_check(None)
        
        # Stage 2: Semantic classification (REVOLUTIONARY - keyword-enhanced!)
        if self.use_semantic and self.semantic_classifier:
            semantic_result = self.semantic_classifier.classify(goal, debug=False)
            
            intent = semantic_result["intent"]
            confidence = semantic_result["confidence"]
            
            logger.info("Semantic classification", goal=goal, intent=intent, confidence=confidence,
                        keywords=semantic_result.get('keywords', [])[:3],
                        matched=semantic_result['num_matched'], relevant=semantic_result['num_relevant'])
            
            # If confidence is high enough, use it
            if confidence >= self.semantic_confidence_threshold:
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
                        "method": "semantic",
                        "confidence": confidence,
                        "keywords": semantic_result.get("keywords", []),
                        "num_matched": semantic_result["num_matched"]
                    },
                    depth=depth
                )
                
                return {"goal": goal, "intent": intent}
            else:
                # Low confidence - fall through to voting
                logger.debug("Low confidence, falling back to voting", confidence=confidence,
                            threshold=self.semantic_confidence_threshold)
        
        # Stage 2.5: Parallel voting (fallback when semantic has low confidence)
        if self.use_parallel_voting and self.parallel_voter and self.voters:
            vote_result = self.parallel_voter.vote(goal, self.voters)
            
            intent = vote_result["winner"]
            confidence = vote_result["confidence"]
            
            logger.info("Parallel voting", goal=goal, intent=intent, num_votes=vote_result['num_votes'],
                        confidence=confidence)
            
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
            logger.warning("Invalid intent, defaulting to generative", intent=intent)
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
                logger.warning("Invalid intent from few-shot", intent=intent)
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
                    "- 'generative' (creative writing, stories, poems, general knowledge questions, explanations, opinions, conversation)\n"
                    "- 'tool_use' (calculations, storing/recalling personal data, API calls, running code, specific actions with measurable results)\n\n"
                    "Important: Questions like 'What is X?' or 'Tell me about Y' are GENERATIVE - they need knowledge, not tools.\n"
                    "Only use tool_use for things that require executing code or calling an API.\n\n"
                    "Respond with ONLY the intent name, nothing else."
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
                logger.warning("Invalid intent from zero-shot", intent=intent)
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
