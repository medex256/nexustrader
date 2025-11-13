#!/usr/bin/env python3
"""
Quick test of LLM with OpenAI
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.llm import invoke_llm

print("="*80)
print("TESTING LLM WITH OPENAI")
print("="*80)
print()

# Simple test
print("[1] Testing basic LLM call...")
response = invoke_llm("Explain in 2 sentences why NVIDIA stock has grown so much in 2024.")

print(f"\nResponse:\n{response}")
print()

print("="*80)
print("✅ LLM TEST COMPLETE")
print("="*80)
