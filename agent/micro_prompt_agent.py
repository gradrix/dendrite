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
        Execute a goal through micro-prompting.
        
        Args:
            goal: Natural language goal
            dry_run: If True, don't execute tools
            
        Returns:
            Execution results and summary
        """
        logger.info(f"🎯 Goal: {goal}")
        logger.info(f"🧠 Using micro-prompting (tiny focused calls)")
        
        # Micro-prompt 1: Decompose goal into micro-tasks
        logger.info("\n" + "="*60)
        logger.info("📋 Micro-Prompt 1: Decompose goal into tasks")
        logger.info("="*60)
        tasks = self._decompose_goal(goal)
        logger.info(f"   Found {len(tasks)} micro-tasks:")
        for task in tasks:
            logger.info(f"   {task.index}. {task.description}")
        
        # Execute each micro-task
        for task in tasks:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔧 Executing Task {task.index}: {task.description}")
            logger.info(f"{'='*60}")
            
            try:
                result = self._execute_micro_task(task, dry_run)
                task.result = result
                task.completed = True
                self.context[f"task_{task.index}"] = result
                logger.info(f"✅ Task {task.index} completed")
            except Exception as e:
                logger.error(f"❌ Task {task.index} failed: {e}")
                task.completed = False
                # Continue with other tasks
        
        # Micro-prompt N: Format final output
        logger.info(f"\n{'='*60}")
        logger.info("📊 Formatting final output")
        logger.info(f"{'='*60}")
        output = self._format_output(goal, tasks)
        
        return {
            "success": True,
            "goal": goal,
            "tasks_completed": len([t for t in tasks if t.completed]),
            "tasks_total": len(tasks),
            "output": output,
            "context": self.context
        }
    
    def _decompose_goal(self, goal: str) -> List[MicroTask]:
        """
        Micro-prompt 1: Break goal into 3-7 micro-tasks.
        
        Context size: ~150 tokens (tiny!)
        """
        prompt = f"""Break this goal into simple micro-tasks (3-7 tasks).

Goal: {goal}

Rules:
- Each task should be ONE simple action
- Be specific and actionable
- Order matters (dependencies)

Output format (just the list):
1. Task description
2. Task description
3. Task description
..."""
        
        response = self.ollama.generate(
            prompt,
            system="You decompose goals into micro-tasks. Output only numbered list.",
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
        scores = {}
        
        for tool_name, tool in self.tools.tools.items():
            score = 0
            search_text = f"{tool.name} {tool.description}".lower()
            
            for keyword in keywords:
                if keyword in search_text:
                    score += 1
                    if keyword in tool.name.lower():
                        score += 2  # Bonus for name match
            
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
