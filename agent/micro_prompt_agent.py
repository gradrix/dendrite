"""
Micro-Prompting Agent: Neuron-Like LLM Architecture

Philosophy:
- Many tiny LLM calls >> Few large LLM calls
- Each call is focused and simple (50-200 tokens)
- Tools discovered on-demand, not all at once
- Gradual building like neurons in a brain
- Perfect for small models (3B params)

Architecture:
1. Decompose goal → micro-tasks
2. For each task:
   a. Extract keywords → find relevant tools (only 3-5)
   b. Select best tool → tiny prompt with small tool list
   c. Determine params → tiny prompt with tool signature
   d. Check if need helpers (time calc, etc.) → tiny prompt
   e. Execute helpers → save results
   f. Execute main tool → tiny prompt for retry
   g. Save result → auto
3. Aggregate → format output

Total: 10-15 micro-prompts @ 100-200 tokens each
vs Old: 2-3 huge prompts @ 5000+ tokens each
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from agent.ollama_client import OllamaClient
from agent.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class MicroTask:
    """A micro-task decomposed from the main goal."""
    description: str
    index: int
    result: Any = None
    completed: bool = False


class MicroPromptAgent:
    """
    Agent that uses many tiny LLM calls instead of few large ones.
    
    Each LLM call is:
    - Focused on ONE decision
    - Small context (50-200 tokens)
    - Easy for 3B models to handle
    - Self-contained
    
    Like neurons building up gradually to solve complex problems.
    """
    
    def __init__(
        self,
        ollama: OllamaClient,
        tool_registry: ToolRegistry,
        max_retries: int = 3
    ):
        self.ollama = ollama
        self.tools = tool_registry
        self.max_retries = max_retries
        self.context: Dict[str, Any] = {}  # Shared memory between tasks
        
    def execute_goal(self, goal: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute a goal through micro-task decomposition.
        
        Flow:
        1. Analyze goal → find relevant tools
        2. Decompose → 1-3 micro-tasks
        3. Execute each task → micro-prompting
        4. Aggregate results → format output
        
        Args:
            goal: Natural language goal
            dry_run: If True, don't execute tools
            
        Returns:
            Execution results and summary
        """
        logger.info(f"🎯 Goal: {goal}")
        logger.info(f"🧠 Using micro-task decomposition")
        
        # Step 0: Analyze goal and discover relevant tools
        logger.info("\n" + "="*60)
        logger.info("🔍 Step 0: Find relevant tools")
        logger.info("="*60)
        tool_context = self._analyze_goal_and_tools(goal)
        
        # Step 1: Decompose goal into micro-tasks
        logger.info("\n" + "="*60)
        logger.info("📋 Step 1: Decompose into micro-tasks")
        logger.info("="*60)
        tasks = self._decompose_goal(goal, tool_context)
        
        if not tasks:
            logger.error("   No tasks generated from goal")
            return {
                'success': False,
                'error': 'Could not decompose goal into tasks',
                'goal': goal
            }
        
        logger.info(f"   Generated {len(tasks)} tasks:")
        for task in tasks:
            logger.info(f"      {task.index}. {task.description}")
        
        # Step 2-N: Execute each micro-task
        all_results = []
        for task in tasks:
            logger.info("\n" + "="*60)
            logger.info(f"▶️  Step {task.index + 1}: Execute '{task.description}'")
            logger.info("="*60)
            
            try:
                result = self._execute_micro_task(task, dry_run)
                task.result = result
                task.completed = True
                all_results.append(result)
                
                # Store in context for next tasks
                self.context[f'task_{task.index}_result'] = result
                
                logger.info(f"   ✅ Task {task.index} completed")
                
            except Exception as e:
                logger.error(f"   ❌ Task {task.index} failed: {e}")
                task.completed = False
                # Continue to next task
        
        # Final step: Aggregate and format
        logger.info("\n" + "="*60)
        logger.info("📊 Final: Aggregate results and format")
        logger.info("="*60)
        
        # Combine all results
        combined_result = {
            'tasks': [{'description': t.description, 'completed': t.completed, 'result': t.result} for t in tasks],
            'all_results': all_results
        }
        
        formatted_output = self._format_final_output(goal, combined_result)
        
        completed_count = sum(1 for t in tasks if t.completed)
        success = completed_count > 0
        
        return {
            'success': success,
            'goal': goal,
            'tasks': tasks,
            'results': all_results,
            'output': formatted_output,
            'completed_tasks': completed_count,
            'total_tasks': len(tasks)
        }
    
    def _analyze_goal_and_tools(self, goal: str) -> str:
        """
        Micro-prompt 0: Analyze goal and discover what tools are available.
        
        This prevents the LLM from trying to manually navigate websites
        when API tools are available.
        
        Context size: ~200 tokens
        """
        # Get keywords from goal
        keywords = self._extract_keywords(goal)
        
        # Find relevant tools (fuzzy search)
        relevant_tools = self._search_tools(keywords)
        
        # Build tool summary
        if relevant_tools:
            tool_list = "\n".join([
                f"- {tool.name}: {tool.description}"
                for tool in relevant_tools[:10]  # Top 10 tools
            ])
            
            logger.info(f"   Found {len(relevant_tools)} relevant tools:")
            for tool in relevant_tools[:10]:
                logger.info(f"      • {tool.name}: {tool.description}")
        else:
            tool_list = "No specific tools found. Use general approach."
            logger.info(f"   No specific tools found")
        
        # Quick analysis prompt
        prompt = f"""Goal: {goal}

Available tools:
{tool_list}

Can this goal be achieved using the available API tools?
Answer: yes/no and which tools to use."""

        response = self.ollama.generate(
            prompt,
            system="You analyze if goals can use available API tools. Be concise.",
            temperature=0.3
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        logger.info(f"   Analysis: {response_str[:150]}...")
        
        # Return tool context for decomposition
        return f"Available tools:\n{tool_list}\n\nTool analysis: {response_str}"
    
    def _format_final_output(self, goal: str, result: Any) -> str:
        """
        Format the result in a user-friendly way using LLM.
        """
        # Convert result to string
        if isinstance(result, dict):
            # Extract the actual data
            if 'activities' in result:
                data = result['activities'][:10]  # Limit to first 10
            elif 'entries' in result:
                data = result['entries'][:10]
            elif 'kudos' in result:
                data = result['kudos'][:10]
            else:
                data = result
            
            data_str = json.dumps(data, indent=2)
        else:
            data_str = str(result)
        
        prompt = f"""Format this data to answer the user's goal.

Goal: {goal}

Data:
{data_str[:2000]}

Instructions:
- Show ALL retrieved items (don't truncate)
- If data includes activity names, IDs, types, kudos counts → show them all in a clear format
- If goal asks for "people who gave kudos" but data only has kudos COUNT → clarify that detailed names require a follow-up query
- Format as numbered list or table for clarity
- Be specific and informative

Example for dashboard feed:
1. Morning Run (ID: 12345678) - Run by John Doe - 5 kudos
2. Evening Bike (ID: 23456789) - Ride by Jane Smith - 12 kudos
3. Afternoon Swim (ID: 34567890) - Swim by Bob Johnson - 3 kudos

Now format ALL items in the data above:"""

        response = self.ollama.generate(
            prompt,
            system="You format data for users. Be concise and direct.",
            temperature=0.3
        )
        
        return str(response) if not isinstance(response, str) else response
    
    def _decompose_goal(self, goal: str, tool_context: str = "") -> List[MicroTask]:
        """
        Micro-prompt 1: Break goal into MINIMAL steps (prefer 1, max 2).
        
        Context size: ~150-300 tokens
        """
        prompt = f"""Break this goal into the absolute MINIMUM steps needed.

Goal: {goal}

{tool_context}

RULES - READ CAREFULLY:
1. **PREFER 1 STEP** if a single tool can do it
2. Use 2 steps ONLY if you must chain tools (e.g., get data, then give kudos)
3. Check tool descriptions - many already return the data you need
4. Don't add unnecessary "format" or "compile" steps - that happens automatically

EXAMPLES OF CORRECT DECOMPOSITION:

Goal: "Get my activities from last 24h with kudos counts"
Correct (1 step):
1. Call getDashboardFeed with hours_ago=24
Wrong (overcomplicated):
1. Get activities
2. Get kudos for each
3. Compile report

Goal: "Get activities and give kudos to each"
Correct (2 steps):
1. Call getDashboardFeed with hours_ago=24
2. Call giveKudos for each activity_id

Now decompose this goal - aim for 1 step, maximum 2:
Goal: {goal}

Output (numbered list only, no explanation):"""
        
        response = self.ollama.generate(
            prompt,
            system="You decompose goals into micro-tasks using available tools. Output only numbered list.",
            temperature=0.3  # Lower temp for structured output
        )
        
        # Ensure response is string
        response_str = str(response) if not isinstance(response, str) else response
        
        logger.info(f"   LLM Response ({len(response_str)} chars):")
        logger.info(f"   {response_str[:200]}...")
        
        # Parse task list
        tasks = []
        for line in response_str.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Match "1. Task" or "1) Task" or "- Task"
            match = re.match(r'^[\d\-\*\.)\]]+\s*(.+)$', line)
            if match:
                task_desc = match.group(1).strip()
                tasks.append(MicroTask(
                    description=task_desc,
                    index=len(tasks) + 1
                ))
        
        return tasks
    
    def _execute_micro_task(self, task: MicroTask, dry_run: bool) -> Any:
        """
        Execute a single micro-task through micro-prompting.
        
        Flow:
        1. Extract keywords (micro-prompt)
        2. Find relevant tools (search, no LLM)
        3. Select best tool (micro-prompt with only 3-5 tools)
        4. Determine parameters (micro-prompt)
        5. Execute with retry (micro-prompt on error)
        """
        # Micro-prompt 2: Extract keywords for tool search
        logger.info(f"\n   🔍 Micro-Prompt: Extract search keywords")
        keywords = self._extract_keywords(task.description)
        logger.info(f"   Keywords: {keywords}")
        
        # Tool search (no LLM, just fuzzy match)
        logger.info(f"\n   📚 Searching tools...")
        relevant_tools = self._search_tools(keywords)
        logger.info(f"   Found {len(relevant_tools)} relevant tools:")
        for tool in relevant_tools:
            logger.info(f"      - {tool.name}: {tool.description}")
        
        if not relevant_tools:
            logger.warning(f"   No tools found for keywords: {keywords}")
            return {"error": "No relevant tools found"}
        
        # Micro-prompt 3: Select best tool (tiny context - only 3-5 tools!)
        logger.info(f"\n   🎯 Micro-Prompt: Select best tool")
        tool_name = self._select_tool(task.description, relevant_tools)
        logger.info(f"   Selected: {tool_name}")
        
        tool = self.tools.get(tool_name)
        if not tool:
            logger.error(f"   Tool {tool_name} not found in registry")
            return {"error": f"Tool {tool_name} not found"}
        
        # Micro-prompt 4: Determine parameters
        logger.info(f"\n   ⚙️  Micro-Prompt: Determine parameters")
        params = self._determine_params(task.description, tool, self.context)
        logger.info(f"   Parameters: {params}")
        
        # Check if need helper tools (e.g., time calculation)
        if self._needs_helper_tools(params):
            logger.info(f"\n   🔧 Need helper tools (e.g., time calculation)")
            params = self._execute_helper_tools(params)
            logger.info(f"   Updated parameters: {params}")
        
        # Execute with retry and self-correction
        logger.info(f"\n   ▶️  Executing: {tool_name}")
        if dry_run:
            logger.info(f"   [DRY RUN] Would execute {tool_name}({params})")
            return {"dry_run": True, "tool": tool_name, "params": params}
        
        return self._execute_with_retry(tool, params)
    
    def _extract_keywords(self, task_desc: str) -> List[str]:
        """
        Micro-prompt 2: Extract 3-5 keywords for tool search.
        
        Context size: ~100 tokens (tiny!)
        """
        prompt = f"""Extract 3-5 keywords to search for tools.

Task: {task_desc}

Output only keywords, comma-separated (no explanation):"""
        
        response = self.ollama.generate(
            prompt,
            system="You extract keywords. Output only comma-separated words.",
            temperature=0.1
        )
        
        # Ensure response is string
        response_str = str(response) if not isinstance(response, str) else response
        
        # Parse keywords
        keywords = [k.strip().lower() for k in response_str.split(',')]
        # Also add words from task description
        task_words = re.findall(r'\b\w+\b', task_desc.lower())
        keywords.extend([w for w in task_words if len(w) > 3])
        
        return list(set(keywords))[:8]  # Max 8 keywords
    
    def _search_tools(self, keywords: List[str]) -> List[Any]:
        """
        Search tool registry by keywords.
        
        NO LLM call - just fuzzy matching on tool names and descriptions.
        Returns top 5 most relevant tools.
        """
        # Check if task involves data transformation/formatting
        transform_keywords = ['format', 'parse', 'extract', 'transform', 'display', 'show', 'list', 'analyze']
        needs_llm_tool = any(kw in keywords for kw in transform_keywords)
        
        scores = {}
        
        for tool_name, tool in self.tools.tools.items():
            score = 0
            search_text = f"{tool.name} {tool.description}".lower()
            
            for keyword in keywords:
                if keyword in search_text:
                    score += 1
                    if keyword in tool.name.lower():
                        score += 2  # Bonus for name match
            
            # Boost llm_analyze_pseudo if task needs formatting
            if tool_name == 'llm_analyze_pseudo' and needs_llm_tool:
                score += 10  # High priority for data transformation tasks
            
            if score > 0:
                scores[tool_name] = score
        
        # Sort by score and return top 5
        sorted_tools = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        return [self.tools.get(name) for name, _ in sorted_tools]
    
    def _select_tool(self, task_desc: str, tools: List[Any]) -> str:
        """
        Micro-prompt 3: Select best tool from small list (3-5 tools).
        
        Context size: ~200 tokens (tiny!)
        """
        tool_list = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in tools
        ])
        
        prompt = f"""Which tool is BEST for this task?

Task: {task_desc}

Available tools (pick ONE):
{tool_list}

Output only the tool name (no explanation):"""
        
        response = self.ollama.generate(
            prompt,
            system="You select tools. Output only tool name.",
            temperature=0.1
        )
        
        # Ensure response is string
        response_str = str(response) if not isinstance(response, str) else response
        
        # Extract tool name (find first match)
        tool_name = response_str.strip().split()[0]
        
        # Verify it's in our list
        for tool in tools:
            if tool.name.lower() in tool_name.lower():
                return tool.name
        
        # Fallback: return first tool
        return tools[0].name
    
    def _determine_params(
        self,
        task_desc: str,
        tool: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Micro-prompt 4: Determine tool parameters.
        
        Context size: ~250 tokens (small!)
        """
        # Format tool signature
        param_info = []
        for p in tool.parameters:
            name = p.get('name', '?')
            ptype = p.get('type', 'any')
            required = p.get('required', False)
            desc = p.get('description', '')
            req_str = "REQUIRED" if required else "optional"
            param_info.append(f"  - {name} ({ptype}) [{req_str}]: {desc}")
        
        param_text = "\n".join(param_info) if param_info else "  (no parameters)"
        
        # Add relevant context
        context_text = ""
        if context:
            context_text = "\n\nAvailable data from previous tasks:\n"
            for key, value in list(context.items())[-3:]:  # Last 3 only
                context_text += f"  - {key}: {str(value)[:100]}\n"
        
        prompt = f"""What parameters for this tool?

Task: {task_desc}
Tool: {tool.name}

Parameters:
{param_text}
{context_text}

Output ONLY valid JSON object (use null if unknown):
{{"param_name": "value"}}"""
        
        response = self.ollama.generate(
            prompt,
            system="You provide parameters as JSON. Output only valid JSON object.",
            temperature=0.2
        )
        
        # Ensure response is string
        response_str = str(response) if not isinstance(response, str) else response
        
        # Parse JSON
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
            if json_match:
                params = json.loads(json_match.group())
                # Remove null values
                params = {k: v for k, v in params.items() if v is not None}
                return params
            else:
                logger.warning(f"Could not parse JSON from response: {response}")
                return {}
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return {}
    
    def _needs_helper_tools(self, params: Dict[str, Any]) -> bool:
        """
        Check if parameters need helper tools (e.g., time calculation).
        
        NO LLM call - just check for known patterns.
        """
        # Check for time-related parameters
        time_params = ['after_unix', 'before_unix', 'timestamp', 'date']
        for param in time_params:
            if param in params and (params[param] is None or params[param] == ""):
                return True
        
        return False
    
    def _execute_helper_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute helper tools (e.g., getCurrentDateTime, getDateTimeHoursAgo).
        
        Uses micro-prompts to determine which helpers needed.
        """
        # Get current time if needed
        if 'after_unix' in params or 'before_unix' in params:
            logger.info(f"   Getting current time...")
            time_tool = self.tools.get('getCurrentDateTime')
            if time_tool:
                time_result = time_tool.execute()
                current_unix = time_result.get('datetime', {}).get('unix_timestamp')
                
                # If after_unix not set and goal mentions time range
                if not params.get('after_unix') and current_unix:
                    # Assume 24 hours for now (could be micro-prompt)
                    params['after_unix'] = current_unix - (24 * 3600)
                    logger.info(f"   Set after_unix to 24h ago: {params['after_unix']}")
        
        return params
    
    def _execute_with_retry(
        self,
        tool: Any,
        params: Dict[str, Any]
    ) -> Any:
        """
        Execute tool with micro-prompt retry on error.
        
        On error, use micro-prompt to analyze and fix parameters.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"   Attempt {attempt}/{self.max_retries}")
                result = tool.execute(**params)
                return result
            except Exception as e:
                logger.warning(f"   Attempt {attempt} failed: {e}")
                
                if attempt == self.max_retries:
                    raise
                
                # Micro-prompt: How to fix error?
                logger.info(f"\n   🔧 Micro-Prompt: Analyze and fix error")
                params = self._fix_error(tool, params, str(e))
                logger.info(f"   Corrected parameters: {params}")
        
        raise Exception(f"Failed after {self.max_retries} attempts")
    
    def _fix_error(
        self,
        tool: Any,
        params: Dict[str, Any],
        error: str
    ) -> Dict[str, Any]:
        """
        Micro-prompt: Analyze error and fix parameters.
        
        Context size: ~300 tokens (small!)
        """
        param_info = "\n".join([
            f"  - {p['name']}: {p.get('type', 'any')}"
            for p in tool.parameters
        ])
        
        prompt = f"""Fix these parameters based on error.

Tool: {tool.name}
Current parameters: {json.dumps(params)}
Error: {error}

Tool signature:
{param_info}

Common fixes:
- Remove unexpected parameters
- Add missing required parameters
- Fix type mismatches

Output ONLY corrected JSON:"""
        
        response = self.ollama.generate(
            prompt,
            system="You fix parameters. Output only valid JSON.",
            temperature=0.1
        )
        
        # Ensure response is string
        response_str = str(response) if not isinstance(response, str) else response
        
        # Parse JSON
        try:
            json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
            if json_match:
                fixed_params = json.loads(json_match.group())
                return {k: v for k, v in fixed_params.items() if v is not None}
            else:
                return params  # Keep original if can't parse
        except Exception:
            return params
    
    def _ai_tool_execute(self, goal: str, context: str = "") -> Dict[str, Any]:
        """
        Special "AI" tool: Use LLM directly to answer when no specific API tool exists.
        
        This is useful for:
        - Analysis/explanation questions
        - Formatting existing data
        - General information requests
        - Fallback when no tool matches
        """
        logger.info(f"   AI Tool: Answering directly with LLM")
        
        prompt = f"""Answer this user request directly.

Goal: {goal}

Context: {context if context else "No additional context"}

Provide a helpful, concise answer. If you need data from an API but don't have it,
explain what API call would be needed."""

        response = self.ollama.generate(
            prompt,
            system="You are a helpful assistant. Provide direct, accurate answers.",
            temperature=0.7
        )
        
        response_str = str(response) if not isinstance(response, str) else response
        
        return {
            'success': True,
            'answer': response_str,
            'source': 'AI direct response'
        }
    
    def _format_output(self, goal: str, tasks: List[MicroTask]) -> str:
        """
        Micro-prompt: Format final output for user.
        
        Context size: ~400 tokens (small!)
        """
        # Summarize task results
        task_summary = []
        for task in tasks:
            status = "✅" if task.completed else "❌"
            result_str = str(task.result)[:100] if task.result else "No result"
            task_summary.append(f"{status} Task {task.index}: {task.description}\n   Result: {result_str}")
        
        summary_text = "\n".join(task_summary)
        
        prompt = f"""Create user-friendly summary.

Original goal: {goal}

Task results:
{summary_text}

Write a concise summary for the user (2-3 sentences):"""
        
        response = self.ollama.generate(
            prompt,
            system="You create concise summaries for users.",
            temperature=0.5
        )
        
        # Ensure response is string
        response_str = str(response) if not isinstance(response, str) else response
        
        return response_str.strip()


# Export
__all__ = ['MicroPromptAgent', 'MicroTask']
