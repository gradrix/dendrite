from .neuron import BaseNeuron
import json

class SchemaValidatorNeuron(BaseNeuron):
    def process(self, goal_id, data: dict):
        schema = data.get("schema")
        if not schema:
            data["is_schema_valid"] = False
            return data

        try:
            json.loads(schema)
            data["is_schema_valid"] = True
        except json.JSONDecodeError:
            data["is_schema_valid"] = False

        self.message_bus.add_message(goal_id, "schema_validation", str(data["is_schema_valid"]))

        return data
