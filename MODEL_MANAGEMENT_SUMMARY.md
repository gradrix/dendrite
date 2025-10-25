# Model Management & Resource Detection System

## Overview

Comprehensive system for automatic model selection, resource detection, and intelligent tool usage for counting tasks.

## What Was Implemented

### 1. **Centralized Model Configuration** (`agent/model_config.py`)
- Model profiles with resource requirements (RAM/VRAM, params, capabilities)
- Model metadata: reasoning, counting reliability, JSON output, code understanding
- Automatic model selection based on available resources
- Support for models from 3B (Raspberry Pi) to 32B+ (high-end workstations)

**Supported Models:**
- **Small (3-4GB)**: qwen2.5:3b, llama3.2:3b, phi3:3.8b
- **Medium (8-16GB)**: llama3.1:8b, qwen2.5:14b  
- **Large (20-32GB)**: mistral-small3.2:24b, qwen2.5:32b, deepseek-r1:32b

### 2. **Resource Detection** (`agent/resource_detector.py`)
- Auto-detect system RAM
- Auto-detect GPU VRAM (NVIDIA/AMD)
- Manual override via `VRAM_GB` environment variable in `.env`
- Platform detection (Linux/macOS/Windows)
- CPU core count

### 3. **Compact Context Storage**
**Problem**: Activities with polylines consumed ~114KB per response, overwhelming small models.

**Solution**: 
- Store only 6 essential fields: `name, type, sport_type, id, distance, date`
- Remove polylines and 50+ unnecessary fields
- Reduces context from ~114KB to ~4KB
- Automatic transformation via `_compact_activity_data()` function

**Log Output:**
```
💾 Stored 57 activities in compact format (removed polylines & extra fields)
📋 Using pre-stored compact format: 57 activities
```

### 4. **Strategy Advisor System**
**Problem**: Even large models (32B) miscounted activities. Small models require guidance.

**Solution**: Expert strategy advisor (`_get_strategy_advice()`) that:
- Detects counting/filtering tasks
- Recommends Python execution over AI counting
- Provides explicit guidance in decomposition prompt
- Forces use of `executeDataAnalysis` tool for reliable results

**Example Output:**
```
🎯 EXPERT STRATEGY RECOMMENDATION:
⚠️ CRITICAL: Use executeDataAnalysis tool with Python code for counting/filtering.
   Reason: AI models (even 32B+) can miscount. Python is 100% reliable.
⚠️ Large dataset detected: Counting 50+ items by AI is unreliable. MUST use Python.
```

### 5. **Improved Tool Selection**
- Enhanced pattern matching for `executeDataAnalysis`
- Higher scores for counting-related neuron descriptions
- Tool description updated to emphasize 100% accuracy vs AI counting
- Examples in tool parameters showing context key access

### 6. **Unified Model Management Script** (`manage-models.sh`)

Replaces `fix-model-download.sh` and `select-model.sh` with single comprehensive tool.

**Commands:**
```bash
./manage-models.sh auto              # Auto-detect, download, configure
./manage-models.sh list              # List downloaded models
./manage-models.sh use <model>       # Switch model (downloads if needed)
./manage-models.sh download <model>  # Download without switching
./manage-models.sh delete <model>    # Remove model
./manage-models.sh recommend         # Show recommendation
./manage-models.sh info              # Show system & model info
```

**Features:**
- Interactive prompts for downloads
- Automatic config.yaml updates
- Checks if model is already downloaded
- Shows full system capabilities and recommendations

### 7. **Automatic Model Selection in main.py**
- Reads `model: "auto"` from config.yaml
- Calls resource detector
- Selects best model for available resources
- Logs model capabilities (reasoning, counting, JSON, code)
- Falls back to configured model if auto-detection fails

**Startup Logs:**
```
🔍 Auto-detecting best model for available resources...
📊 Detected system resources:
   RAM: 30.2 GB
   VRAM: 32.0 GB (GPU available)
   CPU cores: 8
🎯 Selected model: mistral-small3.2:24b
   Reasoning: True, Counting: True, JSON: True, Code: True
✅ Auto-selected model: mistral-small3.2:24b
```

## Configuration

### Environment Variables (`.env`)
```bash
# GPU VRAM override (optional - auto-detected if not set)
VRAM_GB=32

# Strava credentials
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_secret
```

