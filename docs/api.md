# pyvector-rs API Documentation

## Overview
pyvector-rs provides a Python interface to Vector's data processing capabilities through a Rust extension.

## Core Classes

### `pyvector.Vector`

Main class for interacting with Vector pipelines.

#### Constructor
```python
Vector(config: str)
```
- `config`: Vector configuration in TOML format

#### Methods

##### `async start()`
Starts the Vector pipeline. Must be called before sending data.

##### `async stop()`
Stops the Vector pipeline and cleans up resources.

##### `async send(source: str, data: bytes)`
Sends data to a specified Vector source.
- `source`: Source name from Vector config
- `data`: Raw bytes to send

## Configuration Examples

### Basic File Output
```python
config = """
[sources.python]
type = "python"

[sinks.file]
type = "file" 
inputs = ["python"]
path = "/tmp/output.txt"
encoding.codec = "json"
"""
```

### AWS S3 and SQS
```python
config = """
[sources.python]
type = "python"

[sinks.s3]
type = "aws_s3"
inputs = ["python"]
bucket = "my-bucket"
encoding.codec = "json"

[sinks.sqs]
type = "aws_sqs"
inputs = ["python"]
queue_url = "https://sqs.region.amazonaws.com/account/queue"
encoding.codec = "json"
"""
```

### Multiple Sinks with Transforms
```python
config = """
[sources.python]
type = "python"

[transforms.filter]
type = "filter"
inputs = ["python"]
condition = '.level == "error"'

[sinks.errors]
type = "file"
inputs = ["filter"]
path = "/var/log/errors.log"

[sinks.all]
type = "elasticsearch"
inputs = ["python"]
endpoints = ["http://localhost:9200"]
"""
```

## Usage Patterns

### Basic Usage
```python
import asyncio
import json
import pyvector

async def main():
    vector = pyvector.Vector(config)
    await vector.start()
    
    # Send data
    data = json.dumps({"message": "hello"}).encode()
    await vector.send("python", data)
    
    await vector.stop()

asyncio.run(main())
```

### Batch Processing
```python
async def batch_send(vector, items):
    for item in items:
        data = json.dumps(item).encode()
        await vector.send("python", data)
```

### Error Handling
```python
try:
    vector = pyvector.Vector(config)
    await vector.start()
    # ... send data ...
except Exception as e:
    print(f"Vector error: {e}")
finally:
    if vector:
        await vector.stop()
```

## Supported Vector Features

### Sources
- `python`: Custom source for receiving data from Python

### Sinks
- AWS: S3, SQS, SNS, Kinesis
- Azure: Blob Storage
- GCP: Various services
- Elasticsearch
- File, HTTP, Redis, MQTT
- And many more from Vector's ecosystem

### Transforms
- Filter, Reduce, Remap
- Dedupe, Sample, Throttle
- Route, Pipelines

## Performance Notes
- Data is passed with minimal copying between Python and Rust
- Vector handles batching, buffering, and retries automatically
- Async/await interface prevents blocking Python event loop
- Memory usage is managed by Vector's built-in backpressure