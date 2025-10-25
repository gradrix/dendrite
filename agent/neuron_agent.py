"""
Neuron Agent: Self-Organizing Micro-Prompt Architecture

Philosophy:
- Each step is a "neuron" that fires tiny prompts (50-100 tokens)
- Lists automatically spawn "dendrites" (parallel sub-chains)
- Results aggregate back through "axons"
- Continuous validation at each neuron
- Recursive but bounded (max 3 levels)
- No user interaction - fully autonomous

Flow:
1. Goal → Decompose into neurons
2. For each neuron:
   a. Execute (50-100 token prompt)
   b. Detect if list result → spawn dendrites
   c. Validate output → retry if failed
   d. Store in context
3. Aggregate final result

Example:
Goal: "Get activities from last 24h with kudos details"
→ Neuron 1: getDashboardFeed(hours_ago=24) → [7 activities]
  → Detect list: "Need to get kudos for each"
  → Spawn 7 dendrites:
    - Dendrite 1: getActivityKudos(id=123) → [3 kudos]
    - Dendrite 2: getActivityKudos(id=456) → [5 kudos]
    - ... (parallel execution)
  → Aggregate: Merge all kudos into activities list
→ Format final output
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.ollama_client import OllamaClient
from agent.tool_registry import ToolRegistry
from agent.data_compaction import compact_data

logger = logging.getLogger(__name__)


@dataclass
class Neuron:
    """A single execution unit (neuron) in the agent's brain."""
    description: str
    index: int
    depth: int = 0  # Recursion depth (0 = root, 1 = first spawn, etc.)
    result: Any = None
    validated: bool = False
    spawned_dendrites: List['Neuron'] = field(default_factory=list)
    
    
