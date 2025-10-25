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
        tool_registry: ToolRegistry
    ):
        self.ollama = ollama
        self.tools = tool_registry
        self.context: Dict[str, Any] = {}
        self.execution_log: List[str] = []  # For debugging
        
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
                
                # Store in context for subsequent neurons
                self.context[f'neuron_{depth}_{neuron.index}'] = result
                
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
                    
                    # Update final result with corrected output
                    if isinstance(corrective_result, dict) and corrective_result.get('success'):
                        final_result = corrective_result
                        all_results.append(corrective_result)
                    
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
        
        # Pre-execution check: Does this neuron need to iterate over context data?
        if neuron.depth < self.MAX_DEPTH - 1:
            logger.info(f"{indent}│  ├─ Checking for pre-execution spawning...")
            logger.info(f"{indent}│  │  Context keys: {list(self.context.keys())}")
            context_list = self._find_context_list_for_iteration(neuron.description)
            if context_list:
                logger.info(f"{indent}│  ├─ 🌿 Pre-execution spawning (iterate over context)")
                return self._spawn_dendrites_from_context(neuron, context_list, parent_goal)
            else:
                logger.info(f"{indent}│  │  No context list found for iteration")
        
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
            
            # Step 3: Execute tool
            try:
                result = tool.execute(**params)
                logger.info(f"{indent}│  ├─ Result: {self._summarize_result(result)}")
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
    
    # ========================================================================
    # Micro-Prompts (each 50-100 tokens)
    # ========================================================================
    
    def _micro_decompose(self, goal: str, depth: int) -> List[Neuron]:
        """Micro-prompt: Decompose goal into 1-4 neurons."""
        
        prompt = f"""Break this goal into 1-4 simple steps.

Goal: {goal}

Rules:
- Each step = ONE action (ONE tool call OR one AI response)
- If goal asks "get X and convert Y", that's 2 steps
- If goal asks "get X, convert Y, validate Z, report", that's 4 steps
- Each action must be atomic and independent
- Format/display/report steps go at the end

Output (numbered list only):"""
        
        response = self.ollama.generate(
            prompt,
            system="Decompose goals into minimal steps. Output numbered list only.",
            temperature=0.3
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        # Parse neurons
        neurons = []
        for line in response_str.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            match = re.match(r'^[\d\-\*\.)\]]+\s*(.+)$', line)
            if match:
                description = match.group(1).strip()
                neurons.append(Neuron(
                    description=description,
                    index=len(neurons) + 1,
                    depth=depth
                ))
        
        return neurons
    
    def _micro_find_tool(self, neuron_desc: str) -> Optional[Any]:
        """Micro-prompt: Which tool for this neuron?"""
        
        # Check if this is a formatting/display task (no tool needed)
        formatting_keywords = ['format', 'display', 'show', 'report', 'present', 'output', 'print', 'organize']
        has_format_keyword = any(kw in neuron_desc.lower() for kw in formatting_keywords)
        
        # If it's about formatting EXISTING data OR it's last neuron with context, use AI
        is_formatting_existing = any(word in neuron_desc.lower() for word in ['existing', 'available', 'current results', 'all three', 'above', 'results', 'data'])
        has_context = len(self.context) > 0
        
        if has_format_keyword and (is_formatting_existing or (has_context and 'human-readable' in neuron_desc.lower())):
            logger.info(f"   │  │  💡 Detected formatting task, will use AI response")
            return None
        
        # Extract keywords
        keywords = re.findall(r'\b\w{4,}\b', neuron_desc.lower())
        
        # Search tools
        relevant_tools = []
        for tool in self.tools.list_tools():
            tool_text = f"{tool.name} {tool.description}".lower()
            score = sum(1 for kw in keywords if kw in tool_text)
            if score > 0:
                relevant_tools.append((score, tool))
        
        if not relevant_tools:
            return None
        
        # Sort by score and take top 5
        relevant_tools.sort(reverse=True, key=lambda x: x[0])
        top_tools = [t[1] for t in relevant_tools[:5]]
        
        # Micro-prompt: Pick best
        tool_list = "\n".join([f"- {t.name}: {t.description}" for t in top_tools])
        
        prompt = f"""Which tool is BEST for this?

Task: {neuron_desc}

Tools:
{tool_list}

Output only tool name:"""
        
        response = self.ollama.generate(
            prompt,
            system="Select tool. Output only name.",
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
    
    def _micro_determine_params(self, neuron_desc: str, tool: Any, context: Dict) -> Dict[str, Any]:
        """Micro-prompt: What parameters?"""
        
        param_info = "\n".join([
            f"  - {p['name']} ({p.get('type', 'any')}): {p.get('description', '')}"
            for p in tool.parameters
        ])
        
        # Find dendrite item data in context (most relevant for current execution)
        dendrite_item = None
        for key, value in context.items():
            if key.startswith('dendrite_item_') and isinstance(value, dict):
                dendrite_item = value
                break
        
        # Build context info
        context_info = ""
        if dendrite_item:
            # Show the specific item we're processing
            context_info = f"\n\nCurrent item data:\n{json.dumps(dendrite_item, indent=2)[:500]}"
        elif context:
            # Show detailed data from previous steps with actual values
            context_info = "\n\nData available from previous steps (use these values!):"
            for key, value in list(context.items())[:5]:  # Show up to 5 items
                # Show actual result data, not just summary
                if isinstance(value, dict):
                    # For dicts, show relevant fields
                    relevant_fields = {}
                    for field_key in ['unix_timestamp', 'timestamp', 'id', 'activity_id', 'success', 'human_readable', 'count', 'year', 'month']:
                        if field_key in value:
                            relevant_fields[field_key] = value[field_key]
                    if relevant_fields:
                        context_info += f"\n  - {key}: {json.dumps(relevant_fields)}"
                    else:
                        summary = self._summarize_result(value)
                        context_info += f"\n  - {key}: {summary}"
                else:
                    context_info += f"\n  - {key}: {value}"
        
        prompt = """Extract parameters from the task description and available data.

Task: {task}
Tool: {tool_name}

Parameters needed:
{param_info}
{context_info}

CRITICAL RULES:
1. ALL REQUIRED parameters MUST be provided - do NOT return empty {{}}
2. If previous steps returned data with fields like 'unix_timestamp', 'id', 'activity_id' - USE THOSE EXACT VALUES
3. For validateTimestamp: 
   - unix_timestamp comes from previous dateToUnixTimestamp result
   - expected_description should describe the date (e.g., "January 2024")
4. If task mentions a specific ID (like "activity 16242569491"), use that EXACT value
5. If current item data is shown above, extract IDs from it (e.g., activity_id, athlete_id, id)
6. Do NOT use fake/example values like 12345 or 1234567890
7. Extract numeric values as integers, not strings
8. Check REQUIRED field - those parameters CANNOT be omitted!

EXAMPLE: If previous step (neuron_0_2) returned {{"unix_timestamp": 1704067200}}, and you need unix_timestamp parameter, use: {{"unix_timestamp": 1704067200, "expected_description": "January 2024"}}

Output JSON only (no explanation):""".format(
            task=neuron_desc,
            tool_name=tool.name,
            param_info=param_info,
            context_info=context_info
        )
        
        response = self.ollama.generate(
            prompt,
            system="Provide parameters as JSON. Output only valid JSON.",
            temperature=0.2
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
                
                # Clean up None values
                params = {k: v for k, v in params.items() if v is not None}
                
                # Validate required parameters
                required_params = [p['name'] for p in tool.parameters if p.get('required', False)]
                missing_params = [p for p in required_params if p not in params or params[p] in [None, "", {}, []]]
                
                # Fallback: If LLM failed to extract params or missing required params, search context for values
                if not params or missing_params:
                    if missing_params:
                        logger.debug(f"   │  │  ⚠️  Missing required parameters: {missing_params}, trying context search")
                    
                    # Search context for required param values
                    for param_name in missing_params if missing_params else required_params:
                        # Look through all context for this param
                        for ctx_key, ctx_value in context.items():
                            if isinstance(ctx_value, dict) and param_name in ctx_value:
                                params[param_name] = ctx_value[param_name]
                                logger.debug(f"   │  │  ✓ Found {param_name} = {params[param_name]} in {ctx_key}")
                                break
                        
                        # Special handling for validateTimestamp
                        if tool.name == 'validateTimestamp':
                            if param_name == 'unix_timestamp' and param_name not in params:
                                # Look for unix_timestamp in previous conversion result
                                for ctx_value in context.values():
                                    if isinstance(ctx_value, dict) and 'unix_timestamp' in ctx_value:
                                        params['unix_timestamp'] = ctx_value['unix_timestamp']
                                        logger.debug(f"   │  │  ✓ Found unix_timestamp = {params['unix_timestamp']} from previous result")
                                        break
                            
                            if param_name == 'expected_description' and param_name not in params:
                                # Extract from neuron description (e.g., "Validate the timestamp" → look at parent goal)
                                if 'January 2024' in neuron_desc or 'january 2024' in neuron_desc.lower():
                                    params['expected_description'] = 'January 2024'
                                    logger.debug(f"   │  │  ✓ Extracted expected_description from task description")
                    
                    # Final fallback: regex extraction from neuron description
                    if not params or missing_params:
                        params_from_text = self._extract_params_from_text(neuron_desc, tool.parameters, dendrite_item)
                        for key, value in params_from_text.items():
                            if key not in params or params[key] in [None, "", {}, []]:
                                params[key] = value
                
                return params
            except:
                pass
        
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
        """Micro-prompt: Combine neuron results."""
        
        # If only one neuron, return its result directly
        if len(neurons) == 1:
            return results[0]
        
        # Build summary of what each neuron did
        summary = "\n".join([
            f"{n.index}. {n.description} → {self._summarize_result(r)}"
            for n, r in zip(neurons, results)
        ])
        
        prompt = f"""Combine these results to answer the goal.

Goal: {goal}

Results:
{summary}

Output a combined summary (2-3 sentences):"""
        
        response = self.ollama.generate(
            prompt,
            system="Combine results concisely.",
            temperature=0.3
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        return {
            'summary': response_str.strip(),
            'detailed_results': results
        }
    
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
        
        # Build context summary
        context_summary = ""
        if self.context:
            context_summary = "\n\nAvailable data:"
            for key, value in list(self.context.items())[:10]:
                if isinstance(value, dict):
                    # Show the actual data
                    context_summary += f"\n  {key}: {json.dumps(value, indent=2)[:300]}"
                else:
                    context_summary += f"\n  {key}: {value}"
        
        prompt = f"""Answer this task using the available data (no tools available):

Task: {neuron_desc}
{context_summary}

Provide a clear, formatted response:"""
        
        response = self.ollama.generate(
            prompt,
            system="Answer tasks directly using provided data. Format responses clearly.",
            temperature=0.3
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
                    # Check for count or other indicators
                    if 'count' in result:
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
