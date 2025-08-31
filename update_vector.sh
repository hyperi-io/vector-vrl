#!/bin/bash

# Script to update Vector version and check available features

# Get latest version
LATEST_VERSION=$(curl -s -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/repos/vectordotdev/vector/releases/latest | \
    grep '"tag_name"' | cut -d'"' -f4)

echo "Latest Vector version: $LATEST_VERSION"

# Create a temporary Cargo.toml to check available features
cat > /tmp/check_vector_features.toml << EOF
[package]
name = "check-vector"
version = "0.1.0"
edition = "2021"

[dependencies]
vector = { git = "https://github.com/vectordotdev/vector.git", tag = "$LATEST_VERSION", default-features = false }
EOF

# Check what features are available
echo "Checking available features..."
cd /tmp
cargo metadata --manifest-path check_vector_features.toml --format-version 1 2>/dev/null | \
    jq -r '.packages[] | select(.name == "vector") | .features | keys[]' | \
    grep -E "^(transforms-|sinks-)" | sort

# Cleanup
rm -f /tmp/check_vector_features.toml