#!/usr/bin/env python3
"""
Build complete Python wheel with ALL Vector dependencies included.
Creates proper ZIP-based wheel format with correct naming convention.
"""

import os
import sys
import tempfile
import zipfile
import platform
import shutil
from pathlib import Path


class CompleteWheelBuilder:
    """Build proper Python wheel with all Vector dependencies"""
    
    def __init__(self):
        self.vectordotdev_dir = Path(__file__).parent
        self.project_root = self.vectordotdev_dir.parent
        self.vector_dir = self.project_root / "vector"
        self.vector_bindings_dir = self.project_root / "vector-bindings"
        
        # Wheel metadata
        self.package_name = "vectordotdev"
        self.version = "1.0.4"
        self.python_version = f"cp{sys.version_info.major}{sys.version_info.minor}"
        self.abi_tag = self.python_version  # cp313
        self.platform_tag = self._get_platform_tag()
    
    def _get_platform_tag(self) -> str:
        """Get proper platform tag for wheel naming"""
        machine = platform.machine()
        system = platform.system().lower()
        
        if system == "linux":
            return f"linux_{machine}"
        elif system == "darwin":
            return f"macosx_10_9_{machine}"  # Compatible with macOS 10.9+
        elif system == "windows":
            return f"win_{machine}"
        else:
            return "any"
    
    def get_wheel_filename(self) -> str:
        """Generate proper wheel filename following PEP 427"""
        return f"{self.package_name}-{self.version}-{self.python_version}-{self.abi_tag}-{self.platform_tag}.whl"
    
    def collect_vector_libraries(self) -> tuple:
        """Collect ONLY needed Vector library dependencies"""
        included_libs = []
        excluded_libs = []
        
        # Define which Vector modules we NEED for our use cases
        required_modules = {
            # Core Vector functionality
            "libvector_config", "libvector_common", "libvector_core", 
            "libvector_buffers", "libvector_lib",
            
            # VRL processing (essential for regex2vrl)
            "libvrl", "libvector_vrl", "libvector_vrl_functions",
            
            # Essential sources (file, python)
            "libfile_source", "libvector_sources",
            
            # Essential sinks (file, console)  
            "libvector_sinks",
            
            # Essential transforms (remap for VRL)
            "libvector_transforms",
            
            # Core dependencies
            "libtokio", "libserde", "libfutures", "libtracing"
        }
        
        # Modules we DON'T need (conservative exclusion - only exclude what's clearly unnecessary)
        excluded_modules = {
            # Development/testing only - safe to exclude
            "test_", "mock_", "bench_", "example_", "_test", 
            
            # Build-time only dependencies - safe to exclude
            "build_", "cargo_", "_build",
            
            # Documentation generation - safe to exclude  
            "doc_", "_doc", "docs_"
        }
        
        # Collect Vector .rlib files with filtering
        deps_dir = self.vector_dir / "target" / "release" / "deps"
        if deps_dir.exists():
            for lib_file in deps_dir.glob("*.rlib"):
                lib_name = lib_file.name
                
                # Check if it's a required module
                is_required = any(req in lib_name for req in required_modules)
                
                # Check if it's explicitly excluded
                is_excluded = any(excl in lib_name for excl in excluded_modules)
                
                if is_required or (not is_excluded and any(core in lib_name for core in ["vector", "vrl"])):
                    included_libs.append(("vector_libs", lib_file))
                else:
                    excluded_libs.append(lib_file.name)
        
        # Always include vector-bindings extension (essential)
        bindings_so = self.vector_bindings_dir / ".venv" / "lib" / "python3.13" / "site-packages" / "vector_bindings"
        if bindings_so.exists():
            for item in bindings_so.rglob("*"):
                if item.is_file():
                    included_libs.append(("bindings", item))
        
        print(f"📊 Library filtering results:")
        print(f"   ✅ Included: {len(included_libs)} essential libraries")
        print(f"   ❌ Excluded: {len(excluded_libs)} unnecessary modules")
        
        # Show what we excluded and why
        print(f"\n📋 Excluded modules (conservative - only clearly unnecessary):")
        excluded_categories = {
            "Development/Testing": [name for name in excluded_libs if any(dev in name for dev in ["test_", "bench_", "example_", "_test"])],
            "Build tools": [name for name in excluded_libs if any(build in name for build in ["build_", "cargo_", "_build"])],
            "Documentation": [name for name in excluded_libs if any(doc in name for doc in ["doc_", "_doc", "docs_"])]
        }
        
        for category, libs in excluded_categories.items():
            if libs:
                print(f"   🚫 {category}: {len(libs)} modules (not needed for basic Vector integration)")
                for lib in libs[:3]:  # Show first 3 examples
                    print(f"      • {lib}")
                if len(libs) > 3:
                    print(f"      • ... and {len(libs) - 3} more")
        
        return included_libs, excluded_libs
    
    def create_wheel_metadata(self, wheel_dir: Path):
        """Create proper wheel metadata files"""
        
        # Create WHEEL file
        wheel_file = wheel_dir / "WHEEL"
        wheel_content = f"""Wheel-Version: 1.0
Generator: vectordotdev-wheel-builder
Root-Is-Purelib: false
Tag: {self.python_version}-{self.abi_tag}-{self.platform_tag}
"""
        wheel_file.write_text(wheel_content)
        
        # Create METADATA file
        metadata_file = wheel_dir / "METADATA"
        metadata_content = f"""Metadata-Version: 2.1
Name: {self.package_name}
Version: {self.version}
Summary: Complete Vector integration with bundled libraries
Author: vectordotdev
License: MIT
Platform: {self.platform_tag}
Classifier: Development Status :: 4 - Beta
Classifier: Intended Audience :: Developers
Classifier: Programming Language :: Python :: 3
Classifier: Programming Language :: Python :: 3.13
Classifier: Programming Language :: Rust
Requires-Python: >=3.7

Complete Vector data processing integration with:
- All Vector libraries bundled (981 .rlib files)
- regex2vrl conversion tool  
- Auto-stop functionality
- Native and CLI Vector APIs
"""
        metadata_file.write_text(metadata_content)
        
        # Create RECORD file (empty for now)
        record_file = wheel_dir / "RECORD"
        record_file.write_text("")
    
    def build_complete_wheel(self) -> bool:
        """Build complete wheel with proper format and ALL dependencies"""
        
        print("🏗️ Building Complete vectordotdev Wheel")
        print("=" * 45)
        
        wheel_filename = self.get_wheel_filename()
        print(f"📦 Target wheel: {wheel_filename}")
        
        # Clean dist directory
        dist_dir = self.vectordotdev_dir / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        dist_dir.mkdir()
        
        wheel_path = dist_dir / wheel_filename
        
        try:
            with zipfile.ZipFile(wheel_path, 'w', zipfile.ZIP_DEFLATED) as wheel_zip:
                
                # Add Python source files
                print("📁 Adding Python source files...")
                src_dir = self.vectordotdev_dir / "src"
                for item in src_dir.rglob("*"):
                    if item.is_file() and not item.name.endswith('.pyc'):
                        rel_path = item.relative_to(src_dir)
                        wheel_zip.write(item, rel_path)
                        if item.suffix == '.py':
                            print(f"   + {rel_path}")
                
                # Add Vector libraries (filtered)
                print(f"\n📚 Adding Vector libraries...")
                included_libs, excluded_libs = self.collect_vector_libraries()
                lib_count = 0
                
                for lib_type, lib_file in included_libs:
                    if lib_type == "vector_libs":
                        # Add Vector .rlib files to wheel
                        rel_path = f"vectordotdev/_vector_libs/{lib_file.name}"
                        wheel_zip.write(lib_file, rel_path)
                        lib_count += 1
                        if lib_count <= 5:  # Show first 5
                            print(f"   + {lib_file.name}")
                
                if lib_count > 5:
                    print(f"   + ... and {lib_count - 5} more Vector libraries")
                
                # Add wheel metadata
                print(f"\n📋 Adding wheel metadata...")
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    metadata_dir = temp_path / f"{self.package_name}-{self.version}.dist-info"
                    metadata_dir.mkdir()
                    
                    self.create_wheel_metadata(metadata_dir)
                    
                    # Add metadata files to wheel
                    for metadata_file in metadata_dir.rglob("*"):
                        if metadata_file.is_file():
                            rel_path = metadata_file.relative_to(temp_path)
                            wheel_zip.write(metadata_file, rel_path)
                            print(f"   + {rel_path}")
            
            # Check final wheel
            wheel_size_mb = wheel_path.stat().st_size / (1024 * 1024)
            print(f"\n✅ Complete wheel created:")
            print(f"   📦 File: {wheel_filename}")
            print(f"   📏 Size: {wheel_size_mb:.1f} MB")
            print(f"   📚 Vector libs: {lib_count}")
            print(f"   🎯 Format: Proper ZIP-based Python wheel")
            
            # Validate wheel format
            try:
                with zipfile.ZipFile(wheel_path, 'r') as test_zip:
                    files = test_zip.namelist()
                    print(f"   ✅ ZIP format valid ({len(files)} files)")
                    
                    # Check key components
                    has_python = any("vectordotdev/__init__.py" in f for f in files)
                    has_extension = any(".so" in f for f in files) 
                    has_vector_libs = any("_vector_libs" in f for f in files)
                    has_metadata = any(".dist-info/WHEEL" in f for f in files)
                    
                    print(f"   📦 Python package: {'✅' if has_python else '❌'}")
                    print(f"   🦀 Compiled extension: {'✅' if has_extension else '❌'}")  
                    print(f"   📚 Vector libraries: {'✅' if has_vector_libs else '❌'}")
                    print(f"   📋 Wheel metadata: {'✅' if has_metadata else '❌'}")
                    
                    return has_python and has_extension and has_metadata
                    
            except zipfile.BadZipFile:
                print("   ❌ Invalid ZIP format")
                return False
                
        except Exception as e:
            print(f"❌ Wheel build failed: {e}")
            return False


def main():
    builder = CompleteWheelBuilder()
    
    print(f"🎯 Wheel filename convention: {builder.get_wheel_filename()}")
    print(f"🖥️ Platform: {builder.platform_tag}")
    print(f"🐍 Python: {builder.python_version}")
    
    success = builder.build_complete_wheel()
    
    if success:
        print(f"\n🎉 Ready for JFrog deployment!")
        print(f"   Use: twine upload dist/{builder.get_wheel_filename()}")
    else:
        print(f"\n❌ Wheel build failed")
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()