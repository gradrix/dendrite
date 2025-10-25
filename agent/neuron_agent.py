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
    
    MAX_DEPTH = 3  # Maximum recursion depth
    MAX_RETRIES = 2  # Retries per neuron if validation fails
    
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
            params = self._micro_determine_params(neuron.description, tool, self.context)
            logger.info(f"{indent}│  ├─ Params: {json.dumps(params)[:100]}")
            
            # Step 3: Execute tool
            try:
                result = tool.execute(**params)
                logger.info(f"{indent}│  ├─ Result: {self._summarize_result(result)}")
            except Exception as e:
                logger.warning(f"{indent}│  │  ⚠️  Execution error: {e}")
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
        """Micro-prompt: Decompose goal into 1-2 neurons."""
        
        prompt = f"""Break this goal into 1-2 simple steps.

Goal: {goal}

Rules:
- Prefer 1 step if possible
- Use 2 steps only if you must chain actions
- Each step = ONE tool call
- Don't add format/compile steps

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
            # Show summary of available data
            context_info = "\n\nAvailable data from previous steps:"
            for key, value in list(context.items())[:3]:  # Limit to 3 to avoid token overflow
                summary = self._summarize_result(value)
                context_info += f"\n  - {key}: {summary}"
        
        prompt = f"""Extract parameters from the task description and available data.

Task: {neuron_desc}
Tool: {tool.name}

Parameters needed:
{param_info}
{context_info}

CRITICAL RULES:
1. If task mentions a specific ID (like "activity 16242569491"), use that EXACT value
2. If current item data is shown above, extract IDs from it (e.g., activity_id, athlete_id, id)
3. Do NOT use fake/example values like 12345
4. Extract numeric IDs as integers, not strings

Output JSON only (no explanation):"""
        
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
                params = {k: v for k, v in params.items() if v is not None}
                
                # Fallback: If LLM failed to extract params, try regex on neuron description
                if not params or all(v in [None, "", {}, []] for v in params.values()):
                    params = self._extract_params_from_text(neuron_desc, tool.parameters, dendrite_item)
                
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
        
        prompt = f"""Is this result valid for the goal?

Parent goal: {parent_goal}
Current step: {neuron_desc}
Result: {result_summary}

Valid if:
- No error occurred
- Returned data matches what was requested
- Makes progress toward parent goal

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
        """Fallback: Use AI to answer directly."""
        
        prompt = f"""Answer this directly (no tools available):

{neuron_desc}

Provide a brief, helpful response:"""
        
        response = self.ollama.generate(
            prompt,
            system="Answer questions directly and concisely.",
            temperature=0.5
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
                return f"Success: {result.get('count', '?')} items"
            return f"{len(result)} fields"
        elif isinstance(result, list):
            return f"{len(result)} items"
        else:
            return str(result)[:100]
    
    def _log(self, message: str):
        """Add to execution log for debugging."""
        self.execution_log.append(message)
