#!/bin/bash
# Git LFS Setup for Vector Build Caching

set -e

echo "[INFO] Setting up Git LFS for Vector build caching..."

# Check if git lfs is installed
if ! command -v git-lfs >/dev/null 2>&1; then
    echo "[ERROR] Git LFS not installed. Please install it first:"
    echo "  Ubuntu/Debian: sudo apt-get install git-lfs"
    echo "  RHEL/Fedora: sudo dnf install git-lfs"
    echo "  macOS: brew install git-lfs"
    exit 1
fi

# Initialize LFS in repository
echo "[INFO] Initializing Git LFS..."
git lfs install

# Track build cache files
echo "[INFO] Setting up LFS tracking for build caches..."
git lfs track ".tmp/build-cache-*.tar.gz"
git lfs track "target/wheels/*.whl"
git lfs track ".tmp/build_vector_*.log"

# Track large binary dependencies
git lfs track "**/*.so"
git lfs track "**/*.dylib" 
git lfs track "**/*.a"

# Check LFS status
echo "[INFO] Current LFS tracking:"
git lfs track

# Create initial cache directory structure
mkdir -p .tmp/lfs-cache
mkdir -p target/wheels

echo "[INFO] Git LFS setup completed!"
echo ""
echo "Next steps:"
echo "  1. Run: git add .gitattributes"
echo "  2. Run: git commit -m 'Add Git LFS configuration for build caching'"
echo "  3. Enable caching: export PYVECTOR_USE_CACHE=true"
echo "  4. Run build: ./smart-build"