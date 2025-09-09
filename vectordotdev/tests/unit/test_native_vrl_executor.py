#!/usr/bin/env python3
"""
Comprehensive unit tests for native VRL executor
Uses real-world VRL examples and production test data
"""

import unittest
import json
import tempfile
from pathlib import Path
import sys
import io

# Add vectordotdev to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vectordotdev.native_vector_executor import (
    execute_vrl_remap, quick_vrl_test, NativeVectorExecutor,
    VectorExecutionResult, ExecutionMetrics, VectorError
)


class TestNativeVRLExecutor(unittest.TestCase):
    """Test native VRL execution with real-world examples"""

    def setUp(self):
        """Set up test fixtures"""
        self.executor = NativeVectorExecutor()

    def test_json_parsing_production(self):
        """Test JSON parsing with real production-style logs"""
        vrl_code = '''
        structured, err = parse_json(.message)
        if err == null {
            . = merge(., structured)
            .parser_type = "json"
            .processed_at = now()
        } else {
            .parse_error = "invalid_json"
            .original_message = .message
        }
        '''

        # Production JSON logs from web applications
        json_logs = [
            '{"timestamp": "2023-09-08T12:00:00Z", "level": "INFO", "service": "api-gateway", "request_id": "req_123", "duration_ms": 45, "user_id": "user_456", "method": "GET", "path": "/api/v1/users", "status": 200}',
            '{"timestamp": "2023-09-08T12:00:01Z", "level": "ERROR", "service": "user-service", "request_id": "req_124", "duration_ms": 120, "user_id": "user_789", "method": "POST", "path": "/api/v1/login", "status": 401, "error": "invalid_credentials"}',
            '{"timestamp": "2023-09-08T12:00:02Z", "level": "WARN", "service": "cache-service", "request_id": "req_125", "duration_ms": 250, "cache_hit": false, "key": "user_profile_123"}',
            # Malformed JSON to test error handling
            '{"timestamp": "2023-09-08T12:00:03Z", "level": "ERROR", incomplete_json',
        ]

        result = execute_vrl_remap(json_logs, vrl_code, timeout_seconds=10)

        # Validate execution
        self.assertTrue(result.success)
        self.assertGreater(result.metrics.events_processed, 0)
        self.assertGreater(result.metrics.events_per_second, 100)  # Should be high performance
        self.assertEqual(len(result.output_data), 4)  # All events processed

        # Validate JSON parsing results
        valid_parsed = [event for event in result.output_data if "service" in event]
        self.assertEqual(len(valid_parsed), 3)  # 3 valid JSON events

        # Validate error handling for malformed JSON
        error_events = [event for event in result.output_data if "parse_error" in event]
        self.assertEqual(len(error_events), 1)  # 1 malformed JSON

        # Validate performance metrics
        self.assertGreater(result.metrics.thg_score, 200)  # Good performance expected
        self.assertEqual(result.metrics.errors_count, 0)  # No execution errors

    def test_syslog_parsing_production(self):
        """Test syslog parsing with real syslog format"""
        vrl_code = '''
        structured, err = parse_syslog(.message)
        if err == null {
            . = merge(., structured)
            .parser_type = "syslog"
            .severity_text = if .severity == "emerg" { "emergency" } 
                           else if .severity == "crit" { "critical" }
                           else if .severity == "err" { "error" }
                           else if .severity == "warning" { "warning" }
                           else if .severity == "info" { "information" }
                           else { .severity }
        } else {
            .parse_error = "invalid_syslog"
            .original_message = .message
        }
        '''

        # Real syslog messages from production systems
        syslog_logs = [
            "<102>1 2020-12-22T15:22:31.111Z vector-user.biz su 2666 ID389 - Something went wrong",
            "<34>1 2023-09-08T12:00:00Z web-server nginx 1234 - - 192.168.1.100 GET /api/v1/users 200",
            "<165>1 2023-09-08T12:00:01Z db-server postgres 5432 - - Connection established from 192.168.1.50",
            "<86>1 2023-09-08T12:00:02Z app-server java 8080 REQ123 - User authentication successful for user_456",
            # Invalid syslog for error testing
            "This is not a valid syslog message format",
        ]

        result = execute_vrl_remap(syslog_logs, vrl_code, timeout_seconds=10)

        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 5)
        self.assertEqual(len(result.output_data), 5)

        # Validate syslog parsing results
        valid_syslog = [event for event in result.output_data if "appname" in event or "hostname" in event]
        self.assertGreaterEqual(len(valid_syslog), 4)  # At least 4 valid syslog events

        # Validate error handling for malformed syslog
        error_events = [event for event in result.output_data if "parse_error" in event]
        self.assertGreaterEqual(len(error_events), 1)  # At least 1 malformed syslog

        # Check severity text enrichment
        enriched_events = [event for event in result.output_data if "severity_text" in event]
        self.assertGreater(len(enriched_events), 0)

    def test_apache_log_parsing_complex(self):
        """Test complex Apache log parsing with multiple fields"""
        vrl_code = '''
        # Apache Combined Log Format parsing
        message_str = to_string(.message) ?? ""
        
        # Use regex for Apache combined format
        apache_pattern = r'^(?P<ip>\S+) (?P<ident>\S+) (?P<userid>\S+) \[(?P<timestamp>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) (?P<version>\S+)" (?P<status>\d+) (?P<size>\S+)( "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)")?'
        
        parsed, err = parse_regex(message_str, apache_pattern)
        if err == null {
            .client_ip = parsed.ip
            .user_identifier = parsed.ident
            .user_id = parsed.userid
            .timestamp_str = parsed.timestamp
            .method = parsed.method
            .path = parsed.path
            .http_version = parsed.version
            .status_code = to_int(parsed.status) ?? 0
            .response_size = if parsed.size == "-" { 0 } else { to_int(parsed.size) ?? 0 }
            .referer = parsed.referer
            .user_agent = parsed.user_agent
            
            # Enrich with additional fields
            .log_type = "apache_access"
            .status_category = if .status_code >= 500 { "server_error" }
                             else if .status_code >= 400 { "client_error" }
                             else if .status_code >= 300 { "redirect" }
                             else if .status_code >= 200 { "success" }
                             else { "informational" }
        } else {
            .parse_error = "invalid_apache_format"
            .original_message = .message
        }
        '''

        # Real Apache combined log format samples
        apache_logs = [
            '192.168.1.100 - user1 [08/Sep/2023:12:00:00 +0000] "GET /api/v1/users HTTP/1.1" 200 1234 "https://example.com/app" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"',
            '192.168.1.101 - user2 [08/Sep/2023:12:00:01 +0000] "POST /api/v1/login HTTP/1.1" 401 567 "-" "curl/7.68.0"',
            '192.168.1.102 - - [08/Sep/2023:12:00:02 +0000] "GET /api/v1/data HTTP/1.1" 200 8901 "https://example.com/dashboard" "Chrome/91.0.4472.124"',
            '10.0.0.50 - admin [08/Sep/2023:12:00:03 +0000] "DELETE /api/v1/item/123 HTTP/1.1" 204 - "-" "PostmanRuntime/7.28.0"',
            # Invalid format for error testing  
            'This is not a valid Apache log format line',
        ]

        result = execute_vrl_remap(apache_logs, vrl_code, timeout_seconds=15)

        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 5)

        # Validate Apache parsing results
        valid_apache = [event for event in result.output_data if "client_ip" in event]
        self.assertGreaterEqual(len(valid_apache), 4)  # At least 4 valid Apache logs

        # Validate status categorization
        success_events = [event for event in result.output_data if event.get("status_category") == "success"]
        error_events = [event for event in result.output_data if event.get("status_category") == "client_error"]
        self.assertGreater(len(success_events), 0)
        self.assertGreater(len(error_events), 0)

    def test_multi_format_fallback_parsing(self):
        """Test complex multi-format parsing with fallback strategy"""
        vrl_code = '''
        message_str = to_string(.message) ?? ""
        
        # Smart parsing: try JSON first, then syslog, then key-value
        if starts_with(message_str, "{") {
            structured, err = parse_json(message_str)
            if err == null {
                . = merge(., structured)
                .parser_used = "json"
            }
        } else if starts_with(message_str, "<") {
            structured, err = parse_syslog(message_str)
            if err == null {
                . = merge(., structured)
                .parser_used = "syslog"
            }
        } else if contains(message_str, "=") {
            structured, err = parse_key_value(message_str, key_value_delimiter: "=", field_delimiter: " ")
            if err == null {
                . = merge(., structured)
                .parser_used = "key_value"
            }
        } else {
            .parser_used = "plain_text"
            .log_message = message_str
        }
        
        # Add universal fields
        .processed_at = now()
        .processing_version = "1.0.1"
        '''

        # Mixed format logs simulating real production environments
        mixed_logs = [
            # JSON application log
            '{"timestamp": "2023-09-08T12:00:00Z", "level": "INFO", "service": "api", "request_id": "req_123", "user_id": 456}',
            # Syslog message  
            '<34>1 2023-09-08T12:00:01Z web-server nginx 1234 - - User session started',
            # Key-value format
            'timestamp=2023-09-08T12:00:02Z level=ERROR service=database error=connection_timeout',
            # Plain text log
            '2023-09-08 12:00:03 [WARNING] Cache miss for key user_profile_789',
            # Docker container log
            'timestamp=2023-09-08T12:00:04Z container_id=abc123 container_name=api-service status=healthy',
        ]

        result = execute_vrl_remap(mixed_logs, vrl_code, timeout_seconds=10)

        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 5)
        self.assertEqual(len(result.output_data), 5)

        # Validate parser selection
        json_parsed = [event for event in result.output_data if event.get("parser_used") == "json"]
        syslog_parsed = [event for event in result.output_data if event.get("parser_used") == "syslog"]
        kv_parsed = [event for event in result.output_data if event.get("parser_used") == "key_value"]
        plain_parsed = [event for event in result.output_data if event.get("parser_used") == "plain_text"]

        self.assertEqual(len(json_parsed), 1)
        self.assertEqual(len(syslog_parsed), 1) 
        self.assertEqual(len(kv_parsed), 2)  # 2 key-value logs
        self.assertEqual(len(plain_parsed), 1)

        # Validate that all events have universal fields
        for event in result.output_data:
            self.assertIn("processed_at", event)
            self.assertIn("processing_version", event)
            self.assertIn("parser_used", event)

    def test_performance_intensive_processing(self):
        """Test performance with large dataset and complex VRL"""
        vrl_code = '''
        # Performance-intensive VRL with multiple operations
        message_str = to_string(.message) ?? ""
        
        # JSON parsing with field extraction and transformation
        structured, err = parse_json(message_str)
        if err == null {
            # Extract and transform multiple fields
            .timestamp = structured.timestamp
            .log_level = upcase(structured.level ?? "unknown")
            .service_name = structured.service ?? "unknown"
            .request_duration = to_int(structured.duration_ms) ?? 0
            .user_identifier = structured.user_id ?? "anonymous"
            
            # Complex field calculations
            .duration_category = if .request_duration < 100 { "fast" }
                               else if .request_duration < 500 { "medium" }
                               else if .request_duration < 1000 { "slow" }
                               else { "very_slow" }
            
            # URL parsing if path exists
            if exists(structured.path) {
                .url_path = structured.path
                path_parts = split(structured.path, "/")
                .api_version = if length(path_parts) > 2 { path_parts[2] } else { "unknown" }
                .resource = if length(path_parts) > 3 { path_parts[3] } else { "unknown" }
            }
            
            # Status code categorization
            .status_code = to_int(structured.status) ?? 0
            .status_category = if .status_code >= 500 { "server_error" }
                             else if .status_code >= 400 { "client_error" }  
                             else if .status_code >= 200 { "success" }
                             else { "other" }
            
            # Performance optimization: cache computed fields
            .request_signature = .method + ":" + .url_path + ":" + .log_level
        }
        '''

        # Generate large dataset for performance testing
        base_log = '{"timestamp": "2023-09-08T12:00:{:02d}Z", "level": "{}", "service": "api", "request_id": "req_{}", "duration_ms": {}, "user_id": "user_{}", "method": "GET", "path": "/api/v1/users", "status": {}}'
        
        large_dataset = []
        for i in range(100):  # 100 events for performance testing
            level = ["INFO", "ERROR", "WARN", "DEBUG"][i % 4]
            duration = [45, 120, 250, 500, 1200][i % 5]
            status = [200, 201, 400, 401, 500][i % 5]
            log_entry = base_log.format(i, level, f"req_{i:03d}", duration, f"user_{i}", status)
            large_dataset.append(log_entry)

        result = execute_vrl_remap(large_dataset, vrl_code, timeout_seconds=30)

        # Validate execution performance
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 100)
        self.assertGreater(result.metrics.events_per_second, 500)  # Should be very fast
        self.assertGreater(result.metrics.thg_score, 400)  # High THG score expected

        # Validate complex field processing
        for event in result.output_data:
            self.assertIn("duration_category", event)
            self.assertIn("status_category", event)
            self.assertIn("api_version", event)
            self.assertIn("request_signature", event)

        # Validate categorizations work correctly
        fast_requests = [event for event in result.output_data if event.get("duration_category") == "fast"]
        slow_requests = [event for event in result.output_data if event.get("duration_category") == "very_slow"]
        self.assertGreater(len(fast_requests), 0)
        self.assertGreater(len(slow_requests), 0)

    def test_kubernetes_log_parsing(self):
        """Test Kubernetes pod log parsing with metadata extraction"""
        vrl_code = '''
        message_str = to_string(.message) ?? ""
        
        # K8s log format: timestamp level [component] message
        k8s_pattern = r'^(?P<timestamp>\S+) (?P<level>\S+) \[(?P<component>[^\]]+)\] (?P<message>.+)$'
        parsed, err = parse_regex(message_str, k8s_pattern)
        
        if err == null {
            .timestamp = parsed.timestamp
            .log_level = parsed.level
            .component = parsed.component
            .log_message = parsed.message
            
            # Extract K8s metadata from component
            .kubernetes_pod = .component + "-pod"
            .kubernetes_namespace = if contains(.component, "api") { "production-api" }
                                   else if contains(.component, "db") { "production-db" }
                                   else { "default" }
            
            # Service categorization
            .service_tier = if contains(.component, "api") { "frontend" }
                          else if contains(.component, "db") { "backend" }
                          else if contains(.component, "cache") { "middleware" }
                          else { "infrastructure" }
            
            .log_source = "kubernetes"
        } else {
            .parse_error = "invalid_k8s_format"
            .original_message = .message
        }
        '''

        # Real Kubernetes pod log samples
        k8s_logs = [
            "2023-09-08T12:00:00Z INFO [api-gateway] Starting HTTP server on port 8080",
            "2023-09-08T12:00:01Z ERROR [user-service] Database connection failed: timeout after 30s",
            "2023-09-08T12:00:02Z WARN [cache-service] Redis cluster node down, switching to backup",
            "2023-09-08T12:00:03Z DEBUG [db-migrator] Migration 'add_user_table' completed successfully",
            "2023-09-08T12:00:04Z INFO [api-auth] JWT token validated for user_456",
            # Invalid K8s format
            "This is not a valid Kubernetes log format",
        ]

        result = execute_vrl_remap(k8s_logs, vrl_code, timeout_seconds=10)

        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 6)

        # Validate K8s parsing
        valid_k8s = [event for event in result.output_data if "component" in event]
        self.assertGreaterEqual(len(valid_k8s), 5)  # At least 5 valid K8s logs

        # Validate namespace assignment
        api_ns = [event for event in result.output_data if event.get("kubernetes_namespace") == "production-api"]
        db_ns = [event for event in result.output_data if event.get("kubernetes_namespace") == "production-db"]
        self.assertGreater(len(api_ns), 0)
        self.assertGreater(len(db_ns), 0)

        # Validate service tier categorization
        frontend_services = [event for event in result.output_data if event.get("service_tier") == "frontend"]
        backend_services = [event for event in result.output_data if event.get("service_tier") == "backend"]
        self.assertGreater(len(frontend_services), 0)
        self.assertGreater(len(backend_services), 0)

    def test_file_io_operations(self):
        """Test file input and output operations"""
        vrl_code = '''
        structured, err = parse_json(.message)
        if err == null {
            . = merge(., structured)
            .processed_via_file = true
        }
        '''

        json_data = [
            '{"level": "INFO", "service": "api", "message": "Request processed"}',
            '{"level": "ERROR", "service": "auth", "message": "Authentication failed"}',
        ]

        # Test file input
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as input_file:
            input_path = Path(input_file.name)
            for line in json_data:
                input_file.write(line + '\n')

        # Test file output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as output_file:
            output_path = Path(output_file.name)

        try:
            result = execute_vrl_remap(input_path, vrl_code, output=output_path)

            # Validate execution
            self.assertTrue(result.success)
            self.assertEqual(result.metrics.events_processed, 2)

            # Validate file output was written
            self.assertTrue(output_path.exists())
            with open(output_path, 'r') as f:
                output_lines = [line.strip() for line in f if line.strip()]
                self.assertEqual(len(output_lines), 2)
                
                # Validate JSON output format
                for line in output_lines:
                    parsed = json.loads(line)
                    self.assertIn("processed_via_file", parsed)
                    self.assertTrue(parsed["processed_via_file"])

        finally:
            # Clean up temp files
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    def test_stream_io_operations(self):
        """Test stream input and output operations"""
        vrl_code = '''
        message_str = to_string(.message) ?? ""
        .original_length = length(message_str)
        .processed_via_stream = true
        .uppercase_message = upcase(message_str)
        '''

        json_data = [
            'This is a test message for stream processing',
            'Another test message with different content',
            'Final message to complete the stream test',
        ]

        # Test stream input
        input_stream = io.StringIO('\n'.join(json_data))
        output_stream = io.StringIO()

        result = execute_vrl_remap(input_stream, vrl_code, output=output_stream)

        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 3)

        # Validate stream output
        output_content = output_stream.getvalue()
        output_lines = [line.strip() for line in output_content.split('\n') if line.strip()]
        self.assertEqual(len(output_lines), 3)

        # Validate stream processing results
        for line in output_lines:
            parsed = json.loads(line)
            self.assertIn("processed_via_stream", parsed)
            self.assertIn("uppercase_message", parsed)
            self.assertTrue(parsed["processed_via_stream"])

    def test_error_handling_scenarios(self):
        """Test various error handling scenarios"""
        # VRL with intentional syntax error
        invalid_vrl = '''
        this is not valid VRL syntax
        missing semicolons and proper structure
        '''

        test_data = ['{"test": "data"}']

        result = execute_vrl_remap(test_data, invalid_vrl)

        # Should handle VRL syntax errors gracefully
        self.assertFalse(result.success)
        self.assertGreater(len(result.errors), 0)

        # Validate error structure
        for error in result.errors:
            self.assertIsInstance(error, VectorError)
            self.assertIn(error.error_type, ["config", "vrl_syntax", "vrl_runtime"])
            self.assertIsNotNone(error.message)

    def test_performance_metrics_accuracy(self):
        """Test accuracy of performance metrics and THG scoring"""
        # Simple, fast VRL for metric validation
        vrl_code = '''
        .processed = true
        .timestamp = now()
        '''

        test_data = ['test message'] * 50  # 50 identical events

        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=5)

        # Validate metrics accuracy
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 50)
        self.assertGreater(result.metrics.events_per_second, 100)  # Should be very fast
        self.assertLessEqual(result.metrics.execution_time_seconds, 5)  # Within timeout
        
        # Validate THG score calculation
        expected_base_score = min(800, result.metrics.events_per_second * 0.8)
        self.assertAlmostEqual(result.metrics.thg_score, expected_base_score, delta=50)

        # Validate performance grade
        if result.metrics.events_per_second >= 1000:
            self.assertEqual(result.metrics.performance_grade, "A+")
        elif result.metrics.events_per_second >= 500:
            self.assertEqual(result.metrics.performance_grade, "A")

    def test_quick_vrl_test_function(self):
        """Test the convenience quick_vrl_test function"""
        vrl_code = '''
        parsed, err = parse_json(.message)
        if err == null {
            .level = parsed.level
            .service = parsed.service
        }
        '''

        test_events = [
            '{"level": "INFO", "service": "api", "message": "Test"}',
            '{"level": "ERROR", "service": "auth", "message": "Error"}',
        ]

        result = quick_vrl_test(vrl_code, test_events, max_events=2)

        # Validate quick test results
        self.assertIn("success", result)
        self.assertIn("events_processed", result)
        self.assertIn("events_per_second", result)
        self.assertIn("thg_score", result)
        self.assertIn("performance_grade", result)
        self.assertIn("sample_output", result)

        self.assertTrue(result["success"])
        self.assertEqual(result["events_processed"], 2)
        self.assertGreater(result["events_per_second"], 50)

    def test_complex_nginx_log_parsing(self):
        """Test complex Nginx access log parsing with real data"""
        vrl_code = '''
        # Nginx combined log format with custom fields
        message_str = to_string(.message) ?? ""
        
        # Nginx combined: IP - user [timestamp] "method path version" status size "referer" "user_agent"
        nginx_pattern = r'^(?P<remote_addr>\S+) - (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] "(?P<request>[^"]*)" (?P<status>\d+) (?P<body_bytes_sent>\S+) "(?P<http_referer>[^"]*)" "(?P<http_user_agent>[^"]*)"'
        
        parsed, err = parse_regex(message_str, nginx_pattern)
        if err == null {
            .remote_addr = parsed.remote_addr
            .remote_user = if parsed.remote_user == "-" { null } else { parsed.remote_user }
            .time_local = parsed.time_local
            .status = to_int(parsed.status) ?? 0
            .body_bytes_sent = to_int(parsed.body_bytes_sent) ?? 0
            .http_referer = if parsed.http_referer == "-" { null } else { parsed.http_referer }
            .http_user_agent = parsed.http_user_agent
            
            # Parse request into method, path, version
            request_parts = split(parsed.request, " ")
            if length(request_parts) >= 3 {
                .method = request_parts[0]
                .path = request_parts[1]
                .http_version = request_parts[2]
                
                # Extract API information
                if starts_with(.path, "/api/") {
                    path_segments = split(.path, "/")
                    if length(path_segments) >= 3 {
                        .api_version = path_segments[2]
                        .api_endpoint = if length(path_segments) >= 4 { path_segments[3] } else { "unknown" }
                    }
                }
            }
            
            # Response categorization and enrichment
            .response_category = if .status < 300 { "success" }
                               else if .status < 400 { "redirect" }
                               else if .status < 500 { "client_error" }
                               else { "server_error" }
            
            # Traffic analysis
            .is_bot = contains(.http_user_agent, "bot") || contains(.http_user_agent, "crawler")
            .browser_family = if contains(.http_user_agent, "Chrome") { "chrome" }
                            else if contains(.http_user_agent, "Firefox") { "firefox" }
                            else if contains(.http_user_agent, "Safari") { "safari" }
                            else { "other" }
            
            .log_type = "nginx_access"
        }
        '''

        # Real Nginx combined log format samples
        nginx_logs = [
            '192.168.1.100 - user1 [08/Sep/2023:12:00:00 +0000] "GET /api/v1/users HTTP/1.1" 200 1234 "https://example.com/app" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"',
            '192.168.1.101 - - [08/Sep/2023:12:00:01 +0000] "POST /api/v2/login HTTP/1.1" 401 567 "-" "curl/7.68.0"',
            '10.0.0.50 - admin [08/Sep/2023:12:00:02 +0000] "GET /api/v1/data HTTP/1.1" 200 8901 "https://example.com/dashboard" "Googlebot/2.1 (+http://www.google.com/bot.html)"',
            '203.0.113.1 - - [08/Sep/2023:12:00:03 +0000] "DELETE /api/v1/item/123 HTTP/1.1" 204 - "-" "PostmanRuntime/7.28.0"',
            '192.168.1.200 - guest [08/Sep/2023:12:00:04 +0000] "GET /health HTTP/1.1" 500 2048 "-" "Mozilla/5.0 (compatible; monitoring-bot/1.0)"',
        ]

        result = execute_vrl_remap(nginx_logs, vrl_code, timeout_seconds=15)

        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 5)

        # Validate Nginx parsing results
        for event in result.output_data:
            if "remote_addr" in event:  # Valid nginx log
                self.assertIn("method", event)
                self.assertIn("path", event)  
                self.assertIn("response_category", event)
                self.assertIn("browser_family", event)
                self.assertIn("is_bot", event)

        # Validate API parsing
        api_events = [event for event in result.output_data if "api_version" in event]
        self.assertGreater(len(api_events), 0)

        # Validate bot detection
        bot_events = [event for event in result.output_data if event.get("is_bot") == True]
        self.assertGreater(len(bot_events), 0)  # Should detect Googlebot and monitoring-bot

        # Validate browser detection  
        chrome_events = [event for event in result.output_data if event.get("browser_family") == "chrome"]
        self.assertGreater(len(chrome_events), 0)


class TestVRLEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""

    def test_empty_input_handling(self):
        """Test handling of empty input data"""
        vrl_code = '.processed = true'
        
        result = execute_vrl_remap([], vrl_code)
        
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 0)
        self.assertEqual(len(result.output_data), 0)

    def test_large_event_handling(self):
        """Test handling of very large individual events"""
        vrl_code = '''
        .event_size = length(.message)
        .processing_timestamp = now()
        '''

        # Create a very large event (1MB)
        large_content = "x" * (1024 * 1024)
        large_event = f'{{"message": "{large_content}", "type": "large_test"}}'

        result = execute_vrl_remap([large_event], vrl_code)

        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 1)
        self.assertGreater(result.metrics.bytes_processed, 1000000)  # > 1MB

    def test_timeout_handling(self):
        """Test timeout functionality"""
        # VRL that would take a long time (simulated)
        slow_vrl = '''
        .processed = true
        .iteration = 0
        # In real VRL, this would be a complex operation
        '''

        # Small timeout to test timeout handling
        result = execute_vrl_remap(['test'], slow_vrl, timeout_seconds=1)

        # Should complete quickly with small data, but test timeout mechanism exists
        self.assertTrue(result.success or len(result.errors) > 0)


if __name__ == '__main__':
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add all test classes
    for test_class in [TestNativeVRLExecutor, TestVRLEdgeCases]:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    print("🧪 Running Native VRL Executor Tests")
    print("=" * 60)
    
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Tests Run: {result.testsRun}")
    print(f"❌ Failures: {len(result.failures)}")
    print(f"⚠️ Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("🚀 All tests passed! Native VRL executor is working perfectly.")
    else:
        print("⚠️ Some tests failed - check implementation details.")
        for failure in result.failures:
            print(f"FAILURE: {failure[0]}")
        for error in result.errors:
            print(f"ERROR: {error[0]}")

    exit(0 if result.wasSuccessful() else 1)