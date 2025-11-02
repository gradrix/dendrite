"""
Shared test fixtures with isolated storage.

All fixtures use temporary files/directories to avoid polluting the live system.
Each test gets a clean state.
"""

import pytest
import tempfile
import shutil
import os
from pathlib import Path


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
    """
    # Create unique temp directory for THIS test
    temp_dir = tempfile.mkdtemp(prefix="test_cache_")
    
    # Set environment variables for isolated storage
    monkeypatch.setenv("NEURAL_ENGINE_CACHE_DIR", temp_dir)
    monkeypatch.setenv("NEURAL_ENGINE_KV_STORE", os.path.join(temp_dir, "kv_store.json"))
    monkeypatch.setenv("NEURAL_ENGINE_PATTERN_CACHE", os.path.join(temp_dir, "pattern_cache.json"))
    monkeypatch.setenv("NEURAL_ENGINE_INTENT_CACHE", os.path.join(temp_dir, "intent_cache.json"))
    monkeypatch.setenv("NEURAL_ENGINE_TOOL_CACHE", os.path.join(temp_dir, "tool_cache.json"))
    
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
