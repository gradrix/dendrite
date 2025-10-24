"""
Template Engine for Step Execution

Handles variable substitution in step parameters:
- {{variable.path.to.value}} - Dot notation access
- {{loop.item}} - Current loop item
- {{loop.index}} - Current loop index
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Engine for processing template variables in step parameters."""
    
    def __init__(self, context: Optional[Dict[str, Any]] = None):
        """
        Initialize template engine.
        
        Args:
            context: Dictionary of available variables
        """
        self.context = context or {}
        self.loop_context = {}
    
    def set_context(self, context: Dict[str, Any]):
        """Update the context with new variables."""
        self.context.update(context)
    
    def set_loop_context(self, item: Any, index: int):
        """Set the loop context for current iteration."""
        self.loop_context = {
            "item": item,
            "index": index
        }
    
    def clear_loop_context(self):
        """Clear loop context after loop completion."""
        self.loop_context = {}
    
    def resolve_value(self, path: str) -> Any:
        """
        Resolve a dot-notation path to a value.
        
        Args:
            path: Dot-notation path like "variable.field.subfield"
            
        Returns:
            The resolved value or None if not found
            
        Example:
            context = {"time": {"datetime": {"unix": 1234567890}}}
            resolve_value("time.datetime.unix") -> 1234567890
        """
        parts = path.split('.')
        
        # Check if path starts with 'loop'
        if parts[0] == 'loop':
            current = self.loop_context
            parts = parts[1:]  # Skip 'loop' prefix
        else:
            current = self.context
        
        # Navigate through nested dictionaries
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                    current = current[index]
                except (ValueError, IndexError):
                    logger.warning(f"Cannot access index {part} in list")
                    return None
            else:
                logger.warning(f"Cannot access {part} in {type(current)}")
                return None
            
            if current is None:
                return None
        
        return current
    
    def render_value(self, value: Any) -> Any:
        """
        Render a value, substituting any template variables.
        
        Args:
            value: Value to render (can be string, dict, list, or primitive)
            
        Returns:
            Rendered value with substitutions applied
        """
        if isinstance(value, str):
            return self._render_string(value)
        elif isinstance(value, dict):
            return {k: self.render_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.render_value(item) for item in value]
        else:
            return value
    
    def _render_string(self, template: str) -> Any:
        """
        Render a string template.
        
        If the entire string is a template variable, return the actual value.
        Otherwise, substitute variables into the string.
        
        Args:
            template: String that may contain {{variable}} patterns
            
        Returns:
            Rendered value (may not be a string if entire template is one variable)
        """
        # Check if entire string is a single template variable
        single_var_match = re.match(r'^\{\{([^}]+)\}\}$', template.strip())
        if single_var_match:
            var_path = single_var_match.group(1).strip()
            value = self.resolve_value(var_path)
            return value
        
        # Otherwise, substitute all variables in the string
        def replace_var(match):
            var_path = match.group(1).strip()
            value = self.resolve_value(var_path)
            if value is None:
                logger.warning(f"Variable {var_path} not found in context")
                return match.group(0)  # Keep original if not found
            return str(value)
        
        result = re.sub(r'\{\{([^}]+)\}\}', replace_var, template)
        return result
    
    def render_params(self, params_template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render parameter template with current context.
        
        Args:
            params_template: Dictionary with potential template variables
            
        Returns:
            Dictionary with all variables resolved
        """
        return self.render_value(params_template)
    
    def get_loop_array(self, loop_spec: str) -> List[Any]:
        """
        Get the array to loop over from a loop specification.
        
        Args:
            loop_spec: Template variable pointing to an array, e.g., "{{activities}}"
            
        Returns:
            List to iterate over, or empty list if not found
        """
        if not loop_spec:
            return []
        
        # Extract variable path from {{variable}}
        match = re.match(r'^\{\{([^}]+)\}\}$', loop_spec.strip())
        if not match:
            logger.error(f"Invalid loop specification: {loop_spec}")
            return []
        
        var_path = match.group(1).strip()
        value = self.resolve_value(var_path)
        
        if not isinstance(value, list):
            logger.error(f"Loop variable {var_path} is not a list: {type(value)}")
            return []
        
        return value


# Convenience functions for testing
def render_template(template: Any, context: Dict[str, Any]) -> Any:
    """
    Render a template with given context.
    
    Args:
        template: Template to render (string, dict, list, or primitive)
        context: Context variables
        
    Returns:
        Rendered value
    """
    engine = TemplateEngine(context)
    return engine.render_value(template)


if __name__ == "__main__":
    # Test the template engine
    logging.basicConfig(level=logging.DEBUG)
    
    # Test context
    context = {
        "current_time": {
            "datetime": {
                "unix": 1729776000,
                "iso": "2024-10-24T12:00:00Z"
            }
        },
        "activities": [
            {"id": 123, "name": "Morning Run"},
            {"id": 456, "name": "Afternoon Ride"}
        ],
        "count": 42
    }
    
    engine = TemplateEngine(context)
    
    # Test 1: Simple string substitution
    result = engine.render_value("Time: {{current_time.datetime.iso}}")
    print(f"Test 1: {result}")
    assert result == "Time: 2024-10-24T12:00:00Z"
    
    # Test 2: Full variable extraction (not string)
    result = engine.render_value("{{current_time.datetime.unix}}")
    print(f"Test 2: {result}")
    assert result == 1729776000
    assert isinstance(result, int)
    
    # Test 3: Dictionary rendering
    params = {
        "after_unix": "{{current_time.datetime.unix}}",
        "per_page": 30
    }
    result = engine.render_params(params)
    print(f"Test 3: {result}")
    assert result == {"after_unix": 1729776000, "per_page": 30}
    
    # Test 4: Loop context
    activities = engine.get_loop_array("{{activities}}")
    for idx, activity in enumerate(activities):
        engine.set_loop_context(activity, idx)
        rendered = engine.render_value({
            "activity_id": "{{loop.item.id}}",
            "name": "{{loop.item.name}}",
            "position": "{{loop.index}}"
        })
        print(f"Test 4.{idx}: {rendered}")
    
    # Test 5: Missing variable
    result = engine.render_value("{{missing.variable}}")
    print(f"Test 5: {result}")
    assert result is None
    
    print("\n✅ All template engine tests passed!")
