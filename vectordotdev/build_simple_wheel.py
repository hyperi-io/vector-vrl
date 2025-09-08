#!/usr/bin/env python3
"""
Simple wheel builder that creates a proper Python wheel using setuptools.
Focuses on getting a working wheel that passes twine validation.
"""

import os
import subprocess
import sys
from pathlib import Path


def build_simple_wheel():
    """Build wheel using setuptools directly - no custom ZIP handling"""
    
    print("🏗️ Building Simple Python Wheel")
    print("=" * 40)
    
    # Check we have the bundled extension
    bindings_so = Path("src/vectordotdev/_bindings/vector_bindings.cpython-313-x86_64-linux-gnu.so")
    if not bindings_so.exists():
        print("❌ Bundled vector-bindings extension not found")
        return False
    
    print("✅ Bundled extension found")
    
    # Clean dist
    import shutil
    dist_dir = Path("dist")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir()
    
    try:
        # Use pip to install build tools locally
        print("📦 Installing build tools...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "build"], 
                      check=False, capture_output=True)
        
        # Build using standard Python build module
        print("🔧 Building wheel...")
        result = subprocess.run([
            sys.executable, "-m", "build", "--wheel", "--outdir", "dist/"
        ], check=True, capture_output=True, text=True)
        
        print("✅ Build successful!")
        
        # Verify wheel
        wheels = list(dist_dir.glob("*.whl"))
        if wheels:
            wheel = wheels[0]
            size_mb = wheel.stat().st_size / (1024 * 1024)
            print(f"📦 Created: {wheel.name} ({size_mb:.1f} MB)")
            
            # Test wheel format with Python zipfile
            import zipfile
            try:
                with zipfile.ZipFile(wheel, 'r') as zf:
                    files = zf.namelist()
                    print(f"✅ Valid ZIP wheel with {len(files)} files")
                    
                    # Test twine check locally
                    print("🔍 Testing twine check...")
                    twine_result = subprocess.run([
                        sys.executable, "-m", "pip", "install", "--user", "twine"
                    ], capture_output=True)
                    
                    if twine_result.returncode == 0:
                        check_result = subprocess.run([
                            sys.executable, "-m", "twine", "check", str(wheel)
                        ], capture_output=True, text=True)
                        
                        if check_result.returncode == 0:
                            print("✅ twine check passed!")
                            print(f"Output: {check_result.stdout}")
                        else:
                            print(f"❌ twine check failed: {check_result.stderr}")
                            return False
                    
                    return True
                    
            except zipfile.BadZipFile:
                print("❌ Invalid ZIP format")
                return False
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


if __name__ == '__main__':
    # Change to vectordotdev directory
    os.chdir(Path(__file__).parent)
    
    success = build_simple_wheel()
    if success:
        print("\n🎉 Ready for JFrog deployment!")
    else:
        print("\n❌ Wheel build failed")
    
    sys.exit(0 if success else 1)