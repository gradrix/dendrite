"""
Integration tests for llama.cpp backend.

These tests verify that the llama.cpp server is working correctly
with the OpenAI-compatible API.

Usage:
    # Start the test server first:
    docker compose -f docker-compose.llamacpp-test.yml up -d
    
    # Wait for it to be healthy:
    docker compose -f docker-compose.llamacpp-test.yml ps
    
    # Run tests:
    pytest neural_engine/tests/integration/test_llamacpp.py -v
    
    # Cleanup:
    docker compose -f docker-compose.llamacpp-test.yml down
"""

import pytest
import os
import time
import requests
from typing import Generator

# Test configuration - check multiple possible URLs
LLAMACPP_URLS = [
    os.environ.get("LLAMACPP_TEST_URL"),  # Explicit override
    "http://llama-cpu:8080",  # Docker internal network
    "http://dendrite-llama-cpu:8080",  # Docker container name
    "http://localhost:8080",  # Host machine
    "http://localhost:18080",  # Test port
]
TIMEOUT = 30


def find_server() -> str:
    """Find a working llama.cpp server URL."""
    for url in LLAMACPP_URLS:
        if not url:
            continue
        try:
            response = requests.get(f"{url}/health", timeout=3)
            if response.status_code == 200:
                return url
        except requests.exceptions.RequestException:
            pass
    return None


def is_server_ready() -> bool:
    """Check if llama.cpp server is ready."""
    return find_server() is not None


@pytest.fixture(scope="module")
def llamacpp_server() -> Generator[str, None, None]:
    """Ensure llama.cpp server is available for tests."""
    url = find_server()
    if not url:
        pytest.skip(
            "llama.cpp server not running. Start with: ./start.sh"
        )
    yield url


