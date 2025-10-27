import unittest
import os
import json
from pathlib import Path
from neural_engine.core.key_value_store import KeyValueStore

class TestKeyValueStore(unittest.TestCase):
    def setUp(self):
        self.test_store_path = "var/test_kv_store.json"
        # Ensure the directory exists
        Path(self.test_store_path).parent.mkdir(parents=True, exist_ok=True)
        # Clean up any previous test file
        if os.path.exists(self.test_store_path):
            os.remove(self.test_store_path)

    def tearDown(self):
        if os.path.exists(self.test_store_path):
            os.remove(self.test_store_path)

    def test_initial_creation(self):
        self.assertFalse(os.path.exists(self.test_store_path))
        kv_store = KeyValueStore(store_path=self.test_store_path)
        self.assertTrue(os.path.exists(self.test_store_path))
        with open(self.test_store_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data, {})

    def test_set_and_get(self):
        kv_store = KeyValueStore(store_path=self.test_store_path)
        kv_store.set("test_key", "test_value")
        value = kv_store.get("test_key")
        self.assertEqual(value, "test_value")

        # Test overwriting a key
        kv_store.set("test_key", "new_value")
        value = kv_store.get("test_key")
        self.assertEqual(value, "new_value")

        # Test getting a non-existent key
        value = kv_store.get("non_existent_key")
        self.assertIsNone(value)

    def test_delete(self):
        kv_store = KeyValueStore(store_path=self.test_store_path)
        kv_store.set("key_to_delete", "some_value")
        self.assertIsNotNone(kv_store.get("key_to_delete"))

        kv_store.delete("key_to_delete")
        self.assertIsNone(kv_store.get("key_to_delete"))

        # Test deleting a non-existent key (should not raise error)
        try:
            kv_store.delete("non_existent_key")
        except Exception as e:
            self.fail(f"Deleting a non-existent key raised an exception: {e}")

if __name__ == "__main__":
    unittest.main()
