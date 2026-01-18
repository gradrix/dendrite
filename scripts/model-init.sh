#!/bin/bash
#
# Model initialization script for llama.cpp
# Downloads GGUF models based on RAM_PROFILE
#

set -e

MODEL_DIR="/models"
CURRENT_MODEL="$MODEL_DIR/current.gguf"

# Model URLs based on RAM profile
# Using small, efficient models that work well with llama.cpp
declare -A MODELS=(
    # 8GB RAM - Phi-3 Mini (3.8B params, ~2.3GB)
    ["8gb"]="https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf"
    
    # 16GB RAM - Mistral 7B (7B params, ~4.1GB) 
    ["16gb"]="https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    
    # 32GB RAM - Mistral 7B Q5 (better quality)
    ["32gb"]="https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q5_K_M.gguf"
)

RAM_PROFILE="${RAM_PROFILE:-16gb}"
MODEL_URL="${MODELS[$RAM_PROFILE]}"

if [ -z "$MODEL_URL" ]; then
    echo "Unknown RAM profile: $RAM_PROFILE. Using 16gb default."
    MODEL_URL="${MODELS[16gb]}"
fi

echo "=============================================="
echo "Dendrite Model Initialization"
echo "=============================================="
echo "RAM Profile: $RAM_PROFILE"
echo "Model URL: $MODEL_URL"
echo ""

# Check if model already exists
if [ -f "$CURRENT_MODEL" ]; then
    echo "✅ Model already exists at $CURRENT_MODEL"
    echo "   Size: $(du -h $CURRENT_MODEL | cut -f1)"
    exit 0
fi

echo "📥 Downloading model..."
echo "   This may take a few minutes on first run."
echo ""

# Install wget if not present
apt-get update -qq && apt-get install -y -qq wget > /dev/null 2>&1

# Download with progress
wget --progress=bar:force:noscroll -O "$CURRENT_MODEL" "$MODEL_URL"

echo ""
echo "✅ Model downloaded successfully!"
echo "   Size: $(du -h $CURRENT_MODEL | cut -f1)"
echo "   Path: $CURRENT_MODEL"
