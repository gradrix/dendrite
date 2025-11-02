import json
import os
from pathlib import Path

class KeyValueStore:
    def __init__(self, store_path=None):
        # Allow override via parameter or environment variable for test isolation
        if store_path is None:
            store_path = os.environ.get("NEURAL_ENGINE_KV_STORE", "var/kv_store.json")
        
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            with open(self.store_path, "w") as f:
                json.dump({}, f)

    def get(self, key):
        with open(self.store_path, "r") as f:
            data = json.load(f)
        return data.get(key)

    def set(self, key, value):
        with open(self.store_path, "r") as f:
            data = json.load(f)
        data[key] = value
        with open(self.store_path, "w") as f:
            json.dump(data, f, indent=4)

    def delete(self, key):
        with open(self.store_path, "r") as f:
            data = json.load(f)
        if key in data:
            del data[key]
            with open(self.store_path, "w") as f:
                json.dump(data, f, indent=4)
