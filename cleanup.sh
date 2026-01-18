#!/bin/bash
# Cleanup dead code and deprecated files

echo "=== Removing archive_deprecated folder ==="
rm -rf neural_engine/core/archive_deprecated/

echo "=== Removing docs archive ==="
rm -rf docs/archive/

echo "=== Removing tool_use_detector_neuron.py (dead code) ==="
rm -f neural_engine/core/tool_use_detector_neuron.py

echo "=== Checking remaining core files ==="
ls neural_engine/core/*.py | wc -l

echo "=== Done! ==="
