import ollama
import os

class OllamaClient:
    def __init__(self):
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.client = ollama.Client(host=host)

    def generate(self, model, prompt):
        response = self.client.generate(model=model, prompt=prompt)
        return response
