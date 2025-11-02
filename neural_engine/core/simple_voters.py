"""
Simple Voting Neurons - Each asks ONE simple question.

These are used by ParallelVoter to classify intent through voting.
NO EXAMPLES in prompts - just simple yes/no questions.
"""

from .parallel_voter import SimpleVoter


def create_intent_voters(ollama_client):
    """
    Create all voting neurons for intent classification.
    
    Returns list of voter functions that can be run in parallel.
    Keep it small - 4 voters total for speed.
    """
    
    voters = [
        # Voter 1: Does this need external data?
        SimpleVoter(
            ollama_client,
            "Does this goal require accessing stored data or external APIs?",
            positive_label="tool_use",
            negative_label="generative"
        ),
        
        # Voter 2: Is this about user's personal data?
        SimpleVoter(
            ollama_client,
            "Is this goal about the user's personal stored information?",
            positive_label="tool_use",
            negative_label="generative"
        ),
        
        # Voter 3: Can this be answered conversationally?
        SimpleVoter(
            ollama_client,
            "Can this goal be answered purely from conversational knowledge?",
            positive_label="generative",
            negative_label="tool_use"
        ),
        
        # Voter 4: Is this general knowledge?
        SimpleVoter(
            ollama_client,
            "Is this a request for general knowledge or explanation?",
            positive_label="generative",
            negative_label="tool_use"
        ),
    ]
    
    return voters
