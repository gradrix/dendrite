"""
Self-Learning System - Analyzes test failures and suggests new facts.

This system:
1. Runs tests and captures failures
2. Analyzes failure patterns
3. Suggests new classification facts
4. Validates proposed facts
5. Adds validated facts to the database

For production: Same approach but based on user feedback/corrections.
"""

import json
import subprocess
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class TestFailure:
    """A single test failure with context."""
    test_name: str
    failure_type: str  # "classification", "tool_selection", "execution", etc.
    goal: str  # The user goal that failed
    expected: str  # Expected result
    actual: str  # Actual result
    full_traceback: str


@dataclass
class FactSuggestion:
    """A suggested new fact based on failure analysis."""
    id: str
    description: str
    intent: str
    confidence: float
    category: str
    examples: List[str]
    tags: List[str]
    source_failure: str  # Which test failure inspired this
    validation_status: str  # "suggested", "validated", "rejected"


class SelfLearningAnalyzer:
    """
    Analyzes failures and learns new facts automatically.
    
    Revolutionary approach:
    - Test failures → patterns → new facts → improved classification
    - Production: user corrections → new facts → continuous improvement
    """
    
    def __init__(self,
                 facts_file: str = "neural_engine/data/classification_facts.json",
                 suggestions_file: str = "var/prod/fact_suggestions.json"):
        self.facts_file = facts_file
        self.suggestions_file = suggestions_file
        self.suggestions: List[FactSuggestion] = []
        self._load_suggestions()
    
    def _load_suggestions(self):
        """Load previously suggested facts."""
        if Path(self.suggestions_file).exists():
            with open(self.suggestions_file, 'r') as f:
                data = json.load(f)
                self.suggestions = [
                    FactSuggestion(**s) for s in data.get("suggestions", [])
                ]
    
    def _save_suggestions(self):
        """Save fact suggestions to file."""
        Path(self.suggestions_file).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "suggestions": [asdict(s) for s in self.suggestions]
        }
        with open(self.suggestions_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def analyze_test_failures(self, test_pattern: str = "neural_engine/tests/") -> List[TestFailure]:
        """
        Run tests and capture failures for analysis.
        
        Args:
            test_pattern: Pytest pattern to run
        
        Returns:
            List of TestFailure objects
        """
        print(f"🔬 Analyzing test failures in {test_pattern}...")
        
        # Run pytest with JSON output
        result = subprocess.run(
            [
                "docker", "compose", "run", "--rm", "tests",
                "pytest", test_pattern,
                "--tb=short",
                "-v",
                "--json-report",
                "--json-report-file=/tmp/test_report.json"
            ],
            capture_output=True,
            text=True
        )
        
        # Parse failures
        failures = []
        # TODO: Parse pytest output and extract failures
        # For now, return empty list
        
        print(f"   Found {len(failures)} failures to analyze")
        return failures
    
    def suggest_fact_from_failure(self, 
                                   goal: str,
                                   expected_intent: str,
                                   actual_intent: str,
                                   test_name: str) -> FactSuggestion:
        """
        Suggest a new fact based on a classification failure.
        
        Args:
            goal: The goal that was misclassified
            expected_intent: What it should have been classified as
            actual_intent: What it was incorrectly classified as
            test_name: Name of the failing test
        
        Returns:
            FactSuggestion
        """
        # Generate fact ID
        fact_id = f"learned_{len(self.suggestions) + 1:03d}"
        
        # Create description
        description = f"user goal similar to '{goal}'"
        
        # Determine category from intent
        category_map = {
            "tool_use": "learned_tool_use",
            "generative": "learned_generative"
        }
        category = category_map.get(expected_intent, "learned")
        
        # Extract tags from goal
        tags = ["learned", "auto-suggested"] + goal.lower().split()[:3]
        
        suggestion = FactSuggestion(
            id=fact_id,
            description=description,
            intent=expected_intent,
            confidence=0.80,  # Lower confidence for auto-suggested facts
            category=category,
            examples=[goal],
            tags=tags,
            source_failure=test_name,
            validation_status="suggested"
        )
        
        self.suggestions.append(suggestion)
        self._save_suggestions()
        
        print(f"💡 Suggested new fact: {fact_id}")
        print(f"   Goal: '{goal}'")
        print(f"   Expected: {expected_intent}, Got: {actual_intent}")
        
        return suggestion
    
    def validate_suggestion(self, fact_id: str, is_valid: bool, reason: str = None):
        """
        Validate or reject a fact suggestion (human-in-the-loop).
        
        Args:
            fact_id: ID of the suggested fact
            is_valid: Whether to accept or reject
            reason: Optional reason for decision
        """
        suggestion = next((s for s in self.suggestions if s.id == fact_id), None)
        if not suggestion:
            print(f"⚠️  Suggestion {fact_id} not found")
            return
        
        if is_valid:
            suggestion.validation_status = "validated"
            # Add to main facts file
            self._add_to_facts_file(suggestion)
            print(f"✅ Validated and added fact: {fact_id}")
        else:
            suggestion.validation_status = "rejected"
            print(f"❌ Rejected fact: {fact_id}")
            if reason:
                print(f"   Reason: {reason}")
        
        self._save_suggestions()
    
    def _add_to_facts_file(self, suggestion: FactSuggestion):
        """Add a validated suggestion to the main facts file."""
        with open(self.facts_file, 'r') as f:
            data = json.load(f)
        
        # Convert suggestion to fact format
        new_fact = {
            "id": suggestion.id,
            "description": suggestion.description,
            "intent": suggestion.intent,
            "confidence": suggestion.confidence,
            "category": suggestion.category,
            "examples": suggestion.examples,
            "tags": suggestion.tags
        }
        
        data["facts"].append(new_fact)
        
        with open(self.facts_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Added fact to {self.facts_file}")
    
    def get_pending_suggestions(self) -> List[FactSuggestion]:
        """Get all suggestions pending validation."""
        return [s for s in self.suggestions if s.validation_status == "suggested"]
    
    def review_suggestions_interactive(self):
        """Interactive CLI to review pending suggestions."""
        pending = self.get_pending_suggestions()
        
        if not pending:
            print("✓ No pending suggestions to review")
            return
        
        print(f"\n📋 {len(pending)} pending fact suggestions to review:\n")
        
        for i, suggestion in enumerate(pending, 1):
            print(f"{i}. {suggestion.id}")
            print(f"   Description: {suggestion.description}")
            print(f"   Intent: {suggestion.intent}")
            print(f"   Examples: {suggestion.examples}")
            print(f"   Source: {suggestion.source_failure}")
            print()
            
            response = input("   Accept? (y/n/s=skip): ").strip().lower()
            if response == 'y':
                self.validate_suggestion(suggestion.id, is_valid=True)
            elif response == 'n':
                reason = input("   Reason for rejection: ").strip()
                self.validate_suggestion(suggestion.id, is_valid=False, reason=reason)
            print()
