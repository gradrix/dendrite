#!/bin/bash
# model-updater.sh - Periodically checks for model updates and hot-swaps them

set -e

RAM_PROFILE="${RAM_PROFILE:-16gb}"
CHECK_INTERVAL="${CHECK_INTERVAL:-86400}"  # Default: 24 hours
MODELS_DIR="/models"
STATE_FILE="${MODELS_DIR}/model_state.json"

# Model definitions
declare -A MODELS
MODELS["8gb"]="Qwen/Qwen2.5-1.5B-Instruct-GGUF|qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODELS["16gb"]="Qwen/Qwen2.5-3B-Instruct-GGUF|qwen2.5-3b-instruct-q4_k_m.gguf"
MODELS["32gb"]="Qwen/Qwen2.5-7B-Instruct-GGUF|qwen2.5-7b-instruct-q4_k_m.gguf"
MODELS["64gb"]="Qwen/Qwen2.5-32B-Instruct-GGUF|qwen2.5-32b-instruct-q4_k_m.gguf"

IFS='|' read -r REPO_ID FILENAME <<< "${MODELS[$RAM_PROFILE]}"
MODEL_URL="https://huggingface.co/${REPO_ID}/resolve/main/${FILENAME}"
MODEL_PATH="${MODELS_DIR}/${FILENAME}"
CURRENT_LINK="${MODELS_DIR}/current.gguf"

# Install curl if needed
if ! command -v curl &> /dev/null; then
    apt-get update -qq && apt-get install -y -qq curl jq
fi

echo "🔄 Dendrite Model Updater"
echo "   Checking for updates every ${CHECK_INTERVAL} seconds"
echo "   Model: ${FILENAME}"
echo ""

check_and_update() {
    echo "[$(date)] Checking for model updates..."
    
    # Get remote ETag
    REMOTE_ETAG=$(curl -sI -L "$MODEL_URL" | grep -i "^etag:" | awk '{print $2}' | tr -d '"\r')
    
    if [ -z "$REMOTE_ETAG" ]; then
        echo "   ⚠️  Could not fetch remote ETag, skipping update check"
        return
    fi
    
    # Get local ETag from state file
    LOCAL_ETAG=""
    if [ -f "$STATE_FILE" ]; then
        LOCAL_ETAG=$(cat "$STATE_FILE" | grep -o '"etag"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "")
    fi
    
    if [ "$REMOTE_ETAG" = "$LOCAL_ETAG" ]; then
        echo "   ✅ Model is up to date (ETag: ${REMOTE_ETAG:0:16}...)"
        return
    fi
    
    echo "   🆕 New model version available!"
    echo "   Local:  ${LOCAL_ETAG:0:16}..."
    echo "   Remote: ${REMOTE_ETAG:0:16}..."
    echo ""
    echo "   ⬇️  Downloading new version..."
    
    # Download to temp file
    TEMP_PATH="${MODEL_PATH}.new"
    
    CURL_OPTS="-L --progress-bar"
    if [ -n "$HF_TOKEN" ]; then
        CURL_OPTS="$CURL_OPTS -H 'Authorization: Bearer $HF_TOKEN'"
    fi
    
    if curl $CURL_OPTS -o "$TEMP_PATH" "$MODEL_URL"; then
        # Backup old model
        if [ -f "$MODEL_PATH" ]; then
            mv "$MODEL_PATH" "${MODEL_PATH}.old"
        fi
        
        # Swap in new model
        mv "$TEMP_PATH" "$MODEL_PATH"
        
        # Update symlink (atomic on most filesystems)
        ln -sf "$MODEL_PATH" "$CURRENT_LINK"
        
        # Update state file
        cat > "$STATE_FILE" << EOF
{
  "ram_profile": "$RAM_PROFILE",
  "model_file": "$FILENAME",
  "repo_id": "$REPO_ID",
  "etag": "$REMOTE_ETAG",
  "updated_at": "$(date -Iseconds)"
}
EOF
        
        # Remove old model
        rm -f "${MODEL_PATH}.old"
        
        echo ""
        echo "   ✅ Model updated successfully!"
        echo "   ⚠️  Note: llama.cpp server needs restart to use new model"
        echo "      Run: docker compose restart llama-server"
    else
        echo "   ❌ Download failed, keeping existing model"
        rm -f "$TEMP_PATH"
    fi
}

# Initial check
check_and_update

# Loop forever
while true; do
    sleep "$CHECK_INTERVAL"
    check_and_update
done
