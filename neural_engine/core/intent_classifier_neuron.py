from .neuron import BaseNeuron
from .task_simplifier import TaskSimplifier

class IntentClassifierNeuron(BaseNeuron):
    def __init__(self, *args, use_simplifier=True, simplifier_threshold=0.8, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_simplifier = use_simplifier
        self.simplifier_threshold = simplifier_threshold
        if self.use_simplifier:
            self.simplifier = TaskSimplifier()
    
    def _load_prompt(self):
        with open("neural_engine/prompts/intent_classifier_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, goal: str, depth=0):
        # Try simplifier first if enabled
        if self.use_simplifier:
            simplified = self.simplifier.simplify_for_intent_classification(goal)
            
            # If high confidence, use it directly
            if simplified["confidence"] >= self.simplifier_threshold:
                intent = simplified["intent"]
                
                self.add_message_with_metadata(
                    goal_id=goal_id,
                    message_type="intent",
                    data={
                        "intent": intent, 
                        "goal": goal,
                        "method": "simplifier",
                        "confidence": simplified["confidence"],
                        "keyword_matched": simplified.get("keyword_matched")
                    },
                    depth=depth
                )
                
                return {"goal": goal, "intent": intent}
        
        # Fall back to LLM if simplifier disabled or low confidence
        prompt_template = self._load_prompt()
        prompt = prompt_template.format(goal=goal)

        response = self.ollama_client.generate(prompt=prompt)

        intent = response['response'].strip().lower()

        # Use new metadata-rich message format
        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="intent",
            data={
                "intent": intent, 
                "goal": goal,
                "method": "llm"
            },
            depth=depth
        )

        return {"goal": goal, "intent": intent}
