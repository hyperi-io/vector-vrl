#!/usr/bin/env python3
"""
Simple vectordotdev wheel builder - no complex dependencies.
Creates PyPI-ready wheel with bundled vector-bindings.
"""

import subprocess
import sys
from pathlib import Path


def build_vectordotdev_wheel():
    """Build vectordotdev wheel using setuptools directly"""
    
    print("🏗️ Building vectordotdev PyPI wheel...")
    print("=" * 40)
    
    # Check package structure
    src_dir = Path("src")
    if not src_dir.exists():
        print("❌ src/ directory not found")
        return False
    
    # Check bundled bindings
    bindings_dir = src_dir / "vectordotdev" / "_bindings"
    if not bindings_dir.exists():
        print("❌ Bundled vector-bindings not found")
        return False
    
    # List bundled contents
    print("📦 Package contents:")
    for item in (src_dir / "vectordotdev").rglob("*"):
        if item.is_file():
            print(f"   {item}")
    
    # Build using setuptools (no external dependencies)
    try:
        # Install build if not available
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "build"], 
                      check=True, capture_output=True)
        
        # Build wheel
        result = subprocess.run([
            sys.executable, "-m", "build", "--wheel", "--outdir", "dist"
        ], check=True, capture_output=True, text=True)
        
        print("✅ Wheel build successful!")
        
        # Check results
        dist_dir = Path("dist")
        wheels = list(dist_dir.glob("*.whl"))
        
        if wheels:
            wheel = wheels[0]
            size_mb = wheel.stat().st_size / (1024 * 1024)
            print(f"📦 Created wheel: {wheel.name} ({size_mb:.1f} MB)")
            return True
        else:
            print("❌ No wheel created")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Build error: {e}")
        return False


if __name__ == '__main__':
    import os
    os.chdir(Path(__file__).parent)  # Run from vectordotdev directory
    
    success = build_vectordotdev_wheel()
    sys.exit(0 if success else 1)