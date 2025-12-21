"""
Model Manager - Automatic model discovery and updates for llama.cpp

This module handles:
1. Checking HuggingFace for latest GGUF model versions
2. Auto-downloading new versions when available
3. Switching to new models seamlessly
4. Cleanup of old model versions
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a model."""
    name: str
    repo_id: str  # HuggingFace repo, e.g., "Qwen/Qwen2.5-3B-Instruct-GGUF"
    filename: str  # e.g., "qwen2.5-3b-instruct-q4_k_m.gguf"
    quantization: str  # e.g., "Q4_K_M"
    size_gb: float
    local_path: Optional[Path] = None
    last_checked: Optional[datetime] = None
    etag: Optional[str] = None  # For checking updates


# Recommended models for different RAM sizes
RECOMMENDED_MODELS = {
    "8gb": ModelInfo(
        name="qwen2.5-1.5b",
        repo_id="Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        filename="qwen2.5-1.5b-instruct-q4_k_m.gguf",
        quantization="Q4_K_M",
        size_gb=1.0,
    ),
    "16gb": ModelInfo(
        name="qwen2.5-3b",
        repo_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
        filename="qwen2.5-3b-instruct-q4_k_m.gguf",
        quantization="Q4_K_M",
        size_gb=2.0,
    ),
    "32gb": ModelInfo(
        name="qwen2.5-7b",
        repo_id="Qwen/Qwen2.5-7B-Instruct-GGUF",
        filename="qwen2.5-7b-instruct-q4_k_m.gguf",
        quantization="Q4_K_M",
        size_gb=4.5,
    ),
    "64gb": ModelInfo(
        name="qwen2.5-32b",
        repo_id="Qwen/Qwen2.5-32B-Instruct-GGUF",
        filename="qwen2.5-32b-instruct-q4_k_m.gguf",
        quantization="Q4_K_M",
        size_gb=20.0,
    ),
}


