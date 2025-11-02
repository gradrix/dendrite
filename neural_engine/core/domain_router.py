"""
Domain Router - Routes requests to specialized LLM instances.

This improves accuracy by using domain-specific experts instead of
one general-purpose LLM trying to handle everything.
"""

from typing import Optional, Dict, List
import re


class DomainRouter:
    """
    Routes user goals to specialized domain handlers.
    
    Domains:
    - memory: Memory read/write operations
    - strava: Strava API operations
    - calculator: Mathematical calculations
    - general: Everything else (default)
    """
    
    # Domain detection patterns (keyword-based for speed)
    DOMAIN_PATTERNS = {
        "memory": [
            r"\b(remember|recall|store|save|write|memorize|note)\b",
            r"\b(my name|my.*name|user.*name|I am|I'm|my nickname)\b",
            r"\b(memory|remember that)\b",
            r"\b(what is my|what's my|tell me my|retrieve|get my)\b"
        ],
        "strava": [
            r"\b(strava|running|cycling|activity|activities)\b",
            r"\b(workout|exercise|training)\b",
            r"\b(distance|pace|speed)\b"
        ],
        "calculator": [
            r"\b(calculate|compute|add|subtract|multiply|divide)\b",
            r"\b\d+\s*[\+\-\*\/]\s*\d+\b",  # Math expressions
            r"\b(sum|product|quotient|difference)\b",
            r"\b(square root|power|factorial)\b"
        ]
    }
    
    def __init__(self):
        """Initialize domain router with compiled patterns."""
        self.compiled_patterns: Dict[str, List[re.Pattern]] = {}
        
        for domain, patterns in self.DOMAIN_PATTERNS.items():
            self.compiled_patterns[domain] = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in patterns
            ]
    
    def detect_domain(self, goal: str) -> str:
        """
        Detect the domain for a given goal.
        
        Args:
            goal: User goal text
        
        Returns:
            Domain name ("memory", "strava", "calculator", "general")
        """
        # Check each domain
        domain_scores = {}
        
        for domain, patterns in self.compiled_patterns.items():
            matches = 0
            for pattern in patterns:
                if pattern.search(goal):
                    matches += 1
            domain_scores[domain] = matches
        
        # Find domain with most matches
        if domain_scores:
            best_domain = max(domain_scores.items(), key=lambda x: x[1])
            if best_domain[1] > 0:
                return best_domain[0]
        
        # Default to general
        return "general"
    
    def get_specialist_hint(self, domain: str, goal: str) -> Optional[str]:
        """
        Get domain-specific hint for the specialist.
        
        Args:
            domain: Detected domain
            goal: User goal text
        
        Returns:
            Hint string or None
        """
        hints = {
            "memory": self._get_memory_hint(goal),
            "strava": "Focus on Strava-related tools for activity data",
            "calculator": "Select calculator or math-related tools"
        }
        
        return hints.get(domain)
    
    def _get_memory_hint(self, goal: str) -> str:
        """Get specific hint for memory operations."""
        # Detect read vs write
        write_keywords = ["remember", "store", "save", "write", "note", "memorize"]
        read_keywords = ["recall", "what", "retrieve", "get", "tell me"]
        
        goal_lower = goal.lower()
        
        has_write = any(kw in goal_lower for kw in write_keywords)
        has_read = any(kw in goal_lower for kw in read_keywords)
        
        if has_write and not has_read:
            return "This is a WRITE operation - use memory_write tool"
        elif has_read and not has_write:
            return "This is a READ operation - use memory_read tool"
        else:
            return "Determine if this is memory READ or WRITE operation"
