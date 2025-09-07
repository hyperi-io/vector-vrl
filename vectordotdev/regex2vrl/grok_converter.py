"""
Grok to VRL converter
Converts grok patterns to performant VRL code
"""

import re
from typing import Dict, List, Tuple, Optional
from .core import RegexToVRL, PatternAnalysis, PatternType


class GrokToVRL:
    """Convert grok patterns to performant VRL code"""
    
    # Standard grok patterns (subset of most common)
    GROK_PATTERNS = {
        # Basic patterns
        'USERNAME': r'[a-zA-Z0-9._-]+',
        'USER': r'%{USERNAME}',
        'INT': r'(?:[+-]?(?:[0-9]+))',
        'BASE10NUM': r'(?:[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+))',
        'NUMBER': r'%{BASE10NUM}',
        'BASE16NUM': r'(?:0[xX]?[0-9a-fA-F]+)',
        'POSINT': r'\b[1-9][0-9]*\b',
        'NONNEGINT': r'\b[0-9]+\b',
        'WORD': r'\b\w+\b',
        'NOTSPACE': r'\S+',
        'SPACE': r'\s*',
        'DATA': r'.*?',
        'GREEDYDATA': r'.*',
        'QUOTEDSTRING': r'"([^"\\]*(\\.[^"\\]*)*)"',
        'UUID': r'[A-Fa-f0-9]{8}-(?:[A-Fa-f0-9]{4}-){3}[A-Fa-f0-9]{12}',
        
        # Networking
        'MAC': r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}',
        'CISCOMAC': r'(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}',
        'IPV6': r'(?:(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4})',
        'IPV4': r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)',
        'IP': r'%{IPV6}|%{IPV4}',
        'HOSTNAME': r'\b[0-9A-Za-z][0-9A-Za-z-]{0,62}(?:\.[0-9A-Za-z][0-9A-Za-z-]{0,62})*(\.?|\b)',
        'HOST': r'%{HOSTNAME}',
        'IPORHOST': r'%{HOSTNAME}|%{IP}',
        'HOSTPORT': r'%{IPORHOST}:%{POSINT}',
        
        # Paths
        'PATH': r'(?:%{UNIXPATH}|%{WINPATH})',
        'UNIXPATH': r'(?:/[\w_%!$@:.,-]+)+',
        'WINPATH': r'(?:[A-Za-z]+:|\\)(?:\\[^\\?*]*)+',
        'TTY': r'(?:/dev/(?:pts|tty(?:[pq])?)(?:\w+)?/?(?:[0-9]+))',
        
        # Timestamps
        'MONTH': r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b',
        'MONTHNUM': r'(?:0?[1-9]|1[0-2])',
        'MONTHDAY': r'(?:(?:0[1-9])|(?:[12][0-9])|(?:3[01])|[1-9])',
        'DAY': r'(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)',
        'YEAR': r'(?:[0-9]{4})',
        'HOUR': r'(?:2[0123]|[01]?[0-9])',
        'MINUTE': r'(?:[0-5][0-9])',
        'SECOND': r'(?:(?:[0-5][0-9]|60)(?:[.,][0-9]+)?)',
        'TIME': r'%{HOUR}:%{MINUTE}:%{SECOND}',
        'DATE_US': r'%{MONTHNUM}[/-]%{MONTHDAY}[/-]%{YEAR}',
        'DATE_EU': r'%{MONTHDAY}[/-]%{MONTHNUM}[/-]%{YEAR}',
        'ISO8601_TIMEZONE': r'(?:Z|[+-]%{HOUR}:%{MINUTE})',
        'ISO8601_SECOND': r'%{SECOND}',
        'TIMESTAMP_ISO8601': r'%{YEAR}-%{MONTHNUM}-%{MONTHDAY}[T ]%{HOUR}:%{MINUTE}:%{ISO8601_SECOND}%{ISO8601_TIMEZONE}?',
        'DATE': r'%{DATE_US}|%{DATE_EU}',
        'DATESTAMP': r'%{DATE}[- ]%{TIME}',
        'SYSLOGTIMESTAMP': r'%{MONTH} +%{MONTHDAY} %{TIME}',
        'HTTPDATE': r'%{MONTHDAY}/%{MONTH}/%{YEAR}:%{TIME} %{INT}',
        
        # Syslog
        'SYSLOGBASE': r'%{SYSLOGTIMESTAMP:timestamp} (?:%{SYSLOGFACILITY} )?%{SYSLOGHOST:logsource} %{SYSLOGPROG}:',
        'SYSLOGPROG': r'%{PROG:program}(?:\[%{POSINT:pid}\])?',
        'SYSLOGHOST': r'%{IPORHOST}',
        'SYSLOGFACILITY': r'<%{NONNEGINT:facility}.%{NONNEGINT:priority}>',
        'PROG': r'[\w._/-]+',
        
        # Log levels
        'LOGLEVEL': r'(?:ERROR|WARN|WARNING|INFO|DEBUG|TRACE|FATAL|CRITICAL)',
        
        # Web logs
        'HTTPD_COMMONLOG': r'%{IPORHOST:clientip} %{USER:ident} %{USER:auth} \[%{HTTPDATE:timestamp}\] "(?:%{WORD:verb} %{NOTSPACE:request}(?: HTTP/%{NUMBER:httpversion})?|%{DATA:rawrequest})" %{NUMBER:response} (?:%{NUMBER:bytes}|-)',
        'HTTPD_COMBINEDLOG': r'%{HTTPD_COMMONLOG} %{QS:referrer} %{QS:agent}',
        'QS': r'%{QUOTEDSTRING}',
        
        # Email
        'EMAILADDRESS': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        'EMAILLOCALPART': r'[a-zA-Z0-9._%+-]+',
        'EMAILDOMAIN': r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        
        # URIs
        'URI': r'%{URIPROTO}://(?:%{USER}(?::[^@]*)?@)?(?:%{URIHOST})?(?:%{URIPATHPARAM})?',
        'URIPROTO': r'[a-zA-Z]+(?:\+[a-zA-Z]+)?',
        'URIHOST': r'%{IPORHOST}(?::%{POSINT:port})?',
        'URIPATH': r'(?:/[A-Za-z0-9$.+!*\'(){},~:;=@#%_-]*)+',
        'URIPATHPARAM': r'%{URIPATH}(?:\?%{URIPARAM})?',
        'URIPARAM': r'[A-Za-z0-9$.+!*\'(){},~@#%&/=:;_-]*',
    }
    
    def __init__(self):
        self.regex_converter = RegexToVRL()
        self._expanded_patterns = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile and expand all grok patterns"""
        for name, pattern in self.GROK_PATTERNS.items():
            self._expanded_patterns[name] = self._expand_pattern(pattern)
    
    def _expand_pattern(self, pattern: str) -> str:
        """Recursively expand grok pattern references"""
        # Keep expanding until no more %{} references
        max_iterations = 10
        iteration = 0
        
        while '%{' in pattern and iteration < max_iterations:
            # Find all pattern references
            for match in re.finditer(r'%{([A-Z0-9_]+)(?::([a-zA-Z0-9_]+))?}', pattern):
                full_match = match.group(0)
                pattern_name = match.group(1)
                field_name = match.group(2)
                
                if pattern_name in self.GROK_PATTERNS:
                    replacement = self.GROK_PATTERNS[pattern_name]
                    # If there's a field name, make it a named group
                    if field_name:
                        replacement = f'(?P<{field_name}>{replacement})'
                    pattern = pattern.replace(full_match, replacement)
            
            iteration += 1
        
        return pattern
    
    def convert(self, grok_pattern: str, input_field: str = '.message') -> str:
        """
        Convert a grok pattern to VRL code
        
        Args:
            grok_pattern: The grok pattern to convert
            input_field: The VRL field to parse (default: .message)
        
        Returns:
            Generated VRL code
        """
        # Extract field names and expand pattern
        fields = self._extract_fields(grok_pattern)
        expanded_pattern = self._expand_grok_to_regex(grok_pattern)
        
        # Check for common log formats that have built-in parsers
        if self._is_apache_format(grok_pattern):
            return self._generate_apache_parser(input_field)
        elif self._is_nginx_format(grok_pattern):
            return self._generate_nginx_parser(input_field)
        elif self._is_syslog_format(grok_pattern):
            return self._generate_syslog_parser(input_field)
        elif self._is_json_format(grok_pattern):
            return self._generate_json_parser(input_field)
        
        # Generate optimized VRL based on the pattern structure
        return self._generate_optimized_vrl(grok_pattern, fields, expanded_pattern, input_field)
    
    def _extract_fields(self, pattern: str) -> List[Tuple[str, str]]:
        """Extract field names and their patterns from grok pattern"""
        fields = []
        
        # Find all pattern references with field names
        for match in re.finditer(r'%{([A-Z0-9_]+):([a-zA-Z0-9_]+)}', pattern):
            pattern_name = match.group(1)
            field_name = match.group(2)
            fields.append((field_name, pattern_name))
        
        return fields
    
    def _expand_grok_to_regex(self, grok_pattern: str) -> str:
        """Expand a grok pattern to a full regex pattern"""
        pattern = grok_pattern
        
        # Expand all grok pattern references
        max_iterations = 10
        iteration = 0
        
        while '%{' in pattern and iteration < max_iterations:
            for match in re.finditer(r'%{([A-Z0-9_]+)(?::([a-zA-Z0-9_]+))?}', pattern):
                full_match = match.group(0)
                pattern_name = match.group(1)
                field_name = match.group(2)
                
                if pattern_name in self._expanded_patterns:
                    replacement = self._expanded_patterns[pattern_name]
                    if field_name:
                        replacement = f'(?P<{field_name}>{replacement})'
                    pattern = pattern.replace(full_match, replacement)
            
            iteration += 1
        
        return pattern
    
    def _is_apache_format(self, pattern: str) -> bool:
        """Check if pattern is Apache log format"""
        apache_indicators = ['HTTPD_COMMONLOG', 'HTTPD_COMBINEDLOG', 'apache']
        return any(ind in pattern for ind in apache_indicators)
    
    def _is_nginx_format(self, pattern: str) -> bool:
        """Check if pattern is Nginx log format"""
        nginx_indicators = ['nginx', 'NGINXACCESS']
        return any(ind in pattern for ind in nginx_indicators)
    
    def _is_syslog_format(self, pattern: str) -> bool:
        """Check if pattern is syslog format"""
        syslog_indicators = ['SYSLOGBASE', 'SYSLOGTIMESTAMP', 'syslog']
        return any(ind in pattern for ind in syslog_indicators)
    
    def _is_json_format(self, pattern: str) -> bool:
        """Check if pattern expects JSON"""
        return 'JSON' in pattern or 'json' in pattern.lower()
    
    def _generate_apache_parser(self, input_field: str) -> str:
        """Generate VRL for Apache logs"""
        return f'''# Apache log format detected
parsed = parse_apache_log!({input_field}, format: "combined")
. = merge(., parsed)
'''
    
    def _generate_nginx_parser(self, input_field: str) -> str:
        """Generate VRL for Nginx logs"""
        return f'''# Nginx log format detected
parsed = parse_nginx_log!({input_field}, format: "combined")
. = merge(., parsed)
'''
    
    def _generate_syslog_parser(self, input_field: str) -> str:
        """Generate VRL for syslog"""
        return f'''# Syslog format detected
parsed = parse_syslog!({input_field})
. = merge(., parsed)
'''
    
    def _generate_json_parser(self, input_field: str) -> str:
        """Generate VRL for JSON"""
        return f'''# JSON format expected
message_str = string!({input_field})
if starts_with(message_str, "{{") {{
    parsed = parse_json!(message_str)
    . = merge(., parsed)
}}
'''
    
    def _generate_optimized_vrl(self, grok_pattern: str, fields: List[Tuple[str, str]], 
                                regex_pattern: str, input_field: str) -> str:
        """Generate optimized VRL code for the grok pattern"""
        
        vrl_code = f'''# Grok pattern: {grok_pattern}
# Fields to extract: {', '.join([f[0] for f in fields])}
# Performance-optimized VRL (avoiding regex)

message_str = string!({input_field})
'''
        
        # Analyze what we're extracting
        field_types = {f[1] for f in fields}
        
        # Generate extraction based on pattern types
        if 'TIMESTAMP_ISO8601' in field_types or 'SYSLOGTIMESTAMP' in field_types:
            vrl_code += self._generate_timestamp_extraction(fields)
        
        if 'IP' in field_types or 'IPV4' in field_types or 'IPORHOST' in field_types:
            vrl_code += self._generate_ip_extraction(fields)
        
        if 'LOGLEVEL' in field_types:
            vrl_code += self._generate_loglevel_extraction(fields)
        
        if 'NUMBER' in field_types or 'INT' in field_types:
            vrl_code += self._generate_number_extraction(fields)
        
        # If we have GREEDYDATA, it's usually the message at the end
        if 'GREEDYDATA' in field_types:
            vrl_code += self._generate_message_extraction(fields)
        
        # Default to delimiter-based extraction if pattern is simple
        if not any(complex in field_types for complex in ['GREEDYDATA', 'DATA', 'QUOTEDSTRING']):
            vrl_code += self._generate_delimiter_extraction(fields)
        
        return vrl_code
    
    def _generate_timestamp_extraction(self, fields: List[Tuple[str, str]]) -> str:
        """Generate timestamp extraction code"""
        timestamp_field = next((f[0] for f in fields if 'TIMESTAMP' in f[1]), 'timestamp')
        
        return f'''
# Extract timestamp
parts = split(message_str, " ")
if length(parts) >= 2 {{
    # Try ISO8601 format
    ts, err = parse_timestamp(parts[0], format: "%+")
    if err == null {{
        .{timestamp_field} = ts
    }} else {{
        # Try syslog format
        ts, err = parse_timestamp(join(parts[0:3], " "), format: "%b %d %H:%M:%S")
        if err == null {{
            .{timestamp_field} = ts
        }}
    }}
}}
'''
    
    def _generate_ip_extraction(self, fields: List[Tuple[str, str]]) -> str:
        """Generate IP extraction code"""
        ip_field = next((f[0] for f in fields if 'IP' in f[1] or 'HOST' in f[1]), 'ip')
        
        return f'''
# Extract IP address
parts = split(message_str, " ")
for part in parts {{
    if is_ipv4(part) {{
        .{ip_field} = part
        break
    }}
}}
'''
    
    def _generate_loglevel_extraction(self, fields: List[Tuple[str, str]]) -> str:
        """Generate log level extraction code"""
        level_field = next((f[0] for f in fields if 'LOGLEVEL' in f[1]), 'level')
        
        return f'''
# Extract log level
upper_msg = upcase(message_str)
if contains(upper_msg, "ERROR") || contains(upper_msg, "FATAL") {{
    .{level_field} = "ERROR"
}} else if contains(upper_msg, "WARN") {{
    .{level_field} = "WARN"
}} else if contains(upper_msg, "INFO") {{
    .{level_field} = "INFO"
}} else if contains(upper_msg, "DEBUG") {{
    .{level_field} = "DEBUG"
}}
'''
    
    def _generate_number_extraction(self, fields: List[Tuple[str, str]]) -> str:
        """Generate number extraction code"""
        return '''
# Extract numeric fields
parts = split(message_str, " ")
for part in parts {
    # Check if part is numeric
    num, err = to_int(part)
    if err == null {
        # Store number (position-dependent)
        # TODO: Map to specific field based on position
    }
}
'''
    
    def _generate_message_extraction(self, fields: List[Tuple[str, str]]) -> str:
        """Generate message/GREEDYDATA extraction"""
        msg_field = next((f[0] for f in fields if 'GREEDYDATA' in f[1] or 'DATA' in f[1]), 'message')
        
        return f'''
# Extract message (usually everything after structured fields)
# This typically comes after timestamp, level, etc.
parts = split(message_str, " ")
if length(parts) > 3 {{
    .{msg_field} = join(parts[3:], " ")
}}
'''
    
    def _generate_delimiter_extraction(self, fields: List[Tuple[str, str]]) -> str:
        """Generate simple delimiter-based extraction"""
        return f'''
# Delimiter-based field extraction
parts = split(message_str, " ")

# Map parts to fields based on position
# Fields: {', '.join([f[0] for f in fields])}
if length(parts) >= {len(fields)} {{
'''
        
        # Add field assignments
        code = ""
        for i, (field_name, pattern_type) in enumerate(fields):
            if 'INT' in pattern_type or 'NUMBER' in pattern_type:
                code += f'    .{field_name} = to_int!(parts[{i}])\n'
            else:
                code += f'    .{field_name} = parts[{i}]\n'
        
        return code + '}\n'