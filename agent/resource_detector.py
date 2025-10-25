"""
Resource detection for automatic model selection.

Detects available:
- System RAM
- GPU VRAM (if available)
- CPU cores
"""

import logging
import os
import platform
import subprocess
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def detect_system_resources() -> Dict[str, any]:
    """
    Detect available system resources.
    
    Returns:
        Dict with keys: ram_gb, vram_gb, cpu_cores, platform
    """
    resources = {
        'ram_gb': detect_ram_gb(),
        'vram_gb': detect_vram_gb(),
        'cpu_cores': detect_cpu_cores(),
        'platform': platform.system(),
        'machine': platform.machine(),
    }
    
    logger.info("📊 Detected system resources:")
    logger.info(f"   RAM: {resources['ram_gb']:.1f} GB")
    if resources['vram_gb']:
        logger.info(f"   VRAM: {resources['vram_gb']:.1f} GB (GPU available)")
    else:
        logger.info(f"   VRAM: None (CPU only)")
    logger.info(f"   CPU cores: {resources['cpu_cores']}")
    logger.info(f"   Platform: {resources['platform']} ({resources['machine']})")
    
    return resources


def detect_ram_gb() -> float:
    """Detect total system RAM in GB."""
    try:
        # Try reading /proc/meminfo (Linux)
        if os.path.exists('/proc/meminfo'):
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        # MemTotal is in KB
                        kb = int(line.split()[1])
                        return kb / (1024 * 1024)  # Convert to GB
        
        # Try sysctl (macOS)
        if platform.system() == 'Darwin':
            result = subprocess.run(['sysctl', '-n', 'hw.memsize'],
                                   capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                bytes_mem = int(result.stdout.strip())
                return bytes_mem / (1024 ** 3)  # Convert to GB
        
        # Fallback: try psutil if available
        try:
            import psutil
            return psutil.virtual_memory().total / (1024 ** 3)
        except ImportError:
            pass
        
        logger.warning("Could not detect RAM, defaulting to 8GB")
        return 8.0
        
    except Exception as e:
        logger.error(f"Error detecting RAM: {e}")
        return 8.0


def detect_vram_gb() -> Optional[float]:
    """
    Detect available GPU VRAM in GB.
    Returns None if no GPU detected or CUDA/ROCm not available.
    
    Can be overridden with VRAM_GB environment variable.
    """
    # Check for manual override first
    vram_override = os.environ.get('VRAM_GB')
    if vram_override:
        try:
            vram_gb = float(vram_override)
            logger.info(f"🎮 Using manually configured VRAM: {vram_gb:.1f} GB (from VRAM_GB env var)")
            return vram_gb
        except ValueError:
            logger.warning(f"⚠️  Invalid VRAM_GB value: {vram_override}")
    
    # Try multiple methods to detect NVIDIA GPU
    
    # Method 1: Check NVIDIA_VISIBLE_DEVICES env var (Docker container)
    nvidia_devices = os.environ.get('NVIDIA_VISIBLE_DEVICES', '')
    if nvidia_devices and nvidia_devices != 'void':
        logger.info(f"🎮 NVIDIA GPU environment detected: {nvidia_devices}")
    
    # Method 2: Check for nvidia-smi in container
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total',
                               '--format=csv,noheader,nounits'],
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Get first GPU's memory in MB
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                mb = int(lines[0].strip())
                vram_gb = mb / 1024
                logger.info(f"🎮 NVIDIA GPU detected with {vram_gb:.1f} GB VRAM")
                return vram_gb
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.debug(f"nvidia-smi not available in container: {e}")
    
    # Method 3: Try to read from /proc (if mounted)
    try:
        if os.path.exists('/proc/driver/nvidia/gpus'):
            gpu_dirs = os.listdir('/proc/driver/nvidia/gpus')
            if gpu_dirs:
                logger.info(f"🎮 NVIDIA GPU detected via /proc: {len(gpu_dirs)} GPU(s)")
                # Can't get exact VRAM from /proc, but we know GPU exists
                # Default to common VRAM sizes based on detection
                return None  # Will indicate GPU present but need to check elsewhere
    except Exception:
        pass
    
    # Method 4: Check CUDA device files
    cuda_devices = [f for f in os.listdir('/dev') if f.startswith('nvidia')] if os.path.exists('/dev') else []
    if cuda_devices:
        logger.info(f"🎮 NVIDIA CUDA devices detected: {cuda_devices}")
        # GPU present but can't determine VRAM - assume decent GPU
        logger.warning("⚠️  GPU detected but cannot determine VRAM size. Assuming 16GB for model selection.")
        return 16.0  # Conservative estimate
    
    try:
        # Try rocm-smi for AMD GPUs
        result = subprocess.run(['rocm-smi', '--showmeminfo', 'vram'],
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Parse AMD GPU memory (format varies)
            output = result.stdout
            # Look for VRAM Total line
            for line in output.split('\n'):
                if 'VRAM Total' in line or 'Total' in line:
                    # Extract number (usually in MB or GB)
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.isdigit():
                            size = int(part)
                            # Guess unit based on size
                            if size > 1000:  # Likely MB
                                vram_gb = size / 1024
                            else:  # Likely GB
                                vram_gb = size
                            logger.info(f"🎮 AMD GPU detected with ~{vram_gb:.1f} GB VRAM")
                            return vram_gb
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    
    # Check for Intel GPUs (less common for ML)
    # TODO: Add Intel GPU detection if needed
    
    logger.info("No GPU detected or unable to query VRAM. Using CPU mode.")
    return None


def detect_cpu_cores() -> int:
    """Detect number of CPU cores."""
    try:
        return os.cpu_count() or 4
    except Exception:
        return 4


def check_ollama_gpu_support() -> bool:
    """
    Check if Ollama container has GPU support enabled.
    This checks if CUDA/ROCm libraries are accessible.
    """
    try:
        # Check for CUDA
        result = subprocess.run(['docker', 'run', '--rm', 'ollama/ollama:latest',
                               'nvidia-smi'],
                               capture_output=True, timeout=10)
        if result.returncode == 0:
            logger.info("✅ Ollama has NVIDIA GPU support")
            return True
    except Exception:
        pass
    
    try:
        # Check for ROCm
        result = subprocess.run(['docker', 'run', '--rm', 'ollama/ollama:latest',
                               'rocm-smi'],
                               capture_output=True, timeout=10)
        if result.returncode == 0:
            logger.info("✅ Ollama has AMD ROCm support")
            return True
    except Exception:
        pass
    
    logger.info("ℹ️  Ollama running in CPU mode")
    return False


def get_recommended_model() -> str:
    """
    Get recommended model based on detected resources.
    
    Returns:
        Model name string
    """
    from agent.model_config import select_best_model
    
    resources = detect_system_resources()
    
    # Select best model
    profile = select_best_model(
        available_ram_gb=resources['ram_gb'],
        available_vram_gb=resources['vram_gb'],
        prefer_fast=False,  # Prioritize quality over speed
        prefer_reasoning=True  # We want good reasoning
    )
    
    return profile.name
