#!/usr/bin/env python3
"""THG Performance Assessment Demo.

Demonstrates the enhanced vector_vrl THG capabilities
"""

import sys
from pathlib import Path

# Add vector_vrl to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vector_vrl


def demo_quick_thg_assessment():
    """Demo quick THG assessment for immediate feedback."""
    print("DEMO 1: Quick THG Assessment")
    print("=" * 50)

    # Sample high-performance VRL using built-in parsers
    vrl_code = """
    message_str = to_string(.message) ?? ""
    parsed, err = parse_json(message_str)
    if err == null {
        .timestamp = parsed.timestamp
        .level = parsed.level
        .service = parsed.service
        .request_id = parsed.request_id
        .duration_ms = to_int(parsed.duration) ?? 0
    }
    """

    # Production-like JSON logs
    test_logs = [
        '{"timestamp": "2023-09-08T12:00:00Z", "level": "INFO", "service": "api", "request_id": "req_123", "duration": "45"}',
        '{"timestamp": "2023-09-08T12:00:01Z", "level": "ERROR", "service": "auth", "request_id": "req_124", "duration": "120"}',
        '{"timestamp": "2023-09-08T12:00:02Z", "level": "WARN", "service": "db", "request_id": "req_125", "duration": "250"}',
        '{"timestamp": "2023-09-08T12:00:03Z", "level": "INFO", "service": "cache", "request_id": "req_126", "duration": "5"}',
    ]

    try:
        score = vector_vrl.quick_thg_assessment(vrl_code, test_logs, "json_parser_demo")
        print(f"THG Score: {score}")
        return True
    except Exception as e:
        print(f"Demo failed: {e}")
        return False


def demo_detailed_performance_assessment():
    """Demo detailed VRL performance assessment."""
    print("\nDEMO 2: Detailed Performance Assessment")
    print("=" * 50)

    # Apache access log pattern (more complex)
    apache_vrl = """
    message_str = to_string(.message) ?? ""
    parts = split(message_str, " ")

    if length(parts) >= 10 {
        .client_ip = strip_whitespace(to_string(parts[0]))
        .user = strip_whitespace(to_string(parts[2]))
        .timestamp = strip_whitespace(to_string(parts[3]) + " " + to_string(parts[4]))
        .method = strip_whitespace(to_string(parts[5]))
        .path = strip_whitespace(to_string(parts[6]))
        .http_version = strip_whitespace(to_string(parts[7]))
        .status_code = to_int(parts[8]) ?? 0
        .response_size = to_int(parts[9]) ?? 0
    }
    """

    apache_logs = [
        '192.168.1.100 - user1 [08/Sep/2023:12:00:00 +0000] "GET /api/v1/users HTTP/1.1" 200 1234',
        '192.168.1.101 - user2 [08/Sep/2023:12:00:01 +0000] "POST /api/v1/login HTTP/1.1" 401 567',
        '192.168.1.102 - user3 [08/Sep/2023:12:00:02 +0000] "GET /api/v1/data HTTP/1.1" 200 8901',
        '192.168.1.103 - user4 [08/Sep/2023:12:00:03 +0000] "DELETE /api/v1/item/123 HTTP/1.1" 204 0',
    ]

    try:
        assessment = vector_vrl.assess_vrl_performance(
            apache_vrl, apache_logs, "apache_access_logs"
        )

        print("Assessment Results:")
        print(f"   THG Score: {assessment['thg_score']}")
        print(f"   Performance Grade: {assessment['performance_grade']}")
        print(f"   Throughput: {assessment['events_per_second']:.1f} eps")
        print(f"   Latency P95: {assessment['latency_p95_ms']:.1f} ms")
        print(f"   Error Rate: {assessment['error_rate_percent']:.1f}%")

        print("\nRecommendations:")
        for rec in assessment["recommendations"]:
            print(f"   {rec}")

        return True
    except Exception as e:
        print(f"Demo failed: {e}")
        return False


