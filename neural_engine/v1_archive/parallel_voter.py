"""
Parallel Voting System - Multiple neurons vote simultaneously.

Instead of one big prompt with examples, we run multiple simple questions
in parallel and aggregate the votes. More democratic, more scalable.
"""

from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


class ParallelVoter:
    """
    Runs multiple voting neurons in parallel and aggregates results.
    
    Each voter is a simple function that returns a vote with confidence.
    The strongest aggregate vote wins.
    """
    
    def __init__(self, ollama_client, max_workers=5):
        self.ollama_client = ollama_client
        self.max_workers = max_workers
    
    def vote(self, goal: str, voters: List[callable]) -> Dict[str, any]:
        """
        Run all voters in parallel and aggregate votes.
        
        Args:
            goal: The user's goal to classify
            voters: List of voter functions, each returns {"label": str, "confidence": float}
        
        Returns:
            {"winner": str, "confidence": float, "votes": List[Dict]}
        """
        votes = []
        
        # Run all voters in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(voter, goal): voter for voter in voters}
            
            for future in as_completed(futures):
                try:
                    vote = future.result()
                    votes.append(vote)
                except Exception as e:
                    # Skip failed votes
                    print(f"⚠️  Voter failed: {e}")
        
        # Aggregate votes
        winner, confidence = self._aggregate_votes(votes)
        
        return {
            "winner": winner,
            "confidence": confidence,
            "votes": votes,
            "num_votes": len(votes)
        }
    
    def _aggregate_votes(self, votes: List[Dict]) -> Tuple[str, float]:
        """
        Aggregate votes using weighted voting.
        
        Each vote has a label and confidence. We sum confidence per label
        and pick the label with highest total confidence.
        
        Votes with label="abstain" are skipped.
        """
        if not votes:
            return "unknown", 0.0
        
        # Sum confidence per label (skip abstentions)
        label_scores = {}
        abstentions = 0
        
        for vote in votes:
            label = vote.get("label", "unknown")
            confidence = vote.get("confidence", 0.0)
            
            # Skip abstentions
            if label == "abstain":
                abstentions += 1
                continue
            
            if label not in label_scores:
                label_scores[label] = 0.0
            
            label_scores[label] += confidence
        
        # If everyone abstained, return unknown
        if not label_scores:
            return "unknown", 0.0
        
        # Find winner
        winner = max(label_scores, key=label_scores.get)
        total_confidence = sum(label_scores.values())
        
        # Normalize confidence (what % of total votes did winner get?)
        confidence = label_scores[winner] / total_confidence if total_confidence > 0 else 0.0
        
        return winner, confidence


class SimpleVoter:
    """
    Base class for simple voting neurons.
    
    Each voter asks ONE simple yes/no question with NO examples.
    """
    
    def __init__(self, ollama_client, question: str, positive_label: str, negative_label: str = "no"):
        self.ollama_client = ollama_client
        self.question = question
        self.positive_label = positive_label
        self.negative_label = negative_label
    
    def __call__(self, goal: str) -> Dict[str, any]:
        """
        Ask the question and return vote.
        
        Returns:
            {"label": str, "confidence": float, "question": str}
        """
        prompt = f"{self.question}\n\nGoal: {goal}\n\nAnswer (YES or NO):"
        
        response = self.ollama_client.generate(
            prompt=prompt,
            context="parallel_voting",
            options={"temperature": 0}
        )
        
        answer = response['response'].strip().upper()
        
        # Convert to vote
        if "YES" in answer:
            label = self.positive_label
            confidence = 0.9
        elif "NO" in answer:
            label = self.negative_label
            confidence = 0.9
        else:
            # Uncertain - abstain from voting
            label = "abstain"
            confidence = 0.0
        
        return {
            "label": label,
            "confidence": confidence,
            "question": self.question,
            "raw_answer": answer
        }
