"""
Instruction Parser V2 - For Step-by-Step Execution

Parses instruction YAML files with the new step-based format.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

logger = logging.getLogger(__name__)


class StepDefinition:
    """Definition of a single step in an instruction."""
    
    def __init__(self, step_dict: Dict[str, Any]):
        self.id = step_dict.get('id')
        self.description = step_dict.get('description', '')
        self.tool = step_dict.get('tool')
        self.params = step_dict.get('params', {})
        self.params_template = step_dict.get('params_template', {})
        self.depends_on = step_dict.get('depends_on', [])
        self.save_as = step_dict.get('save_as')
        self.loop = step_dict.get('loop')
        self.context = step_dict.get('context')
        self.input = step_dict.get('input')
        self.output_format = step_dict.get('output_format')
        self.aggregate = step_dict.get('aggregate', False)
        self.optional = step_dict.get('optional', False)
        
        # Convert depends_on to list if single string
        if isinstance(self.depends_on, str):
            self.depends_on = [self.depends_on]
    
    def __repr__(self):
        return f"StepDefinition(id={self.id}, tool={self.tool}, depends_on={self.depends_on})"
    
    def has_dependencies(self) -> bool:
        """Check if step has dependencies."""
        return len(self.depends_on) > 0
    
    def is_loop_step(self) -> bool:
        """Check if step executes in a loop."""
        return self.loop is not None
    
    def is_llm_step(self) -> bool:
        """Check if step requires LLM reasoning."""
        return self.tool == 'llm_analyze'


class InstructionV2:
    """
    Parsed instruction with step-by-step execution plan.
    """
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.name = ""
        self.description = ""
        self.execution_mode = "sequential"
        self.steps: List[StepDefinition] = []
        self.permissions = {}
        self.context_template = ""
        
        self._load()
        self._validate()
    
    def _load(self):
        """Load instruction from YAML file."""
        try:
            with open(self.filepath) as f:
                data = yaml.safe_load(f)
            
            self.name = data.get('name', '')
            self.description = data.get('description', '')
            self.execution_mode = data.get('execution_mode', 'sequential')
            self.context_template = data.get('context', '')
            self.permissions = data.get('permissions', {})
            
            # Parse steps
            steps_data = data.get('steps', [])
            for step_dict in steps_data:
                step = StepDefinition(step_dict)
                self.steps.append(step)
            
            logger.info(f"Loaded instruction '{self.name}' with {len(self.steps)} steps")
            
        except Exception as e:
            logger.error(f"Failed to load instruction from {self.filepath}: {e}")
            raise
    
    def _validate(self):
        """Validate instruction structure."""
        errors = []
        
        # Check required fields
        if not self.name:
            errors.append("Instruction must have a name")
        
        if not self.steps:
            errors.append("Instruction must have at least one step")
        
        # Check step IDs are unique
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            errors.append("Step IDs must be unique")
        
        # Check dependencies exist
        step_id_set = set(step_ids)
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in step_id_set:
                    errors.append(f"Step '{step.id}' depends on non-existent step '{dep}'")
        
        # Check for circular dependencies
        if self._has_circular_dependencies():
            errors.append("Circular dependencies detected in steps")
        
        # Check tools are specified
        for step in self.steps:
            if not step.tool:
                errors.append(f"Step '{step.id}' must specify a tool")
        
        if errors:
            error_msg = "Instruction validation failed:\n  " + "\n  ".join(errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _has_circular_dependencies(self) -> bool:
        """Check for circular dependencies in step graph."""
        # Build dependency graph
        graph = {step.id: set(step.depends_on) for step in self.steps}
        
        # DFS to detect cycles
        def has_cycle(node: str, visited: Set[str], rec_stack: Set[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        visited = set()
        for step_id in graph:
            if step_id not in visited:
                if has_cycle(step_id, visited, set()):
                    return True
        
        return False
    
    def get_execution_order(self) -> List[StepDefinition]:
        """
        Get steps in execution order (topological sort).
        
        For sequential mode, this respects the order in the YAML.
        Dependencies are still checked but order is preserved.
        
        Returns:
            List of steps in execution order
        """
        if self.execution_mode == "sequential":
            # Return steps in YAML order
            # But verify dependencies are satisfied
            available = set()
            for step in self.steps:
                for dep in step.depends_on:
                    if dep not in available:
                        logger.warning(
                            f"Step '{step.id}' depends on '{dep}' which comes later. "
                            f"Consider reordering steps."
                        )
                available.add(step.id)
            
            return self.steps
        
        else:
            # Topological sort for planned mode
            return self._topological_sort()
    
    def _topological_sort(self) -> List[StepDefinition]:
        """
        Perform topological sort on steps based on dependencies.
        
        Returns:
            List of steps in dependency order
        """
        # Build adjacency list and in-degree count
        graph = {step.id: step for step in self.steps}
        in_degree = {step.id: 0 for step in self.steps}
        adj_list = {step.id: [] for step in self.steps}
        
        for step in self.steps:
            for dep in step.depends_on:
                adj_list[dep].append(step.id)
                in_degree[step.id] += 1
        
        # Kahn's algorithm
        queue = [step_id for step_id in in_degree if in_degree[step_id] == 0]
        result = []
        
        while queue:
            step_id = queue.pop(0)
            result.append(graph[step_id])
            
            for neighbor in adj_list[step_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(self.steps):
            raise ValueError("Cannot perform topological sort (circular dependency)")
        
        return result
    
    def get_step(self, step_id: str) -> Optional[StepDefinition]:
        """Get step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if tool is allowed by permissions."""
        # For now, allow all tools
        # Can be extended with explicit allow/deny lists
        return True
    
    def requires_approval_for(self, step: StepDefinition) -> bool:
        """Check if step requires user approval."""
        requires_approval = self.permissions.get('requires_approval', [])
        
        # Check if tool is in approval list
        if step.tool in requires_approval:
            return True
        
        # Check if specific step ID is in approval list
        if step.id in requires_approval:
            return True
        
        return False
    
    def allows_write_operations(self) -> bool:
        """Check if write operations are allowed."""
        return self.permissions.get('allow_write', False)


def load_instruction(filepath: str) -> InstructionV2:
    """
    Load instruction from YAML file.
    
    Args:
        filepath: Path to instruction YAML file
        
    Returns:
        Parsed InstructionV2 object
    """
    return InstructionV2(Path(filepath))


if __name__ == "__main__":
    # Test instruction parser
    logging.basicConfig(level=logging.DEBUG)
    
    # Create test instruction YAML in memory
    test_yaml = """
