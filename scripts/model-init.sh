#!/bin/bash
# model-init.sh - Downloads the appropriate model for the RAM profile

set -e

RAM_PROFILE="${RAM_PROFILE:-16gb}"
MODELS_DIR="/models"
STATE_FILE="${MODELS_DIR}/model_state.json"

# Model definitions (repo_id, filename, size_description)
declare -A MODELS
MODELS["8gb"]="Qwen/Qwen2.5-1.5B-Instruct-GGUF|qwen2.5-1.5b-instruct-q4_k_m.gguf|1GB"
MODELS["16gb"]="Qwen/Qwen2.5-3B-Instruct-GGUF|qwen2.5-3b-instruct-q4_k_m.gguf|2GB"
MODELS["32gb"]="Qwen/Qwen2.5-7B-Instruct-GGUF|qwen2.5-7b-instruct-q4_k_m.gguf|4.5GB"
MODELS["64gb"]="Qwen/Qwen2.5-32B-Instruct-GGUF|qwen2.5-32b-instruct-q4_k_m.gguf|20GB"

# Parse model info
IFS='|' read -r REPO_ID FILENAME SIZE_DESC <<< "${MODELS[$RAM_PROFILE]}"

if [ -z "$REPO_ID" ]; then
    echo "❌ Unknown RAM profile: $RAM_PROFILE"
    echo "   Valid options: 8gb, 16gb, 32gb, 64gb"
    exit 1
fi

MODEL_URL="https://huggingface.co/${REPO_ID}/resolve/main/${FILENAME}"
MODEL_PATH="${MODELS_DIR}/${FILENAME}"
CURRENT_LINK="${MODELS_DIR}/current.gguf"

echo "🧠 Dendrite Model Initializer"
echo "   RAM Profile: ${RAM_PROFILE}"
echo "   Model: ${FILENAME} (${SIZE_DESC})"
echo ""

# Check if model already exists
if [ -f "$MODEL_PATH" ]; then
    echo "✅ Model already downloaded: $MODEL_PATH"
    
    # Ensure symlink is correct
    ln -sf "$MODEL_PATH" "$CURRENT_LINK"
    echo "✅ Symlinked to: $CURRENT_LINK"
    exit 0
fi

# Install curl if needed
if ! command -v curl &> /dev/null; then
    echo "📦 Installing curl..."
    apt-get update -qq && apt-get install -y -qq curl
fi

# Download model
echo "⬇️  Downloading model from HuggingFace..."
echo "   URL: $MODEL_URL"
echo ""

TEMP_PATH="${MODEL_PATH}.downloading"

# Add HF token if provided (for gated models)
CURL_OPTS="-L --progress-bar"
if [ -n "$HF_TOKEN" ]; then
    CURL_OPTS="$CURL_OPTS -H 'Authorization: Bearer $HF_TOKEN'"
fi

# Download with progress
curl $CURL_OPTS -o "$TEMP_PATH" "$MODEL_URL"

# Verify download
if [ ! -f "$TEMP_PATH" ]; then
    echo "❌ Download failed!"
    exit 1
fi

# Get file size
SIZE=$(du -h "$TEMP_PATH" | cut -f1)
echo ""
echo "📦 Downloaded: $SIZE"

# Atomic rename
mv "$TEMP_PATH" "$MODEL_PATH"

# Create symlink for llama.cpp
ln -sf "$MODEL_PATH" "$CURRENT_LINK"

# Update state file
cat > "$STATE_FILE" << EOF
{
  "ram_profile": "$RAM_PROFILE",
  "model_file": "$FILENAME",
  "repo_id": "$REPO_ID",
  "downloaded_at": "$(date -Iseconds)",
  "size": "$SIZE"
}
EOF

echo ""
echo "✅ Model ready: $MODEL_PATH"
echo "✅ Symlinked to: $CURRENT_LINK"
echo ""
echo "🚀 llama.cpp server can now start!"