class ModelManager:
    """
    Manages GGUF models for llama.cpp with automatic updates.
    
    Usage:
        manager = ModelManager("/models")
        model_path = await manager.ensure_model("16gb")
        # Returns path to ready-to-use GGUF file
    """
    
    def __init__(self, models_dir: str = "/models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.models_dir / "model_state.json"
        self.check_interval = timedelta(hours=24)  # Check for updates daily
        self._state = self._load_state()
    
    def _load_state(self) -> dict:
        """Load persistent state about downloaded models."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except Exception as e:
                logger.warning(f"Failed to load model state: {e}")
        return {"models": {}, "last_update_check": None}
    
    def _save_state(self):
        """Persist state to disk."""
        self.state_file.write_text(json.dumps(self._state, indent=2, default=str))
    
    async def ensure_model(self, ram_profile: str = "16gb") -> Path:
        """
        Ensure a model is available and up-to-date.
        
        Args:
            ram_profile: One of "8gb", "16gb", "32gb", "64gb"
            
        Returns:
            Path to the GGUF model file
        """
        if ram_profile not in RECOMMENDED_MODELS:
            raise ValueError(f"Unknown RAM profile: {ram_profile}. Use: {list(RECOMMENDED_MODELS.keys())}")
        
        model_info = RECOMMENDED_MODELS[ram_profile]
        model_path = self.models_dir / model_info.filename
        
        # Check if we need to update
        should_update = await self._should_check_update(model_info)
        
        if should_update:
            logger.info(f"Checking for updates to {model_info.name}...")
            new_available = await self._check_for_update(model_info)
            if new_available or not model_path.exists():
                await self._download_model(model_info)
        
        if not model_path.exists():
            # First time download
            await self._download_model(model_info)
        
        return model_path
    
    async def _should_check_update(self, model_info: ModelInfo) -> bool:
        """Determine if we should check for updates."""
        model_state = self._state["models"].get(model_info.name, {})
        last_checked = model_state.get("last_checked")
        
        if not last_checked:
            return True
        
        last_checked_dt = datetime.fromisoformat(last_checked)
        return datetime.now() - last_checked_dt > self.check_interval
    
    async def _check_for_update(self, model_info: ModelInfo) -> bool:
        """
        Check HuggingFace for model updates using ETag.
        Returns True if a newer version is available.
        """
        import aiohttp
        
        url = f"https://huggingface.co/{model_info.repo_id}/resolve/main/{model_info.filename}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, allow_redirects=True) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to check for updates: HTTP {response.status}")
                        return False
                    
                    remote_etag = response.headers.get("ETag", "").strip('"')
                    
                    # Update last checked time
                    if model_info.name not in self._state["models"]:
                        self._state["models"][model_info.name] = {}
                    self._state["models"][model_info.name]["last_checked"] = datetime.now().isoformat()
                    self._save_state()
                    
                    # Compare with local etag
                    local_etag = self._state["models"].get(model_info.name, {}).get("etag")
                    
                    if local_etag and local_etag == remote_etag:
                        logger.info(f"{model_info.name} is up to date")
                        return False
                    
                    if local_etag:
                        logger.info(f"New version of {model_info.name} available!")
                    return True
                    
        except Exception as e:
            logger.warning(f"Failed to check for updates: {e}")
            return False
    
    async def _download_model(self, model_info: ModelInfo):
        """Download model from HuggingFace with progress."""
        import aiohttp
        
        url = f"https://huggingface.co/{model_info.repo_id}/resolve/main/{model_info.filename}"
        model_path = self.models_dir / model_info.filename
        temp_path = self.models_dir / f"{model_info.filename}.downloading"
        
        logger.info(f"Downloading {model_info.name} ({model_info.size_gb}GB)...")
        logger.info(f"From: {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(f"Download failed: HTTP {response.status}")
                    
                    total_size = int(response.headers.get("Content-Length", 0))
                    etag = response.headers.get("ETag", "").strip('"')
                    downloaded = 0
                    
                    with open(temp_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192 * 1024):  # 8MB chunks
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size:
                                pct = (downloaded / total_size) * 100
                                logger.info(f"Progress: {pct:.1f}% ({downloaded / 1e9:.2f}GB / {total_size / 1e9:.2f}GB)")
            
            # Atomic rename
            temp_path.rename(model_path)
            
            # Update state
            self._state["models"][model_info.name] = {
                "etag": etag,
                "downloaded_at": datetime.now().isoformat(),
                "last_checked": datetime.now().isoformat(),
                "path": str(model_path),
            }
            self._save_state()
            
            logger.info(f"✅ Downloaded {model_info.name} to {model_path}")
            
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to download {model_info.name}: {e}")
    
    def get_current_model_path(self, ram_profile: str = "16gb") -> Optional[Path]:
        """Get path to currently downloaded model, or None if not downloaded."""
        if ram_profile not in RECOMMENDED_MODELS:
            return None
        
        model_info = RECOMMENDED_MODELS[ram_profile]
        model_path = self.models_dir / model_info.filename
        
        if model_path.exists():
            return model_path
        return None
    
    def cleanup_old_models(self, keep_profiles: list[str] = None):
        """Remove old model versions to free disk space."""
        if keep_profiles is None:
            keep_profiles = ["16gb"]
        
        keep_files = set()
        for profile in keep_profiles:
            if profile in RECOMMENDED_MODELS:
                keep_files.add(RECOMMENDED_MODELS[profile].filename)
        
        for file in self.models_dir.glob("*.gguf"):
            if file.name not in keep_files:
                logger.info(f"Removing old model: {file.name}")
                file.unlink()


# Convenience function for scripts
async def auto_update_model(ram_profile: str = "16gb", models_dir: str = "/models") -> str:
    """
    One-liner to ensure model is downloaded and up-to-date.
    
    Returns path to model file as string.
    """
    manager = ModelManager(models_dir)
    path = await manager.ensure_model(ram_profile)
    return str(path)