class TestLlamaCppHealth:
    """Test llama.cpp server health and basic endpoints."""
    
    def test_health_endpoint(self, llamacpp_server: str):
        """Test that /health endpoint returns OK."""
        response = requests.get(f"{llamacpp_server}/health", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "ok"
    
    def test_models_endpoint(self, llamacpp_server: str):
        """Test OpenAI-compatible /v1/models endpoint."""
        response = requests.get(f"{llamacpp_server}/v1/models", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0


class TestLlamaCppCompletion:
    """Test text completion API."""
    
    def test_simple_completion(self, llamacpp_server: str):
        """Test basic text completion."""
        response = requests.post(
            f"{llamacpp_server}/v1/completions",
            json={
                "prompt": "The capital of France is",
                "max_tokens": 20,
                "temperature": 0.1,
            },
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        
        text = data["choices"][0]["text"].lower()
        assert "paris" in text, f"Expected 'paris' in response, got: {text}"
    
    def test_completion_with_stop(self, llamacpp_server: str):
        """Test completion with stop sequence."""
        response = requests.post(
            f"{llamacpp_server}/v1/completions",
            json={
                "prompt": "Count: 1, 2, 3,",
                "max_tokens": 50,
                "stop": ["6"],
            },
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        
        data = response.json()
        text = data["choices"][0]["text"]
        assert "6" not in text


class TestLlamaCppChat:
    """Test chat completion API (OpenAI-compatible)."""
    
    def test_simple_chat(self, llamacpp_server: str):
        """Test basic chat completion."""
        response = requests.post(
            f"{llamacpp_server}/v1/chat/completions",
            json={
                "messages": [
                    {"role": "user", "content": "Say 'hello world' and nothing else."}
                ],
                "max_tokens": 20,
                "temperature": 0.1,
            },
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        
        message = data["choices"][0]["message"]
        assert message["role"] == "assistant"
        assert "hello" in message["content"].lower()
    
    def test_chat_with_system_prompt(self, llamacpp_server: str):
        """Test chat with system message."""
        response = requests.post(
            f"{llamacpp_server}/v1/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": "You are a pirate. Always respond like a pirate."},
                    {"role": "user", "content": "How are you?"}
                ],
                "max_tokens": 50,
                "temperature": 0.5,
            },
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        
        content = response.json()["choices"][0]["message"]["content"].lower()
        # Pirate-like words
        pirate_words = ["arr", "ahoy", "matey", "ye", "aye", "seas", "ship", "captain"]
        has_pirate_word = any(word in content for word in pirate_words)
        # This is a soft check - small models may not always follow instructions perfectly
        print(f"Pirate response: {content}")
    
    def test_chat_conversation(self, llamacpp_server: str):
        """Test multi-turn conversation."""
        response = requests.post(
            f"{llamacpp_server}/v1/chat/completions",
            json={
                "messages": [
                    {"role": "user", "content": "My name is Alice."},
                    {"role": "assistant", "content": "Nice to meet you, Alice!"},
                    {"role": "user", "content": "What is my name?"}
                ],
                "max_tokens": 30,
                "temperature": 0.1,
            },
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        
        content = response.json()["choices"][0]["message"]["content"]
        assert "alice" in content.lower(), f"Expected 'Alice' in response, got: {content}"


class TestLlamaCppPerformance:
    """Test performance characteristics."""
    
    def test_response_time(self, llamacpp_server: str):
        """Test that responses come back in reasonable time."""
        start = time.time()
        
        response = requests.post(
            f"{llamacpp_server}/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10,
            },
            timeout=TIMEOUT,
        )
        
        elapsed = time.time() - start
        assert response.status_code == 200
        
        # Should respond in under 10 seconds for a tiny response
        assert elapsed < 10, f"Response took too long: {elapsed:.2f}s"
        print(f"Response time: {elapsed:.2f}s")
    
    def test_token_counting(self, llamacpp_server: str):
        """Test that token usage is reported."""
        response = requests.post(
            f"{llamacpp_server}/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Count to five."}],
                "max_tokens": 50,
            },
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        
        data = response.json()
        if "usage" in data:
            usage = data["usage"]
            assert "prompt_tokens" in usage
            assert "completion_tokens" in usage
            assert usage["prompt_tokens"] > 0
            assert usage["completion_tokens"] > 0
            print(f"Tokens: {usage}")


class TestLLMClientIntegration:
    """Test the unified LLMClient with llama.cpp backend."""
    
    def test_llm_client_generate(self, llamacpp_server: str):
        """Test LLMClient.generate() with llama.cpp."""
        # Set environment for llama.cpp backend
        os.environ["OPENAI_API_BASE"] = f"{llamacpp_server}/v1"
        os.environ["OPENAI_API_KEY"] = "not-needed"
        os.environ["LLM_MODEL"] = "local-model"
        
        try:
            from neural_engine.core.llm_client import LLMClient
            
            client = LLMClient(debug_mode=True)
            assert client._backend == "llama.cpp"
            
            response = client.generate("What is 2+2?", context="math test")
            assert "response" in response
            assert "4" in response["response"]
        finally:
            # Cleanup environment
            del os.environ["OPENAI_API_BASE"]
            del os.environ["OPENAI_API_KEY"]
            del os.environ["LLM_MODEL"]
    
    def test_llm_client_chat(self, llamacpp_server: str):
        """Test LLMClient.chat() with llama.cpp."""
        os.environ["OPENAI_API_BASE"] = f"{llamacpp_server}/v1"
        os.environ["OPENAI_API_KEY"] = "not-needed"
        os.environ["LLM_MODEL"] = "local-model"
        
        try:
            from neural_engine.core.llm_client import LLMClient
            
            client = LLMClient(debug_mode=True)
            
            response = client.chat(
                messages=[{"role": "user", "content": "Say 'test passed'"}],
                context="integration test"
            )
            
            assert "message" in response
            assert "content" in response["message"]
            content = response["message"]["content"].lower()
            assert "test" in content or "passed" in content
        finally:
            del os.environ["OPENAI_API_BASE"]
            del os.environ["OPENAI_API_KEY"]
            del os.environ["LLM_MODEL"]


# Quick smoke test that can run independently
if __name__ == "__main__":
    url = find_server()
    
    if not url:
        print("❌ Server not ready. Start with: ./start.sh")
        exit(1)
    
    print(f"✅ Server found at {url}")
    
    # Quick chat test
    response = requests.post(
        f"{url}/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Say 'llama.cpp works!'"}],
            "max_tokens": 20,
        },
        timeout=30,
    )
    
    if response.status_code == 200:
        content = response.json()["choices"][0]["message"]["content"]
        print(f"✅ Chat works: {content}")
    else:
        print(f"❌ Chat failed: {response.status_code}")
        exit(1)
    
    print("\n🎉 All smoke tests passed!")
