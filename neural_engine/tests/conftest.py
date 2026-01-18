"""
Shared test fixtures with isolated storage.

All fixtures use temporary files/directories to avoid polluting the live system.
Each test gets a clean state.
"""

import pytest
import tempfile
import shutil
import os
import subprocess
import time
import httpx
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def ensure_llm_container():
    """
    Ensure the LLM container is running before any tests start.
    
    This runs ONCE per test session and waits for the container to be healthy.
    """
    llm_base = os.environ.get("OPENAI_API_BASE", "http://llama-gpu:8080/v1")
    
    # Extract host from URL
    if "llama-gpu" in llm_base or "llama-cpu" in llm_base:
        # We're in Docker, check if LLM is reachable
        health_url = llm_base.replace("/v1", "/health")
        
        max_wait = 60  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = httpx.get(health_url, timeout=5)
                if response.status_code == 200:
                    print(f"\n✅ LLM container is healthy: {health_url}")
                    break
            except Exception:
                pass
            
            elapsed = int(time.time() - start_time)
            if elapsed % 10 == 0:
                print(f"\n⏳ Waiting for LLM container... ({elapsed}s)")
            time.sleep(2)
        else:
            pytest.fail(
                f"LLM container not available at {health_url} after {max_wait}s. "
                "Start it with: docker compose up -d llama-gpu"
            )
    
    yield


@pytest.fixture(scope="function")
def temp_cache_dir():
    """
    Create a temporary directory for cache files.
    Automatically cleaned up after each test.
    """
    temp_dir = tempfile.mkdtemp(prefix="test_cache_")
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def isolated_intent_cache(temp_cache_dir):
    """Path to isolated intent cache file."""
    return os.path.join(temp_cache_dir, "intent_cache.json")


@pytest.fixture(scope="function")
def isolated_tool_cache(temp_cache_dir):
    """Path to isolated tool cache file."""
    return os.path.join(temp_cache_dir, "tool_cache.json")


@pytest.fixture(scope="function")
def isolated_kv_store(temp_cache_dir):
    """Path to isolated key-value store file."""
    return os.path.join(temp_cache_dir, "kv_store.json")


@pytest.fixture(autouse=True, scope="function")
def clean_test_environment(monkeypatch):
    """
    Automatically set up clean test environment for ALL tests.
    Each test gets its own temporary directory for complete isolation.
    Clears all in-memory caches and message bus before each test.
    
    CRITICAL: Uses separate Redis database (db=1) to avoid deleting production data!
    """
    # Create unique temp directory for THIS test
    temp_dir = tempfile.mkdtemp(prefix="test_cache_")
    
    # CRITICAL: Use separate Redis database for tests (db=1, not db=0 production)
    monkeypatch.setenv("REDIS_DB", "1")
    
    # Set environment variables for isolated storage
    monkeypatch.setenv("NEURAL_ENGINE_CACHE_DIR", temp_dir)
    monkeypatch.setenv("NEURAL_ENGINE_KV_STORE", os.path.join(temp_dir, "kv_store.json"))
    monkeypatch.setenv("NEURAL_ENGINE_PATTERN_CACHE", os.path.join(temp_dir, "pattern_cache.json"))
    monkeypatch.setenv("NEURAL_ENGINE_INTENT_CACHE", os.path.join(temp_dir, "intent_cache.json"))
    monkeypatch.setenv("NEURAL_ENGINE_TOOL_CACHE", os.path.join(temp_dir, "tool_cache.json"))
    
    # Clear all in-memory caches BEFORE test runs
    from neural_engine.core.message_bus import MessageBus
    from neural_engine.core.pattern_cache import PatternCache
    
    # Clear message bus (Redis-backed) - now safely in db=1 test database
    message_bus = MessageBus()
    # Delete all keys matching goal_* pattern in TEST database only
    for key in message_bus.redis.keys("goal_*"):
        message_bus.redis.delete(key)
    
    # Clear pattern cache (singleton)
    pattern_cache = PatternCache()
    pattern_cache.clear()
    
    # Note: VotingToolSelector cache is file-based and will be isolated
    # by the temp_dir created above (each test gets its own directory)
    
    yield temp_dir
    
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def verify_test_isolation():
    """
    Verify we're not accidentally using live system files in tests.
    Runs once per test session.
    """
    # Print warning if we detect live cache access during tests
    live_cache_dir = Path("var")
    if live_cache_dir.exists():
        print(f"\n⚠️  REMINDER: Tests should use isolated fixtures, not {live_cache_dir}/")
        print("   Use temp_cache_dir fixture or isolated_*_cache fixtures")


@pytest.fixture(scope="function")
def system_config():
    """
    Provide a SystemConfig for integration testing.
    
    Uses real Redis but isolated test database.
    Uses real LLM client.
    """
    import redis.asyncio as redis_async
    from neural_engine.core.config import SystemConfig, Environment
    
    # Create Redis client for test database
    redis_host = os.environ.get("REDIS_HOST", "redis")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    redis_db = int(os.environ.get("REDIS_DB", 1))  # Use db=1 for tests
    
    redis_client = redis_async.Redis(
        host=redis_host, 
        port=redis_port, 
        db=redis_db,
        decode_responses=True
    )
    
    from neural_engine.core.llm_client import LLMClient
    config = SystemConfig.create_for_testing(
        redis_client=redis_client,
        llm_client=LLMClient()
    )
    
    yield config


@pytest.fixture(scope="function")
def minimal_config():
    """
    Provide a minimal SystemConfig for unit testing.
    
    No external dependencies - suitable for fast unit tests.
    """
    from neural_engine.core.config import SystemConfig
    return SystemConfig.create_minimal()

