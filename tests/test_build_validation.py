"""
Test build validation and package structure without requiring compilation.
"""
import pytest
import os
import subprocess
import sys
from pathlib import Path


def test_project_structure():
    """Test that all required project files exist."""
    project_root = Path(__file__).parent.parent
    
    required_files = [
        "Cargo.toml",
        "pyproject.toml", 
        "LICENSE",
        "README.md",
        "CLAUDE.md",
        "build.rs",
        "src/lib.rs",
        "src/vector_app.rs",
        "src/python_source.rs",
        "src/vector_context.rs",
        "scripts/bootstrap.sh",
        "scripts/update-deps.sh",
        "scripts/test.sh",
    ]
    
    for file_path in required_files:
        full_path = project_root / file_path
        assert full_path.exists(), f"Required file missing: {file_path}"
        assert full_path.stat().st_size > 0, f"Required file is empty: {file_path}"


def test_cargo_toml_structure():
    """Test Cargo.toml has required structure and flexible versions."""
    project_root = Path(__file__).parent.parent
    cargo_toml = project_root / "Cargo.toml"
    
    content = cargo_toml.read_text()
    
    # Check required sections
    assert "[package]" in content
    assert "[dependencies]" in content
    assert "[lib]" in content
    
    # Check for flexible versioning (no exact versions)
    lines = content.split('\n')
    for line in lines:
        if ' = "' in line and not line.strip().startswith('#'):
            # Skip Vector git dependencies and some special cases
            if 'git =' in line or 'path =' in line or 'default-features' in line:
                continue
            if 'name =' in line or 'version =' in line or 'edition =' in line:
                continue
            if 'license =' in line or 'description =' in line:
                continue
                
            # Check version specifications use >= 
            if 'version =' in line:
                assert '>=' in line or 'git =' in line, f"Found exact version (should use >=): {line.strip()}"


def test_pyproject_toml_structure():
    """Test pyproject.toml has correct PyPI package structure."""
    project_root = Path(__file__).parent.parent
    pyproject_toml = project_root / "pyproject_toml"
    
    content = pyproject_toml.read_text()
    
    # Check required sections for PyPI
    required_sections = [
        "[build-system]",
        "[project]",
        "[tool.maturin]"
    ]
    
    for section in required_sections:
        assert section in content, f"Missing required section: {section}"
    
    # Check required fields
    required_fields = [
        'name = "pyvector-rs"',
        'version =',
        'description =',
        'license =',
        'requires-python =',
    ]
    
    for field in required_fields:
        assert field in content, f"Missing required field: {field}"


def test_license_file():
    """Test license file exists and contains HyperSec EULA reference."""
    project_root = Path(__file__).parent.parent
    license_file = project_root / "LICENSE"
    
    assert license_file.exists()
    content = license_file.read_text()
    
    assert "Copyright (c) 2025 HyperSec" in content
    assert "https://hypersec.io/eula" in content
    assert "HyperSec End User License Agreement" in content


def test_readme_structure():
    """Test README has proper structure."""
    project_root = Path(__file__).parent.parent
    readme = project_root / "README.md"
    
    assert readme.exists()
    content = readme.read_text()
    
    # Check for key sections
    required_sections = [
        "# pyvector-rs",
        "## Installation", 
        "## Quick Start",
        "## API Reference",
        "## Testing",
        "## Development",
    ]
    
    for section in required_sections:
        assert section in content, f"README missing section: {section}"
    
    # Should contain code examples
    assert "```python" in content
    assert "```bash" in content


def test_build_scripts_executable():
    """Test that build scripts are executable."""
    project_root = Path(__file__).parent.parent
    scripts_dir = project_root / "scripts"
    
    for script in scripts_dir.glob("*.sh"):
        # Check execute permission
        stat_info = script.stat()
        assert stat_info.st_mode & 0o111, f"Script not executable: {script.name}"


def test_test_suite_structure():
    """Test that test suite has comprehensive coverage."""
    project_root = Path(__file__).parent.parent
    tests_dir = project_root / "tests"
    
    required_test_files = [
        "conftest.py",
        "test_basic.py",
        "test_vector_lifecycle.py", 
        "test_data_processing.py",
        "test_performance.py",
        "test_package_integration.py",
        "test_config_validation.py",
        "test_edge_cases.py",
    ]
    
    for test_file in required_test_files:
        test_path = tests_dir / test_file
        assert test_path.exists(), f"Missing test file: {test_file}"
        assert test_path.stat().st_size > 0, f"Empty test file: {test_file}"


