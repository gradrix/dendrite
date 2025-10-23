"""
Action Executor

Executes tool actions with safety checks and permissions.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from agent.tool_registry import ToolRegistry
from agent.instruction_loader import Instruction

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes actions with safety checks."""
    
    def __init__(
        self,
        registry: ToolRegistry,
        dry_run: bool = False,
        max_actions: int = 10,
        cooldown_seconds: int = 5
    ):
        self.registry = registry
        self.dry_run = dry_run
        self.max_actions = max_actions
        self.cooldown_seconds = cooldown_seconds
    
    def execute_actions(
        self,
        actions: List[Dict[str, Any]],
        instruction: Instruction,
        approval_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a list of actions with safety checks.
        
        Returns:
            List of results for each action
        """
        if not actions:
            logger.info("No actions to execute")
            return []
        
        # Safety: Limit number of actions
        if len(actions) > self.max_actions:
            logger.warning(
                f"Too many actions requested ({len(actions)}). "
                f"Limiting to {self.max_actions}"
            )
            actions = actions[:self.max_actions]
        
        results = []
        
        for i, action in enumerate(actions):
            tool_name = action.get("tool")
            params = action.get("params", {})
            
            logger.info(f"Action {i+1}/{len(actions)}: {tool_name}({params})")
            
            # Check if tool exists
            tool = self.registry.get(tool_name)
            if not tool:
                error = f"Tool not found: {tool_name}"
                logger.error(error)
                results.append({
                    "success": False,
                    "error": error,
                    "tool": tool_name
                })
                continue
            
            # Check if tool is allowed in instruction
            if not instruction.is_tool_allowed(tool_name):
                error = f"Tool {tool_name} not allowed in instruction"
                logger.error(error)
                results.append({
                    "success": False,
                    "error": error,
                    "tool": tool_name
                })
                continue
            
            # Check permissions
            if tool.permissions == "write":
                # Check instruction permissions
                if not instruction.permissions.get("allow_write", False):
                    # Specific permission checks
                    permission_key = f"allow_{tool_name.lower()}"
                    if not instruction.permissions.get(permission_key, False):
                        error = f"Write permission denied for {tool_name}"
                        logger.warning(error)
                        results.append({
                            "success": False,
                            "error": error,
                            "tool": tool_name,
                            "requires_approval": True
                        })
                        continue
            
            # Check if requires approval
            action_description = f"{tool_name} with {params}"
            if instruction.requires_approval_for(action_description):
                logger.info(f"Action requires approval: {action_description}")
                
                if approval_callback:
                    approved = approval_callback(tool_name, params)
                    if not approved:
                        results.append({
                            "success": False,
                            "error": "Action not approved",
                            "tool": tool_name,
                            "requires_approval": True
                        })
                        continue
                else:
                    # No approval callback, skip
                    results.append({
                        "success": False,
                        "error": "Requires approval but no approval mechanism available",
                        "tool": tool_name,
                        "requires_approval": True
                    })
                    continue
            
            # Execute action
            try:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would execute: {tool_name}({params})")
                    result = {
                        "success": True,
                        "tool": tool_name,
                        "params": params,
                        "dry_run": True,
                        "result": "Dry run - not executed"
                    }
                else:
                    # Actually execute
                    logger.info(f"Executing: {tool_name}")
                    output = tool.execute(**params)
                    result = {
                        "success": True,
                        "tool": tool_name,
                        "params": params,
                        "result": output
                    }
                    logger.info(f"Action completed successfully")
                
                results.append(result)
                
                # Cooldown between actions
                if i < len(actions) - 1 and not self.dry_run:
                    logger.debug(f"Cooldown: {self.cooldown_seconds}s")
                    time.sleep(self.cooldown_seconds)
                
            except Exception as e:
                error = f"Error executing {tool_name}: {str(e)}"
                logger.error(error, exc_info=True)
                results.append({
                    "success": False,
                    "error": error,
                    "tool": tool_name,
                    "params": params
                })
        
        # Summary
        success_count = sum(1 for r in results if r.get("success"))
        logger.info(
            f"Executed {len(results)} actions: "
            f"{success_count} successful, {len(results) - success_count} failed"
        )
        
        return results
