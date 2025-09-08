"""
Advanced pattern analyzer for regex2vrl
Decomposes complex regex and grok patterns into high-performance VRL code
Version: 2.0.0 - High Performance Focused
"""

import re
from typing import List, Dict, Tuple, Optional, Set, Union
from dataclasses import dataclass
from enum import Enum


class LogFormat(Enum):
    """Detected log format types for built-in parser selection"""
    JSON = "json"
    APACHE_COMBINED = "apache_combined"
    APACHE_COMMON = "apache_common"
    NGINX_ACCESS = "nginx_access"
    NGINX_ERROR = "nginx_error"
    SYSLOG_RFC3164 = "syslog_rfc3164"
    SYSLOG_RFC5424 = "syslog_rfc5424"
    KEY_VALUE = "key_value"
    CSV = "csv"
    LOGFMT = "logfmt"
    AWS_ALB = "aws_alb"
    AWS_VPC_FLOW = "aws_vpc_flow"
    DOCKER_JSON = "docker_json"
    KUBERNETES_CRI = "kubernetes_cri"
    CUSTOM_DELIMITED = "custom_delimited"
    STRUCTURED_FIELDS = "structured_fields"
    UNSTRUCTURED = "unstructured"


@dataclass
class FieldExtraction:
    """Represents a field to extract with its characteristics"""
    name: str
    position: Optional[int] = None
    delimiter: Optional[str] = None
    field_type: str = "string"  # string, number, timestamp, ip, boolean
    pattern_hint: Optional[str] = None
    validation_range: Optional[Tuple[int, int]] = None
    is_optional: bool = False


@dataclass
class PatternAnalysisResult:
    """Complete analysis of a regex/grok pattern"""
    original_pattern: str
    detected_format: LogFormat
    confidence: float  # 0.0 to 1.0
    fields_to_extract: List[FieldExtraction]
    suggested_delimiters: List[str]
    complexity_score: int  # 1-10, higher is more complex
    estimated_thg: int  # Expected THG performance
    requires_fallback: bool = False
    builtin_parser: Optional[str] = None