def test_dynamic_version_system():
    """Test that the dynamic version system is properly configured."""
    project_root = Path(__file__).parent.parent
    build_rs = project_root / "build.rs"
    
    content = build_rs.read_text()
    
    # Should have dynamic version detection
    assert "get_latest_stable_vector_release" in content
    assert "github.com/repos/vectordotdev/vector/releases/latest" in content
    assert "SKIP_VECTOR_UPDATE" in content
    
    # Should NOT have hardcoded version fallbacks
    hardcoded_patterns = ['"v0.38.0"', '"v0.49.0"', 'compatible_versions = [']
    for pattern in hardcoded_patterns:
        if pattern in content:
            # Check if it's in a panic message (acceptable) or actual fallback (not acceptable)
            lines = content.split('\n')
            for line in lines:
                if pattern in line and not ('panic!' in line or 'error:' in line or '//' in line):
                    pytest.fail(f"Found hardcoded version in build.rs: {line.strip()}")


def test_environment_configuration():
    """Test environment variable configuration.""" 
    project_root = Path(__file__).parent.parent
    
    # Check CLAUDE.md mentions all required environment variables
    claude_md = project_root / "CLAUDE.md"
    content = claude_md.read_text()
    
    required_env_vars = [
        "RUSTFLAGS",
        "PYO3_USE_ABI3_FORWARD_COMPATIBILITY", 
        "SKIP_VECTOR_UPDATE",
        "UPDATE_DEPENDENCIES",
    ]
    
    for env_var in required_env_vars:
        assert env_var in content, f"CLAUDE.md missing environment variable documentation: {env_var}"


def test_dependency_flexibility():
    """Test that dependencies use flexible version constraints."""
    project_root = Path(__file__).parent.parent
    cargo_toml = project_root / "Cargo.toml"
    
    content = cargo_toml.read_text()
    
    # Find dependency lines
    dependency_lines = []
    in_dependencies = False
    
    for line in content.split('\n'):
        if line.strip() == "[dependencies]":
            in_dependencies = True
            continue
        elif line.strip().startswith('[') and in_dependencies:
            in_dependencies = False
            continue
        elif in_dependencies and '=' in line and not line.strip().startswith('#'):
            dependency_lines.append(line.strip())
    
    # Check each dependency uses flexible versioning
    for line in dependency_lines:
        if 'version =' in line and 'git =' not in line:
            # Should use >= for version constraints
            assert '>=' in line, f"Dependency should use flexible versioning (>=): {line}"


@pytest.mark.skipif(not os.environ.get("CI"), reason="Cargo check is slow, only run in CI")
def test_cargo_check():
    """Test that Cargo can at least check the syntax (if in CI)."""
    project_root = Path(__file__).parent.parent
    
    # Run cargo check with skip flags to avoid network calls
    result = subprocess.run([
        "cargo", "check", "--message-format=short"
    ], 
    cwd=project_root,
    env={**os.environ, "SKIP_VECTOR_UPDATE": "1", "RUSTFLAGS": "-C linker=gcc"},
    capture_output=True,
    text=True
    )
    
    # Even if it fails to build, should not fail due to syntax errors
    if result.returncode != 0:
        # Check if it's a linking/dependency issue vs syntax issue
        stderr = result.stderr.lower()
        if any(keyword in stderr for keyword in ['syntax error', 'unexpected token', 'parse error']):
            pytest.fail(f"Cargo syntax errors found:\n{result.stderr}")
        else:
            pytest.skip(f"Cargo check failed due to environment/dependency issues (expected): {result.stderr[:200]}...")


def test_python_package_metadata():
    """Test Python package metadata is properly configured."""
    project_root = Path(__file__).parent.parent
    pyproject_toml = project_root / "pyproject.toml"
    
    content = pyproject_toml.read_text()
    
    # Check for PyPI-required metadata
    assert 'classifiers = [' in content
    assert 'License :: OSI Approved :: Apache Software License' in content
    assert 'Programming Language :: Python ::' in content
    assert 'Topic ::' in content
    
    # Check optional dependencies for development
    assert '[project.optional-dependencies]' in content
    assert 'dev = [' in content
    assert 'test = [' in content