import ollama
import os

class OllamaClient:
    def __init__(self):
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "mistral")
        self.client = ollama.Client(host=host)

    def generate(self, prompt):
        response = self.client.generate(model=self.model, prompt=prompt)
        return response
