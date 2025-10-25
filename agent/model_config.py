"""
Model configuration and selection based on available resources.

This module provides:
- Model profiles with resource requirements
- Automatic model selection based on available RAM/VRAM
- Centralized model configuration
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelProfile:
    """Profile for an LLM model with resource requirements."""
    name: str
    size: str  # e.g., "3b", "8b", "32b"
    params_billion: float  # Actual parameter count in billions
    min_ram_gb: float  # Minimum RAM required
    min_vram_gb: Optional[float]  # Minimum VRAM if using GPU (None = CPU only)
    recommended_ram_gb: float  # Recommended RAM for good performance
    context_window: int  # Context window size in tokens
    
    # Capabilities
    good_at_reasoning: bool = False  # Chain-of-thought reasoning
    good_at_counting: bool = False  # Reliable counting through lists
    good_at_json: bool = False  # Structured JSON output
    good_at_code: bool = False  # Code generation/understanding
    fast_inference: bool = False  # Fast response times
    
    # Performance notes
    notes: str = ""
    
    def __str__(self):
        return f"{self.name} ({self.size}, {self.params_billion}B params, min {self.min_ram_gb}GB RAM)"


# Model registry with resource requirements and capabilities
MODEL_PROFILES: Dict[str, ModelProfile] = {
    # Small models (3B-7B) - Raspberry Pi friendly
    "qwen2.5:3b": ModelProfile(
        name="qwen2.5:3b",
        size="3b",
        params_billion=3.0,
        min_ram_gb=4,
        min_vram_gb=3,
        recommended_ram_gb=6,
        context_window=32768,
        good_at_reasoning=False,
        good_at_counting=False,  # Struggles with counting
        good_at_json=True,
        good_at_code=True,
        fast_inference=True,
        notes="Fast, good JSON output, but unreliable counting. Best with Python tools."
    ),
    
    "llama3.2:3b": ModelProfile(
        name="llama3.2:3b",
        size="3b",
        params_billion=3.2,
        min_ram_gb=4,
        min_vram_gb=3,
        recommended_ram_gb=6,
        context_window=8192,
        good_at_reasoning=False,
        good_at_counting=False,
        good_at_json=False,
        good_at_code=False,
        fast_inference=True,
        notes="Very fast but limited capabilities. Use for simple tasks only."
    ),
    
    "phi3:3.8b": ModelProfile(
        name="phi3:3.8b",
        size="3.8b",
        params_billion=3.8,
        min_ram_gb=5,
        min_vram_gb=4,
        recommended_ram_gb=7,
        context_window=4096,
        good_at_reasoning=True,
        good_at_counting=False,
        good_at_json=True,
        good_at_code=True,
        fast_inference=True,
        notes="Good reasoning for small model, but still needs Python for counting."
    ),
    
    # Medium models (7B-13B) - Desktop/server
    "llama3.1:8b": ModelProfile(
        name="llama3.1:8b",
        size="8b",
        params_billion=8.0,
        min_ram_gb=8,
        min_vram_gb=6,
        recommended_ram_gb=12,
        context_window=128000,
        good_at_reasoning=True,
        good_at_counting=False,  # Still unreliable
        good_at_json=True,
        good_at_code=True,
        fast_inference=True,
        notes="Excellent all-rounder. Large context. Still use Python for counting 100+ items."
    ),
    
    "mistral-small3.2:24b": ModelProfile(
        name="mistral-small3.2:24b",
        size="24b",
        params_billion=24.0,
        min_ram_gb=20,
        min_vram_gb=16,
        recommended_ram_gb=28,
        context_window=32768,
        good_at_reasoning=True,
        good_at_counting=True,  # Better at counting than smaller models
        good_at_json=True,
        good_at_code=True,
        fast_inference=False,
        notes="High quality reasoning and better counting. Needs significant resources."
    ),
    
    "qwen2.5:14b": ModelProfile(
        name="qwen2.5:14b",
        size="14b",
        params_billion=14.0,
        min_ram_gb=12,
        min_vram_gb=10,
        recommended_ram_gb=16,
        context_window=32768,
        good_at_reasoning=True,
        good_at_counting=False,
        good_at_json=True,
        good_at_code=True,
        fast_inference=False,
        notes="Balanced performance. Good code understanding."
    ),
    
    # Large models (32B+) - High-end systems
    "deepseek-r1:32b": ModelProfile(
        name="deepseek-r1:32b",
        size="32b",
        params_billion=32.0,
        min_ram_gb=32,
        min_vram_gb=24,
        recommended_ram_gb=40,
        context_window=64000,
        good_at_reasoning=True,  # Chain-of-thought reasoning
        good_at_counting=False,  # Reasoning can introduce counting errors!
        good_at_json=True,
        good_at_code=True,
        fast_inference=False,
        notes="Advanced reasoning model. Ironically, reasoning chains can cause counting errors. Use Python for counting."
    ),
    
    "qwen2.5:32b": ModelProfile(
        name="qwen2.5:32b",
        size="32b",
        params_billion=32.0,
        min_ram_gb=32,
        min_vram_gb=24,
        recommended_ram_gb=40,
        context_window=32768,
        good_at_reasoning=True,
        good_at_counting=True,  # Better than deepseek-r1 for counting
        good_at_json=True,
        good_at_code=True,
        fast_inference=False,
        notes="High-quality all-purpose model. More reliable counting than deepseek-r1."
    ),
}


def select_best_model(available_ram_gb: float, available_vram_gb: Optional[float] = None,
                     prefer_fast: bool = False, prefer_reasoning: bool = False) -> ModelProfile:
    """
    Select the best model based on available resources and preferences.
    
    Args:
        available_ram_gb: Available system RAM in GB
        available_vram_gb: Available GPU VRAM in GB (None if CPU only)
        prefer_fast: Prefer faster inference over capabilities
        prefer_reasoning: Prefer reasoning capabilities
        
    Returns:
        Best matching ModelProfile
    """
    suitable_models: List[ModelProfile] = []
    
    for profile in MODEL_PROFILES.values():
        # Check RAM requirement
        if profile.min_ram_gb > available_ram_gb:
            continue
        
        # Check VRAM requirement if using GPU
        if available_vram_gb is not None and profile.min_vram_gb is not None:
            if profile.min_vram_gb > available_vram_gb:
                continue
        
        suitable_models.append(profile)
    
    if not suitable_models:
        logger.warning(f"No suitable models for {available_ram_gb}GB RAM. Using smallest model.")
        return MODEL_PROFILES["qwen2.5:3b"]
    
    # Sort by preference
    def score_model(m: ModelProfile) -> float:
        score = m.params_billion  # Bigger is generally better
        
        if prefer_fast and m.fast_inference:
            score += 5
        
        if prefer_reasoning and m.good_at_reasoning:
            score += 10
        
        # Bonus for good JSON and code (always useful)
        if m.good_at_json:
            score += 2
        if m.good_at_code:
            score += 2
        
        # Penalty if using much more than minimum RAM
        if m.recommended_ram_gb > available_ram_gb:
            score -= 5
        
        return score
    
    suitable_models.sort(key=score_model, reverse=True)
    best = suitable_models[0]
    
    logger.info(f"🎯 Selected model: {best}")
    logger.info(f"   Reasoning: {best.good_at_reasoning}, Counting: {best.good_at_counting}, "
                f"JSON: {best.good_at_json}, Code: {best.good_at_code}")
    
    if not best.good_at_counting:
        logger.warning(f"⚠️  Model '{best.name}' is not reliable at counting. "
                      f"Will use Python tools for counting tasks.")
    
    return best


def get_model_profile(model_name: str) -> Optional[ModelProfile]:
    """Get profile for a specific model."""
    return MODEL_PROFILES.get(model_name)


def list_available_models(min_ram_gb: float = 4) -> List[ModelProfile]:
    """List all models that fit in given RAM."""
    return [p for p in MODEL_PROFILES.values() if p.min_ram_gb <= min_ram_gb]