### Config.yaml
```yaml
ollama:
  base_url: "http://ollama:11434"
  
  # Auto-detect best model on startup
  model: "auto"
  
  # Or specify manually
  # model: "mistral-small3.2:24b"
  
  fallback_model: "llama3.1:8b"
  
  # Force Python for counting (recommended - even 32B models can miscount)
  force_python_counting: true
  
  timeout: 600
  max_retries: 3
  temperature: 0.7
```

## Usage Examples

### Initial Setup
```bash
# 1. Check system and get recommendation
./manage-models.sh recommend

# 2. Auto-setup (detect, download, configure)
./manage-models.sh auto

# 3. Run agent
./start-agent.sh
```

### Switch Models
```bash
# Switch to specific model
./manage-models.sh use llama3.1:8b

# Or edit config.yaml manually
# model: "llama3.1:8b"
```

### Check Status
```bash
# See what's downloaded
./manage-models.sh list

# Full system info
./manage-models.sh info
```

## Why This Matters

### For Raspberry Pi / Edge Devices
- **Auto-detects limited resources** (4-8GB RAM)
- **Selects appropriate small models** (3B-8B parameters)
- **Compact context** prevents OOM errors
- **Python tools** compensate for small model limitations

### For Workstations / Servers
- **Utilizes full GPU** (detected 32GB VRAM)
- **Selects powerful models** (24B-32B parameters)
- **Still uses Python for counting** (even large models can fail)
- **Optimal performance** without manual tuning

## Key Insights

### AI Counting is Unreliable
- ❌ 3B models: Cannot count reliably (tested)
- ❌ 32B deepseek-r1: Chain-of-thought reasoning causes errors
- ❌ Even with clean data (4KB vs 114KB), miscounting occurs
- ✅ **Solution**: Force Python execution for 100% accuracy

### Context Size Matters
- **Before**: 57 activities × ~2KB polylines = ~114KB
- **After**: 57 activities × 6 fields = ~4KB  
- **27x reduction** in context size
- Still AI miscounted → Python tools are the real solution

### Strategy Guidance Works
- Expert advisor detects task characteristics
- Explicit recommendations in decomposition prompt
- Tool selection scoring prioritizes Python for counting
- Models learn to choose correct tool

## Future Enhancements

1. **Proactive Model Download**: Auto-download on first startup if `model: "auto"`
2. **Performance Benchmarks**: Track inference speed per model
3. **Cost Tracking**: Monitor compute usage
4. **Model Profiles**: User-defined custom model configurations
5. **Remote Models**: Support for API-based models (OpenAI, Anthropic)

## Files Changed/Created

### New Files
- `agent/model_config.py` - Model profiles and selection logic
- `agent/resource_detector.py` - Hardware detection
- `show_model_recommendation.py` - CLI tool for recommendations
- `manage-models.sh` - Unified model management (replaces 2 scripts)

### Modified Files
- `main.py` - Auto model selection on startup
- `config.yaml` - Model selection strategy and force_python_counting
- `agent/neuron_agent.py` - Strategy advisor, compact storage, improved tool matching
- `tools/analysis_tools.py` - Enhanced tool description
- `docker-compose.yml` - VRAM_GB environment variable
- `.env` - VRAM_GB configuration
- `Dockerfile.agent` - Copy show_model_recommendation.py

### Deleted Files
- `fix-model-download.sh` (functionality merged into manage-models.sh)
- `select-model.sh` (functionality merged into manage-models.sh)

## Testing

```bash
# Test resource detection
./manage-models.sh recommend

# Test model download
./manage-models.sh auto

# Test counting with strategy advisor
./start-agent.sh --once --instruction test_count_runs --text
```

Expected: Agent uses `executeDataAnalysis` tool with Python code for 100% accurate counting.

## Model Recommendations by System

| System | RAM | VRAM | Recommended Model | Notes |
|--------|-----|------|-------------------|-------|
| Raspberry Pi 4/5 | 4-8GB | None | qwen2.5:3b | Fast, use Python tools |
| Standard Laptop | 8-16GB | None | llama3.1:8b | 128K context, excellent |
| Gaming PC | 16-32GB | 8-12GB | qwen2.5:14b | Balanced performance |
| Workstation | 32GB+ | 16GB+ | mistral-small3.2:24b | High quality, better counting |
| High-end Server | 64GB+ | 24GB+ | qwen2.5:32b | Best quality |

**RTX 5090 System** (30GB RAM + 32GB VRAM): → **mistral-small3.2:24b** ✅
