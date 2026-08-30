#!/usr/bin/env python3
"""
Debug Vector subprocess execution to see what's happening.
"""

import subprocess
import tempfile
from pathlib import Path


def test_vector_debug():
    """Debug Vector execution"""

    with tempfile.TemporaryDirectory(prefix="vector_debug_") as temp_dir:
        temp_path = Path(temp_dir)

        # Create Vector data directory
        vector_data_dir = temp_path / "vector_data"
        vector_data_dir.mkdir(exist_ok=True)

        # Create simple input file
        input_file = temp_path / "input.log"
        with open(input_file, "w") as f:
            f.write("hello world\n")
            f.write("test message\n")

        # Create simple Vector config
        output_file = temp_path / "output.jsonl"
        config_file = temp_path / "config.toml"

        config_content = f"""
data_dir = "{temp_path}/vector_data"

[sources.file_input]
type = "file"
include = ["{input_file}"]
read_from = "beginning"

[transforms.test_transform]
type = "remap"
inputs = ["file_input"]
source = '''
.processed = true
.test_field = "added"
'''

[sinks.file_output]
type = "file"
inputs = ["test_transform"]
path = "{output_file}"
encoding.codec = "json"
"""

        with open(config_file, "w") as f:
            f.write(config_content)

        print(f"Temp directory: {temp_path}")
        print(f"Config file: {config_file}")
        print(f"Input file: {input_file}")
        print(f"Output file: {output_file}")

        print("\nConfig content:")
        print(config_content)

        print("\nInput content:")
        with open(input_file) as f:
            print(f.read())

        # Run Vector with verbose output
        print("\nRunning Vector...")

        try:
            # Run Vector with more verbose flags
            result = subprocess.run(
                ["/usr/bin/vector", "--config", str(config_file), "--verbose"],
                capture_output=True,
                text=True,
                timeout=15,
            )

            print(f"Vector exit code: {result.returncode}")
            print(f"Vector stdout: {result.stdout}")
            print(f"Vector stderr: {result.stderr}")

            # Check if output file was created
            if output_file.exists():
                print("\nOutput file created!")
                with open(output_file) as f:
                    content = f.read()
                    print(f"Output content:\n{content}")
            else:
                print("\nOutput file not created")

            # List all files created
            print("\nFiles in temp directory:")
            for file in temp_path.iterdir():
                print(f"  {file.name}: {file.stat().st_size} bytes")

        except subprocess.TimeoutExpired:
            print("Vector timed out")
        except Exception as e:
            print(f"Error running Vector: {e}")


if __name__ == "__main__":
    test_vector_debug()
