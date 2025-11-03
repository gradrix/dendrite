"""
Domain Router - Routes requests to specialized LLM instances.

This improves accuracy by using domain-specific experts instead of
one general-purpose LLM trying to handle everything.

Uses micro-LLM approach: small focused LLM call for domain detection.
No regex patterns - generalizable and maintainable.
"""

from typing import Optional


class DomainRouter:
    """
    Routes user goals to specialized domain handlers.
    
    Domains:
    - memory: Memory read/write operations
    - strava: Strava API operations
    - calculator: Mathematical calculations
    - general: Everything else (default)
    
    Uses small LLM call for robust, generalizable domain detection.
    """
    
    def __init__(self, ollama_client=None):
        """Initialize domain router with optional LLM client."""
        self.ollama_client = ollama_client
    
    def detect_domain(self, goal: str) -> str:
        """
        Detect the domain for a given goal using per-domain voting.
        
        Each domain gets asked: "Does this goal belong to YOUR domain?"
        Highest confidence wins.
        
        Args:
            goal: User goal text
        
        Returns:
            Domain name ("memory", "strava", "calculator", "general")
        """
        # If no LLM client, use fast keyword fallback
        if not self.ollama_client:
            return self._keyword_fallback(goal)
        
        # Vote each domain
        domains = [
            ("memory", "personal user information stored previously: remembering user's name, preferences, past conversations, things the user told you to remember"),
            ("strava", "fitness activities, running, cycling, workouts, exercise data from Strava"),
            ("calculator", "mathematical calculations, numbers, arithmetic operations"),
        ]
        
        best_domain = "general"
        best_confidence = 0
        
        for domain_name, domain_desc in domains:
            prompt = f"""Goal: "{goal}"

Does this goal belong to the {domain_name} domain?
({domain_desc})

Answer YES or NO with confidence 0-100:
YES if goal clearly matches this domain
NO if goal doesn't match this domain

Format:
ANSWER: [YES or NO]
CONFIDENCE: [0-100]"""
            
            try:
                response = self.ollama_client.generate(prompt=prompt, check_tokens=False)
                text = response['response'].strip().upper()
                
                # Parse response
                answer = "YES" if "YES" in text.split('\n')[0] else "NO"
                confidence = 0
                for line in text.split('\n'):
                    if 'CONFIDENCE' in line:
                        import re
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            confidence = int(numbers[0])
                            break
                
                # If YES and higher confidence than previous best
                if answer == "YES" and confidence > best_confidence:
                    best_domain = domain_name
                    best_confidence = confidence
                    
            except Exception:
                continue
        
        return best_domain
    
    def _keyword_fallback(self, goal: str) -> str:
        """Minimal keyword-based fallback for domain detection (only when LLM unavailable)."""
        goal_lower = goal.lower()
        
        # Only check for most obvious keywords
        if any(kw in goal_lower for kw in ["remember", "my name", "what is my"]):
            return "memory"
        if "strava" in goal_lower:
            return "strava"
        if any(kw in goal_lower for kw in ["calculate", "+", "-", "*", "/"]):
            return "calculator"
        
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
