#!/bin/bash
# CI/CD Build Script with Smart Vector Auto-Update
# This script is designed for unmonitored CI/CD that automatically
# updates to new Vector versions when they become available

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "🤖 Starting CI/CD build with smart Vector version management..."
echo "📅 Build started at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Function to report build status (customize for your CI system)
report_status() {
    local status="$1"
    local message="$2"
    local version="${3:-unknown}"
    
    echo "📊 BUILD_STATUS: $status"
    echo "📋 MESSAGE: $message"
    echo "🏷️  VECTOR_VERSION: $version"
    
    # For GitHub Actions
    if [ -n "$GITHUB_ACTIONS" ]; then
        echo "::notice title=Build Status::$message (Vector $version)"
        echo "vector_version=$version" >> $GITHUB_OUTPUT
        echo "build_status=$status" >> $GITHUB_OUTPUT
    fi
    
    # For GitLab CI
    if [ -n "$GITLAB_CI" ]; then
        echo "VECTOR_VERSION=$version" >> build.env
        echo "BUILD_STATUS=$status" >> build.env
    fi
}

# Function to check if we should force a version update
should_force_update() {
    # Force update if:
    # 1. No previous build info exists
    # 2. Previous build failed
    # 3. BUILD_FORCE_UPDATE environment variable is set
    
    if [ -n "$BUILD_FORCE_UPDATE" ]; then
        echo "🔄 Force update requested via BUILD_FORCE_UPDATE"
        return 0
    fi
    
    if [ ! -f ".vector-build-info" ]; then
        echo "📄 No previous build info - first time build"
        return 0
    fi
    
    if ! grep -q "BUILD_SUCCESS=true" ".vector-build-info"; then
        echo "⚠️  Previous build failed - forcing version check"
        return 0
    fi
    
    # Check if build info is older than 7 days (optional freshness check)
    if [ -n "$BUILD_CHECK_FRESHNESS" ]; then
        local build_date=$(grep "BUILD_DATE=" ".vector-build-info" | cut -d'=' -f2)
        if [ -n "$build_date" ]; then
            local build_timestamp=$(date -d "$build_date" +%s 2>/dev/null || echo "0")
            local current_timestamp=$(date +%s)
            local age_days=$(( (current_timestamp - build_timestamp) / 86400 ))
            
            if [ "$age_days" -gt 7 ]; then
                echo "🗓️  Build info is $age_days days old - checking for updates"
                return 0
            fi
        fi
    fi
    
    return 1
}

# Function to validate build environment
check_build_environment() {
    echo "🔍 Checking build environment..."
    
    # Check required tools
    for tool in git curl uv cargo; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            report_status "FAILED" "Missing required tool: $tool" "unknown"
            exit 1
        fi
    done
    
    # Check network connectivity
    if ! curl -s --connect-timeout 5 https://github.com >/dev/null; then
        report_status "FAILED" "No network connectivity to GitHub" "unknown"
        exit 1
    fi
    
    echo "✅ Build environment validated"
}

# Main CI build function
main() {
    check_build_environment
    
    # Check if we need to update Vector version
    if should_force_update; then
        echo "🚀 Running smart build with Vector version detection..."
        
        # Remove old build info to force fresh detection
        rm -f .vector-build-info
        
        # Run smart build script
        if bash "$SCRIPT_DIR/smart-build.sh"; then
            # Extract version info from build results
            local vector_version="unknown"
            if [ -f ".vector-build-info" ]; then
                vector_version=$(grep "VECTOR_VERSION=" ".vector-build-info" | cut -d'=' -f2)
            fi
            
            report_status "SUCCESS" "Build completed successfully with auto-version detection" "$vector_version"
            
            # Run tests if requested
            if [ -n "$RUN_TESTS" ]; then
                echo "🧪 Running test suite..."
                if uv run pytest tests/ -v; then
                    echo "✅ All tests passed"
                else
                    report_status "WARNING" "Build succeeded but tests failed" "$vector_version"
                    exit 1
                fi
            fi
            
        else
            report_status "FAILED" "Smart build failed - all Vector versions incompatible" "unknown"
            exit 1
        fi
        
    else
        echo "📋 Using cached Vector version information..."
        
        # Extract cached version
        local cached_version=$(grep "VECTOR_VERSION=" ".vector-build-info" | cut -d'=' -f2 2>/dev/null || echo "unknown")
        
        # Simple build without version detection
        echo "🔨 Building with cached Vector $cached_version..."
        
        if env SKIP_VECTOR_UPDATE=1 RUSTFLAGS="-C linker=gcc" PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 \
           uv run maturin develop; then
            
            report_status "SUCCESS" "Build completed with cached version" "$cached_version"
            
            # Run tests if requested  
            if [ -n "$RUN_TESTS" ]; then
                echo "🧪 Running test suite..."
                if uv run pytest tests/ -v; then
                    echo "✅ All tests passed"
                else
                    report_status "WARNING" "Build succeeded but tests failed" "$cached_version"
                    exit 1
                fi
            fi
            
        else
            echo "❌ Cached version build failed - forcing version update..."
            # Recursive call with force update
            BUILD_FORCE_UPDATE=1 exec "$0"
        fi
    fi
    
    echo "🎉 CI/CD build completed successfully!"
}

# Handle cleanup on exit
cleanup() {
    echo "🧹 Cleaning up temporary files..."
    # Add any cleanup logic here
}

trap cleanup EXIT

# Run main function
main "$@"