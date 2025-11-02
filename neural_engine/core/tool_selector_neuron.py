from .neuron import BaseNeuron
from .tool_discovery import ToolDiscovery
from .tool_selection_validator_neuron import ToolSelectionValidatorNeuron
from .task_simplifier import TaskSimplifier
from .pattern_cache import PatternCache
from typing import Optional, Dict, List, Tuple
import json

class ToolSelectorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, tool_registry, 
                 tool_discovery: Optional[ToolDiscovery] = None,
                 enable_validation: bool = False,  # Disabled by default - mostly LLM quality issues
                 use_simplifier: bool = True,  # Use TaskSimplifier to help small LLM
                 use_pattern_cache: bool = True,  # Use pattern cache for adaptive learning
                 cache_threshold: float = 0.80,  # Cosine similarity threshold for cache hits
                 max_retries: int = 3,  # Reduced to 3 to avoid test timeouts
                 pattern_cache: Optional[PatternCache] = None):  # Allow injection for testing
        super().__init__(message_bus, ollama_client)
        self.tool_registry = tool_registry
        self.tool_discovery = tool_discovery
        self.enable_validation = enable_validation
        self.use_simplifier = use_simplifier
        self.use_pattern_cache = use_pattern_cache
        self.cache_threshold = cache_threshold
        self.validator = ToolSelectionValidatorNeuron(max_retries=max_retries) if enable_validation else None
        self.simplifier = TaskSimplifier() if use_simplifier else None
        
        # Initialize pattern cache for adaptive learning
        if self.use_pattern_cache:
            self.pattern_cache = pattern_cache if pattern_cache else PatternCache(
                cache_file="var/tool_cache.json"
            )
        else:
            self.pattern_cache = None
        
        # Track usage for performance comparison
        self.selection_stats = {
            "semantic_enabled": tool_discovery is not None,
            "simplifier_enabled": use_simplifier,
            "pattern_cache_enabled": use_pattern_cache,
            "total_selections": 0,
            "avg_candidates_considered": 0,
            "simplifier_narrowing_count": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }

    def _load_prompt(self):
        with open("neural_engine/prompts/tool_selector_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id: str, goal: str, depth: int):
        # STAGE 0: Check pattern cache first (fastest - ~5ms)
        if self.use_pattern_cache:
            cached_decision, cache_confidence = self.pattern_cache.lookup(
                goal, 
                threshold=self.cache_threshold
            )
            
            if cached_decision:
                self.selection_stats["cache_hits"] += 1
                self.selection_stats["total_selections"] += 1
                
                # Reconstruct result from cached decision
                result_data = {
                    "goal": goal,
                    "selected_tools": cached_decision.get("selected_tools", []),
                    "method": "pattern_cache",
                    "confidence": cache_confidence
                }
                
                # Use new metadata-rich message format
                self.add_message_with_metadata(
                    goal_id=goal_id,
                    message_type="tool_selection",
                    data=result_data,
                    depth=depth
                )
                
                print(f"⚡ Pattern cache hit for tool selection (confidence: {cache_confidence:.2f})")
                return result_data
            else:
                self.selection_stats["cache_misses"] += 1
        
        # Stage 3: LLM Selection from top candidates
        if self.tool_discovery:
            # Use 3-stage filtering (Stages 1+2 already done in discover_tools)
            discovered_tools = self.tool_discovery.discover_tools(
                goal_text=goal,
                semantic_limit=20,  # Stage 1: 1000+ → 20 candidates
                ranking_limit=5      # Stage 2: 20 → 5 top performers
            )
            
            # Build tool definitions for top 5 candidates only
            tool_definitions = {}
            for tool_info in discovered_tools:
                tool_name = tool_info['tool_name']
                tool = self.tool_registry.get_tool(tool_name)
                if tool:
                    tool_def = tool.get_tool_definition()
                    # Add metadata from registry
                    if hasattr(tool, '_module_name'):
                        tool_def["module_name"] = tool._module_name
                    if hasattr(tool, '_class_name'):
                        tool_def["class_name"] = tool._class_name
                    # Add performance score from Stage 2
                    tool_def["performance_score"] = tool_info.get('score', 0.5)
                    tool_def["success_rate"] = tool_info.get('success_rate')
                    tool_definitions[tool_name] = tool_def
            
            self.selection_stats["avg_candidates_considered"] = len(tool_definitions)
        else:
            # Fallback: Use all tools (original behavior)
            tool_definitions = self.tool_registry.get_all_tool_definitions()
            self.selection_stats["avg_candidates_considered"] = len(tool_definitions)
        
        # NEW: Try TaskSimplifier to narrow tools before LLM
        narrowed_tools = tool_definitions
        simplifier_hint = None
        simplifier_confidence = 0.0
        
        if self.simplifier and len(tool_definitions) > 3:
            # Get tool names
            available_tool_names = list(tool_definitions.keys())
            
            # Ask simplifier to narrow down
            simplified = self.simplifier.simplify_for_tool_selection(goal, available_tool_names)
            
            # If confident, use narrowed list
            if simplified["confidence"] > 0.6:
                narrowed_tool_names = simplified["narrowed_tools"]
                narrowed_tools = {
                    name: tool_definitions[name] 
                    for name in narrowed_tool_names 
                    if name in tool_definitions
                }
                simplifier_hint = simplified["explicit_hint"]
                simplifier_confidence = simplified["confidence"]
                
                self.selection_stats["simplifier_narrowing_count"] += 1
                print(f"🎯 TaskSimplifier: {len(tool_definitions)} tools → {len(narrowed_tools)} tools (confidence: {simplifier_confidence:.2f})")
        
        self.selection_stats["total_selections"] += 1
        
        # Build context for validation
        context = {
            "goal": goal,
            "available_tools": narrowed_tools,  # Use narrowed tools
            "simplifier_hint": simplifier_hint  # Pass hint to LLM
        }
        
        # Get similar examples from pattern cache (only highly relevant!)
        # Use higher threshold (0.7) and limit to 2 examples max
        similar_examples = []
        if self.use_pattern_cache:
            similar_examples = self.pattern_cache.get_similar_examples_with_queries(
                goal, k=2, min_similarity=0.7
            )
        
        # Add similar examples to context
        if similar_examples:
            context["similar_examples_with_queries"] = similar_examples
        
        # Select tool with validation and retry
        if self.enable_validation:
            selected_tools, validation_result = self._select_with_validation(
                goal_id, context, depth, narrowed_tools
            )
        else:
            # Fallback to original behavior without validation
            selected_tools = self._select_tool_once(context, narrowed_tools)
            validation_result = None
        
        result_data = {
            "goal": goal,
            "selected_tools": selected_tools
        }
        
        # Determine method used and confidence
        method = "llm_adaptive"
        confidence = 0.70  # Base LLM confidence
        
        # Add simplifier metadata if used
        if simplifier_hint:
            method = "simplifier_llm"
            confidence = min(0.85, 0.70 + (simplifier_confidence * 0.15))  # Boost confidence
            result_data["simplifier"] = {
                "narrowed_from": len(tool_definitions),
                "narrowed_to": len(narrowed_tools),
                "confidence": simplifier_confidence
            }
        
        # Add method and confidence tracking
        result_data["method"] = method
        result_data["confidence"] = confidence
        
        # Add validation metadata if available
        if validation_result:
            result_data["validation"] = {
                "valid": validation_result["valid"],
                "attempts": validation_result.get("attempts", 1),
                "had_errors": len(validation_result.get("errors", [])) > 0
            }
        
        # Store successful selection in pattern cache for learning
        # Only store if we got a valid tool selection
        if self.use_pattern_cache and selected_tools and len(selected_tools) > 0:
            cache_data = {
                "selected_tools": selected_tools,
                "method": method
            }
            self.pattern_cache.store(goal, cache_data, confidence=confidence)
            print(f"📚 Stored tool selection in pattern cache (confidence: {confidence:.2f})")
        
        # Use new metadata-rich message format
        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="tool_selection",
            data=result_data,
            depth=depth
        )
        
        return result_data
    
    def _select_with_validation(self, goal_id: str, context: Dict, depth: int, tool_definitions: Dict) -> Tuple[List[Dict], Dict]:
        """
        Select tool with validation and retry mechanism.
        
        Returns:
            (selected_tools, validation_result)
        """
        attempt = 0
        retry_context = context.copy()
        
        while attempt < self.validator.max_retries:
            attempt += 1
            
            # Select tool
            selected_tools = self._select_tool_once(retry_context, tool_definitions)
            
            # Validate
            validation_result = self.validator.validate_selection(selected_tools, context)
            validation_result["attempts"] = attempt
            validation_result["previous_selection"] = selected_tools
            
            if validation_result["valid"]:
                if attempt > 1:
                    print(f"✅ Tool selection successful after {attempt} attempts")
                return selected_tools, validation_result
            
            # Selection has errors - check if we should retry
            if not self.validator.should_retry(attempt):
                print(f"⚠️  Tool selection validation failed after {attempt} attempts. Using best effort.")
                return selected_tools, validation_result
            
            # Build retry context with targeted feedback
            print(f"🔄 Retry attempt {attempt}/{self.validator.max_retries}: {validation_result['feedback'][:100]}...")
            retry_context = self.validator.get_retry_context(
                validation_result, context, attempt
            )
        
        # Max retries reached
        print(f"⚠️  Max retries ({self.validator.max_retries}) reached. Using last attempt.")
        return selected_tools, validation_result
    
    def _select_tool_once(self, context: Dict, tool_definitions: Dict) -> List[Dict]:
        """
        Select tool once (single LLM call).
        
        Args:
            context: May include retry_instruction for feedback-based retry,
                     simplifier_hint for task simplification,
                     and similar_examples_with_queries from pattern cache
            tool_definitions: Available tools (may be narrowed by simplifier)
        
        Returns:
            List of selected tools
        """
        goal = context["goal"]
        
        # Check if we have good few-shot examples
        has_fewshot = "similar_examples_with_queries" in context and context["similar_examples_with_queries"]
        
        if has_fewshot and not context.get("retry_instruction"):
            # Use chat API with few-shot (but not during retries - keep it simple)
            return self._select_with_fewshot(goal, context["similar_examples_with_queries"], tool_definitions)
        else:
            # Use traditional prompt-based approach (for retries or zero-shot)
            return self._select_with_prompt(context, tool_definitions)
    
    def _select_with_fewshot(self, goal: str, examples: List[Tuple[str, Dict, float]], tool_definitions: Dict) -> List[Dict]:
        """
        Select tool using chat API with few-shot examples.
        
        Args:
            goal: The goal requiring a tool
            examples: List of (query, decision, similarity) tuples
            tool_definitions: Available tools
        
        Returns:
            List of selected tools
        """
        # Build chat messages
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a tool selector. Given a user goal and available tools, "
                    "select the most appropriate tool.\n\n"
                    "Respond with JSON: {\"tool_name\": \"<tool_name>\", \"reasoning\": \"<brief reason>\"}\n\n"
                    f"Available tools:\n{json.dumps(tool_definitions, indent=2)}"
                )
            }
        ]
        
        # Add few-shot examples (MAX 2 to keep prompt small!)
        for query, decision, similarity in examples[:2]:
            selected_tools = decision.get("selected_tools", [])
            if selected_tools and len(selected_tools) > 0:
                tool_name = selected_tools[0]["name"]
                messages.append({"role": "user", "content": query})
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({"tool_name": tool_name, "reasoning": "Similar to past successful selection"})
                })
        
        # Add actual query
        messages.append({"role": "user", "content": goal})
        
        # Call chat API
        try:
            response = self.ollama_client.chat(messages)
            response_text = response['message']['content'].strip()
            response_json = json.loads(response_text)
            selected_tool_name = response_json["tool_name"]

            tool = self.tool_registry.get_tool(selected_tool_name)
            if not tool:
                raise ValueError(f"Tool '{selected_tool_name}' not found in registry.")

            # Get enriched tool definition from registry
            tool_info = tool_definitions[selected_tool_name]
            
            return [{
                "name": selected_tool_name,
                "module": tool_info["module_name"],
                "class": tool_info["class_name"]
            }]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"⚠️  Failed to parse tool selection from few-shot: {e}")
            # Fallback to prompt-based
            return self._select_with_prompt({"goal": goal, "available_tools": tool_definitions}, tool_definitions)
    
    def _select_with_prompt(self, context: Dict, tool_definitions: Dict) -> List[Dict]:
        """
        Select tool using traditional prompt (zero-shot or with retry instructions).
        
        Args:
            context: Context including goal and optional retry/hint info
            tool_definitions: Available tools
        
        Returns:
            List of selected tools
        """
        prompt_template = self._load_prompt()
        
        # Build prompt with optional hints
        prompt_parts = []
        
        # Add simplifier hint if available (helps small LLM understand task)
        if "simplifier_hint" in context and context["simplifier_hint"]:
            prompt_parts.append(f"HINT: {context['simplifier_hint']}\n\n")
        
        # Add retry instruction if this is a retry
        if "retry_instruction" in context:
            prompt_parts.append(f"{context['retry_instruction']}\n\n")
        
        # Add main prompt
        prompt_parts.append(prompt_template.format(
            goal=context["goal"],
            tools=json.dumps(tool_definitions, indent=2)
        ))
        
        prompt = "".join(prompt_parts)

        response = self.ollama_client.generate(prompt=prompt)
        
        try:
            # Parse LLM response
            response_json = json.loads(response['response'].strip())
            selected_tool_name = response_json["tool_name"]

            tool = self.tool_registry.get_tool(selected_tool_name)
            if not tool:
                raise ValueError(f"Tool '{selected_tool_name}' not found in registry.")

            # Get enriched tool definition from registry
            tool_info = tool_definitions[selected_tool_name]
            
            return [{
                "name": selected_tool_name,
                "module": tool_info["module_name"],
                "class": tool_info["class_name"]
            }]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Failed to parse response - return empty list
            print(f"⚠️  Failed to parse tool selection: {e}")
            return []
