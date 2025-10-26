"""
Neuron submodules for NeuronAgent.
Contains modular implementations of key agent capabilities.
"""

from agent.neuron import aggregation
from agent.neuron import spawning
from agent.neuron import validation
from agent.neuron import decomposition
from agent.neuron import execution

__all__ = ['aggregation', 'spawning', 'validation', 'decomposition', 'execution']

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
