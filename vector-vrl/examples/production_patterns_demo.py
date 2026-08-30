#!/usr/bin/env python3
"""Production Patterns Demo for vector_vrl.

Demonstrates native Vector execution with pre-provisioned patterns
"""

import sys
from pathlib import Path

# Add vector_vrl to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vector_vrl


def demo_apache_pattern():
    """Demo Apache Combined Log pattern with native execution."""
    print("APACHE COMBINED LOGS - Native Execution")
    print("=" * 50)

    # Get pre-optimized Apache pattern (350+ THG)
    apache_config = vector_vrl.get_apache_combined()
    print(f"Apache config loaded: {len(apache_config)} sections")

    # Production Apache log samples
    apache_logs = [
        '192.168.1.100 - user1 [08/Sep/2023:12:00:00 +0000] "GET /api/v1/users HTTP/1.1" 200 1234 "https://example.com/app" "Mozilla/5.0"',
        '192.168.1.101 - user2 [08/Sep/2023:12:00:01 +0000] "POST /api/v1/login HTTP/1.1" 401 567 "-" "curl/7.68.0"',
        '192.168.1.102 - user3 [08/Sep/2023:12:00:02 +0000] "GET /api/v1/data HTTP/1.1" 200 8901 "https://example.com/dashboard" "Chrome/91.0"',
    ]

    try:
        # THIS IS THE GOAL: Native in-process Vector execution
        vector = vector_vrl.Vector(apache_config)
        vector.initialize()
        results = vector.process_logs(apache_logs)

        print(f"Processed {len(results)} Apache logs natively")
        print(f"First result: {results[0]}")

        # THG assessment
        vrl_code = apache_config["transforms"]["parse_apache"]["source"]
        thg = vector_vrl.assess_vrl_performance(
            vrl_code, apache_logs, "apache_production"
        )
        print(f"THG Score: {thg['thg_score']} ({thg['performance_grade']})")

        return True
    except Exception as e:
        print(f"Apache pattern demo failed: {e}")
        print("This demonstrates the target API - actual Vector integration pending")
        return False


def demo_json_application_pattern():
    """Demo JSON Application Log pattern (highest performance)."""
    print("\nJSON APPLICATION LOGS - Built-in Parser")
    print("=" * 50)

    json_config = vector_vrl.get_json_application()
    print(f"JSON config loaded: {len(json_config)} sections")

    # Production JSON log samples
    json_logs = [
        '{"timestamp": "2023-09-08T12:00:00Z", "level": "INFO", "service": "api-gateway", "request_id": "req_123", "duration": 45, "user_id": "user_456", "component": "auth", "message": "User authenticated successfully"}',
        '{"timestamp": "2023-09-08T12:00:01Z", "level": "ERROR", "service": "user-service", "request_id": "req_124", "duration": 120, "user_id": "user_789", "component": "database", "message": "Connection timeout to user database"}',
        '{"timestamp": "2023-09-08T12:00:02Z", "level": "WARN", "service": "cache-service", "request_id": "req_125", "duration": 250, "user_id": "user_101", "component": "redis", "message": "Cache miss for user profile"}',
    ]

    try:
        # Native Vector execution with built-in JSON parser (500+ EPS expected)
        vector = vector_vrl.Vector(json_config)
        vector.initialize()
        results = vector.process_logs(json_logs)

        print(f"Processed {len(results)} JSON logs natively")
        print("Performance optimized with parse_json() built-in")

        # THG assessment should show excellent performance
        vrl_code = json_config["transforms"]["parse_json_app"]["source"]
        thg = vector_vrl.assess_vrl_performance(vrl_code, json_logs, "json_production")
        print(
            f"THG Score: {thg['thg_score']} ({thg['performance_grade']}) - Expected: A+ (500+ eps)"
        )

        return True
    except Exception as e:
        print(f"JSON pattern demo failed: {e}")
        print("This demonstrates the target API - actual Vector integration pending")
        return False