class NeuronAgent:
    """
    Agent that executes through self-organizing neuron chains.
    
    Key features:
    - Automatic list iteration (spawns dendrites)
    - Micro-prompts (50-100 tokens each)
    - Continuous validation (no user interaction)
    - Bounded recursion (max_depth=3)
    - Sequential execution (safer for LLM)
    """
    
    MAX_DEPTH = 5  # Maximum recursion depth
    MAX_RETRIES = 3  # Retries per neuron if validation fails
    
    def __init__(
        self,
        ollama: OllamaClient,
        tool_registry: ToolRegistry,
        config: Optional[Dict] = None
    ):
        self.ollama = ollama
        self.tools = tool_registry
        self.config = config or {}
        self.context: Dict[str, Any] = {}
        self.execution_log: List[str] = []  # For debugging
    
    def _check_memory_relevance(self, goal: str) -> Dict[str, Any]:
        """
        Memory Overseer: Check if saved state is relevant to this goal.
        
        Returns dict of {key: value} for relevant state, or empty dict if none.
        
        This prevents context bloat by only loading relevant memory.
        """
        try:
            # 1. List all state keys (fast, no data loading yet)
            keys_result = self.tools.execute_tool('listStateKeys')
            
            if not keys_result.get('success') or not keys_result.get('keys'):
                return {}
            
            state_keys = [k['key'] for k in keys_result['keys']]
            
            if not state_keys:
                return {}
            
            # 2. Ask LLM which keys are relevant (tiny prompt!)
            prompt = f"""Goal: "{goal}"

Available memory keys: {', '.join(state_keys)}

Which memory keys are relevant to this goal?

Output ONLY valid JSON:
{{"relevant_keys": ["key1", "key2"]}}

If none relevant, output:
{{"relevant_keys": []}}"""

            response = self.ollama.generate(
                prompt,
                system="You identify relevant saved state keys. Output ONLY JSON, no explanation.",
                temperature=0
            )
            
            # 3. Parse response
            try:
                # Extract JSON from response
                response_str = str(response).strip()
                
                # Try to find JSON in response
                import re
                json_match = re.search(r'\{[^}]*\}', response_str)
                if json_match:
                    decision = json.loads(json_match.group())
                else:
                    decision = json.loads(response_str)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse memory relevance decision: {e}")
                return {}
            
            relevant_keys = decision.get('relevant_keys', [])
            
            if not relevant_keys:
                logger.info("🧠 Memory check: No relevant saved state")
                return {}
            
            # 4. Load only relevant state
            memory_context = {}
            for key in relevant_keys:
                result = self.tools.execute_tool('loadState', key=key)
                if result.get('success') and result.get('found'):
                    memory_context[key] = result['value']
                    logger.info(f"🧠 Loaded memory: {key} ({len(str(result['value']))} chars)")
            
            return memory_context
            
        except Exception as e:
            logger.warning(f"Memory relevance check failed: {e}")
            return {}
    
    def execute_goal(self, goal: str, depth: int = 0) -> Dict[str, Any]:
        """
        Execute a goal through neuron chains.
        
        Args:
            goal: Natural language goal
            depth: Current recursion depth (for spawned sub-goals)
            
        Returns:
            Execution results
        """
        if depth >= self.MAX_DEPTH:
            logger.warning(f"   ⚠️  Max depth {self.MAX_DEPTH} reached, stopping recursion")
            return {'success': False, 'error': 'Max recursion depth reached'}
        
        logger.info(f"{'  ' * depth}🎯 Goal (depth={depth}): {goal}")
        self._log(f"[DEPTH {depth}] Goal: {goal}")
        
        # Store original goal in context for inter-neuron communication (only at root)
        if depth == 0:
            self.context['_original_goal'] = goal
        
        # Memory Overseer: Check if we have relevant saved state (only at root level)
        memory_context = {}
        if depth == 0:
            logger.info(f"{'  ' * depth}╭─ Memory Check")
            memory_context = self._check_memory_relevance(goal)
            
            if memory_context:
                # Inject memory into goal context
                memory_summary = []
                for key, value in memory_context.items():
                    if isinstance(value, dict) and 'count' in value:
                        memory_summary.append(f"- {key}: {value.get('count', 0)} entries")
                    else:
                        memory_summary.append(f"- {key}: {len(str(value))} chars")
                
                logger.info(f"{'  ' * depth}│  💾 Found relevant memory:")
                for summary in memory_summary:
                    logger.info(f"{'  ' * depth}│  {summary}")
                
                # Add to context so neurons can use it
                self.context['_memory'] = memory_context
            else:
                logger.info(f"{'  ' * depth}│  ℹ️  No relevant memory found")
        
        # Neuron 1: Decompose goal into minimal neurons
        logger.info(f"{'  ' * depth}╭─ Decompose")
        neurons = self._micro_decompose(goal, depth)
        
        if not neurons:
            logger.error(f"{'  ' * depth}   ❌ No neurons generated")
            return {'success': False, 'error': 'Could not decompose goal'}
        
        logger.info(f"{'  ' * depth}├─ Generated {len(neurons)} neurons")
        for neuron in neurons:
            logger.info(f"{'  ' * depth}│  {neuron.index}. {neuron.description}")
        
        # Execute each neuron sequentially
        all_results = []
        for neuron in neurons:
            logger.info(f"{'  ' * depth}├─ Neuron {neuron.index}")
            
            try:
                result = self._execute_neuron(neuron, goal)
                neuron.result = result
                all_results.append(result)
                
                # Store in context (auto-saves large data to disk)
                context_key = f'neuron_{depth}_{neuron.index}'
                compact_result = compact_data(result, context_key=context_key)
                self.context[context_key] = compact_result
                
            except Exception as e:
                logger.error(f"{'  ' * depth}│  ❌ Neuron {neuron.index} failed: {e}")
                neuron.result = {'error': str(e)}
                all_results.append(neuron.result)
        
        # Final: Aggregate results
        logger.info(f"{'  ' * depth}╰─ Aggregate")
        final_result = self._micro_aggregate(goal, neurons, all_results)
        
        # CRITICAL: Check if goal is actually complete
        if depth == 0:  # Only validate at root level
            logger.info(f"{'  ' * depth}╰─ Goal Completion Check")
            is_complete = self._validate_goal_completion(goal, final_result)
            
            if not is_complete:
                logger.warning(f"{'  ' * depth}   ⚠️  Goal may not be fully complete")
                # Ask LLM what's missing
                missing_info = self._check_what_is_missing(goal, final_result)
                logger.info(f"{'  ' * depth}   📋 Missing: {missing_info}")
                
                # Auto-retry: Add a corrective neuron
                logger.info(f"{'  ' * depth}   🔄 Adding corrective neuron...")
                corrective_goal = self._generate_corrective_goal(goal, missing_info, final_result)
                logger.info(f"{'  ' * depth}   🎯 Corrective goal: {corrective_goal}")
                
                # Execute corrective neuron
                corrective_neuron = Neuron(
                    description=corrective_goal,
                    index=len(neurons) + 1,
                    depth=depth
                )
                
                try:
                    corrective_result = self._execute_neuron(corrective_neuron, goal)
                    logger.info(f"{'  ' * depth}   ✅ Corrective neuron complete")
                    
                    # Append corrective result and re-aggregate
                    if isinstance(corrective_result, dict) and corrective_result.get('success'):
                        all_results.append(corrective_result)
                        neurons.append(corrective_neuron)
                        # Re-aggregate with updated results
                        final_result = self._micro_aggregate(goal, neurons, all_results)
                    
                except Exception as e:
                    logger.error(f"{'  ' * depth}   ❌ Corrective neuron failed: {e}")

        
        return {
            'success': True,
            'goal': goal,
            'depth': depth,
            'neurons': neurons,
            'results': all_results,
            'final': final_result
        }
    
    def _execute_neuron(self, neuron: Neuron, parent_goal: str) -> Any:
        """
        Execute a single neuron with validation and auto-spawning.
        
        Flow:
        1. Check if this neuron needs to iterate over previous results (pre-execution spawning)
        2. Find tool and determine params
        3. Execute tool
        4. Detect if result needs spawning (post-execution spawning)
        5. Validate result
        6. Retry if validation fails (max 2 times)
        """
        indent = '  ' * neuron.depth
        
        # Pre-execution check: Does this neuron need spawning?
        if neuron.depth < self.MAX_DEPTH - 1:
            logger.info(f"{indent}│  ├─ Checking for pre-execution spawning...")
            logger.info(f"{indent}│  │  Context keys: {list(self.context.keys())}")
            
            # Type 1: Iteration spawning ("for each activity")
            context_list = self._find_context_list_for_iteration(neuron.description)
            if context_list:
                logger.info(f"{indent}│  ├─ 🌿 Pre-execution spawning (iterate over context)")
                return self._spawn_dendrites_from_context(neuron, context_list, parent_goal)
            
            # Type 2: Multi-step spawning ("start AND end", "both X and Y")
            subtasks = self._detect_multi_step_task(neuron.description)
            if subtasks and len(subtasks) > 1:
                logger.info(f"{indent}│  ├─ 🌿 Pre-execution spawning ({len(subtasks)} sub-tasks)")
                return self._spawn_dendrites_for_subtasks(neuron, subtasks, parent_goal)
            
            logger.info(f"{indent}│  │  No spawning needed")
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            logger.info(f"{indent}│  ├─ Attempt {attempt}/{self.MAX_RETRIES}")
            
            # Step 1: Find tool
            tool = self._micro_find_tool(neuron.description)
            if not tool:
                logger.warning(f"{indent}│  │  ⚠️  No tool found, using AI")
                return self._micro_ai_response(neuron.description)
            
            logger.info(f"{indent}│  ├─ Tool: {tool.name}")
            
            # Step 2: Determine parameters
            try:
                params = self._micro_determine_params(neuron.description, tool, self.context)
            except Exception as param_error:
                import traceback
                logger.error(f"{indent}│  ❌ Parameter determination failed: {param_error}")
                logger.info(f"{indent}│  Traceback:\n{traceback.format_exc()}")
                raise
            
            try:
                params_str = json.dumps(params)[:100]
            except Exception as je:
                params_str = str(params)[:100]
            logger.info(f"{indent}│  ├─ Params: {params_str}")
            
            # Step 2.5: Validate Python code for executeDataAnalysis
            if tool.name == 'executeDataAnalysis' and 'python_code' in params:
                validated_code = self._validate_python_code(
                    neuron.description,
                    params['python_code'],
                    self.context
                )
                if validated_code:
                    logger.info(f"{indent}│  ├─ ✅ Code validated")
                    params['python_code'] = validated_code
            
            # Step 3: Execute tool
            try:
                # Special case: executeDataAnalysis needs context
                if tool.name == 'executeDataAnalysis':
                    result = tool.execute(**params, **self.context)
                else:
                    result = tool.execute(**params)
                logger.info(f"{indent}│  ├─ Result: {self._summarize_result(result)}")
                
                # Check if execution returned an error with retry flag
                if isinstance(result, dict) and not result.get('success', True):
                    error_msg = result.get('error', 'Unknown error')
                    should_retry = result.get('retry', False)
                    hint = result.get('hint', '')
                    
                    logger.warning(f"{indent}│  │  ⚠️  Tool returned error: {error_msg}")
                    if hint:
                        logger.info(f"{indent}│  │  💡 Hint: {hint}")
                    
                    if should_retry and attempt < self.MAX_RETRIES:
                        logger.info(f"{indent}│  │  🔄 Retrying with corrected code...")
                        # Re-validate and regenerate code
                        continue
                    elif not should_retry:
                        # Fatal error, don't retry
                        logger.error(f"{indent}│  │  ❌ Fatal error, cannot retry")
                        raise Exception(error_msg)
                    
            except Exception as e:
                import traceback
                error_msg = str(e)
                logger.warning(f"{indent}│  │  ⚠️  Execution error: {error_msg}")
                logger.debug(f"{indent}│  │  Traceback: {traceback.format_exc()}")
                
                # ERROR REFLECTION: Ask LLM what went wrong
                if "404" in error_msg or "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                    logger.info(f"{indent}│  │  🔍 Reflecting on error - likely hallucinated parameter")
                    
                    reflection = self._reflect_on_error(
                        neuron_desc=neuron.description,
                        tool_name=tool.name,
                        params=params,
                        error=error_msg,
                        context=self.context
                    )
                    
                    logger.info(f"{indent}│  │  💡 Reflection: {reflection.get('diagnosis', 'Unknown')}")
                    
                    # If reflection suggests parameter fix, try it
                    if reflection.get('suggested_fix'):
                        logger.info(f"{indent}│  │  🔧 Applying suggested fix...")
                        suggested_params = reflection.get('suggested_params', {})
                        if suggested_params:
                            try:
                                logger.info(f"{indent}│  │  🔄 Retry with: {json.dumps(suggested_params)[:100]}")
                                result = tool.execute(**suggested_params)
                                logger.info(f"{indent}│  ├─ Result: {self._summarize_result(result)}")
                                # Success! Continue with validation
                            except Exception as retry_error:
                                logger.warning(f"{indent}│  │  ❌ Suggested fix failed: {retry_error}")
                                if attempt == self.MAX_RETRIES:
                                    raise
                                continue
                        else:
                            # No suggested params, retry from scratch
                            if attempt == self.MAX_RETRIES:
                                raise
                            continue
                    else:
                        # No fix suggested, retry
                        if attempt == self.MAX_RETRIES:
                            raise
                        continue
                else:
                    # Not a 404 error, just retry
                    if attempt == self.MAX_RETRIES:
                        raise
                    continue
            
            # Step 4: Detect list → spawn dendrites
            if neuron.depth < self.MAX_DEPTH - 1:  # Leave room for one more level
                spawn_needed = self._micro_detect_spawn_needed(neuron.description, result)
                
                if spawn_needed:
                    logger.info(f"{indent}│  ├─ 🌿 Spawning dendrites")
                    result = self._spawn_dendrites(neuron, result, parent_goal)
            
            # Step 5: Validate
            is_valid = self._micro_validate(parent_goal, neuron.description, result)
            logger.info(f"{indent}│  ├─ Valid: {is_valid}")
            
            if is_valid:
                neuron.validated = True
                logger.info(f"{indent}│  ╰─ ✅ Neuron complete")
                return result
            else:
                logger.warning(f"{indent}│  │  ⚠️  Validation failed, retrying")
                if attempt == self.MAX_RETRIES:
                    logger.error(f"{indent}│  ╰─ ❌ Max retries reached, accepting result")
                    return result
        
        return result
    
    def _find_context_list_for_iteration(self, neuron_desc: str) -> Optional[List[Dict]]:
        """
        Check if this neuron needs to iterate over a list from context.
        
        Returns the list if found, None otherwise.
        """
        # Check for "for each" / "each activity" / "all items" keywords
        iteration_keywords = ['for each', 'each activity', 'each item', 'all activities', 'every activity']
        if not any(kw in neuron_desc.lower() for kw in iteration_keywords):
            return None
        
        # Look for lists in context (from previous neurons)
        for key, value in self.context.items():
            if not isinstance(value, dict):
                continue
            
            # Check if this looks like a list result
            items = self._extract_list_items(value)
            if items and len(items) > 1:
                return items
        
        return None
    
    def _spawn_dendrites_from_context(self, parent_neuron: Neuron, items: List[Dict], parent_goal: str) -> Any:
        """
        Spawn dendrites based on context list (pre-execution spawning).
        
        This is used when a neuron like "Get kudos for each activity" needs to iterate
        over a list from a previous neuron.
        """
        indent = '  ' * parent_neuron.depth
        logger.info(f"{indent}│  ├─ Found {len(items)} items in context")
        
        # Extract what to do with each item from neuron description
        item_goal_template = self._micro_extract_item_goal_from_desc(parent_neuron.description)
        logger.info(f"{indent}│  ├─ Item goal: {item_goal_template}")
        
        # Spawn dendrite for each item
        dendrite_results = []
        for i, item in enumerate(items, 1):
            logger.info(f"{indent}│  ├─ Dendrite {i}/{len(items)}")
            
            # Format goal for this specific item
            item_goal = self._format_item_goal(item_goal_template, item, i)
            
            # Create dendrite neuron
            dendrite = Neuron(
                description=item_goal,
                index=i,
                depth=parent_neuron.depth + 1
            )
            
            # IMPORTANT: Store item data in context so it can be used for parameter extraction
            item_context_key = f'dendrite_item_{parent_neuron.depth + 1}_{i}'
            self.context[item_context_key] = item
            
            # Execute recursively
            dendrite_result = self.execute_goal(item_goal, depth=parent_neuron.depth + 1)
            
            # Clean up item context after execution
            self.context.pop(item_context_key, None)
            
            dendrite.result = dendrite_result
            parent_neuron.spawned_dendrites.append(dendrite)
            dendrite_results.append(dendrite_result)
        
        logger.info(f"{indent}│  ╰─ All dendrites complete, aggregating")
        
        # Create aggregated result
        aggregated = {
            'success': True,
            'items_processed': len(items),
            'dendrite_results': dendrite_results,
            'items': items
        }
        
        return aggregated
    
    def _spawn_dendrites(self, parent_neuron: Neuron, result: Any, parent_goal: str) -> Any:
        """
        Spawn dendrites (sub-neurons) for each item in a list result.
        
        Args:
            parent_neuron: The neuron that produced the list
            result: The result containing a list
            parent_goal: Original goal for context
            
        Returns:
            Enhanced result with dendrite outputs aggregated
        """
        indent = '  ' * parent_neuron.depth
        
        # Extract items from result
        items = self._extract_list_items(result)
        if not items:
            logger.info(f"{indent}│  │  No items to spawn for")
            return result
        
        logger.info(f"{indent}│  ├─ Found {len(items)} items")
        
        # Micro-prompt: What should we do with each item?
        item_goal_template = self._micro_extract_item_goal(parent_neuron.description, result)
        logger.info(f"{indent}│  ├─ Item goal: {item_goal_template}")
        
        # Spawn dendrite for each item (sequential execution)
        dendrite_results = []
        for i, item in enumerate(items, 1):
            logger.info(f"{indent}│  ├─ Dendrite {i}/{len(items)}")
            
            # Format goal for this specific item
            item_goal = self._format_item_goal(item_goal_template, item, i)
            
            # Create dendrite neuron
            dendrite = Neuron(
                description=item_goal,
                index=i,
                depth=parent_neuron.depth + 1
            )
            
            # IMPORTANT: Store item data in context so it can be used for parameter extraction
            item_context_key = f'dendrite_item_{parent_neuron.depth + 1}_{i}'
            self.context[item_context_key] = item
            
            # Execute recursively (this is the key!)
            dendrite_result = self.execute_goal(item_goal, depth=parent_neuron.depth + 1)
            
            # Clean up item context after execution
            self.context.pop(item_context_key, None)
            
            dendrite.result = dendrite_result
            parent_neuron.spawned_dendrites.append(dendrite)
            dendrite_results.append(dendrite_result)
        
        logger.info(f"{indent}│  ╰─ All dendrites complete, aggregating")
        
        # Aggregate dendrite results back into parent result
        aggregated = self._micro_aggregate_dendrites(result, items, dendrite_results)
        return aggregated
    
    def _detect_multi_step_task(self, neuron_desc: str) -> Optional[List[str]]:
        """
        Detect if this neuron requires multiple sub-tasks (e.g., "get start AND end timestamps").
        
        Returns list of sub-task descriptions if detected, None otherwise.
        """
        import re
        
        # Keywords that suggest multiple parallel tasks
        multi_keywords = [
            'start and end',
            'both',
            'and also',
            'as well as',
            'along with'
        ]
        
        # Check if description mentions needing multiple things
        desc_lower = neuron_desc.lower()
        if not any(kw in desc_lower for kw in multi_keywords):
            return None
        
        # CRITICAL: First check if there's a tool that can do this in one call
        # Extract keywords for tool search
        keywords = re.findall(r'\b\w{4,}\b', neuron_desc.lower())
        
        # Search for tools that match
        relevant_tools = []
        for tool in self.tools.list_tools():
            tool_text = f"{tool.name} {tool.description}".lower()
            score = sum(1 for kw in keywords if kw in tool_text)
            if score > 2:  # Good match
                relevant_tools.append((score, tool))
        
        if relevant_tools:
            # Sort by score and check top tool
            relevant_tools.sort(reverse=True, key=lambda x: x[0])
            top_tool = relevant_tools[0][1]
            
            # If tool description mentions "start and end" or "both", it can handle this
            if any(kw in top_tool.description.lower() for kw in ['start and end', 'both', 'range']):
                logger.debug(f"   │  │  ✓ Found tool {top_tool.name} that handles multi-step task")
                return None  # Don't spawn - let tool handle it
        
        # No suitable tool found, need to decompose
        # Use LLM to decompose into ATOMIC sub-tasks
        # CRITICAL: Show what data is already available to avoid "fetch" tasks
        context_summary = ""
        if self.context:
            available_keys = [k for k in self.context.keys() if not k.startswith('_')]
            if available_keys:
                context_summary = f"\n\nData already in context (DON'T create 'fetch' tasks for these):\n"
                for key in available_keys[:5]:  # Show first 5
                    value = self.context[key]
                    if isinstance(value, dict):
                        if '_ref_id' in value:
                            context_summary += f"  - {key}: Large data (already loaded)\n"
                        elif 'unix_timestamp' in value:
                            context_summary += f"  - {key}: Timestamp = {value.get('unix_timestamp')}\n"
                        elif 'result' in value:
                            context_summary += f"  - {key}: Result already computed\n"
                        else:
                            context_summary += f"  - {key}: Data available\n"
        
        prompt = f"""Break this into ATOMIC sub-tasks that each call ONE tool.

Task: {neuron_desc}
{context_summary}
IMPORTANT Rules:
1. Each sub-task must be ONE specific tool call (e.g., "Call dateToUnixTimestamp for January 1").
2. Do NOT create "fetch" or "get result" tasks for data that's already in context!
3. Do NOT create tasks like "Parse January" or "Extract value" - those aren't tool calls.
4. If data is already available in context, the sub-task should USE it, not fetch it.

If this can be done with a SINGLE tool call, output "SINGLE_TASK".

Output (numbered list of specific tool calls, or SINGLE_TASK):"""
        
        response = self.ollama.generate(
            prompt,
            system="Decompose into atomic tool calls. Each sub-task = ONE tool execution.",
            temperature=0.1
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        if 'SINGLE_TASK' in response_str.upper():
            return None
        
        # Extract numbered items
        import re
        subtasks = []
        for match in re.finditer(r'^\d+\.\s*(.+)$', response_str, re.MULTILINE):
            subtasks.append(match.group(1).strip())
        
        # Only return if we have 2-3 subtasks (not 5+)
        if 2 <= len(subtasks) <= 3:
            return subtasks
        else:
            logger.debug(f"   │  │  ⚠️  Too many subtasks ({len(subtasks)}), treating as single task")
            return None
    
    def _spawn_dendrites_for_subtasks(self, parent_neuron: Neuron, subtasks: List[str], parent_goal: str) -> Any:
        """
        Spawn dendrites for multiple sub-tasks that need to be completed.
        
        Example: "Get start and end timestamps" spawns 2 dendrites:
        - Dendrite 1: "Get start timestamp"
        - Dendrite 2: "Get end timestamp"
        """
        indent = '  ' * parent_neuron.depth
        logger.info(f"{indent}│  ├─ Sub-tasks:")
        for i, task in enumerate(subtasks, 1):
            logger.info(f"{indent}│  │  {i}. {task}")
        
        # Execute each sub-task
        dendrite_results = []
        for i, task_desc in enumerate(subtasks, 1):
            logger.info(f"{indent}│  ├─ Sub-task {i}/{len(subtasks)}")
            
            # Create dendrite neuron
            dendrite = Neuron(
                description=task_desc,
                index=i,
                depth=parent_neuron.depth + 1
            )
            
            # Execute recursively
            dendrite_result = self.execute_goal(task_desc, depth=parent_neuron.depth + 1)
            
            dendrite.result = dendrite_result
            parent_neuron.spawned_dendrites.append(dendrite)
            dendrite_results.append(dendrite_result)
        
        logger.info(f"{indent}│  ╰─ All sub-tasks complete, aggregating")
        
        # Aggregate results from all sub-tasks
        aggregated = {
            'success': True,
            'subtasks_completed': len(subtasks),
            'results': dendrite_results
        }
        
        # Merge specific fields if available (e.g., timestamps)
        for result in dendrite_results:
            if isinstance(result, dict):
                # Merge timestamp fields
                for key in ['after_unix', 'before_unix', 'unix_timestamp', 'start_timestamp', 'end_timestamp']:
                    if key in result:
                        aggregated[key] = result[key]
        
        return aggregated
    
    # ========================================================================
    # Micro-Prompts (each 50-100 tokens)
    # ========================================================================
    
    def _micro_decompose(self, goal: str, depth: int) -> List[Neuron]:
        """Micro-prompt: Decompose goal into 1-4 neurons."""
        
        # STEP 0: Get expert strategy recommendation first
        strategy_advice = self._get_strategy_advice(goal)
        
        prompt = f"""Break this goal into 1-4 simple steps. NO DUPLICATES.

Goal: {goal}

{strategy_advice}

Rules:
- Each step = ONE action (ONE tool call OR one AI response)
- If goal asks "how many X activities", that's typically: (1) convert dates, (2) fetch ALL activities, (3) use executeDataAnalysis with Python to count type=X
- When fetching data, get ALL data first, then filter/analyze in a separate step
- Format/display/report steps go at the end
- NO DUPLICATE STEPS - each step must be different
- IMPORTANT: If goal mentions a date period (like "January 2024", "September 2025", "last week"):
  * First step: Convert date to timestamps (start and end)
  * Second step: Fetch data using those timestamps
  * Third step: Use executeDataAnalysis to count/filter (NO new fetch, work with existing data)
  * Fourth step: Format results
- If goal asks for a specific activity TYPE (e.g., "running activities", "rides"):
  * The filtering step should say "Use executeDataAnalysis to count activities where type=Run"
  * Do NOT rely on AI counting - use Python for accurate counting

Examples:
- "How many runs in Jan 2024?" → (1) Convert Jan 2024 to timestamps, (2) Fetch all activities, (3) Use executeDataAnalysis to count where sport_type contains 'Run'
- "Show my 3 rides from last month" → (1) Convert last month to timestamps, (2) Fetch all activities, (3) Use executeDataAnalysis to filter type=Ride and take first 3, (4) Format

Output numbered list (1-4 steps, NO duplicates):"""
        
        response = self.ollama.generate(
            prompt,
            system="Decompose goals into minimal steps. NO duplicates. Prefer executeDataAnalysis for counting/filtering. Output numbered list only.",
            temperature=0.2  # Lower temperature for more deterministic output
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        # Parse neurons
        neurons = []
        seen_descriptions = set()  # Track to prevent duplicates
        
        for line in response_str.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            match = re.match(r'^[\d\-\*\.)\]]+\s*(.+)$', line)
            if match:
                description = match.group(1).strip()
                
                # Check for duplicates (normalize text for comparison)
                normalized = description.lower().strip('.')
                if normalized in seen_descriptions:
                    logger.warning(f"   │  ⚠️  Skipping duplicate neuron: {description}")
                    continue
                
                seen_descriptions.add(normalized)
                neurons.append(Neuron(
                    description=description,
                    index=len(neurons) + 1,
                    depth=depth
                ))
        
        # Limit to 4 neurons maximum
        if len(neurons) > 4:
            logger.warning(f"   │  ⚠️  Too many neurons ({len(neurons)}), keeping first 4")
            neurons = neurons[:4]
        
        return neurons
    
    def _get_strategy_advice(self, goal: str) -> str:
        """
        Get expert strategy advice for approaching the goal.
        This guides the AI towards better tool selection (especially Python for counting).
        """
        # Detect task characteristics
        is_counting = any(word in goal.lower() for word in ['how many', 'count', 'number of'])
        is_filtering = any(word in goal.lower() for word in ['filter', 'where', 'type=', 'matching'])
        mentions_large_data = any(word in goal.lower() for word in ['all', 'every', 'total'])
        has_date_range = any(word in goal.lower() for word in ['month', 'week', 'year', 'september', 'january', 'last'])
        
        advice_parts = []
        
        # Force Python counting if configured or if task involves counting
        force_python = self.config.get('ollama', {}).get('force_python_counting', True)
        
        if is_counting or is_filtering:
            if force_python or mentions_large_data:
                advice_parts.append("⚠️ CRITICAL: Use executeDataAnalysis tool with Python code for counting/filtering.")
                advice_parts.append("   Reason: AI models (even 32B+) can miscount. Python is 100% reliable.")
                advice_parts.append("   Example: executeDataAnalysis(python_code='result = {\"count\": len([x for x in data[\"neuron_0_2\"][\"activities\"] if \"Run\" in x.get(\"sport_type\", \"\")])}')")
            
            if mentions_large_data:
                advice_parts.append("⚠️ Large dataset detected: Counting 50+ items by AI is unreliable. MUST use Python.")
        
        if has_date_range:
            advice_parts.append("💡 Date range detected: First convert to timestamps, then fetch once, then analyze.")
        
        if not advice_parts:
            return ""
        
        strategy = "\n🎯 EXPERT STRATEGY RECOMMENDATION:\n" + "\n".join(advice_parts) + "\n"
        logger.info(f"   💡 Strategy advice provided for: {goal[:50]}...")
        return strategy
    
    def _validate_python_code(self, task: str, python_code: str, context: Dict) -> Optional[str]:
        """
        Validate that Python code will correctly answer the task.
        Returns simplified/corrected code or None if validation fails.
        """
        import ast
        
        # FIRST: Check Python syntax before asking LLM
        try:
            ast.parse(python_code)
        except SyntaxError as e:
            logger.warning(f"   │  │  ⚠️  Python syntax error detected: {e}")
            return None  # Force regeneration with new code
        
        # Get context summary for validation
        context_summary = []
        for key, value in context.items():
            if isinstance(value, dict):
                if '_format' in value and value.get('_format') == 'disk_reference':
                    context_summary.append(f"  ✓ {key}: LARGE DATA - {value.get('summary', 'N/A')}")
                    context_summary.append(f"     → Use: data['{key}']['_ref_id'] then load_data_reference(...)")
                elif 'success' in value and 'result' in value:
                    context_summary.append(f"  ✗ {key}: Scalar result = {value.get('result')} (NOT a data reference)")
                else:
                    context_summary.append(f"  {key}: {self._summarize_result(value)}")
        
        prompt = f"""Validate this Python code will correctly answer the task.

TASK: {task}

PYTHON CODE:
```python
{python_code}
```

AVAILABLE CONTEXT KEYS:
{chr(10).join(context_summary)}

KEY GUIDE:
✓ = Large data reference (has _ref_id, must load with load_data_reference)
✗ = Scalar result (just a number/value, NOT loadable)

VALIDATION CHECKS:
1. Does the code use the CORRECT context key? (✓ keys for data, not ✗ keys)
2. Does it answer the EXACT question asked?
3. Does it access fields that actually exist in the data?
4. Is it unnecessarily complex? (Simple is better)
5. Does it handle the disk reference correctly? (load_data_reference returns {{'activities': [...], 'count': N}})

CRITICAL: For counting tasks, the code should be SIMPLE:
- Load data: loaded = load_data_reference(ref_id)
- Count: result = len([x for x in loaded['activities'] if condition])
- DON'T try to extract extra fields like 'date', 'description' unless specifically asked

COMMON ERRORS TO FIX:
- Using neuron_0_2 when it's a scalar result, should use neuron_0_1 (the actual data)
- Trying to load_data_reference on a scalar result
- Accessing wrong fields in the data structure

If code is CORRECT, output: VALID
If code needs fixing, output corrected Python code (just the code, no explanation)
If code is completely wrong, output: INVALID

Response:"""
        
        response = self.ollama.generate(
            prompt,
            system="You validate Python code. Output VALID, corrected code, or INVALID.",
            temperature=0.1
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        if 'VALID' in response_str.upper() and 'INVALID' not in response_str.upper():
            logger.debug(f"   │  │  ✓ Code validation passed")
            return python_code
        elif 'INVALID' in response_str.upper():
            logger.warning(f"   │  │  ⚠️  Code validation failed - code is invalid")
            return None
        else:
            # LLM provided corrected code
            # Extract code block
            code_match = re.search(r'```(?:python)?\n(.+?)\n```', response_str, re.DOTALL)
            if code_match:
                corrected = code_match.group(1).strip()
                logger.info(f"   │  │  🔧 Code corrected by validator")
                logger.debug(f"   │  │  Original: {python_code[:100]}...")
                logger.debug(f"   │  │  Corrected: {corrected[:100]}...")
                return corrected
            else:
                # Try to extract code without markers
                corrected = response_str.strip()
                if corrected and not corrected.startswith('VALID') and not corrected.startswith('INVALID'):
                    logger.info(f"   │  │  🔧 Code corrected by validator")
                    return corrected
                else:
                    logger.warning(f"   │  │  ⚠️  Could not extract corrected code")
                    return python_code  # Return original if we can't parse correction
    
    def _micro_find_tool(self, neuron_desc: str) -> Optional[Any]:
        """Micro-prompt: Which tool for this neuron?"""
        
        # Check if this is a counting/filtering task - MUST use Python tool
        counting_keywords = ['count', 'how many', 'filter', 'where', 'matching', 'with type']
        is_counting = any(kw in neuron_desc.lower() for kw in counting_keywords)
        
        # If counting/filtering, force executeDataAnalysis tool
        if is_counting:
            for tool in self.tools.list_tools():
                if tool.name.lower() == 'executedataanalysis':
                    logger.info(f"   │  │  🐍 Counting task detected, forcing Python tool: {tool.name}")
                    return tool
        
        # Check if this is a formatting/display task (no tool needed)
        formatting_keywords = ['format', 'display', 'show', 'report', 'present', 'output', 'print', 'organize']
        has_format_keyword = any(kw in neuron_desc.lower() for kw in formatting_keywords)
        
        # Check if task mentions working with existing/fetched/previous data (for formatting only)
        works_with_existing = any(word in neuron_desc.lower() for word in [
            'existing', 'available', 'fetched', 'current results', 'all three', 
            'above', 'results', 'data', 'from previous', 'from fetched', 'first'
        ])
        
        has_context = len(self.context) > 0
        
        # Check if context contains a data reference (compacted large data)
        has_data_reference = any(
            isinstance(v, dict) and v.get('_format') == 'disk_reference' 
            for v in self.context.values()
        )
        
        # If it's about formatting EXISTING data...
        if has_format_keyword and (works_with_existing or has_context):
            # If data is compacted to disk, we need executeDataAnalysis to load it
            if has_data_reference:
                logger.info(f"   │  │  💡 Detected formatting of compacted data, suggesting executeDataAnalysis")
                # Return executeDataAnalysis tool for loading and formatting
                for tool in self.tools.list_tools():
                    if tool.name.lower() == 'executedataanalysis':
                        return tool
                # Fallback if tool not found
                logger.warning(f"   │  │  ⚠️  executeDataAnalysis tool not found, using AI")
                return None
            else:
                # Small data in context, AI can format directly
                logger.info(f"   │  │  💡 Detected formatting task on existing data, will use AI response")
                return None
        
        # Intent-based matching with stronger signals
        desc_lower = neuron_desc.lower()
        relevant_tools = []
        
        for tool in self.tools.list_tools():
            score = 0
            tool_name_lower = tool.name.lower()
            tool_desc_lower = tool.description.lower()
            
            # Strong intent signals (worth 10 points each)
            intent_signals = {
                'fetch.*activities': ['getmyactivities', 'getdashboardfeed'],
                'get.*my.*activities': ['getmyactivities'],
                'get.*strava.*activities': ['getmyactivities'],
                'retrieve.*activities': ['getmyactivities', 'getdashboardfeed'],
                'convert.*timestamp': ['datetounixtimestamp', 'getdaterangetimestamps'],
                'start.*end.*timestamp': ['getdaterangetimestamps'],
                'date.*range': ['getdaterangetimestamps'],
                'give.*kudos': ['givekudos', 'givekudostoparticipants'],
                'validate.*timestamp': ['validatetimestamp'],
                'current.*date': ['getcurrentdatetime'],
                # Python execution for counting/filtering
                'count.*activities': ['executedataanalysis'],
                'count.*where': ['executedataanalysis'],
                'filter.*where': ['executedataanalysis'],
                'executedataanalysis.*count': ['executedataanalysis'],
                'python.*count': ['executedataanalysis'],
                'use.*executedataanalysis': ['executedataanalysis'],
            }
            
            for pattern, matching_tools in intent_signals.items():
                if re.search(pattern, desc_lower):
                    if tool_name_lower in matching_tools:
                        score += 10
            
            # Extract keywords for general matching (worth 1 point each)
            keywords = re.findall(r'\b\w{4,}\b', desc_lower)
            tool_text = f"{tool_name_lower} {tool_desc_lower}"
            score += sum(1 for kw in keywords if kw in tool_text)
            
            # Boost for exact key phrase matches in description (worth 5 points)
            key_phrases = {
                'my activities': 'getmyactivities',
                'my own': 'getmyactivities',
                'strava activities': 'getmyactivities',
                'friends activities': 'getdashboardfeed',
                'dashboard feed': 'getdashboardfeed',
                'executedataanalysis': 'executedataanalysis',
                'python code': 'executedataanalysis',
                'count activities': 'executedataanalysis',
            }
            
            for phrase, matching_tool in key_phrases.items():
                if phrase in desc_lower and tool_name_lower == matching_tool:
                    score += 5
            
            if score > 0:
                relevant_tools.append((score, tool))
        
        if not relevant_tools:
            return None
        
        # Sort by score and take top 5
        relevant_tools.sort(reverse=True, key=lambda x: x[0])
        top_tools = [t[1] for t in relevant_tools[:5]]
        
        logger.debug(f"   │  │  Top tools: {[(t.name, s) for s, t in relevant_tools[:5]]}")
        
        # If top tool has significantly higher score, use it directly
        if len(relevant_tools) >= 2:
            top_score = relevant_tools[0][0]
            second_score = relevant_tools[1][0]
            if top_score >= second_score + 5:  # Clear winner
                logger.debug(f"   │  │  ✓ Clear winner: {relevant_tools[0][1].name} (score {top_score} vs {second_score})")
                return relevant_tools[0][1]
        
        # Otherwise, ask LLM to pick from top 5
        tool_list = "\n".join([f"- {t.name}: {t.description}" for t in top_tools])
        
        prompt = f"""Select the BEST tool for this task:

Task: {neuron_desc}

Available tools:
{tool_list}

Instructions:
- Choose the tool that most directly accomplishes the task
- For fetching data: use get/fetch tools
- For converting dates: use timestamp tools
- For counting/filtering: if data already exists, don't use tools (use AI analysis)

Output ONLY the tool name:"""
        
        response = self.ollama.generate(
            prompt,
            system="You select tools. Output only the tool name, nothing else.",
            temperature=0.1
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        tool_name = response_str.strip().split()[0]
        
        # Find matching tool
        selected_tool = None
        for tool in top_tools:
            if tool.name.lower() in tool_name.lower():
                selected_tool = tool
                break
        
        if not selected_tool:
            selected_tool = top_tools[0] if top_tools else None
        
        # VALIDATION: Double-check if tool matches the task
        if selected_tool and len(top_tools) > 1:
            validation_prompt = f"""Is this tool correct for the task?

Task: {neuron_desc}
Selected tool: {selected_tool.name} - {selected_tool.description}

Question: Does this tool do what the task asks?
- If YES, output: YES
- If NO, output: NO and suggest better tool name

Answer:"""
            
            validation_response = self.ollama.generate(
                validation_prompt,
                system="Validate tool selection. Output YES or NO.",
                temperature=0.1
            )
            
            validation_str = str(validation_response) if not isinstance(validation_response, str) else validation_response
            
            if 'no' in validation_str.lower():
                logger.warning(f"   │  │  ⚠️  Tool validation failed: {selected_tool.name} may not be correct")
                # Try to extract suggested tool name
                for tool in top_tools:
                    if tool.name.lower() in validation_str.lower() and tool != selected_tool:
                        logger.info(f"   │  │  🔄 Switching to suggested tool: {tool.name}")
                        selected_tool = tool
                        break
        
        return selected_tool
    
    def _clarify_vague_terms(self, neuron_desc: str, tool: Any, context: Dict) -> str:
        """
        Inter-neuron communication: Ask decomposer to clarify vague terms.
        
        This allows Neuron N to ask "what did you mean by X?" to the neuron
        that created the task decomposition.
        
        Returns: Clarified description or original if no clarification needed
        """
        # Detect vague terms that need clarification
        vague_terms = []
        
        # Common vague patterns
        vague_patterns = {
            r'\bkudos data\b': 'kudos data',
            r'\bextract.*data\b': 'extract data',
            r'\bprocess.*items\b': 'process items',
            r'\bhandle.*activities\b': 'handle activities',
            r'\bget.*information\b': 'get information',
            r'\bfetch.*details\b': 'fetch details',
        }
        
        desc_lower = neuron_desc.lower()
        for pattern, term in vague_patterns.items():
            if re.search(pattern, desc_lower):
                vague_terms.append(term)
        
        if not vague_terms:
            return neuron_desc  # No vague terms, no clarification needed
        
        # Get original goal from context (if available)
        original_goal = self.context.get('_original_goal', 'Unknown goal')
        
        # Get sample data from context to show actual field names available
        sample_data_info = ""
        for key, value in context.items():
            if key.startswith('_') or key.startswith('dendrite_'):
                continue
            if isinstance(value, dict):
                if '_format' in value and value.get('_format') == 'disk_reference':
                    # Show what fields are in this large data
                    sample_data_info += f"\n  - {key} contains: {value.get('summary', 'data')}"
                elif 'result' in value:
                    # Show sample of result data
                    result = value.get('result')
                    if isinstance(result, list) and len(result) > 0:
                        first_item = result[0]
                        if isinstance(first_item, dict):
                            sample_data_info += f"\n  - {key} has items with fields: {', '.join(first_item.keys())}"
        
        # Ask for clarification from the "decomposer" (simulate inter-neuron communication)
        prompt = f"""You are the decomposer neuron that created this sub-task. A child neuron needs clarification.

ORIGINAL GOAL: {original_goal}

SUB-TASK (created by you): {neuron_desc}

TOOL SELECTED: {tool.name} - {tool.description}

AVAILABLE DATA IN CONTEXT:{sample_data_info}

QUESTION: The child neuron asks: "What exactly do you mean by '{vague_terms[0]}'?"

Think about:
1. What was the ORIGINAL goal asking for?
2. What fields/attributes should be extracted? (Use ACTUAL field names from AVAILABLE DATA above)
3. What format should the result have?

CRITICAL: Use the EXACT field names that exist in the data!
- For Strava activities, use: 'id' (NOT 'activity_id'), 'start_date' (NOT 'timestamp'), 'name', 'sport_type', 'kudos_count'
- Don't invent field names that don't exist in the data

Examples:
- Vague: "extract kudos data" 
  → Clear: "extract these fields from activities: id, start_date, name, sport_type, kudos_count"

- Vague: "process activities"
  → Clear: "for each activity, extract the 'name' and 'start_date' fields"

Output ONLY the clarified task description (rewrite the sub-task with EXACT field names):"""
        
        response = self.ollama.generate(
            prompt,
            system="You clarify vague task descriptions. Be specific about field names and formats.",
            temperature=0.1
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        clarified = response_str.strip().split('\n')[0]  # Take first line
        
        # Only use clarification if it's actually more specific (longer and mentions fields)
        if len(clarified) > len(neuron_desc) and any(word in clarified.lower() for word in ['field', 'attribute', 'name', 'type', 'count', 'id', 'timestamp']):
            return clarified
        else:
            return neuron_desc
    
    def _micro_determine_params(self, neuron_desc: str, tool: Any, context: Dict) -> Dict[str, Any]:
        """Micro-prompt: What parameters?"""
        
        # STEP 0: CLARIFY vague terms before proceeding
        # Check if neuron description contains vague terms that need clarification
        clarified_desc = self._clarify_vague_terms(neuron_desc, tool, context)
        if clarified_desc != neuron_desc:
            logger.info(f"   │  │  💬 Clarified task: {clarified_desc}")
            neuron_desc = clarified_desc  # Use clarified description
        
        param_info = "\n".join([
            f"  - {p['name']} ({p.get('type', 'any')}): {p.get('description', '')}"
            for p in tool.parameters
        ])
        
        # STEP 1: AUTO-MAP parameters from context (deterministic matching)
        # Only auto-map if the tool ACTUALLY accepts these parameters
        auto_mapped_params = {}
        param_names = [p['name'] for p in tool.parameters]
        
        # Search context for exact parameter name matches (only for params this tool accepts)
        for param_name in param_names:
            for ctx_key, ctx_value in context.items():
                # Direct key match in dict - tool accepts this param, context has it
                if isinstance(ctx_value, dict) and param_name in ctx_value:
                    auto_mapped_params[param_name] = ctx_value[param_name]
                    logger.debug(f"   │  │  🔗 Auto-mapped {param_name} = {ctx_value[param_name]} from {ctx_key}")
                    break
        
        # Find dendrite item data in context (most relevant for current execution)
        dendrite_item = None
        for key, value in context.items():
            if key.startswith('dendrite_item_') and isinstance(value, dict):
                dendrite_item = value
                break
        
        # Build context info - show what we auto-mapped and what else is available
        context_info = ""
        if auto_mapped_params:
            context_info += f"\n\nAuto-mapped parameters (ALREADY SET - do not override):\n{json.dumps(auto_mapped_params, indent=2)}"
        
        if dendrite_item:
            # Show the specific item we're processing
            context_info += f"\n\nCurrent item data:\n{json.dumps(dendrite_item, indent=2)[:500]}"
        elif context:
            # Show detailed data from previous steps with actual values
            context_info += "\n\nData available from previous neurons (YOUR DISPOSAL - use as needed):"
            
            # UNIVERSAL CONTEXT GUIDE: Show what's available for ANY tool
            context_info += "\n\nCONTEXT KEYS AVAILABLE:"
            for key, value in context.items():
                if key.startswith('_'):  # Skip internal keys like _original_goal
                    continue
                    
                if isinstance(value, dict):
                    if '_format' in value and value.get('_format') == 'disk_reference':
                        # This is a DATA reference (for executeDataAnalysis)
                        context_info += f"\n  📦 {key}: LARGE DATA - {value.get('summary', 'data reference')}"
                        context_info += f"\n     → For Python: data['{key}']['_ref_id'] then load_data_reference(...)"
                    elif 'success' in value and 'result' in value:
                        # This is a RESULT from a previous neuron - SHOW THE ACTUAL DATA!
                        result_data = value.get('result')
                        # Format result nicely for display
                        if isinstance(result_data, list) and len(result_data) > 0:
                            result_str = json.dumps(result_data, indent=2)[:500]  # Show up to 500 chars
                            context_info += f"\n  ✅ {key}: Result (list with {len(result_data)} items)"
                            context_info += f"\n     DATA: {result_str}"
                            context_info += f"\n     → To use as parameter: Copy this data directly into your JSON"
                        elif isinstance(result_data, dict):
                            result_str = json.dumps(result_data, indent=2)[:500]
                            context_info += f"\n  ✅ {key}: Result (dict)"
                            context_info += f"\n     DATA: {result_str}"
                            context_info += f"\n     → To use as parameter: Copy this data directly into your JSON"
                        else:
                            context_info += f"\n  ✅ {key}: Result = {result_data}"
                            context_info += f"\n     → To use as parameter: Use this value directly"
                    elif 'success' in value:
                        # This is a SCALAR result (no 'result' field, but has direct values like unix_timestamp)
                        # Extract key fields to show
                        key_fields = {k: v for k, v in value.items() if k != 'success' and k != 'input'}
                        context_info += f"\n  📊 {key}: SCALAR RESULT - {key_fields}"
                        context_info += f"\n     → NOT a data reference! Use values directly: data['{key}']['unix_timestamp']"
                        context_info += f"\n     → ⚠️ WARNING: NO '_ref_id' field! This is NOT disk data!"
                        context_info += f"\n     → ❌ DO NOT try: load_data_reference(data['{key}']['_ref_id']) - will fail!"
                    else:
                        context_info += f"\n  📋 {key}: {self._summarize_result(value)}"
            
            context_info += "\n\nHOW TO USE CONTEXT DATA:"
            context_info += "\n  - CRITICAL: ONLY use context keys that are listed above! Don't invent keys that don't exist!"
            context_info += "\n  - If you need data that's not in context, the tool will fail. That's OK - describe what you need."
            context_info += "\n  - If tool needs 'entries' parameter and context shows DATA → copy that data AS-IS (keep field names unchanged)"
            context_info += "\n  - For scalar results (📊), access fields directly: data['neuron_X_Y']['unix_timestamp']"
            context_info += "\n  - For disk data (📦), use: data['neuron_X_Y']['_ref_id'] then load_data_reference(...)"
            context_info += "\n  - NEVER try to load_data_reference on scalar results - they have NO _ref_id!"
        
        prompt = """Extract parameters from the task description and available data.

Task: {task}
Tool: {tool_name}

Parameters needed:
{param_info}
{context_info}

CRITICAL RULES FOR PARAMETER EXTRACTION:
0. **CRITICAL**: ONLY use context keys listed in "CONTEXT KEYS AVAILABLE" above! 
   - If you try to use a key that doesn't exist (e.g., data['neuron_0_2'] when only neuron_1_1 exists), you will get KeyError!
   - Check the list carefully and ONLY use keys that are actually shown!
1. If parameters are already auto-mapped (shown above), include them in your output
2. For remaining REQUIRED parameters - extract from task description or context data
3. ONLY use parameters that this tool actually accepts (check parameter list above)
4. IMPORTANT: Check "CONTEXT KEYS AVAILABLE" - previous neurons have produced data you can use!
   - 📦 (LARGE DATA): Has '_ref_id' → use load_data_reference(data['key']['_ref_id'])
   - 📊 (SCALAR RESULT): NO '_ref_id' → access fields directly like data['key']['unix_timestamp']
   - ✅ (RESULT): Has 'result' field → access as data['key']['result']
5. For mergeTimeseriesState specifically:
   - Copy 'entries' data with original field names unchanged
   - Set 'timestamp_field' to match the actual field name in the data (e.g., 'start_date' not 'timestamp')
   - Set 'id_field' to match the actual ID field in the data (e.g., 'id')
6. For date/time filtering (after_unix, before_unix): 
   - Use these ONLY if the tool accepts them AND the task requires date filtering
   - If task says "format" or "display" without mentioning dates, DON'T add date filters
7. If task mentions extracting data from previous steps, look for it in context (e.g., "activities", "activity_id")
8. Extract numeric values as integers, not strings
8. Do NOT use fake/example values like 12345 or 1234567890
9. Check the parameter list - if a parameter is not listed, do NOT include it

EXAMPLES:
- Task: "Fetch activities from January 2024", auto-mapped: {{"after_unix": 1704067200, "before_unix": 1706745599}}
  → Output: {{"after_unix": 1704067200, "before_unix": 1706745599, "per_page": 200}}

- Task: "Format the activities", Tool params: [name, description], auto-mapped: {{"after_unix": 1704067200}}
  → Output: {{}} (don't include after_unix - tool doesn't accept it!)

- Task: "Merge extracted data", Tool needs: entries, Context shows: neuron_0_2: Result = [{{...}}, {{...}}]
  → Output: {{"entries": [extracted data from neuron_0_2]}}

- Task: "Get first 3 activities", context shows activities list
  → Output: {{}} or {{"per_page": 3}} (depending on tool params)

Output JSON only (no explanation):""".format(
            task=neuron_desc,
            tool_name=tool.name,
            param_info=param_info,
            context_info=context_info
        )
        
        response = self.ollama.generate(
            prompt,
            system="Extract parameters from context and output as JSON. When context shows 'neuron_0_X: Result = [data]', include that actual data in your JSON output. Output only valid JSON with actual values, not references.",
            temperature=0.1  # Lower temperature for more deterministic extraction
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        # Extract JSON
        json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
        if json_match:
            try:
                params = json.loads(json_match.group())
                
                # FIX: Sometimes LLM wraps params in {"tool": "X", "parameters": {...}}
                # Extract the actual parameters if this happens
                if isinstance(params, dict) and 'parameters' in params and 'tool' in params:
                    logger.debug(f"   │  │  🔧 Unwrapping nested parameters structure")
                    params = params['parameters']
                
                # MERGE: Start with auto-mapped params, then overlay LLM-extracted ones
                final_params = {**auto_mapped_params, **params}
                
                # VALIDATION: Filter out parameters the tool doesn't accept
                valid_param_names = [p['name'] for p in tool.parameters]
                invalid_params = [k for k in final_params.keys() if k not in valid_param_names]
                if invalid_params:
                    logger.debug(f"   │  │  🗑️  Removing invalid params: {invalid_params} (tool {tool.name} doesn't accept them)")
                    final_params = {k: v for k, v in final_params.items() if k in valid_param_names}
                
                # Clean up None values (but keep auto-mapped values even if None)
                final_params = {k: v for k, v in final_params.items() if v is not None or k in auto_mapped_params}
                
                # Clean up None values (but keep auto-mapped values even if None)
                final_params = {k: v for k, v in final_params.items() if v is not None or k in auto_mapped_params}
                
                # Validate required parameters
                required_params = [p['name'] for p in tool.parameters if p.get('required', False)]
                missing_params = [p for p in required_params if p not in final_params or final_params[p] in [None, "", {}, []]]
                
                # Fallback: If still missing required params, search context for values
                if missing_params:
                    logger.debug(f"   │  │  ⚠️  Missing required parameters: {missing_params}, trying context search")
                    
                    # Search context for required param values
                    for param_name in missing_params:
                        # Look through all context for this param
                        for ctx_key, ctx_value in context.items():
                            if isinstance(ctx_value, dict) and param_name in ctx_value:
                                final_params[param_name] = ctx_value[param_name]
                                logger.debug(f"   │  │  ✓ Found {param_name} = {final_params[param_name]} in {ctx_key}")
                                break
                        
                        # Special handling for validateTimestamp
                        if tool.name == 'validateTimestamp':
                            if param_name == 'unix_timestamp' and param_name not in final_params:
                                # Look for unix_timestamp in previous conversion result
                                for ctx_value in context.values():
                                    if isinstance(ctx_value, dict) and 'unix_timestamp' in ctx_value:
                                        final_params['unix_timestamp'] = ctx_value['unix_timestamp']
                                        logger.debug(f"   │  │  ✓ Found unix_timestamp = {final_params['unix_timestamp']} from previous result")
                                        break
                
                logger.debug(f"   │  │  📦 Final parameters: {final_params}")
                return final_params
                
            except json.JSONDecodeError as e:
                logger.error(f"   │  │  ❌ Failed to parse parameters: {e}")
                # Return auto-mapped params if JSON parsing failed
                return auto_mapped_params if auto_mapped_params else {}
        
        # If no JSON match, return auto-mapped params
        return auto_mapped_params if auto_mapped_params else {}
        
        # Final fallback: extract from text
        return self._extract_params_from_text(neuron_desc, tool.parameters, dendrite_item)
    
    def _extract_params_from_text(self, text: str, param_defs: List[Dict], item_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Extract parameters from text using regex and item data."""
        params = {}
        
        # First, try to get from item_data if available
        if item_data:
            for param_def in param_defs:
                param_name = param_def['name']
                # Check direct field match
                if param_name in item_data:
                    params[param_name] = item_data[param_name]
                # Check common aliases
                elif param_name == 'activity_id':
                    # Try: id, activity_id, or any numeric ID field
                    for key in ['activity_id', 'id']:
                        if key in item_data and isinstance(item_data[key], (int, str)):
                            try:
                                params[param_name] = int(item_data[key]) if isinstance(item_data[key], str) else item_data[key]
                                break
                            except:
                                pass
        
        # Second, if no item_data, search through ALL context for the first matching data
        if not params and hasattr(self, 'context'):
            for context_value in self.context.values():
                if isinstance(context_value, dict):
                    # Look for lists of activities
                    activities = self._extract_list_items(context_value)
                    if activities and len(activities) > 0:
                        # Use the first activity's ID
                        first_item = activities[0]
                        for param_def in param_defs:
                            param_name = param_def['name']
                            if param_name == 'activity_id' and 'activity_id' in first_item:
                                try:
                                    params[param_name] = int(first_item['activity_id'])
                                    break
                                except:
                                    pass
                    if params:
                        break
        
        # Third, extract from text using regex patterns
        for param_def in param_defs:
            param_name = param_def['name']
            if param_name in params:
                continue  # Already found
            
            # Look for patterns like "activity 12345" or "activity_id: 12345"
            patterns = [
                rf"{param_name}[:\s]+(\d+)",
                rf"(?:activity|athlete|user|item)\s+(\d{{8,}})",  # Long IDs
                rf"id[:\s]+(\d{{8,}})"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        params[param_name] = int(match.group(1))
                        break
                    except:
                        pass
        
        return params
    
    def _micro_detect_spawn_needed(self, neuron_desc: str, result: Any) -> bool:
        """Micro-prompt: Does this need dendrite spawning?"""
        
        # Quick check: Is result a list?
        items = self._extract_list_items(result)
        if not items or len(items) <= 1:
            return False
        
        # Quick check: Does description mention iteration?
        iteration_keywords = ['each', 'every', 'all', 'for each']
        if not any(kw in neuron_desc.lower() for kw in iteration_keywords):
            return False
        
        # CRITICAL: First check if data is already complete
        sample_item = items[0] if items else {}
        
        # Step 1: What fields are needed?
        field_check_prompt = f"""What data fields are needed for this task?

Task: {neuron_desc}
Sample item available: {json.dumps(sample_item, indent=2)[:400]}

Question: Are ALL required fields ALREADY present in the sample item above?

Think step by step:
1. What fields does the task ask for?
2. Are they in the sample item?
3. If ALL fields exist, answer NO
4. If ANY field is missing, answer YES

Answer YES (if spawning needed) or NO (if data complete):"""
        
        field_response = self.ollama.generate(
            field_check_prompt,
            system="Check if data is complete. Answer YES if spawning needed, NO if data is already complete.",
            temperature=0.1
        )
        
        field_response_str = str(field_response) if not isinstance(field_response, str) else field_response
        
        # If data is complete, don't spawn
        if 'no' in field_response_str.lower():
            logger.info(f"   │  │  ✓ Data already complete, no spawning needed")
            return False
        
        # Step 2: Double-check if spawning requires API calls
        prompt = f"""Does this task require calling MORE tools/APIs for EACH item individually?

Task: {neuron_desc}
Result: {len(items)} items returned
Sample item: {json.dumps(sample_item, indent=2)[:300]}

Examples:
- "Show activities with name and kudos count" + item has kudos_count → NO
- "Get activities and get kudos GIVERS for each" + item lacks giver names → YES
- "Update all activities" → YES (need write API per item)

Answer yes or no only:"""
        
        response = self.ollama.generate(
            prompt,
            system="Answer yes or no only. Say no if data is already complete or no API calls needed per item.",
            temperature=0.1
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        should_spawn = 'yes' in response_str.lower()
        
        if should_spawn:
            logger.info(f"   │  │  🔄 Spawning needed: Missing data or action required per item")
        else:
            logger.info(f"   │  │  ✓ No spawning needed: Data complete or no per-item actions")
        
        return should_spawn
    
    def _micro_extract_item_goal(self, neuron_desc: str, result: Any) -> str:
        """Micro-prompt: What to do with each item?"""
        
        items = self._extract_list_items(result)
        sample_item = items[0] if items else {}
        
        prompt = f"""What should be done for EACH item?

Original task: {neuron_desc}
Sample item: {json.dumps(sample_item, indent=2)[:200]}

Output a goal template (use {{field_name}} for placeholders):
Example: "Get kudos for activity {{activity_id}}"

Goal template:"""
        
        response = self.ollama.generate(
            prompt,
            system="Extract goal template for list items.",
            temperature=0.2
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        return response_str.strip().split('\n')[0]
    
    def _micro_extract_item_goal_from_desc(self, neuron_desc: str) -> str:
        """Extract goal template from description without result data."""
        
        prompt = f"""Convert this task into a goal template for EACH item.

Task: {neuron_desc}

Examples:
- "For each activity, get kudos" → "Get kudos for activity {{activity_id}}"
- "Get names of people who gave kudos to each activity" → "Get kudos names for activity {{activity_id}}"
- "Update all activities" → "Update activity {{activity_id}}"

Output template (use {{field_name}} for placeholders):"""
        
        response = self.ollama.generate(
            prompt,
            system="Extract goal template. Use placeholders like {{activity_id}}.",
            temperature=0.2
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        return response_str.strip().split('\n')[0]
    
    def _micro_validate(self, parent_goal: str, neuron_desc: str, result: Any) -> bool:
        """Micro-prompt: Is this result valid?"""
        
        result_summary = self._summarize_result(result)
        
        # Check for explicit success/error indicators
        if isinstance(result, dict):
            # Write operations: success=True means valid
            if 'success' in result:
                return result['success'] is True or result['success'] == 'true'
            # Explicit errors are invalid
            if 'error' in result:
                return False
        
        # For read operations, ask LLM to validate
        prompt = f"""Is this result valid for the goal?

Parent goal: {parent_goal}
Current step: {neuron_desc}
Result: {result_summary}

Valid if:
- No error occurred
- Returned data matches what was requested
- Makes progress toward parent goal
- For write operations: "Success: operation completed" means VALID

Answer yes or no:"""
        
        response = self.ollama.generate(
            prompt,
            system="Validate results. Answer yes or no only.",
            temperature=0.1
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        return 'yes' in response_str.lower()
    
    def _micro_aggregate(self, goal: str, neurons: List[Neuron], results: List[Any]) -> Any:
        """Micro-prompt: Combine neuron results into final answer."""
        
        # If only one neuron, return its result directly
        if len(neurons) == 1:
            return results[0]
        
        # For counting questions, find the final count result
        is_counting = any(word in goal.lower() for word in ['how many', 'count'])
        if is_counting:
            # Look for the last result that has a 'result' key with a number
            for r in reversed(results):
                if isinstance(r, dict) and 'result' in r and isinstance(r['result'], (int, float)):
                    count = r['result']
                    logger.info(f"📊 Found count result: {count}")
                    return {
                        'success': True,
                        'count': int(count),
                        'answer': f"{int(count)} activities"
                    }
        
        # Build summary of what each neuron did
        summary = "\n".join([
            f"Step {n.index + 1}: {n.description}\n  Result: {self._summarize_result(r)}"
            for n, r in zip(neurons, results)
        ])
        
        # Detect if this is a question that needs a simple answer
        is_question = any(word in goal.lower() for word in ['how many', 'what', 'which', 'when', 'where', 'who', 'count'])
        
        if is_question:
            prompt = f"""Answer this question using the results:

Question: {goal}

Steps taken:
{summary}

Provide a direct, concise answer (1-2 sentences):"""
            
            response = self.ollama.generate(
                prompt,
                system="Answer questions directly and concisely. For 'how many' questions, start with the number.",
                temperature=0.2
            )
        else:
            prompt = f"""Summarize what was accomplished:

Goal: {goal}

Steps:
{summary}

Provide a brief summary (2-3 sentences):"""
            
            response = self.ollama.generate(
                prompt,
                system="Summarize accomplishments concisely.",
                temperature=0.3
            )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        # Truncate large detailed_results to keep logs readable
        truncated_results = self._truncate_large_results(results, max_size_kb=10)
        
        return {
            'summary': response_str.strip(),
            'detailed_results': truncated_results
        }
    
    def _truncate_large_results(self, results: List[Any], max_size_kb: int = 10) -> List[Any]:
        """Truncate large results to keep logs readable."""
        import json
        
        # Convert any Neuron objects to dicts first
        serializable_results = []
        for result in results:
            if hasattr(result, '__dict__'):  # Neuron or other objects
                # Convert to basic dict, excluding complex nested objects
                result_dict = {}
                for key, value in result.__dict__.items():
                    if isinstance(value, (str, int, float, bool, type(None))):
                        result_dict[key] = value
                    elif isinstance(value, dict):
                        result_dict[key] = "[dict]"
                    elif isinstance(value, list):
                        result_dict[key] = f"[list with {len(value)} items]"
                    else:
                        result_dict[key] = str(type(value).__name__)
                serializable_results.append(result_dict)
            else:
                serializable_results.append(result)
        
        # Check total size
        try:
            results_json = json.dumps(serializable_results)
            size_kb = len(results_json) / 1024
        except (TypeError, ValueError):
            # If still not serializable, just return simplified version
            return [{"info": "Result truncated - could not serialize"}]
        
        if size_kb <= max_size_kb:
            return serializable_results  # Small enough, keep as-is
        
        # Truncate each result
        truncated = []
        for result in serializable_results:
            if isinstance(result, dict):
                # Keep metadata but truncate large data fields
                truncated_result = {}
                for key, value in result.items():
                    if key in ['success', 'count', 'error', 'message', 'added', 'duplicates', 'total_count']:
                        # Keep small metadata fields
                        truncated_result[key] = value
                    elif isinstance(value, (list, dict)):
                        # Truncate large structures
                        value_json = json.dumps(value)
                        if len(value_json) > 500:
                            if isinstance(value, list):
                                truncated_result[key] = f"[{len(value)} items, truncated for brevity]"
                            else:
                                truncated_result[key] = "[large object, truncated for brevity]"
                        else:
                            truncated_result[key] = value
                    else:
                        truncated_result[key] = value
                truncated.append(truncated_result)
            else:
                truncated.append(result)
        
        return truncated
    
    def _micro_aggregate_dendrites(self, parent_result: Any, items: List[Dict], dendrite_results: List[Any]) -> Any:
        """Micro-prompt: Merge dendrite results back into parent."""
        
        # Simple merge: add dendrite data to each item
        if isinstance(parent_result, dict) and 'entries' in parent_result:
            enhanced_entries = []
            for item, dendrite in zip(items, dendrite_results):
                enhanced_item = item.copy()
                enhanced_item['_dendrite_result'] = dendrite.get('final', dendrite)
                enhanced_entries.append(enhanced_item)
            
            parent_result['entries'] = enhanced_entries
        
        return parent_result
    
    def _micro_ai_response(self, neuron_desc: str) -> Dict[str, Any]:
        """Fallback: Use AI to answer directly using context data."""
        
        # Build context summary - include actual data structures
        # Filter out non-serializable objects (like Neuron instances)
        serializable_context = {}
        for key, value in self.context.items():
            try:
                # Try to serialize - if it fails, skip or convert
                json.dumps(value)
                serializable_context[key] = value
            except TypeError:
                # Not JSON serializable (e.g., Neuron objects)
                if isinstance(value, dict):
                    # Try to extract serializable parts
                    clean_value = {}
                    for k, v in value.items():
                        try:
                            json.dumps(v)
                            clean_value[k] = v
                        except TypeError:
                            # Skip non-serializable nested values
                            continue
                    if clean_value:
                        serializable_context[key] = clean_value
        
        context_summary = ""
        compact_data = None  # For small model optimization
        
        # Debug: log what context we have
        logger.info(f"   │  │  🔍 Context keys available: {list(serializable_context.keys())}")
        
        if serializable_context:
            context_summary = "\n\nAvailable data:"
            for key, value in list(serializable_context.items())[:10]:
                # Log each context item for debugging
                logger.info(f"   │  │  📦 {key}: {type(value).__name__} = {str(value)[:100]}")
                
                if isinstance(value, dict):
                    # For activities list, OPTIMIZE for small models
                    if 'activities' in value:
                        activities = value['activities']
                        
                        # Check if already in compact format (from context storage)
                        is_compact = value.get('format') == 'compact'
                        
                        if isinstance(activities, list) and len(activities) > 0:
                            # Check if this is a counting/filtering task
                            is_counting = any(word in neuron_desc.lower() for word in ['count', 'how many', 'number of'])
                            is_filtering = any(word in neuron_desc.lower() for word in ['filter', 'type', 'where', 'matching'])
                            
                            if is_counting or is_filtering:
                                # Use pre-compacted data if available, otherwise compact now
                                if is_compact:
                                    compact_activities = activities  # Already compact!
                                    logger.info(f"📋 Using pre-stored compact format: {len(activities)} activities")
                                else:
                                    # Legacy path: compact on-the-fly (shouldn't happen with new storage)
                                    compact_activities = []
                                    for act in activities:
                                        compact = {
                                            'name': act.get('name', 'Unknown'),
                                            'type': act.get('type', 'Unknown'),
                                            'sport_type': act.get('sport_type', act.get('type', 'Unknown')),
                                            'id': act.get('id'),
                                            'distance': act.get('distance'),
                                            'date': act.get('start_date_local', act.get('start_date', ''))[:10]  # Just date part
                                        }
                                        compact_activities.append(compact)
                                
                                compact_data = compact_activities
                                context_summary += f"\n  {key}: {len(activities)} activities (compact format)"
                                context_summary += f"\n    Format: name, type, sport_type, id, distance, date"
                                context_summary += f"\n    Activities:\n"
                                # Show ALL activities in compact format for small models
                                for i, act in enumerate(compact_activities[:100]):  # Limit to 100 for safety
                                    context_summary += f"      {i+1}. {act['name']} | type={act['sport_type']} | date={act['date']}\n"
                                if len(compact_activities) > 100:
                                    context_summary += f"      ... and {len(compact_activities) - 100} more\n"
                                
                                # Log what we're showing
                                logger.info(f"   │  │  📋 Compact format: showing {min(len(compact_activities), 100)} activities to AI")
                                run_count = sum(1 for a in compact_activities if 'Run' in a.get('sport_type', ''))
                                logger.info(f"   │  │  🏃 Activities with 'Run' in sport_type: {run_count}")
                                
                                # SANITY CHECK: Write activities to temp file for debugging
                                try:
                                    with open('/tmp/ai_activities_debug.json', 'w') as f:
                                        json.dump({'count': len(compact_activities), 'run_count': run_count, 'activities': compact_activities[:10]}, f, indent=2)
                                except:
                                    pass
                            else:
                                # For non-counting tasks, show structure only
                                context_summary += f"\n  {key}: List of {len(activities)} activities"
                                first_activity = activities[0]
                                context_summary += f"\n    Each activity has: {', '.join(first_activity.keys())}"
                                context_summary += f"\n    Example: {json.dumps(first_activity, indent=4)[:500]}"
                    else:
                        context_summary += f"\n  {key}: {json.dumps(value, indent=2)[:400]}"
                else:
                    context_summary += f"\n  {key}: {value}"
        
        # Improved prompt with specific instructions for common tasks
        task_type = ""
        if any(word in neuron_desc.lower() for word in ['count', 'how many']):
            task_type = "\n\n**YOU ARE COUNTING**"
            task_type += "\nInstructions:"
            task_type += "\n1. Look at EVERY activity listed above"
            task_type += "\n2. Check each one's 'type' or 'sport_type' field"
            task_type += "\n3. Count only those matching the requested type"
            task_type += "\n4. Output: 'COUNT: X activities' where X is the exact number"
            task_type += "\n\nExample: If asked 'how many runs', count where sport_type contains 'Run'"
        elif any(word in neuron_desc.lower() for word in ['filter', 'find', 'get']):
            task_type = "\n\n**YOU ARE FILTERING**"
            task_type += "\n1. Look at the activities list"
            task_type += "\n2. Find items matching the criteria"
            task_type += "\n3. List them clearly with their names"
        elif any(word in neuron_desc.lower() for word in ['format', 'report', 'present', 'show']):
            task_type = "\n\n**YOU ARE FORMATTING/REPORTING DATA**"
            task_type += "\n1. Take the existing data from context above"
            task_type += "\n2. Present the ACTUAL VALUES (timestamps, dates, numbers, etc.)"
            task_type += "\n3. Make it human-readable but INCLUDE THE RAW DATA"
            task_type += "\n4. DO NOT just summarize - SHOW the actual results"
            task_type += "\n\nExample: Instead of 'The timestamp was converted', say 'Unix timestamp: 1704067200 (January 1, 2024)'"
        
        prompt = f"""Task: {neuron_desc}
{context_summary}
{task_type}

Your answer:"""
        
        # Debug: save full prompt to file
        try:
            debug_file = f"/tmp/ai_prompt_debug_{goal_type}_{self.depth}_{self.sequence}.txt"
            with open(debug_file, 'w') as f:
                f.write("=== FULL PROMPT ===\n")
                f.write(prompt)
                f.write("\n\n=== SERIALIZABLE CONTEXT ===\n")
                f.write(json.dumps(serializable_context, indent=2)[:2000])
            logger.info(f"   │  │  📝 Debug prompt saved to {debug_file}")
        except Exception as e:
            logger.warning(f"   │  │  ⚠️  Could not save debug prompt: {e}")
        
        # Log prompt stats
        logger.info(f"   │  │  📝 Prompt: {len(prompt)} chars, {len(prompt.split())} words")
        
        response = self.ollama.generate(
            prompt,
            system="You count and analyze data precisely. For counting: examine each item in the list and count matches. Output exact numbers.",
            temperature=0.1  # Lower temperature for more deterministic analysis
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        return {
            'type': 'ai_response',
            'answer': response_str.strip()
        }
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def _extract_list_items(self, result: Any) -> List[Dict]:
        """Extract list of items from result."""
        if not isinstance(result, dict):
            return []
        
        # Try common list fields
        for field in ['entries', 'activities', 'kudos', 'items', 'data']:
            if field in result and isinstance(result[field], list):
                return result[field]
        
        return []
    
    def _format_item_goal(self, template: str, item: Dict, index: int) -> str:
        """Format goal template with item data."""
        try:
            return template.format(**item)
        except KeyError:
            # Fallback: use first available ID field
            for id_field in ['id', 'activity_id', 'athlete_id', 'item_id']:
                if id_field in item:
                    return template.replace('{' + id_field + '}', str(item[id_field]))
            return f"{template} (item {index})"
    
    def _summarize_result(self, result: Any) -> str:
        """Summarize result for logging."""
        if isinstance(result, dict):
            if 'error' in result:
                return f"Error: {result['error']}"
            if 'entries' in result:
                return f"{len(result['entries'])} entries"
            if 'success' in result:
                # Handle write operations better
                success_val = result['success']
                if success_val is True or success_val == 'true':
                    # Check for result key first (most specific)
                    if 'result' in result:
                        return f"Result: {result['result']}"
                    # Check for count or other indicators
                    elif 'count' in result:
                        return f"Success: {result['count']} items"
                    elif 'activity_id' in result:
                        return f"Success: operation completed for activity {result['activity_id']}"
                    else:
                        return "Success: operation completed"
                else:
                    return f"Failed: {result.get('error', 'Unknown error')}"
            return f"{len(result)} fields"
        elif isinstance(result, list):
            return f"{len(result)} items"
        else:
            return str(result)[:100]
    
    def _log(self, message: str):
        """Add to execution log for debugging."""
        self.execution_log.append(message)
    
    def _validate_goal_completion(self, goal: str, result: Any) -> bool:
        """Validate if the goal has been fully completed."""
        
        result_summary = self._summarize_result_for_validation(result)
        
        # Check if goal explicitly asks for formatting/display
        format_keywords = ['show', 'display', 'report', 'summary', 'list', 'format', 'readable', 'human-readable']
        needs_formatting = any(keyword in goal.lower() for keyword in format_keywords)
        
        # Check if result is raw data structure
        # Look in top level OR in detailed_results
        def contains_raw_data(obj):
            if isinstance(obj, dict):
                # Check top level
                if any(key in obj for key in ['activities', 'entries']):
                    return True
                # Check nested detailed_results
                if 'detailed_results' in obj:
                    detailed = obj['detailed_results']
                    if isinstance(detailed, list):
                        # Check if there's at least one AI response in the list
                        has_ai_response = any(
                            isinstance(item, dict) and item.get('type') == 'ai_response' 
                            for item in detailed
                        )
                        # If there's an AI response, consider it formatted
                        if has_ai_response:
                            return False
                        return any(contains_raw_data(item) for item in detailed)
                    else:
                        return contains_raw_data(detailed)
            return False
        
        is_raw_data = contains_raw_data(result)
        
        # Determine result type for validation
        if is_raw_data:
            result_type = f"⚠️ RAW DATA STRUCTURE (contains API response fields)"
        elif isinstance(result, str):
            result_type = "✅ HUMAN-READABLE TEXT (string)"
        elif isinstance(result, dict) and 'summary' in result:
            # Check if summary is descriptive text or just a confirmation
            summary = result.get('summary', '')
            if isinstance(summary, str) and len(summary) > 100:
                result_type = "✅ FORMATTED SUMMARY (contains descriptive text)"
            else:
                result_type = "⚠️ SUMMARY TOO SHORT (not human-readable report)"
        else:
            result_type = f"❓ UNKNOWN TYPE: {type(result).__name__}"
        
        prompt = f"""Has this goal been FULLY completed?

Goal: {goal}

Result Type: {result_type}

Result summary:
{result_summary}

Requirements for "FULLY completed":
1. All data requested in the goal is present ✓
2. Data is in the format requested
3. No partial results or missing fields
4. If goal asked for "show", "display", "report", or "summary", the output MUST be human-readable text (not raw JSON/dict with API fields like 'activities', 'success', 'count')

CRITICAL FORMAT CHECK:
- Goal requires formatting? {'YES - Must be human-readable text' if needs_formatting else 'NO - Any format OK'}
- Result is raw data? {'YES - This is NOT acceptable for formatted output!' if is_raw_data else 'NO - Format is OK'}

❌ REJECT if goal needs formatting but result is raw data!

Answer (YES or NO only):"""
        
        response = self.ollama.generate(
            prompt,
            system="You are a strict validator. If goal requires human-readable output (show/display/report) but result type is RAW DATA STRUCTURE, you MUST answer NO.",
            temperature=0.1
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        is_complete = 'yes' in response_str.lower()
        
        if is_complete:
            logger.info(f"   ✅ Goal validation passed: Complete")
        else:
            logger.warning(f"   ⚠️  Goal validation failed: Incomplete")
        
        return is_complete
    
    def _check_what_is_missing(self, goal: str, result: Any) -> str:
        """Determine what is missing from the goal completion."""
        
        result_summary = self._summarize_result_for_validation(result)
        
        prompt = f"""What is missing or wrong with this result?

Goal: {goal}

Current result:
{result_summary}

Identify what's missing or needs to be fixed:
- Missing data fields?
- Wrong format?
- Not human-readable when it should be?
- Partial results?

Be specific and concise (1-2 sentences):"""
        
        response = self.ollama.generate(
            prompt,
            system="Identify what's missing to complete the goal. Be specific.",
            temperature=0.2
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        return response_str.strip()
    
    def _reflect_on_error(self, neuron_desc: str, tool_name: str, params: Dict, error: str, context: Dict) -> Dict:
        """
        Reflect on tool execution error to diagnose the problem.
        Returns diagnosis and suggested fix if available.
        """
        # Summarize context
        context_summary = []
        for key, value in context.items():
            if isinstance(value, list):
                context_summary.append(f"- {key}: list of {len(value)} items")
                if value and isinstance(value[0], dict):
                    sample_keys = list(value[0].keys())[:3]
                    context_summary.append(f"  Sample keys: {sample_keys}")
            elif isinstance(value, dict):
                sample_keys = list(value.keys())[:3]
                context_summary.append(f"- {key}: dict with keys {sample_keys}")
            else:
                context_summary.append(f"- {key}: {str(value)[:50]}")
        
        context_str = '\n'.join(context_summary) if context_summary else "No context available"
        
        prompt = f"""A tool execution failed. Diagnose what went wrong.

Neuron Goal: {neuron_desc}
Tool Called: {tool_name}
Parameters Used: {json.dumps(params, indent=2)}
Error: {error}

Available Context Data:
{context_str}

Common Issues:
1. Hallucinated ID: Parameter uses made-up ID instead of actual ID from context
2. Wrong parameter type: String instead of int, etc.
3. Missing required parameter
4. Wrong parameter extracted from context

Provide:
1. diagnosis: What went wrong (1 sentence)
2. suggested_fix: Brief description of fix (if available)
3. suggested_params: Corrected parameters (JSON, if applicable)

Response format (JSON):
{{"diagnosis": "...", "suggested_fix": "...", "suggested_params": {{...}} }}"""
        
        response = self.ollama.generate(
            prompt,
            system="Diagnose tool execution errors and suggest fixes. Focus on parameter issues.",
            temperature=0.2
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        # Parse JSON response
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
            if json_match:
                reflection = json.loads(json_match.group())
                return reflection
        except Exception as e:
            logger.warning(f"Failed to parse reflection: {e}")
        
        return {"diagnosis": response_str.strip(), "suggested_fix": None, "suggested_params": None}
    
    def _generate_corrective_goal(self, original_goal: str, missing_info: str, current_result: Any) -> str:
        """Generate a corrective goal to fix what's missing."""
        
        result_summary = self._summarize_result_for_validation(current_result)
        
        prompt = f"""Create a corrective step to complete this goal.

Original goal: {original_goal}

What's missing: {missing_info}

Current data available:
{result_summary}

CRITICAL RULES:
1. The data is ALREADY FETCHED - don't fetch again
2. Only format/transform what's already there
3. Use phrases like "Format the existing", "Display the current", "Transform the available"
4. Do NOT use "extract", "get", "retrieve", "fetch" - data is already here!

Examples (GOOD):
- "Format the existing activities data into a readable summary with name, type, and kudos count"
- "Display the current results in a human-readable report"
- "Transform the available activity list into a summary report showing name, type, and kudos"

Examples (BAD - will trigger re-fetching):
- "Extract name, type, kudos from each activity" ❌
- "Get activity details for each item" ❌
- "Retrieve kudos count for activities" ❌

Corrective step (use ONLY formatting/display verbs):"""
        
        response = self.ollama.generate(
            prompt,
            system="Generate a FORMATTING-ONLY corrective step. Data is already available. Do NOT use extraction verbs.",
            temperature=0.2
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        return response_str.strip().split('\n')[0]  # Take first line only
    
    def _summarize_result_for_validation(self, result: Any, max_length: int = 500) -> str:
        """Summarize result for validation (more detailed than logging summary)."""
        if isinstance(result, dict):
            # Show structure and sample data
            summary_parts = []
            
            if 'final' in result:
                # This is a nested result from execute_goal
                return self._summarize_result_for_validation(result['final'], max_length)
            
            if 'error' in result:
                return f"Error: {result['error']}"
            
            if 'success' in result:
                summary_parts.append(f"Status: {'Success' if result.get('success') else 'Failed'}")
            
            if 'count' in result:
                summary_parts.append(f"Count: {result['count']}")
            
            if 'activities' in result:
                activities = result['activities']
                if activities and len(activities) > 0:
                    sample = activities[0]
                    fields = list(sample.keys())
                    summary_parts.append(f"Activities: {len(activities)} items")
                    summary_parts.append(f"Fields: {', '.join(fields[:10])}")
                    # Show first activity sample
                    if 'name' in sample:
                        summary_parts.append(f"Sample: {sample.get('name')} ({sample.get('type')}) - {sample.get('kudos_count', 0)} kudos")
            
            if 'entries' in result:
                entries = result['entries']
                summary_parts.append(f"Entries: {len(entries)} items")
            
            result_str = "\n".join(summary_parts)
            if len(result_str) > max_length:
                return result_str[:max_length] + "..."
            return result_str
            
        elif isinstance(result, list):
            if len(result) > 0:
                sample = result[0]
                return f"List: {len(result)} items, sample: {str(sample)[:200]}"
            return f"Empty list"
        else:
            result_str = str(result)
            if len(result_str) > max_length:
                return result_str[:max_length] + "..."
            return result_str
