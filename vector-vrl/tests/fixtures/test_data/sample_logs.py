#!/usr/bin/env python3
"""
Sample log data for testing regex2vrl conversions.
Provides realistic log samples across different formats and applications.
"""

import json
import random
from datetime import datetime, timedelta


class LogDataGenerator:
    """Generate realistic sample log data for testing"""

    def __init__(self):
        self.base_time = datetime.now()
        self.ips = [
            "192.168.1.100",
            "192.168.1.101",
            "10.0.0.1",
            "10.0.0.5",
            "172.16.0.50",
            "172.16.0.100",
            "203.0.113.1",
            "198.51.100.42",
        ]
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "curl/7.68.0",
            "PostmanRuntime/7.29.0",
            "python-requests/2.28.1",
        ]
        self.usernames = ["john", "admin", "guest", "api_user", "service_account"]
        self.paths = [
            "/",
            "/index.html",
            "/api/users",
            "/api/data",
            "/health",
            "/login",
            "/dashboard",
            "/static/css/style.css",
            "/favicon.ico",
        ]

    def apache_combined_logs(self, count: int = 50) -> list[str]:
        """Generate Apache Combined Log Format entries"""
        logs = []

        for i in range(count):
            timestamp = self.base_time + timedelta(seconds=i)
            ip = random.choice(self.ips)
            user = random.choice(self.usernames + ["-"])
            method = random.choice(["GET", "POST", "PUT", "DELETE"])
            path = random.choice(self.paths)
            status = random.choice(
                [200, 200, 200, 201, 404, 500]
            )  # Weighted toward success
            size = random.randint(100, 5000)
            referrer = random.choice(["-", "https://google.com", "https://github.com"])
            user_agent = random.choice(self.user_agents)

            log = f'{ip} - {user} [{timestamp.strftime("%d/%b/%Y:%H:%M:%S +0000")}] "{method} {path} HTTP/1.1" {status} {size} "{referrer}" "{user_agent}"'
            logs.append(log)

        return logs

    def syslog_logs(self, count: int = 30) -> list[str]:
        """Generate syslog format entries"""
        logs = []
        programs = ["sshd", "nginx", "kernel", "postgres", "systemd", "docker"]
        hostnames = ["server01", "web-server", "db-server", "app-node-1"]

        for i in range(count):
            timestamp = self.base_time + timedelta(seconds=i)
            hostname = random.choice(hostnames)
            program = random.choice(programs)
            pid = random.randint(1000, 9999)

            messages = {
                "sshd": [
                    f"Accepted password for {random.choice(self.usernames)} from {random.choice(self.ips)} port 22 ssh2",
                    f"Failed password for invalid user from {random.choice(self.ips)} port 22 ssh2",
                    f"Connection closed by {random.choice(self.ips)} port 22",
                ],
                "nginx": [
                    f"{random.choice(self.ips)} - GET /health 200",
                    f"{random.choice(self.ips)} - POST /api/data 201",
                    f"worker process {pid} exited on signal 15",
                ],
                "postgres": [
                    "database connection established",
                    "checkpoint starting: time",
                    f"connection authorized: user={random.choice(self.usernames)} database=app",
                ],
            }

            message = random.choice(messages.get(program, ["system event occurred"]))

            log = f"{timestamp.strftime('%b %d %H:%M:%S')} {hostname} {program}[{pid}]: {message}"
            logs.append(log)

        return logs

    def json_application_logs(self, count: int = 40) -> list[str]:
        """Generate JSON application logs"""
        logs = []
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        services = [
            "auth-service",
            "user-service",
            "payment-service",
            "notification-service",
        ]

        for i in range(count):
            timestamp = self.base_time + timedelta(seconds=i)
            level = random.choice(levels)
            service = random.choice(services)

            base_log = {
                "timestamp": timestamp.isoformat() + "Z",
                "level": level,
                "service": service,
                "trace_id": f"trace-{random.randint(100000, 999999)}",
            }

            # Add level-specific content
            if level == "ERROR":
                base_log.update(
                    {
                        "message": "Database connection failed",
                        "error": "timeout after 30s",
                        "retry_count": random.randint(1, 5),
                        "stack_trace": "at DatabaseConnection.connect() line 45",
                    }
                )
            elif level == "WARNING":
                base_log.update(
                    {
                        "message": "High memory usage detected",
                        "memory_percent": round(random.uniform(75.0, 95.0), 1),
                        "threshold": 80.0,
                    }
                )
            elif level == "INFO":
                base_log.update(
                    {
                        "message": random.choice(
                            [
                                "User login successful",
                                "Request processed",
                                "Cache updated",
                            ]
                        ),
                        "user_id": f"user-{random.randint(10000, 99999)}",
                        "ip": random.choice(self.ips),
                        "duration_ms": random.randint(50, 500),
                    }
                )
            else:  # DEBUG
                base_log.update(
                    {
                        "message": "Cache operation",
                        "operation": random.choice(["hit", "miss", "set", "delete"]),
                        "key": f"cache-key-{random.randint(1000, 9999)}",
                        "ttl": random.randint(60, 3600),
                    }
                )

            logs.append(json.dumps(base_log))

        return logs

    def nginx_access_logs(self, count: int = 45) -> list[str]:
        """Generate Nginx access log format"""
        logs = []

        for i in range(count):
            timestamp = self.base_time + timedelta(seconds=i)
            ip = random.choice(self.ips)
            user = random.choice(self.usernames + ["-"])
            method = random.choice(["GET", "POST", "PUT", "DELETE"])
            path = random.choice(self.paths)
            status = random.choice([200, 200, 200, 201, 404, 500])
            size = random.randint(100, 5000)
            referrer = random.choice(["-", "https://google.com", "https://github.com"])
            user_agent = random.choice(self.user_agents)

            log = f'{ip} - {user} [{timestamp.strftime("%d/%b/%Y:%H:%M:%S +0000")}] "{method} {path} HTTP/1.1" {status} {size} "{referrer}" "{user_agent}"'
            logs.append(log)

        return logs

    def custom_delimited_logs(self, count: int = 25) -> list[str]:
        """Generate custom pipe-delimited logs"""
        logs = []
        components = ["WebServer", "Database", "Cache", "Queue", "Auth"]
        levels = ["INFO", "WARN", "ERROR", "DEBUG"]

        for i in range(count):
            timestamp = self.base_time + timedelta(seconds=i)
            level = random.choice(levels)
            component = random.choice(components)

            messages = {
                "WebServer": "Request processed successfully",
                "Database": "Query executed in 45ms",
                "Cache": "Cache miss for key user:12345",
                "Queue": "Message published to topic:events",
                "Auth": "Token validated for user",
            }

            message = messages.get(component, "System event")

            log = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')}|{level}|{component}|{message}"
            logs.append(log)

        return logs

    def kubernetes_pod_logs(self, count: int = 35) -> list[str]:
        """Generate Kubernetes pod log format"""
        logs = []
        streams = ["stdout", "stderr"]
        logtags = ["F", "P"]

        for i in range(count):
            timestamp = self.base_time + timedelta(seconds=i)
            stream = random.choice(streams)
            logtag = random.choice(logtags)

            # Container log content (could be JSON or plain text)
            if random.choice([True, False]):  # 50% JSON, 50% plain
                log_content = json.dumps(
                    {
                        "level": random.choice(["info", "error", "warning"]),
                        "msg": "Kubernetes application log",
                        "pod": f"app-{random.randint(1000, 9999)}",
                        "namespace": "production",
                    }
                )
            else:
                log_content = f"Application starting on port 8080 in pod app-{random.randint(1000, 9999)}"

            log = f"{timestamp.isoformat()}Z {stream} {logtag} {log_content}"
            logs.append(log)

        return logs

    def generate_test_suite(self) -> dict[str, list[str]]:
        """Generate a complete test suite of log samples"""
        return {
            "apache_combined": self.apache_combined_logs(50),
            "syslog": self.syslog_logs(30),
            "json_application": self.json_application_logs(40),
            "nginx_access": self.nginx_access_logs(45),
            "custom_delimited": self.custom_delimited_logs(25),
            "kubernetes_pods": self.kubernetes_pod_logs(35),
        }


def save_test_data_files():
    """Save test data to files for use in tests"""
    import os

    generator = LogDataGenerator()
    test_suite = generator.generate_test_suite()

    # Create test data directory
    test_data_dir = "tests/test_data/samples"
    os.makedirs(test_data_dir, exist_ok=True)

    for log_type, logs in test_suite.items():
        file_path = f"{test_data_dir}/{log_type}.log"
        with open(file_path, "w") as f:
            for log in logs:
                f.write(log + "\n")
        print(f"Generated {len(logs)} {log_type} log entries -> {file_path}")


if __name__ == "__main__":
    save_test_data_files()
