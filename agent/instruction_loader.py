"""
Instruction Loader

Loads and parses instruction files (YAML) for the AI agent.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class Instruction:
    """Represents a loaded instruction for the agent."""
    
    def __init__(self, data: Dict[str, Any], file_path: str):
        self.file_path = file_path
        self.name = data.get("name", "Unnamed Task")
        self.description = data.get("description", "")
        self.schedule = data.get("schedule", "manual")
        self.enabled = data.get("enabled", True)
        self.context = data.get("context", "")
        self.tools_allowed = data.get("tools_allowed", [])
        self.decision_rules = data.get("decision_rules", {})
        self.permissions = data.get("permissions", {})
        self.requires_approval = data.get("requires_approval", [])
        self.output = data.get("output", {})
    
    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed in this instruction."""
        if not self.tools_allowed:
            return True  # No restrictions
        return tool_name in self.tools_allowed
    
    def requires_approval_for(self, action: str) -> bool:
        """Check if an action requires approval."""
        for rule in self.requires_approval:
            if rule.lower() in action.lower():
                return True
        return False
    
    def get_context_prompt(self) -> str:
        """Get the formatted context for the LLM."""
        parts = [self.context]
        
        # Add decision rules as context
        if self.decision_rules:
            parts.append("\nDecision Rules:")
            for category, rules in self.decision_rules.items():
                parts.append(f"\n{category.title()}:")
                if isinstance(rules, list):
                    for rule in rules:
                        parts.append(f"  - {rule}")
                else:
                    parts.append(f"  {rules}")
        
        return "\n".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "schedule": self.schedule,
            "enabled": self.enabled,
            "tools_allowed": self.tools_allowed,
            "permissions": self.permissions,
        }


class InstructionLoader:
    """Loads instruction files from directory."""
    
    def __init__(self, instructions_dir: str = "instructions"):
        self.instructions_dir = Path(instructions_dir)
        self.instructions: Dict[str, Instruction] = {}
    
    def load_all(self) -> List[Instruction]:
        """Load all instruction files."""
        if not self.instructions_dir.exists():
            logger.warning(f"Instructions directory not found: {self.instructions_dir}")
            return []
        
        loaded = []
        for file_path in self.instructions_dir.glob("*.yaml"):
            try:
                instruction = self.load_file(file_path)
                if instruction and instruction.enabled:
                    self.instructions[instruction.name] = instruction
                    loaded.append(instruction)
                    logger.info(f"Loaded instruction: {instruction.name}")
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
        
        return loaded
    
    def load_file(self, file_path: Path) -> Optional[Instruction]:
        """Load a single instruction file."""
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        if not data:
            return None
        
        return Instruction(data, str(file_path))
    
    def get(self, name: str) -> Optional[Instruction]:
        """Get instruction by name."""
        return self.instructions.get(name)
    
    def get_scheduled(self, schedule: str) -> List[Instruction]:
        """Get instructions with specific schedule."""
        return [
            inst for inst in self.instructions.values()
            if inst.schedule == schedule and inst.enabled
        ]
