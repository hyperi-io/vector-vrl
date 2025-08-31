"""
Test Vector application lifecycle management.
"""
import pytest
import pyvector
import textwrap
import json
import asyncio


@pytest.mark.asyncio
async def test_vector_creation():
    """Test Vector instance creation with valid config."""
    config = """
    [sources.python]
    type = "python"
    
    [sinks.console]
    type = "console"
    inputs = ["python"]
    encoding.codec = "json"
    """
    
    vector = pyvector.Vector(textwrap.dedent(config))
    assert vector is not None


@pytest.mark.asyncio
async def test_vector_start_stop():
    """Test Vector start and stop operations."""
    config = """
    [sources.python]
    type = "python"
    
    [sinks.console]
    type = "console"
    inputs = ["python"]
    encoding.codec = "json"
    """
    
    vector = pyvector.Vector(textwrap.dedent(config))
    
    # Start Vector
    await vector.start()
    
    # Stop Vector
    await vector.stop()


@pytest.mark.asyncio
async def test_vector_restart():
    """Test Vector restart capabilities."""
    config = """
    [sources.python]
    type = "python"
    
    [sinks.console]
    type = "console"
    inputs = ["python"]
    encoding.codec = "json"
    """
    
    vector = pyvector.Vector(textwrap.dedent(config))
    
    # First lifecycle
    await vector.start()
    await vector.stop()
    
    # Second lifecycle
    await vector.start()
    await vector.stop()


@pytest.mark.asyncio
async def test_concurrent_vectors():
    """Test multiple Vector instances running concurrently."""
    config_template = """
    [sources.python]
    type = "python"
    
    [sinks.console]
    type = "console"
    inputs = ["python"]
    encoding.codec = "json"
    """
    
    vectors = []
    for i in range(3):
        vector = pyvector.Vector(textwrap.dedent(config_template))
        vectors.append(vector)
    
    # Start all vectors concurrently
    await asyncio.gather(*[v.start() for v in vectors])
    
    # Send data to each
    tasks = []
    for i, vector in enumerate(vectors):
        data = json.dumps({"vector_id": i, "message": f"hello from vector {i}"}).encode()
        tasks.append(vector.send("python", data))
    
    await asyncio.gather(*tasks)
    
    # Stop all vectors
    await asyncio.gather(*[v.stop() for v in vectors])


@pytest.mark.asyncio
async def test_vector_error_handling():
    """Test Vector error handling with invalid configurations."""
    
    # Test with invalid source type
    invalid_config = """
    [sources.python]
    type = "nonexistent_source"
    """
    
    with pytest.raises(Exception):
        vector = pyvector.Vector(textwrap.dedent(invalid_config))
        await vector.start()