class UniversalPatternAnalyzer:
    """
    Analyzes regex and grok patterns to generate high-performance VRL code.
    Never uses regex functions - only built-in parsers and string operations.
    """
    
    def __init__(self):
        # Built-in parser detection patterns
        self.builtin_patterns = {
            LogFormat.JSON: [
                r'^\s*\{.*\}\s*$',
                r'json',
                r'^\s*\[.*\]\s*$'
            ],
            LogFormat.APACHE_COMBINED: [
                r'HTTPD_COMBINEDLOG',
                r'remote_addr.*remote_user.*time_local.*request.*status.*body_bytes_sent.*http_referer.*http_user_agent'
            ],
            LogFormat.APACHE_COMMON: [
                r'HTTPD_COMMONLOG',
                r'remote_addr.*remote_user.*time_local.*request.*status.*body_bytes_sent'
            ],
            LogFormat.NGINX_ACCESS: [
                r'nginx.*access',
                r'remote_addr.*request_time'
            ],
            LogFormat.SYSLOG_RFC3164: [
                r'SYSLOG',
                r'timestamp.*hostname.*program.*message',
                r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}'
            ],
            LogFormat.KEY_VALUE: [
                r'key.*=.*value',
                r'parse_key_value',
                r'\w+=\w+'
            ],
            LogFormat.CSV: [
                r'csv',
                r'comma.*separated',
                r'(?:[^,]*,){2,}'
            ],
            LogFormat.AWS_ALB: [
                r'aws.*alb',
                r'elb.*access'
            ],
            LogFormat.AWS_VPC_FLOW: [
                r'vpc.*flow',
                r'srcaddr.*dstaddr.*srcport.*dstport'
            ]
        }
        
        # Common field patterns and their types
        self.field_type_patterns = {
            'timestamp': [
                r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',
                r'timestamp', r'time', r'date', r'datetime',
                r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}'
            ],
            'ip': [
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
                r'ip', r'addr', r'host', r'client', r'server'
            ],
            'number': [
                r'\d+',
                r'status', r'code', r'port', r'size', r'bytes',
                r'count', r'length', r'duration', r'pid'
            ],
            'boolean': [
                r'true|false', r'yes|no', r'on|off',
                r'enabled', r'disabled', r'success', r'failed'
            ]
        }

    def analyze_pattern(self, pattern: str, sample_logs: List[str] = None) -> PatternAnalysisResult:
        """
        Analyze a regex or grok pattern to determine the best VRL conversion approach.
        Uses sample logs if provided to improve accuracy.
        """
        # Clean and normalize pattern
        normalized_pattern = self._normalize_pattern(pattern)
        
        # Detect format using multiple strategies
        detected_format = self._detect_log_format(normalized_pattern, sample_logs)
        confidence = self._calculate_confidence(normalized_pattern, detected_format, sample_logs)
        
        # Extract field information
        fields = self._extract_field_information(normalized_pattern, detected_format)
        
        # Analyze delimiters
        delimiters = self._detect_delimiters(normalized_pattern, sample_logs)
        
        # Calculate complexity and performance
        complexity = self._calculate_complexity(normalized_pattern, fields)
        estimated_thg = self._estimate_thg_performance(detected_format, complexity, len(fields))
        
        # Determine if built-in parser can be used
        builtin_parser = self._select_builtin_parser(detected_format, confidence)
        
        return PatternAnalysisResult(
            original_pattern=pattern,
            detected_format=detected_format,
            confidence=confidence,
            fields_to_extract=fields,
            suggested_delimiters=delimiters,
            complexity_score=complexity,
            estimated_thg=estimated_thg,
            requires_fallback=complexity > 7,
            builtin_parser=builtin_parser
        )

    def _normalize_pattern(self, pattern: str) -> str:
        """Normalize pattern by removing common regex artifacts"""
        # Remove anchors
        pattern = re.sub(r'^[\^]', '', pattern)
        pattern = re.sub(r'[\$]$', '', pattern)
        
        # Convert common grok patterns to readable form
        grok_replacements = {
            r'%\{TIMESTAMP_ISO8601:(\w+)\}': r'(?P<\1>timestamp_iso8601)',
            r'%\{SYSLOGTIMESTAMP:(\w+)\}': r'(?P<\1>syslog_timestamp)',
            r'%\{IPV4:(\w+)\}': r'(?P<\1>ipv4)',
            r'%\{HOSTNAME:(\w+)\}': r'(?P<\1>hostname)',
            r'%\{WORD:(\w+)\}': r'(?P<\1>word)',
            r'%\{INT:(\w+)\}': r'(?P<\1>integer)',
            r'%\{GREEDYDATA:(\w+)\}': r'(?P<\1>greedydata)',
            r'%\{DATA:(\w+)\}': r'(?P<\1>data)',
            r'%\{QUOTEDSTRING:(\w+)\}': r'(?P<\1>quotedstring)',
            r'%\{HTTPD_COMMONLOG\}': 'apache_common_log',
            r'%\{HTTPD_COMBINEDLOG\}': 'apache_combined_log'
        }
        
        for grok_pattern, replacement in grok_replacements.items():
            pattern = re.sub(grok_pattern, replacement, pattern)
        
        return pattern

    def _detect_log_format(self, pattern: str, sample_logs: List[str] = None) -> LogFormat:
        """Detect the most likely log format"""
        scores = {fmt: 0 for fmt in LogFormat}
        
        # Pattern-based detection
        pattern_lower = pattern.lower()
        
        for log_format, indicators in self.builtin_patterns.items():
            for indicator in indicators:
                if isinstance(indicator, str):
                    if indicator.lower() in pattern_lower:
                        scores[log_format] += 3
                else:
                    # For regex indicators (not used for matching, just scoring)
                    indicator_lower = str(indicator).lower()
                    if any(word in pattern_lower for word in indicator_lower.split('.*')):
                        scores[log_format] += 2

        # Sample-based detection if provided
        if sample_logs:
            for sample in sample_logs[:5]:  # Limit analysis to first 5 samples
                sample_lower = sample.lower()
                
                # JSON detection
                if sample.strip().startswith('{') and sample.strip().endswith('}'):
                    scores[LogFormat.JSON] += 5
                elif sample.strip().startswith('[') and sample.strip().endswith(']'):
                    scores[LogFormat.JSON] += 3
                
                # Key-value detection
                if '=' in sample and len(re.findall(r'\w+=\w+', sample)) >= 2:
                    scores[LogFormat.KEY_VALUE] += 4
                
                # CSV detection
                if ',' in sample and len(sample.split(',')) >= 3:
                    scores[LogFormat.CSV] += 3
                
                # Apache/Nginx detection
                if '"GET ' in sample or '"POST ' in sample:
                    if 'Mozilla' in sample or 'curl' in sample:
                        scores[LogFormat.APACHE_COMBINED] += 4
                    else:
                        scores[LogFormat.APACHE_COMMON] += 3
                
                # Syslog detection
                if re.match(r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', sample):
                    scores[LogFormat.SYSLOG_RFC3164] += 5

        # Return format with highest score, defaulting to UNSTRUCTURED
        if max(scores.values()) == 0:
            return LogFormat.UNSTRUCTURED
        
        return max(scores, key=scores.get)

    def _calculate_confidence(self, pattern: str, detected_format: LogFormat, 
                           sample_logs: List[str] = None) -> float:
        """Calculate confidence in format detection (0.0 to 1.0)"""
        confidence = 0.3  # Base confidence
        
        # High confidence for obvious patterns
        if detected_format == LogFormat.JSON and ('{' in pattern and '}' in pattern):
            confidence += 0.5
        elif detected_format == LogFormat.KEY_VALUE and '=' in pattern:
            confidence += 0.4
        elif 'apache' in pattern.lower() or 'nginx' in pattern.lower():
            confidence += 0.4
        elif 'syslog' in pattern.lower():
            confidence += 0.4
        
        # Boost confidence if we have sample logs that match
        if sample_logs:
            matching_samples = 0
            for sample in sample_logs[:5]:
                if self._sample_matches_format(sample, detected_format):
                    matching_samples += 1
            confidence += (matching_samples / min(len(sample_logs), 5)) * 0.3
        
        return min(confidence, 1.0)

    def _sample_matches_format(self, sample: str, log_format: LogFormat) -> bool:
        """Check if a sample log matches the detected format"""
        sample = sample.strip()
        
        if log_format == LogFormat.JSON:
            return (sample.startswith('{') and sample.endswith('}')) or \
                   (sample.startswith('[') and sample.endswith(']'))
        elif log_format == LogFormat.KEY_VALUE:
            return '=' in sample and len(re.findall(r'\w+=\w+', sample)) >= 1
        elif log_format == LogFormat.CSV:
            return ',' in sample and len(sample.split(',')) >= 2
        elif log_format in [LogFormat.APACHE_COMBINED, LogFormat.APACHE_COMMON]:
            return '"GET ' in sample or '"POST ' in sample
        elif log_format == LogFormat.SYSLOG_RFC3164:
            return bool(re.match(r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', sample))
        
        return False

    def _extract_field_information(self, pattern: str, log_format: LogFormat) -> List[FieldExtraction]:
        """Extract field information from the pattern"""
        fields = []
        
        # Extract named groups
        named_groups = re.findall(r'\(\?P<(\w+)>', pattern)
        
        for i, group_name in enumerate(named_groups):
            field_type = self._infer_field_type(group_name, pattern)
            
            field = FieldExtraction(
                name=group_name,
                position=i,
                field_type=field_type,
                is_optional='?' in pattern  # Simple heuristic
            )
            
            # Add validation ranges for numeric fields
            if field_type == 'number':
                if 'status' in group_name.lower():
                    field.validation_range = (100, 599)
                elif 'port' in group_name.lower():
                    field.validation_range = (1, 65535)
            
            fields.append(field)
        
        # If no named groups, try to infer from format
        if not fields and log_format != LogFormat.UNSTRUCTURED:
            fields = self._infer_fields_from_format(log_format)
        
        return fields

    def _infer_field_type(self, field_name: str, pattern: str) -> str:
        """Infer field type from name and context"""
        field_name_lower = field_name.lower()
        
        for field_type, indicators in self.field_type_patterns.items():
            for indicator in indicators:
                if isinstance(indicator, str) and indicator in field_name_lower:
                    return field_type
        
        return 'string'

    def _infer_fields_from_format(self, log_format: LogFormat) -> List[FieldExtraction]:
        """Infer standard fields for known log formats"""
        format_fields = {
            LogFormat.APACHE_COMBINED: [
                FieldExtraction("remote_addr", 0, field_type="ip"),
                FieldExtraction("remote_user", 1, field_type="string"),
                FieldExtraction("time_local", 2, field_type="timestamp"),
                FieldExtraction("request", 3, field_type="string"),
                FieldExtraction("status", 4, field_type="number", validation_range=(100, 599)),
                FieldExtraction("body_bytes_sent", 5, field_type="number"),
                FieldExtraction("http_referer", 6, field_type="string"),
                FieldExtraction("http_user_agent", 7, field_type="string"),
            ],
            LogFormat.SYSLOG_RFC3164: [
                FieldExtraction("timestamp", 0, field_type="timestamp"),
                FieldExtraction("hostname", 1, field_type="string"),
                FieldExtraction("program", 2, field_type="string"),
                FieldExtraction("message", 3, field_type="string"),
            ]
        }
        
        return format_fields.get(log_format, [])

    def _detect_delimiters(self, pattern: str, sample_logs: List[str] = None) -> List[str]:
        """Detect likely delimiters for string splitting"""
        delimiters = []
        
        # Common delimiters in order of preference
        common_delims = [' ', '\t', ',', '|', ';', ':']
        
        for delim in common_delims:
            if delim in pattern:
                delimiters.append(delim)
        
        # Analyze sample logs for delimiter frequency
        if sample_logs:
            delimiter_counts = {delim: 0 for delim in common_delims}
            
            for sample in sample_logs[:5]:
                for delim in common_delims:
                    delimiter_counts[delim] += sample.count(delim)
            
            # Add frequently occurring delimiters
            avg_occurrences = sum(delimiter_counts.values()) / len(delimiter_counts)
            for delim, count in delimiter_counts.items():
                if count > avg_occurrences and delim not in delimiters:
                    delimiters.append(delim)
        
        return delimiters or [' ']  # Default to space

    def _calculate_complexity(self, pattern: str, fields: List[FieldExtraction]) -> int:
        """Calculate pattern complexity score (1-10)"""
        complexity = 1
        
        # Base complexity from pattern length
        if len(pattern) > 100:
            complexity += 2
        elif len(pattern) > 50:
            complexity += 1
        
        # Add complexity for number of fields
        complexity += min(len(fields), 3)
        
        # Add complexity for special regex features
        complex_features = ['(?:', '(?=', '(?!', '*', '+', '|', '{', '}']
        for feature in complex_features:
            if feature in pattern:
                complexity += 1
        
        return min(complexity, 10)

    def _estimate_thg_performance(self, log_format: LogFormat, complexity: int, 
                                num_fields: int) -> int:
        """Estimate THG performance rating"""
        base_rating = 350  # Target high performance
        
        # Built-in parsers get maximum rating
        if log_format in [LogFormat.JSON, LogFormat.KEY_VALUE, LogFormat.CSV,
                         LogFormat.APACHE_COMBINED, LogFormat.SYSLOG_RFC3164]:
            return base_rating
        
        # Reduce rating based on complexity
        base_rating -= complexity * 20
        base_rating -= num_fields * 5
        
        # Minimum performance target
        return max(base_rating, 250)

    def _select_builtin_parser(self, log_format: LogFormat, confidence: float) -> Optional[str]:
        """Select appropriate built-in parser if available"""
        if confidence < 0.6:
            return None
        
        parser_map = {
            LogFormat.JSON: "parse_json",
            LogFormat.KEY_VALUE: "parse_key_value", 
            LogFormat.CSV: "parse_csv",
            LogFormat.LOGFMT: "parse_logfmt",
            LogFormat.SYSLOG_RFC3164: "parse_syslog",
            LogFormat.SYSLOG_RFC5424: "parse_syslog",
            LogFormat.APACHE_COMBINED: "parse_apache_log",
            LogFormat.APACHE_COMMON: "parse_apache_log",
            LogFormat.NGINX_ACCESS: "parse_nginx_log",
            LogFormat.AWS_ALB: "parse_aws_alb_log",
            LogFormat.AWS_VPC_FLOW: "parse_aws_vpc_flow_log"
        }
        
        return parser_map.get(log_format)