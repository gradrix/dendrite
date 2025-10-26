"""
Neuron module - Modular components for the Dendrite agent.

This module contains cleanly separated components:
- aggregation: Result aggregation and summarization
- spawning: Dendrite (sub-neuron) spawning logic
"""

from agent.neuron import aggregation
from agent.neuron import spawning

__all__ = ['aggregation', 'spawning']

from .aggregation import (
    aggregate_results,
    aggregate_dendrite_results,
    summarize_result,
    summarize_result_for_validation,
    truncate_large_results
)

__all__ = [
    'aggregate_results',
    'aggregate_dendrite_results',
    'summarize_result',
    'summarize_result_for_validation',
    'truncate_large_results',
]
