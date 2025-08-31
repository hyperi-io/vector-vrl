"""
Pytest configuration and shared fixtures for pyvector-rs tests.
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_json_data():
    """Provide sample JSON data for testing."""
    return [
        {"level": "info", "message": "Application started", "timestamp": "2024-01-01T12:00:00Z"},
        {"level": "warning", "message": "High memory usage", "timestamp": "2024-01-01T12:01:00Z", "memory_mb": 512},
        {"level": "error", "message": "Connection failed", "timestamp": "2024-01-01T12:02:00Z", "error_code": 500},
        {"level": "info", "message": "Retry successful", "timestamp": "2024-01-01T12:03:00Z"},
        {"level": "debug", "message": "Debug trace", "timestamp": "2024-01-01T12:04:00Z", "trace_id": "abc123"},
    ]


@pytest.fixture
def minimal_vector_config():
    """Provide minimal working Vector configuration."""
    return """
    [sources.python]
    type = "python"
    
    [sinks.console]
    type = "console"
    inputs = ["python"]
    encoding.codec = "json"
    """


@pytest.fixture
def file_sink_config(tmp_path):
    """Provide Vector config with file sink for testing."""
    output_file = tmp_path / "test_output.json"
    return f"""
    [sources.python]
    type = "python"
    
    [sinks.file]
    type = "file"
    inputs = ["python"]
    path = "{output_file}"
    encoding.codec = "json"
    """, output_file


@pytest.fixture
def performance_config(tmp_path):
    """Provide Vector config optimized for performance testing."""
    output_file = tmp_path / "performance.json"
    return f"""
    [sources.python]
    type = "python"
    
    [sinks.file]
    type = "file"
    inputs = ["python"]
    path = "{output_file}"
    encoding.codec = "json"
    
    # Performance optimizations
    [sinks.file.batch]
    max_events = 1000
    timeout_secs = 1
    """, output_file


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark certain tests."""
    for item in items:
        # Mark performance tests
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        
        # Mark slow tests
        if any(keyword in item.nodeid for keyword in ["throughput", "burst", "large"]):
            item.add_marker(pytest.mark.slow)
        
        # Mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment for each test."""
    # Any setup needed for each test
    yield
    # Any cleanup needed after each test