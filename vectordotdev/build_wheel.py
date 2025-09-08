#!/usr/bin/env python3
"""
Build script for vectordotdev PyPI wheel.
Bundles vector-bindings compiled extension into self-contained wheel.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


class VectorDotDevWheelBuilder:
    """Build complete PyPI wheel with all dependencies bundled"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.vectordotdev_dir = Path(__file__).parent
        self.vector_bindings_dir = self.project_root / "vector-bindings"
        self.build_dir = self.project_root / "build"
    
    def ensure_dependencies_built(self):
        """Ensure all dependencies are built before wheel creation"""
        print("🔍 Checking build dependencies...")
        
        # Check if vector-bindings is built
        bindings_so = self.vector_bindings_dir / ".venv" / "lib" / "python3.13" / "site-packages" / "vector_bindings"
        
        if not bindings_so.exists():
            print("🔧 Building vector-bindings...")
            # Run the 3-stage build system to ensure everything is built
            result = subprocess.run([
                str(self.build_dir / "build"), "--verbose"
            ], cwd=self.project_root)
            
            if result.returncode != 0:
                raise RuntimeError("Failed to build dependencies")
        
        print("✅ Dependencies ready")
    
    def bundle_vector_bindings(self):
        """Copy vector-bindings extension into vectordotdev package"""
        print("📦 Bundling vector-bindings extension...")
        
        # Find the compiled extension
        bindings_pkg = self.vector_bindings_dir / ".venv" / "lib" / "python3.13" / "site-packages" / "vector_bindings"
        
        if not bindings_pkg.exists():
            raise RuntimeError(f"vector-bindings not found at {bindings_pkg}")
        
        # Create _bindings directory in vectordotdev
        bindings_dest = self.vectordotdev_dir / "src" / "vectordotdev" / "_bindings"
        bindings_dest.mkdir(parents=True, exist_ok=True)
        
        # Copy the entire vector_bindings package
        if bindings_dest.exists():
            shutil.rmtree(bindings_dest)
        
        shutil.copytree(bindings_pkg, bindings_dest)
        
        # Create __init__.py for the bundled extension
        init_file = bindings_dest / "__init__.py"
        init_file.write_text("""# Bundled vector-bindings extension
# This contains the compiled Rust extension with Vector integration

from .vector_bindings import *

# Expose the main API
__all__ = [
    'Vector', 'VectorCliPy', 'vrl_check', 'vrl_functions', 
    'check_config_syntax_py', 'parse_cli_args_py'
]
""")
        
        print(f"✅ vector-bindings bundled to {bindings_dest}")
    
    def update_vectordotdev_imports(self):
        """Update vectordotdev/__init__.py to use bundled extension"""
        print("🔧 Updating vectordotdev imports...")
        
        init_file = self.vectordotdev_dir / "src" / "vectordotdev" / "__init__.py"
        
        # Update to import from bundled extension first
        new_content = '''"""
vectordotdev - Complete PyPI package with bundled Vector bindings.

This package includes the compiled vector-bindings extension and provides
a complete, self-contained Vector integration for Python.
"""

# Import from bundled vector-bindings extension
try:
    # Try bundled extension first (included in PyPI wheel)
    from ._bindings import (
        Vector, VectorCliPy, vrl_check, vrl_functions,
        check_config_syntax_py, parse_cli_args_py
    )
    _bindings_source = "bundled"
    _bindings_available = True
    
except ImportError:
    # Fallback to external vector-bindings if available
    try:
        import vector_bindings
        Vector = vector_bindings.Vector
        VectorCliPy = vector_bindings.VectorCliPy
        vrl_check = vector_bindings.vrl_check
        vrl_functions = vector_bindings.vrl_functions
        check_config_syntax_py = vector_bindings.check_config_syntax_py
        parse_cli_args_py = vector_bindings.parse_cli_args_py
        
        _bindings_source = "external"
        _bindings_available = True
        
    except ImportError as e:
        # No bindings available
        print(f"⚠️ Warning: vector bindings not available: {e}")
        _bindings_available = False
        _bindings_source = "none"
        
        # Stub implementations
        class Vector:
            def __init__(self, config): raise ImportError("Vector bindings not available")
        class VectorCliPy:
            def __init__(self, args): raise ImportError("Vector CLI bindings not available")
        def vrl_check(code): raise ImportError("VRL functions not available")
        def vrl_functions(): raise ImportError("VRL functions not available") 
        def check_config_syntax_py(config): raise ImportError("Config validation not available")
        def parse_cli_args_py(args): raise ImportError("CLI parsing not available")


# Version information
__version__ = "1.0.1"
__author__ = "vectordotdev"


def get_bindings_info():
    """Get information about available bindings"""
    return {
        "available": _bindings_available,
        "source": _bindings_source,
        "version": __version__,
        "bundled": _bindings_source == "bundled"
    }


# Re-export key components
__all__ = [
    "Vector",
    "VectorCliPy", 
    "vrl_check",
    "vrl_functions", 
    "check_config_syntax_py",
    "parse_cli_args_py",
    "get_bindings_info"
]
'''
        
        init_file.write_text(new_content)
        print("✅ vectordotdev imports updated for bundled extension")
    
    def build_wheel(self):
        """Build the complete PyPI wheel"""
        print("🏗️ Building vectordotdev PyPI wheel...")
        
        # Clean previous builds
        dist_dir = self.vectordotdev_dir / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        
        # Build wheel with setuptools
        result = subprocess.run([
            sys.executable, "-m", "build", "--wheel", "--outdir", "dist"
        ], cwd=self.vectordotdev_dir, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Wheel build failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False
        
        # Check wheel was created
        wheels = list(dist_dir.glob("*.whl"))
        if wheels:
            wheel_file = wheels[0]
            wheel_size = wheel_file.stat().st_size / (1024 * 1024)  # MB
            print(f"✅ PyPI wheel created: {wheel_file.name} ({wheel_size:.1f} MB)")
            
            # Show wheel contents
            self.inspect_wheel(wheel_file)
            return True
        else:
            print("❌ No wheel file generated")
            return False
    
    def inspect_wheel(self, wheel_file: Path):
        """Inspect wheel contents to verify completeness"""
        print(f"\n🔍 Wheel Contents Inspection:")
        
        try:
            import zipfile
            with zipfile.ZipFile(wheel_file, 'r') as zf:
                files = zf.namelist()
                
                # Check key components
                has_vectordotdev = any("vectordotdev/__init__.py" in f for f in files)
                has_regex2vrl = any("regex2vrl" in f for f in files)
                has_bindings = any("_bindings" in f and ".so" in f for f in files)
                has_tests = any("test" in f for f in files)
                
                print(f"   vectordotdev package: {'✅' if has_vectordotdev else '❌'}")
                print(f"   regex2vrl module: {'✅' if has_regex2vrl else '❌'}")  
                print(f"   Compiled bindings: {'✅' if has_bindings else '❌'}")
                print(f"   Tests excluded: {'✅' if not has_tests else '❌'}")
                print(f"   Total files: {len(files)}")
                
                # Show sample files
                print(f"\n   Sample contents:")
                for f in sorted(files)[:10]:
                    print(f"     {f}")
                if len(files) > 10:
                    print(f"     ... and {len(files) - 10} more files")
                    
        except Exception as e:
            print(f"   ❌ Inspection failed: {e}")
    
    def build_complete_wheel(self):
        """Build complete PyPI-ready wheel with all dependencies"""
        print("🎯 Building Complete vectordotdev PyPI Wheel")
        print("=" * 55)
        
        try:
            # Step 1: Ensure dependencies are built
            self.ensure_dependencies_built()
            
            # Step 2: Bundle vector-bindings extension  
            self.bundle_vector_bindings()
            
            # Step 3: Update imports for bundled extension
            self.update_vectordotdev_imports()
            
            # Step 4: Build the wheel
            success = self.build_wheel()
            
            if success:
                print("\n🎉 Complete PyPI wheel ready!")
                print("   - Self-contained with all Vector dependencies")
                print("   - Includes regex2vrl conversion tool") 
                print("   - Bundled vector-bindings extension")
                print("   - Ready for 'pip install vectordotdev'")
                return True
            else:
                print("\n❌ Wheel build failed")
                return False
                
        except Exception as e:
            print(f"❌ Build error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Build vectordotdev PyPI wheel')
    parser.add_argument('--inspect-only', action='store_true', help='Just inspect existing wheel')
    parser.add_argument('--clean', action='store_true', help='Clean build')
    
    args = parser.parse_args()
    
    builder = VectorDotDevWheelBuilder()
    
    if args.clean:
        # Clean all build artifacts
        for path in ["vectordotdev/dist", "vectordotdev/build", "vectordotdev/src/vectordotdev/_bindings"]:
            full_path = Path(path)
            if full_path.exists():
                shutil.rmtree(full_path)
                print(f"🧹 Cleaned {path}")
    
    if args.inspect_only:
        # Just inspect existing wheel
        wheels = list(Path("vectordotdev/dist").glob("*.whl"))
        if wheels:
            builder.inspect_wheel(wheels[0])
        else:
            print("❌ No wheel found to inspect")
        return
    
    # Build complete wheel
    success = builder.build_complete_wheel()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()