# Quick Reference: Model Management & Smart Counting

## 🚀 Quick Start

```bash
# 1. Auto-detect best model for your system
./manage-models.sh auto

# 2. Run agent with counting task
./start-agent.sh --once --instruction test_count_runs --text
```

## 📊 Model Management Commands

```bash
./manage-models.sh auto              # Auto-detect & setup
./manage-models.sh list              # Show downloaded models
./manage-models.sh use <model>       # Switch to specific model
./manage-models.sh recommend         # See recommendation
./manage-models.sh info              # Full system status
```

## ⚙️ Configuration

### Auto-Detection (Recommended)
```yaml
# config.yaml
ollama:
  model: "auto"  # Automatically selects best model
  force_python_counting: true  # Use Python for accurate counting
```

### Manual Selection
```yaml
ollama:
  model: "mistral-small3.2:24b"  # Specific model
```

### VRAM Override
```bash
# .env
VRAM_GB=32  # Override auto-detection
```

## 🎯 Model Recommendations

| Your System | Recommended Model |
|-------------|-------------------|
| 4-8GB RAM | `qwen2.5:3b` |
| 8-16GB RAM | `llama3.1:8b` |
| 16-32GB RAM | `qwen2.5:14b` |
| 32GB+ RAM + 16GB+ GPU | `mistral-small3.2:24b` |
| 64GB+ RAM + 24GB+ GPU | `qwen2.5:32b` |

## 🔧 What Was Fixed

### Problem 1: Counting Inaccuracy
**Before**: AI counted 2 runs when there were actually 8
**After**: Strategy advisor forces Python execution → 100% accurate

### Problem 2: Context Overflow  
**Before**: 57 activities × ~2KB polylines = ~114KB context
**After**: 57 activities × 6 fields = ~4KB (27x smaller)

### Problem 3: Manual Model Selection
**Before**: Edit config.yaml, check resources manually, download model
**After**: `./manage-models.sh auto` does everything

## 💡 Key Features

✅ **Automatic resource detection** (RAM/VRAM)
✅ **Compact context storage** (removes polylines)
✅ **Strategy advisor** (guides tool selection)
✅ **Python execution for counting** (100% reliable)
✅ **Unified model management** (one script, all operations)
✅ **Smart tool selection** (executeDataAnalysis for counting)

## 📝 Example: Counting Activities

```bash
# Ask: "How many running activities in September 2024?"

# Agent will:
1. Detect counting task
2. Recommend Python tool via strategy advisor
3. Convert date to timestamps
4. Fetch activities (compact format, 6 fields only)
5. Use executeDataAnalysis with Python:
   result = len([x for x in data['neuron_0_2']['activities'] 
                 if 'Run' in x.get('sport_type', '')])
6. Return accurate count: 8 activities ✅
```

## 🔍 Troubleshooting

### Model not found
```bash
# Download it
./manage-models.sh download mistral-small3.2:24b
```

### VRAM not detected
```bash
# Add to .env
echo "VRAM_GB=32" >> .env
```

### Wrong model selected
```bash
# Override with specific model
./manage-models.sh use llama3.1:8b
```

### AI still miscounting
```bash
# Ensure force_python_counting is enabled in config.yaml
ollama:
  force_python_counting: true
```

## 📚 More Info

- Full details: `MODEL_MANAGEMENT_SUMMARY.md`
- Model profiles: `agent/model_config.py`
- Resource detection: `agent/resource_detector.py`
- Strategy advisor: `agent/neuron_agent.py` (line 690+)

## 🎨 System Architecture

```
User Request
    ↓
Strategy Advisor (detects counting task)
    ↓
Decompose Goal → Neurons
    ↓
Neuron 1: Convert dates (getDateRangeTimestamps)
    ↓
Neuron 2: Fetch activities (getMyActivities)
    ↓  → Compact Storage (6 fields, no polylines)
    ↓
Neuron 3: Count with Python (executeDataAnalysis)
    ↓  → result = len([x for x in data['activities'] if 'Run' in x['sport_type']])
    ↓
Format & Return → 100% accurate count ✅
```

## 🌟 Why This Approach?

1. **Small models (3B-8B)**: Cannot count reliably → Use Python
2. **Large models (32B+)**: Reasoning can cause errors → Use Python  
3. **Python execution**: Simple, fast, 100% reliable
4. **Compact context**: 27x smaller → Works on Raspberry Pi
5. **Auto-detection**: Zero configuration for end users

**Result**: Same agent code works on Raspberry Pi AND high-end workstations! 🚀
