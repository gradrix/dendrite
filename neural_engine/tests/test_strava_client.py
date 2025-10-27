import unittest
from unittest.mock import MagicMock
from neural_engine.core.key_value_store import KeyValueStore
from neural_engine.clients.strava_client import StravaClient
from neural_engine.core.exceptions import AuthenticationRequiredError

class TestStravaClient(unittest.TestCase):
    def test_missing_credentials_raises_error(self):
        mock_kv_store = MagicMock(spec=KeyValueStore)
        mock_kv_store.get.return_value = None

        with self.assertRaises(AuthenticationRequiredError):
            StravaClient(mock_kv_store)

if __name__ == "__main__":
    unittest.main()