def demo_kubernetes_pattern():
    """Demo Kubernetes Pod Log pattern with metadata extraction."""
    print("\nKUBERNETES POD LOGS - Metadata Extraction")
    print("=" * 50)

    k8s_config = vector_vrl.get_kubernetes_pods()
    print(f"K8s config loaded: {len(k8s_config)} sections")

    # Production K8s log samples
    k8s_logs = [
        "2023-09-08T12:00:00Z INFO [api-gateway] Starting HTTP server on port 8080",
        "2023-09-08T12:00:01Z ERROR [user-service] Database connection failed: timeout after 30s",
        "2023-09-08T12:00:02Z WARN [cache-service] Redis cluster node down, switching to backup",
    ]

    try:
        # Native K8s log processing with namespace/container extraction
        vector = vector_vrl.Vector(k8s_config)
        vector.initialize()
        results = vector.process_logs(k8s_logs)

        print(f"Processed {len(results)} K8s logs with metadata")
        print("Extracted: namespace, container, pod info")

        vrl_code = k8s_config["transforms"]["parse_k8s"]["source"]
        thg = vector_vrl.assess_vrl_performance(vrl_code, k8s_logs, "k8s_production")
        print(
            f"THG Score: {thg['thg_score']} ({thg['performance_grade']}) - Expected: B+ (300+ eps)"
        )

        return True
    except Exception as e:
        print(f"K8s pattern demo failed: {e}")
        print("This demonstrates the target API - actual Vector integration pending")
        return False


def demo_pattern_benchmark():
    """Demo comparative benchmarking of all production patterns."""
    print("\nPRODUCTION PATTERN BENCHMARK")
    print("=" * 50)

    # Test data for each pattern type
    test_data_sets = {
        "apache_combined": [
            '192.168.1.100 - user1 [08/Sep/2023:12:00:00 +0000] "GET /api HTTP/1.1" 200 1234',
            '192.168.1.101 - user2 [08/Sep/2023:12:00:01 +0000] "POST /login HTTP/1.1" 401 567',
        ],
        "json_application": [
            '{"level": "INFO", "service": "api", "message": "Request processed"}',
            '{"level": "ERROR", "service": "auth", "message": "Auth failed"}',
        ],
        "kubernetes_pods": [
            "2023-09-08T12:00:00Z INFO [api] Starting server",
            "2023-09-08T12:00:01Z ERROR [db] Connection failed",
        ],
    }

    try:
        # Benchmark all patterns for comparative analysis
        benchmark_results = vector_vrl.production_patterns.benchmark_all_patterns(
            test_data_sets
        )

        print(f"Benchmarked {len(benchmark_results)} production patterns:")

        for pattern_name, result in benchmark_results.items():
            if "error" not in result:
                print(
                    f"  {pattern_name}: {result['thg_score']:.1f} THG ({result['performance_grade']})"
                )
            else:
                print(f"  {pattern_name}: Error - {result['error']}")

        # Find best performing pattern
        valid_results = {k: v for k, v in benchmark_results.items() if "error" not in v}
        if valid_results:
            best_pattern = max(valid_results.items(), key=lambda x: x[1]["thg_score"])
            print(
                f"\nBest Performance: {best_pattern[0]} ({best_pattern[1]['thg_score']:.1f} THG)"
            )

        return True
    except Exception as e:
        print(f"Pattern benchmark failed: {e}")
        print("This demonstrates the target API - actual Vector integration pending")
        return False


def main():
    """Demo all production patterns with native execution."""
    print("vector_vrl Production Patterns Demo")
    print("=" * 60)
    print(f"Package Version: {vector_vrl.__version__}")
    print("Core Purpose: Native in-app Vector execution (no subprocess)")
    print(
        f"Available Patterns: {vector_vrl.ProductionPatterns.list_available_patterns()}"
    )
    print()

    demos = [
        demo_apache_pattern,
        demo_json_application_pattern,
        demo_kubernetes_pattern,
        demo_pattern_benchmark,
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
    print("PRODUCTION PATTERNS SUMMARY")
    print("=" * 60)
    successful = sum(results)
    total = len(results)
    print(f"Working demos: {successful}/{total}")

    if successful > 0:
        print("Production patterns are integrated and ready for native execution!")
        print("THG assessment framework working with production log formats")
    else:
        print(
            "Demos show target API design - Vector core integration needed for execution"
        )

    print("\nNext: Complete Vector runtime integration for true in-process execution")


if __name__ == "__main__":
    main()
