"""
Domain Router - Routes requests to specialized LLM instances.

This improves accuracy by using domain-specific experts instead of
one general-purpose LLM trying to handle everything.

Uses semantic tool discovery to determine domain - no hardcoded keywords!
The domain is inferred from which tools match the goal semantically.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neural_engine.core.tool_discovery import ToolDiscovery


class DomainRouter:
    """
    Routes user goals to specialized domain handlers.
    
    Domains are INFERRED from tool metadata, not hardcoded:
    - If top matching tools have domain="fitness" → route to strava specialist
    - If top matching tools have domain="memory" → route to memory specialist  
    - Otherwise → general
    
    This is the semantic, generalizable approach!
    """
    
    def __init__(self, ollama_client=None, tool_discovery: Optional['ToolDiscovery'] = None):
        """Initialize domain router with optional LLM client and tool discovery."""
        self.ollama_client = ollama_client
        self.tool_discovery = tool_discovery
    
    def detect_domain(self, goal: str) -> str:
        """
        Detect the domain for a given goal using semantic tool matching.
        
        NEW approach:
        1. Use tool_discovery to find semantically matching tools
        2. Look at the domain metadata of top matches
        3. Route to the dominant domain
        
        This means "show me my runs from last week" will:
        - Match strava_get_my_activities (domain="fitness")
        - Route to strava domain
        
        Without any hardcoded keywords!
        
        Args:
            goal: User goal text
        
        Returns:
            Domain name ("memory", "strava", "calculator", "general")
        """
        # Try semantic tool discovery first (the smart way!)
        if self.tool_discovery:
            domain = self._detect_via_tool_discovery(goal)
            if domain != "general":
                return domain
        
        # Fallback to LLM voting if tool discovery didn't give clear result
        if self.ollama_client:
            return self._detect_via_llm_voting(goal)
        
        # Last resort: keyword fallback
        return self._keyword_fallback(goal)
    
    def _detect_via_tool_discovery(self, goal: str) -> str:
        """
        Detect domain by looking at which tools match semantically.
        
        This is the CORE innovation - no keywords needed!
        """
        # Get top 5 semantically matching tools
        candidates = self.tool_discovery.semantic_search(goal, n_results=5)
        
        if not candidates:
            return "general"
        
        # Count domains from tool metadata
        domain_scores = {}
        for i, candidate in enumerate(candidates):
            # Weight by position (first match matters more)
            weight = 1.0 / (i + 1)
            
            # Get domain from metadata (stored during indexing)
            domain = candidate.get('domain', 'general')
            
            # Map fitness domain to strava (for specialist routing)
            if domain == 'fitness':
                domain = 'strava'
            
            domain_scores[domain] = domain_scores.get(domain, 0) + weight
        
        # Return highest scoring domain
        if domain_scores:
            best_domain = max(domain_scores, key=domain_scores.get)
            # Only return if it has significant score
            if domain_scores[best_domain] > 0.5:
                return best_domain
        
        return "general"
    
    def _detect_via_llm_voting(self, goal: str) -> str:
        """Fallback: Use LLM to vote on domain."""
        domains = [
            ("memory", "retrieving or storing PERSONAL INFORMATION that the user previously told you (their name, preferences, favorites). NOT for external data like fitness activities or API data."),
            ("strava", "fitness activities, running data, cycling, workouts, exercise tracking from Strava API - including 'runs', 'rides', 'activities', recent fitness data"),
            ("calculator", "mathematical calculations, numbers, arithmetic operations"),
        ]
        
        best_domain = "general"
        best_confidence = 0
        
        for domain_name, domain_desc in domains:
            prompt = f"""Goal: "{goal}"

Does this goal belong to the {domain_name} domain?
({domain_desc})

IMPORTANT:
- "memory" is ONLY for recalling things the USER TOLD YOU (like their name, preferences)
- "strava" is for fitness data like runs, rides, activities (even if it says "my runs")
- If the goal asks about exercise/fitness activities, answer NO for memory, YES for strava

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
        
        # Check Strava first (most specific)
        strava_keywords = ["strava", "activity", "activities", "run", "runs", "ride", "cycling", 
                          "workout", "exercise", "kudos", "segment", "athlete", "recent runs",
                          "recent activities"]
        if any(kw in goal_lower for kw in strava_keywords):
            return "strava"
        
        # Only check for most obvious memory keywords (must be more specific)
        # Avoid single words like "my" that appear in many contexts
        memory_keywords = ["remember this", "my name is", "what is my name", 
                          "what did i tell you", "do you remember", "store my", "save my name"]
        if any(kw in goal_lower for kw in memory_keywords):
            return "memory"
        
        # Calculator keywords
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