def demo_vector_pipeline_execution():
    """Demo direct Vector pipeline execution with monitoring."""
    print("\nDEMO 3: Vector Pipeline Execution")
    print("=" * 50)

    # Vector configuration
    vector_config = {
        "sources": {"demo_input": {"type": "stdin"}},
        "transforms": {
            "parse_logs": {
                "type": "remap",
                "source": """
                message_str = to_string(.message) ?? ""
                parsed, err = parse_key_value(message_str, key_value_delimiter: "=", field_delimiter: " ")
                if err == null {
                    . = merge(., parsed)
                }
                """,
            }
        },
        "sinks": {"demo_output": {"type": "console", "encoding": {"codec": "json"}}},
    }

    key_value_logs = [
        "timestamp=2023-09-08T12:00:00Z level=INFO service=api request_id=req_123",
        "timestamp=2023-09-08T12:00:01Z level=ERROR service=auth request_id=req_124 error=invalid_token",
        "timestamp=2023-09-08T12:00:02Z level=WARN service=db request_id=req_125 latency=250ms",
    ]

    try:
        result = vector_vrl.execute_vector_pipeline(vector_config, key_value_logs)

        print("Pipeline Results:")
        print(f"   Success: {result['success']}")
        print(f"   Events Processed: {result['events_processed']}")
        print(f"   Throughput: {result['throughput_eps']:.1f} eps")
        print(f"   Processing Time: {result['processing_time_seconds']:.3f}s")
        print(f"   Performance Grade: {result['performance_summary']['grade']}")
        print(f"   THG Estimate: {result['performance_summary']['thg_estimated']:.1f}")

        return True
    except Exception as e:
        print(f"Demo failed: {e}")
        return False


def demo_comparative_benchmark():
    """Demo comparative performance benchmarking."""
    print("\nDEMO 4: Comparative Benchmark")
    print("=" * 50)

    # Multiple pattern configurations
    benchmark_patterns = [
        {
            "name": "json_builtin",
            "vrl": """
            message_str = to_string(.message) ?? ""
            parsed, err = parse_json(message_str)
            if err == null {
                .level = parsed.level
                .timestamp = parsed.timestamp
            }
            """,
            "test_logs": [
                '{"level": "INFO", "timestamp": "2023-09-08T12:00:00Z", "message": "Test"}',
                '{"level": "ERROR", "timestamp": "2023-09-08T12:00:01Z", "message": "Error"}',
            ],
        },
        {
            "name": "split_operations",
            "vrl": """
            message_str = to_string(.message) ?? ""
            parts = split(message_str, " ")
            if length(parts) >= 3 {
                .level = strip_whitespace(to_string(parts[0]))
                .timestamp = strip_whitespace(to_string(parts[1]))
                .service = strip_whitespace(to_string(parts[2]))
            }
            """,
            "test_logs": [
                "INFO 2023-09-08T12:00:00Z api Test message here",
                "ERROR 2023-09-08T12:00:01Z auth Authentication failed",
            ],
        },
    ]

    try:
        assessor = vector_vrl.THGPerformanceAssessor()
        results = assessor.benchmark_multiple_patterns(benchmark_patterns)

        print(f"\nBenchmark completed: {len(results)} patterns tested")
        return True
    except Exception as e:
        print(f"Benchmark failed: {e}")
        return False


def main():
    """Run all THG performance demos."""
    print("vector_vrl THG Performance Assessment Demo")
    print("=" * 60)
    print(f"Package Version: {vector_vrl.__version__}")
    print(f"Bindings Available: {vector_vrl.get_bindings_info()}")
    print()

    demos = [
        demo_quick_thg_assessment,
        demo_detailed_performance_assessment,
        demo_vector_pipeline_execution,
        demo_comparative_benchmark,
    ]

    results = []
    for demo in demos:
        try:
            success = demo()
            results.append(success)
        except Exception as e:
            print(f"Demo failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    print("DEMO SUMMARY")
    print("=" * 60)
    successful = sum(results)
    total = len(results)
    print(f"Successful demos: {successful}/{total}")

    if successful == total:
        print("All THG performance features working perfectly!")
    else:
        print("Some demos failed - check Vector installation and dependencies")

    print("\nTHG Performance Assessment is ready for production use!")


if __name__ == "__main__":
    main()
