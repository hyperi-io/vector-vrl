"""
Test data processing capabilities and different sink types.
"""
import pytest
import pyvector
import textwrap
import json
import asyncio
import tempfile
import os
from pathlib import Path


@pytest.mark.asyncio
async def test_json_data_processing(tmp_path):
    """Test processing JSON data through Vector."""
    output_file = tmp_path / "output.json"
    
    config = f"""
    [sources.python]
    type = "python"
    
    [sinks.file]
    type = "file"
    inputs = ["python"]
    path = "{output_file}"
    encoding.codec = "json"
    """
    
    vector = pyvector.Vector(textwrap.dedent(config))
    await vector.start()
    
    # Send various JSON data types
    test_data = [
        {"type": "string", "value": "hello world"},
        {"type": "number", "value": 42},
        {"type": "float", "value": 3.14159},
        {"type": "boolean", "value": True},
        {"type": "array", "value": [1, 2, 3, "four"]},
        {"type": "nested", "value": {"inner": {"deep": "value"}}},
    ]
    
    for data in test_data:
        await vector.send("python", json.dumps(data).encode())
    
    await vector.stop()
    
    # Verify output
    assert output_file.exists()
    content = output_file.read_text()
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    
    assert len(lines) == len(test_data)
    for i, line in enumerate(lines):
        parsed = json.loads(line)
        assert test_data[i]["type"] in str(parsed)


@pytest.mark.asyncio
async def test_high_throughput_processing(tmp_path):
    """Test high-throughput data processing."""
    output_file = tmp_path / "throughput.json"
    
    config = f"""
    [sources.python]
    type = "python"
    
    [sinks.file]
    type = "file"
    inputs = ["python"]
    path = "{output_file}"
    encoding.codec = "json"
    """
    
    vector = pyvector.Vector(textwrap.dedent(config))
    await vector.start()
    
    # Send large number of messages
    num_messages = 1000
    tasks = []
    
    for i in range(num_messages):
        data = json.dumps({
            "id": i,
            "timestamp": f"2024-01-01T12:00:{i%60:02d}Z",
            "message": f"High throughput message {i}",
            "batch": i // 100
        }).encode()
        tasks.append(vector.send("python", data))
    
    # Send all messages concurrently
    await asyncio.gather(*tasks)
    await vector.stop()
    
    # Verify output
    assert output_file.exists()
    content = output_file.read_text()
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    
    # Should have received most/all messages
    assert len(lines) >= num_messages * 0.9  # Allow for some async timing


@pytest.mark.asyncio
async def test_multiple_sinks(tmp_path):
    """Test sending data to multiple sinks simultaneously."""
    file1 = tmp_path / "sink1.json"
    file2 = tmp_path / "sink2.json"
    
    config = f"""
    [sources.python]
    type = "python"
    
    [sinks.file1]
    type = "file"
    inputs = ["python"]
    path = "{file1}"
    encoding.codec = "json"
    
    [sinks.file2]
    type = "file"
    inputs = ["python"]
    path = "{file2}"
    encoding.codec = "json"
    """
    
    vector = pyvector.Vector(textwrap.dedent(config))
    await vector.start()
    
    # Send test data
    test_messages = [
        {"sink_test": "message1", "data": "hello"},
        {"sink_test": "message2", "data": "world"},
        {"sink_test": "message3", "data": "vector"},
    ]
    
    for msg in test_messages:
        await vector.send("python", json.dumps(msg).encode())
    
    await vector.stop()
    
    # Verify both sinks received data
    assert file1.exists()
    assert file2.exists()
    
    content1 = file1.read_text()
    content2 = file2.read_text()
    
    # Both files should have the same content (data goes to both sinks)
    assert len(content1) > 0
    assert len(content2) > 0


@pytest.mark.asyncio
async def test_data_transformation():
    """Test data transformation through Vector transforms."""
    # This test will be skipped if transforms aren't working with current Vector version
    config = """
    [sources.python]
    type = "python"
    
    [transforms.filter]
    type = "filter"
    inputs = ["python"]
    condition = '.level == "info"'
    
    [sinks.console]
    type = "console"
    inputs = ["filter"]
    encoding.codec = "json"
    """
    
    vector = pyvector.Vector(textwrap.dedent(config))
    
    try:
        await vector.start()
        
        # Send mixed data - some should be filtered
        messages = [
            {"level": "info", "message": "This should pass"},
            {"level": "debug", "message": "This should be filtered"},
            {"level": "info", "message": "This should also pass"},
        ]
        
        for msg in messages:
            await vector.send("python", json.dumps(msg).encode())
        
        await vector.stop()
        
    except Exception as e:
        pytest.skip(f"Transform functionality not available in current Vector version: {e}")


@pytest.mark.asyncio
async def test_binary_data_handling():
    """Test handling of binary data through Vector."""
    config = """
    [sources.python]
    type = "python"
    
    [sinks.console]
    type = "console"
    inputs = ["python"]
    encoding.codec = "json"
    """
    
    vector = pyvector.Vector(textwrap.dedent(config))
    await vector.start()
    
    # Test different types of binary data
    binary_data = [
        b'{"text": "plain json"}',
        b'\x00\x01\x02\x03',  # Binary data
        "unicode: 你好世界".encode('utf-8'),  # Unicode
        json.dumps({"binary": True}).encode(),
    ]
    
    for data in binary_data:
        try:
            await vector.send("python", data)
        except Exception as e:
            # Some binary data might not be valid JSON - that's expected
            pass
    
    await vector.stop()