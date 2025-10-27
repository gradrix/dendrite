import unittest
from unittest.mock import MagicMock, patch, ANY
import os
from neural_engine.core.ollama_client import OllamaClient

class TestOllamaClient(unittest.TestCase):

    @patch('ollama.Client')
    def test_model_is_available_locally(self, mock_ollama_client):
        """
        Tests that the client does NOT pull the model if it's already available.
        """
        # Arrange
        mock_instance = mock_ollama_client.return_value
        # Simulate the model being present in the local list
        mock_instance.list.return_value = {"models": [{"model": "mistral:latest"}]}

        # Act
        with patch.dict(os.environ, {"OLLAMA_MODEL": "mistral"}):
            client = OllamaClient()

        # Assert
        # Check that list was called
        mock_instance.list.assert_called_once()
        # Check that pull was NOT called
        mock_instance.pull.assert_not_called()

    @patch('ollama.Client')
    def test_model_is_not_available_locally(self, mock_ollama_client):
        """
        Tests that the client PULLS the model if it's not available locally.
        """
        # Arrange
        mock_instance = mock_ollama_client.return_value
        # Simulate an empty list of local models
        mock_instance.list.return_value = {"models": []}

        # Act
        with patch.dict(os.environ, {"OLLAMA_MODEL": "mistral"}):
            client = OllamaClient()

        # Assert
        # Check that list was called
        mock_instance.list.assert_called_once()
        # Check that pull WAS called with the correct model name
        mock_instance.pull.assert_called_once_with("mistral")

if __name__ == '__main__':
    unittest.main()
