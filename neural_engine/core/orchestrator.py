from typing import List
from .neuron import BaseNeuron

class Orchestrator:
    def __init__(self, neurons: List[BaseNeuron]):
        self.neurons = neurons

    def execute(self, goal_id, initial_data):
        data = initial_data
        for neuron in self.neurons:
            data = neuron.process(goal_id, data)
        return data
