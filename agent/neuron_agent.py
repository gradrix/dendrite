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
from agent.neuron import aggregation, spawning, validation, decomposition, execution

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
        """Execute a single neuron with validation and auto-spawning."""
        return execution.execute_neuron(
            neuron=neuron,
            parent_goal=parent_goal,
            context=self.context,
            tools=self.tools,
            ollama=self.ollama,
            execute_goal_fn=self.execute_goal,
            micro_validate_fn=self._micro_validate,
            summarize_result_fn=self._summarize_result,
            find_context_list_fn=spawning.find_context_list_for_iteration,
            spawn_from_context_fn=self._spawn_dendrites_from_context,
            detect_multi_step_fn=self._detect_multi_step_task,
            spawn_for_subtasks_fn=self._spawn_dendrites_for_subtasks,
            spawn_dendrites_fn=self._spawn_dendrites,
            aggregate_dendrites_fn=self._micro_aggregate_dendrites,
            detect_spawn_needed_fn=self._micro_detect_spawn_needed,
            ai_response_fn=self._micro_ai_response,
            max_depth=self.MAX_DEPTH,
            max_retries=self.MAX_RETRIES
        )
    
    def _find_context_list_for_iteration(self, neuron_desc: str) -> Optional[List[Dict]]:
        """Check if this neuron needs to iterate over a list from context."""
        return spawning.find_context_list_for_iteration(neuron_desc, self.context)
    
    def _spawn_dendrites_from_context(self, parent_neuron: Neuron, items: List[Dict], parent_goal: str) -> Any:
        """Spawn dendrites based on context list (pre-execution spawning)."""
        return spawning.spawn_dendrites_from_context(
            parent_neuron, items, parent_goal, self.context, self.execute_goal, self.ollama
        )
    
    def _spawn_dendrites(self, parent_neuron: Neuron, result: Any, parent_goal: str) -> Any:
        """Spawn dendrites (sub-neurons) for each item in a list result."""
        return spawning.spawn_dendrites(
            parent_neuron, result, parent_goal, self.context,
            self.execute_goal, self._micro_aggregate_dendrites, self.ollama
        )
    
    def _detect_multi_step_task(self, neuron_desc: str, context: Dict = None, tools = None) -> Optional[List[str]]:
        """Detect if this neuron requires multiple sub-tasks."""
        # Use instance context/tools if not provided (for backward compatibility)
        ctx = context if context is not None else self.context
        tls = tools if tools is not None else self.tools
        return spawning.detect_multi_step_task(neuron_desc, ctx, tls, self.ollama)
    
    def _spawn_dendrites_for_subtasks(self, parent_neuron: Neuron, subtasks: List[str], parent_goal: str) -> Any:
        """Spawn dendrites for multiple sub-tasks that need to be completed."""
        return spawning.spawn_dendrites_for_subtasks(parent_neuron, subtasks, parent_goal, self.execute_goal)
    
    # ========================================================================
    # Micro-Prompts (each 50-100 tokens)
    # ========================================================================
    
    def _micro_decompose(self, goal: str, depth: int) -> List[Neuron]:
        """Micro-prompt: Decompose goal into 1-4 neurons."""
        return decomposition.micro_decompose(goal, depth, self.config, self.ollama, self.tools.list_tools())
    
    def _get_strategy_advice(self, goal: str) -> str:
        """Get expert strategy advice for approaching the goal."""
        return decomposition.get_strategy_advice(goal, self.config, self.ollama)
    
    def _validate_python_code(self, task: str, python_code: str, context: Dict) -> Optional[str]:
        """Validate that Python code will correctly answer the task."""
        return execution.validate_python_code(task, python_code, context, self._summarize_result, self.ollama)
    
    def _micro_find_tool(self, neuron_desc: str) -> Optional[Any]:
        """Micro-prompt: Which tool for this neuron?"""
        return execution.micro_find_tool(neuron_desc, self.context, self.tools, self.ollama)
    
    def _clarify_vague_terms(self, neuron_desc: str, tool: Any, context: Dict) -> str:
        """Inter-neuron communication: Ask decomposer to clarify vague terms."""
        return execution.clarify_vague_terms(neuron_desc, tool, context, self.ollama)
    
    def _micro_determine_params(self, neuron_desc: str, tool: Any, context: Dict) -> Dict[str, Any]:
        """Micro-prompt: What parameters?"""
        return execution.micro_determine_params(neuron_desc, tool, context, self.ollama, self._summarize_result)
    
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
        return spawning.micro_extract_item_goal(neuron_desc, result, self.ollama)
    
    def _micro_extract_item_goal_from_desc(self, neuron_desc: str) -> str:
        """Extract goal template from description without result data."""
        return spawning.micro_extract_item_goal_from_desc(neuron_desc, self.ollama)
    
    def _micro_validate(self, parent_goal: str, neuron_desc: str, result: Any) -> bool:
        """Micro-prompt: Is this result valid?"""
        return validation.micro_validate(parent_goal, neuron_desc, result, self._summarize_result, self.ollama)
    
    def _validate_goal_completion(self, goal: str, result: Any) -> bool:
        """Validate if the goal has been fully completed."""
        return validation.validate_goal_completion(goal, result, self._summarize_result_for_validation, self.ollama)
    
    def _check_what_is_missing(self, goal: str, result: Any) -> str:
        """Determine what is missing from the goal completion."""
        return validation.check_what_is_missing(goal, result, self._summarize_result_for_validation, self.ollama)
    
    def _generate_corrective_goal(self, original_goal: str, missing_info: str, current_result: Any) -> str:
        """Generate a corrective goal to fix what's missing."""
        return validation.generate_corrective_goal(
            original_goal, missing_info, current_result, self._summarize_result_for_validation, self.ollama
        )
    
    def _micro_aggregate(self, goal: str, neurons: List[Neuron], results: List[Any]) -> Any:
        """Micro-prompt: Combine neuron results into final answer."""
        return aggregation.aggregate_results(goal, neurons, results, self.ollama)
    
    def _truncate_large_results(self, results: List[Any], max_size_kb: int = 10) -> List[Any]:
        """Truncate large results to keep logs readable."""
        return aggregation.truncate_large_results(results, max_size_kb)
    
    def _micro_aggregate_dendrites(self, parent_result: Any, items: List[Dict], dendrite_results: List[Any]) -> Any:
        """Micro-prompt: Merge dendrite results back into parent."""
        return aggregation.aggregate_dendrite_results(parent_result, items, dendrite_results)
    
    def _micro_ai_response(self, neuron_desc: str, depth: int = 0, sequence: int = 0) -> Dict[str, Any]:
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
                        # For timestamp/date results, show full data (not truncated)
                        context_summary += f"\n  {key}: {json.dumps(value, indent=2)}"
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
            task_type += "\n**CRITICAL**: You must extract and display the ACTUAL DATA VALUES from the context above."
            task_type += "\n**DO NOT** write 'the workflow was successful' or 'all steps completed'."
            task_type += "\n**DO** write the actual numbers, timestamps, dates, validation results."
            task_type += "\n\nRequired format:"
            task_type += "\n1. Current date/time: [ACTUAL TIMESTAMP AND DATE]"
            task_type += "\n2. Converted timestamp: [ACTUAL NUMBER]"
            task_type += "\n3. Validation: [ACTUAL RESULT: valid/invalid]"
            task_type += "\n\nExample output:"
            task_type += "\n- Current: 1761432898 (October 25, 2025)"
            task_type += "\n- January 2024: 1706745600 (February 1, 2024)"
            task_type += "\n- Validation: ✅ Valid"
        
        prompt = f"""Task: {neuron_desc}
{context_summary}
{task_type}

Your answer:"""
        
        # Debug: save full prompt to file
        try:
            debug_file = f"/tmp/ai_prompt_debug_d{depth}_s{sequence}.txt"
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
        
        # Adjust system prompt based on task type
        if 'FORMATTING/REPORTING' in prompt:
            system_prompt = "Extract and display ACTUAL data values (numbers, timestamps, dates). Never say 'workflow successful' - always show the real data."
        else:
            system_prompt = "You count and analyze data precisely. For counting: examine each item in the list and count matches. Output exact numbers."
        
        response = self.ollama.generate(
            prompt,
            system=system_prompt,
            temperature=0.1  # Lower temperature for more deterministic analysis
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        # Clean up response - remove common artifacts
        response_str = response_str.strip()
        # Remove common garbage prefixes (single words followed by newline at start)
        lines = response_str.split('\n', 1)
        if len(lines) > 1 and len(lines[0].split()) == 1 and len(lines[0]) < 20:
            # First line is a single short word - probably garbage
            response_str = lines[1].strip()
        
        return {
            'type': 'ai_response',
            'answer': response_str
        }
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def _extract_list_items(self, result: Any) -> List[Dict]:
        """Extract list of items from result."""
        return spawning.extract_list_items(result)
    
    def _format_item_goal(self, template: str, item: Dict, index: int) -> str:
        """Format goal template with item data."""
        return spawning.format_item_goal(template, item, index)
    
    def _summarize_result(self, result: Any) -> str:
        """Summarize result for logging."""
        return aggregation.summarize_result(result)
    
    def _log(self, message: str):
        """Add to execution log for debugging."""
        self.execution_log.append(message)
    
    def _reflect_on_error(self, neuron_desc: str, tool_name: str, params: Dict, error: str, context: Dict) -> Dict:
        """Reflect on tool execution error to diagnose the problem."""
        return execution.reflect_on_error(neuron_desc, tool_name, params, error, context, self.ollama)
    
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
        return aggregation.summarize_result_for_validation(result, max_length)