name: "Test Instruction"
description: "Test for parser"
execution_mode: "sequential"

steps:
  - id: "step1"
    description: "First step"
    tool: "getTool1"
    params:
      value: 42
    save_as: "result1"
  
  - id: "step2"
    description: "Second step"
    tool: "getTool2"
    params_template:
      input: "{{result1.output}}"
    depends_on: ["step1"]
    save_as: "result2"
  
  - id: "step3"
    description: "Loop step"
    tool: "processTool"
    loop: "{{result2.items}}"
    params_template:
      item_id: "{{loop.item.id}}"
    depends_on: ["step2"]
    aggregate: true

permissions:
  allow_write: true
  requires_approval: []
"""
    
    # Save test YAML
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(test_yaml)
        test_file = f.name
    
    try:
        # Load and validate
        instruction = load_instruction(test_file)
        
        print(f"✅ Loaded: {instruction.name}")
        print(f"✅ Mode: {instruction.execution_mode}")
        print(f"✅ Steps: {len(instruction.steps)}")
        
        # Test execution order
        order = instruction.get_execution_order()
        print(f"✅ Execution order: {[s.id for s in order]}")
        
        # Test step access
        step2 = instruction.get_step('step2')
        print(f"✅ Step2 dependencies: {step2.depends_on}")
        print(f"✅ Step2 has deps: {step2.has_dependencies()}")
        
        # Test step3 loop
        step3 = instruction.get_step('step3')
        print(f"✅ Step3 is loop: {step3.is_loop_step()}")
        print(f"✅ Step3 aggregate: {step3.aggregate}")
        
        print("\n✅ All instruction parser tests passed!")
        
    finally:
        import os
        os.unlink(test_file)
