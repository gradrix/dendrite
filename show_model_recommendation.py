#!/usr/bin/env python3
"""
Model selection helper - shows recommended model based on system resources.
"""

import sys
sys.path.insert(0, '/app')

from agent.resource_detector import detect_system_resources
from agent.model_config import MODEL_PROFILES, select_best_model, list_available_models

def main():
    print("🔍 Detecting system resources...")
    resources = detect_system_resources()
    print()

    print("📊 Your System:")
    print(f"   RAM: {resources['ram_gb']:.1f} GB")
    if resources['vram_gb']:
        print(f"   VRAM: {resources['vram_gb']:.1f} GB (GPU detected)")
    else:
        print("   VRAM: None (CPU only)")
    print(f"   CPU Cores: {resources['cpu_cores']}")
    print()

    print("=" * 60)
    print("🎯 RECOMMENDED MODEL")
    print("=" * 60)
    best = select_best_model(
        available_ram_gb=resources['ram_gb'],
        available_vram_gb=resources['vram_gb'],
        prefer_fast=False,
        prefer_reasoning=True
    )
    print()
    print(f"✅ Best match: {best.name}")
    print(f"   Size: {best.params_billion}B parameters")
    print(f"   RAM required: {best.min_ram_gb} GB (min), {best.recommended_ram_gb} GB (recommended)")
    if best.min_vram_gb:
        print(f"   VRAM required: {best.min_vram_gb} GB")
    print(f"   Context window: {best.context_window:,} tokens")
    print()
    print("📋 Capabilities:")
    print(f"   Reasoning: {'✅' if best.good_at_reasoning else '❌'}")
    print(f"   Counting: {'✅ (reliable)' if best.good_at_counting else '❌ (use Python tool)'}")
    print(f"   JSON: {'✅' if best.good_at_json else '❌'}")
    print(f"   Code: {'✅' if best.good_at_code else '❌'}")
    print(f"   Fast: {'✅' if best.fast_inference else '❌'}")
    print()
    print(f"💡 Notes: {best.notes}")
    print()

    print("=" * 60)
    print("📦 ALL AVAILABLE MODELS (for your RAM)")
    print("=" * 60)
    available = list_available_models(min_ram_gb=resources['ram_gb'])
    available.sort(key=lambda x: x.params_billion)
    print()
    for model in available:
        print(f"• {model.name} ({model.size})")
        print(f"  RAM: {model.min_ram_gb} GB min, {model.recommended_ram_gb} GB recommended")
        r = "✅" if model.good_at_reasoning else "❌"
        c = "✅" if model.good_at_counting else "❌"
        f = "✅" if model.fast_inference else "❌"
        print(f"  Reasoning: {r} | Counting: {c} | Fast: {f}")
        print(f"  {model.notes}")
        print()

    print("=" * 60)
    print("⚙️  TO USE RECOMMENDED MODEL")
    print("=" * 60)
    print()
    print("Edit config.yaml and set:")
    print("  ollama:")
    print(f'    model: "{best.name}"')
    print()
    print("Or use auto-detection:")
    print("  ollama:")
    print('    model: "auto"')
    print()

    print("=" * 60)
    print("📥 TO DOWNLOAD MODEL")
    print("=" * 60)
    print()
    print(f"Run: docker exec -it ollama ollama pull {best.name}")
    print()

if __name__ == "__main__":
    main()
