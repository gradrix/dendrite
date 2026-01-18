#!/usr/bin/env python3
"""
Dendrite Neural Engine - Main Entry Point

Usage:
    python main.py --goal "What is 2+2?"
    python main.py --interactive
    python main.py --server
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from neural_engine.v2.cli import main

if __name__ == "__main__":
    main()
