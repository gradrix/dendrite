class KnowledgeBase:
    def __init__(self):
        self.knowledge = {}

    def add_knowledge(self, domain, keywords):
        self.knowledge[domain] = keywords

    def get_knowledge(self, domain):
        return self.knowledge.get(domain, [])
