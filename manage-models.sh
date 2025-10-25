#!/bin/bash
#
# Unified Model Management Script
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.yaml"

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_header() {
    echo ""
    echo -e "${CYAN}=========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}=========================================${NC}"
}

check_ollama() {
    if ! docker ps | grep -q ollama; then
        print_error "Ollama container is not running!"
        print_info "Start it with: ./setup-ollama.sh"
        exit 1
    fi
}

get_recommended_model() {
    docker compose run --rm agent python3 show_model_recommendation.py 2>/dev/null | \
        grep "Best match:" | awk '{print $4}'
}

show_recommendation() {
    print_header "Model Recommendation"
    docker compose run --rm agent python3 show_model_recommendation.py 2>/dev/null
}

list_downloaded_models() {
    print_header "Downloaded Models in Ollama"
    docker exec ollama ollama list 2>/dev/null || {
        print_error "Failed to list models"
        return 1
    }
}

is_model_downloaded() {
    local model_name="$1"
    docker exec ollama ollama list 2>/dev/null | grep -q "^${model_name}"
}

download_model() {
    local model_name="$1"
    
    if is_model_downloaded "$model_name"; then
        print_info "Model '${model_name}' is already downloaded"
        return 0
    fi
    
    print_info "Downloading model: ${model_name}"
    print_warning "This may take several minutes..."
    
    docker exec -it ollama ollama pull "$model_name" || {
        print_error "Failed to download model"
        return 1
    }
    
    print_info "✅ Model downloaded successfully!"
}

delete_model() {
    local model_name="$1"
    
    if ! is_model_downloaded "$model_name"; then
        print_warning "Model not downloaded"
        return 1
    fi
    
    print_warning "Delete '${model_name}'? [y/N]"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        docker exec ollama ollama rm "$model_name"
        print_info "✅ Model deleted"
    fi
}

update_config_model() {
    local model_name="$1"
    
    if grep -q "^  model:" "$CONFIG_FILE"; then
        sed -i "s|^  model:.*|  model: \"${model_name}\"|" "$CONFIG_FILE"
        print_info "✅ Updated config.yaml"
    else
        print_error "Could not find model config"
        return 1
    fi
}

get_current_model() {
    grep "^  model:" "$CONFIG_FILE" | sed 's/.*: *"\([^"]*\)".*/\1/' || echo "auto"
}

cmd_auto() {
    print_header "🤖 Auto-Select Best Model"
    check_ollama
    
    recommended=$(get_recommended_model)
    if [ -z "$recommended" ]; then
        print_error "Failed to get recommendation"
        exit 1
    fi
    
    show_recommendation
    
    if ! is_model_downloaded "$recommended"; then
        print_info "Download ${recommended}? [Y/n]"
        read -r response
        [[ ! "$response" =~ ^[Nn]$ ]] && download_model "$recommended"
    else
        print_info "✅ Model already downloaded"
    fi
    
    current=$(get_current_model)
    if [ "$current" != "$recommended" ]; then
        print_info "Update config to use ${recommended}? [Y/n]"
        read -r response
        [[ ! "$response" =~ ^[Nn]$ ]] && update_config_model "$recommended"
    fi
    
    print_info "✅ Setup complete!"
}

cmd_list() {
    check_ollama
    list_downloaded_models
    echo ""
    print_info "Configured: $(get_current_model)"
}

cmd_use() {
    [ -z "$1" ] && { print_error "Usage: $0 use <model-name>"; exit 1; }
    check_ollama
    
    is_model_downloaded "$1" || {
        print_info "Download $1? [Y/n]"
        read -r response
        [[ ! "$response" =~ ^[Nn]$ ]] && download_model "$1"
    }
    
    update_config_model "$1"
    print_info "✅ Now using: $1"
}

cmd_download() {
    [ -z "$1" ] && { print_error "Usage: $0 download <model-name>"; exit 1; }
    check_ollama
    download_model "$1"
}

cmd_delete() {
    [ -z "$1" ] && { print_error "Usage: $0 delete <model-name>"; exit 1; }
    check_ollama
    delete_model "$1"
}

cmd_recommend() {
    show_recommendation
}

cmd_info() {
    check_ollama
    print_header "System & Model Information"
    print_info "Configured: $(get_current_model)"
    echo ""
    list_downloaded_models
    echo ""
    print_info "Recommended: $(get_recommended_model)"
}

show_help() {
    cat << EOF
${CYAN}Model Management${NC}

${GREEN}Commands:${NC}
  ${YELLOW}auto${NC}              Auto-detect and setup best model
  ${YELLOW}list${NC}              List downloaded models
  ${YELLOW}use <model>${NC}       Switch to a model (downloads if needed)
  ${YELLOW}download <model>${NC}  Download a model
  ${YELLOW}delete <model>${NC}    Delete a model
  ${YELLOW}recommend${NC}         Show recommended model
  ${YELLOW}info${NC}              Show system info and models

${GREEN}Examples:${NC}
  $0 auto
  $0 use mistral-small3.2:24b
  $0 list
  $0 download llama3.1:8b

EOF
}

main() {
    case "${1:-help}" in
        auto) cmd_auto ;;
        list|ls) cmd_list ;;
        use|switch) shift; cmd_use "$@" ;;
        download|pull) shift; cmd_download "$@" ;;
        delete|rm) shift; cmd_delete "$@" ;;
        recommend|rec) cmd_recommend ;;
        info|status) cmd_info ;;
        *) show_help ;;
    esac
}

main "$@"
