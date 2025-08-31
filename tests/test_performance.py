"""
Performance and stress tests for pyvector-rs.
"""
import pytest
import pyvector
import textwrap
import json
import asyncio
import time
import uuid
from pathlib import Path


@pytest.mark.asyncio
async def test_send_performance(tmp_path):
    """Test sending performance with timing measurements."""
    output_file = tmp_path / "performance.json"
    
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
    
    # Performance test
    num_messages = 10000
    message_size = 100  # bytes
    
    # Generate test data
    test_message = {
        "id": 0,
        "data": "x" * message_size,
        "timestamp": time.time()
    }
    
    start_time = time.time()
    
    # Send messages
    for i in range(num_messages):
        test_message["id"] = i
        test_message["timestamp"] = time.time()
        await vector.send("python", json.dumps(test_message).encode())
    
    end_time = time.time()
    await vector.stop()
    
    # Calculate performance metrics
    duration = end_time - start_time
    messages_per_second = num_messages / duration
    bytes_per_second = (num_messages * len(json.dumps(test_message))) / duration
    
    print(f"Performance Results:")
    print(f"  Messages: {num_messages}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Messages/sec: {messages_per_second:.2f}")
    print(f"  Bytes/sec: {bytes_per_second:.2f}")
    
    # Verify output file exists and has content
    assert output_file.exists()
    assert output_file.stat().st_size > 0


@pytest.mark.asyncio
async def test_concurrent_senders():
    """Test concurrent sending from multiple coroutines."""
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
    
    async def sender_task(sender_id: int, num_messages: int):
        """Individual sender task."""
        for i in range(num_messages):
            data = json.dumps({
                "sender_id": sender_id,
                "message_id": i,
                "uuid": str(uuid.uuid4()),
                "content": f"Message {i} from sender {sender_id}"
            }).encode()
            await vector.send("python", data)
    
    # Run multiple concurrent senders
    num_senders = 5
    messages_per_sender = 100
    
    start_time = time.time()
    
    # Create and run sender tasks concurrently
    tasks = [
        sender_task(sender_id, messages_per_sender) 
        for sender_id in range(num_senders)
    ]
    
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    await vector.stop()
    
    duration = end_time - start_time
    total_messages = num_senders * messages_per_sender
    
    print(f"Concurrent Sending Results:")
    print(f"  Senders: {num_senders}")
    print(f"  Messages per sender: {messages_per_sender}")
    print(f"  Total messages: {total_messages}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Messages/sec: {total_messages/duration:.2f}")


@pytest.mark.asyncio
async def test_large_message_handling(tmp_path):
    """Test handling of large messages."""
    output_file = tmp_path / "large_messages.json"
    
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
    
    # Test progressively larger messages
    sizes = [1_000, 10_000, 100_000, 1_000_000]  # 1KB to 1MB
    
    for size in sizes:
        large_data = {
            "size": size,
            "content": "A" * size,
            "metadata": {
                "test": "large_message",
                "size_bytes": size
            }
        }
        
        start_time = time.time()
        await vector.send("python", json.dumps(large_data).encode())
        end_time = time.time()
        
        print(f"Sent {size} byte message in {(end_time - start_time)*1000:.2f}ms")
    
    await vector.stop()
    
    # Verify output
    assert output_file.exists()
    assert output_file.stat().st_size > sum(sizes)  # Should be larger than sum of test data


@pytest.mark.asyncio 
async def test_memory_usage():
    """Test memory usage during sustained operation."""
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
    
    # Send sustained traffic
    base_message = {"test": "memory_usage", "data": "x" * 1000}
    
    # Send messages in batches to monitor memory
    for batch in range(10):
        batch_tasks = []
        for i in range(100):
            message = base_message.copy()
            message["batch"] = batch
            message["id"] = i
            batch_tasks.append(
                vector.send("python", json.dumps(message).encode())
            )
        
        await asyncio.gather(*batch_tasks)
        # Small delay between batches
        await asyncio.sleep(0.1)
    
    await vector.stop()


@pytest.mark.asyncio
async def test_burst_traffic(tmp_path):
    """Test handling of sudden traffic bursts."""
    output_file = tmp_path / "burst.json"
    
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
    
    # Normal traffic
    for i in range(10):
        data = json.dumps({"phase": "normal", "id": i}).encode()
        await vector.send("python", data)
        await asyncio.sleep(0.01)  # 10ms between messages
    
    # Sudden burst
    burst_tasks = []
    for i in range(1000):
        data = json.dumps({"phase": "burst", "id": i, "uuid": str(uuid.uuid4())}).encode()
        burst_tasks.append(vector.send("python", data))
    
    start_burst = time.time()
    await asyncio.gather(*burst_tasks)
    end_burst = time.time()
    
    # Back to normal
    for i in range(10):
        data = json.dumps({"phase": "post_burst", "id": i}).encode()
        await vector.send("python", data)
        await asyncio.sleep(0.01)
    
    await vector.stop()
    
    print(f"Burst of 1000 messages completed in {(end_burst - start_burst)*1000:.2f}ms")
    
    # Verify output
    assert output_file.exists()
    content = output_file.read_text()
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    
    # Should have received most messages
    assert len(lines) >= 1000  # At least the burst messages