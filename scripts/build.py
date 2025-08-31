#!/usr/bin/env python3
"""
Build and test automation script for pyvector-rs
"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"→ {description}")
    print(f"  Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"✗ Failed: {description}")
        print(f"  Error: {result.stderr}")
        return False
    else:
        print(f"✓ Success: {description}")
        if result.stdout.strip():
            print(f"  Output: {result.stdout.strip()}")
        return True

def main():
    """Main build and test pipeline"""
    os.chdir(Path(__file__).parent.parent)
    
    steps = [
        ("cargo fmt --check", "Check Rust formatting"),
        ("cargo clippy -- -D warnings", "Run Rust linting"),
        ("maturin develop", "Build and install Python extension"),
        ("pytest tests/ -v", "Run Python tests"),
        ("python example.py", "Run example script"),
    ]
    
    print("🚀 Starting pyvector-rs build and test pipeline")
    print("=" * 50)
    
    failed_steps = []
    
    for cmd, description in steps:
        if not run_command(cmd, description):
            failed_steps.append(description)
        print()
    
    print("=" * 50)
    if failed_steps:
        print("❌ Build pipeline failed!")
        print("Failed steps:")
        for step in failed_steps:
            print(f"  - {step}")
        sys.exit(1)
    else:
        print("✅ All steps completed successfully!")

if __name__ == "__main__":
    main()