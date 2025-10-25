# WSL GPU Setup - Completed

## Summary
Successfully configured NVIDIA GPU support for Docker in WSL on Debian Trixie.

## System Info
- **OS**: Debian GNU/Linux 13 (Trixie)
- **WSL**: Microsoft WSL
- **GPU**: NVIDIA GeForce RTX 5090 (32GB VRAM)
- **Driver**: 581.42 (Windows), 580.95.02 (WSL)
- **CUDA**: 13.0

## What Was Done

### 1. Added NVIDIA Container Toolkit Repository (Debian Trixie)
```bash
# Install GPG tools
sudo apt-get install -y gpg curl

# Add NVIDIA GPG key
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# Add repository
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Update and install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
```

### 2. Configured Docker Runtime
```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo service docker restart
```

### 3. Verified GPU Access
```bash
# Check runtime
docker info | grep -i runtimes
# Output: Runtimes: io.containerd.runc.v2 nvidia runc

# Test GPU
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
# Output: RTX 5090 detected successfully
```

### 4. Ollama Auto-Detection Works
```bash
./setup-ollama.sh
# Output: [INFO] GPU detected and available to Docker (auto): enabling --gpus all
```

## Current Status
✅ **GPU Enabled**: The setup script automatically detects and uses GPU  
✅ **USE_GPU=auto**: Default mode works correctly  
✅ **Ollama Container**: Running with `--gpus all` flag

## Notes for Debian Trixie Users
- The standard Ubuntu instructions don't work because Trixie isn't in NVIDIA's default repository list
- Need to manually add the repository with proper GPG key configuration
- The `nvidia-container-toolkit` package is version 1.18.0-1

## Verification Commands
```bash
# Check NVIDIA driver visibility
nvidia-smi

# Check Docker runtime
docker info | grep -i runtimes

# Test GPU in container
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi

# Check Ollama container GPU usage
docker logs ollama
```

## Optional: Force GPU On/Off
In `.env`:
```bash
USE_GPU=auto   # Auto-detect (default, recommended)
USE_GPU=true   # Force GPU (requires toolkit)
USE_GPU=false  # Force CPU-only
```

## Performance Expectations
With RTX 5090 (32GB VRAM):
- **llama3.1:8b**: Should run smoothly with fast inference
- **Larger models**: Can handle up to ~30B parameter models efficiently
- **Speed**: 10-50x faster than CPU-only inference
