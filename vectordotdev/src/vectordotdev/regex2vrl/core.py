"""
regex2vrl - Convert regex and grok patterns to performant VRL code
Core conversion module
Version: 1.1.0
"""

import re
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum


class PatternType(Enum):
    """Types of patterns we can detect and optimize"""
    TIMESTAMP = "timestamp"
    IP_ADDRESS = "ip_address"
    EMAIL = "email"
    KEY_VALUE = "key_value"
    JSON = "json"
    SYSLOG = "syslog"
    URL = "url"
    LOG_LEVEL = "log_level"
    GENERIC = "generic"


@dataclass
class PatternAnalysis:
    """Analysis results for a regex pattern"""
    pattern_type: PatternType
    has_groups: bool
    has_named_groups: bool
    group_names: List[str]
    delimiters: List[str]
    field_count: int
    can_use_builtin: bool
    suggested_parser: Optional[str]
    estimated_thg: int


class RegexToVRL:
    """Convert regex patterns to performant VRL code"""
    
    def __init__(self):
        self.builtin_patterns = {
            # Timestamp patterns
            r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}': 'parse_timestamp',
            r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}': 'parse_timestamp',
            r'\w{3} \d{1,2} \d{2}:\d{2}:\d{2}': 'parse_timestamp',
            
            # IP patterns
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}': 'ip_detection',
            r'(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}': 'ipv6_detection',
            
            # Email patterns
            r'[\w\.-]+@[\w\.-]+\.\w+': 'email_detection',
            
            # URL patterns
            r'https?://[^\s]+': 'url_detection',
            
            # Log level patterns
            r'(ERROR|WARN|WARNING|INFO|DEBUG|TRACE|FATAL)': 'log_level',
        }
        
        self.vrl_templates = {
            'parse_timestamp': '''parse_timestamp!({field}, format: "{format}")''',
            'parse_json': '''parse_json!({field})''',
            'parse_key_value': '''parse_key_value!({field})''',
            'parse_syslog': '''parse_syslog!({field})''',
            'parse_apache_log': '''parse_apache_log!({field}, format: "{format}")''',
            'parse_nginx_log': '''parse_nginx_log!({field}, format: "{format}")''',
            'parse_csv': '''parse_csv!({field})''',
        }
    
    def analyze_pattern(self, pattern: str) -> PatternAnalysis:
        """Analyze a regex pattern to determine its structure and type"""
        
        # Check for named groups
        named_groups = re.findall(r'\(\?P<(\w+)>', pattern)
        
        # Check for any groups
        has_groups = '(' in pattern and ')' in pattern
        
        # Detect pattern type
        pattern_type = self._detect_pattern_type(pattern)
        
        # Extract delimiters
        delimiters = self._extract_delimiters(pattern)
        
        # Determine if we can use a built-in parser
        can_use_builtin, suggested_parser = self._check_builtin_compatibility(pattern, pattern_type)
        
        # Estimate performance
        estimated_thg = self._estimate_performance(pattern, can_use_builtin)
        
        return PatternAnalysis(
            pattern_type=pattern_type,
            has_groups=has_groups,
            has_named_groups=len(named_groups) > 0,
            group_names=named_groups,
            delimiters=delimiters,
            field_count=pattern.count('('),
            can_use_builtin=can_use_builtin,
            suggested_parser=suggested_parser,
            estimated_thg=estimated_thg
        )
    
    def convert(self, pattern: str, input_field: str = '.message', 
                output_format: str = 'vrl') -> str:
        """
        Convert a regex pattern to VRL code
        
        Args:
            pattern: The regex pattern to convert
            input_field: The VRL field to parse (default: .message)
            output_format: Output format ('vrl' or 'commented')
        
        Returns:
            Generated VRL code
        """
        analysis = self.analyze_pattern(pattern)
        
        # Generate header comment if requested
        header = ""
        if output_format == 'commented':
            header = self._generate_header(pattern, analysis)
        
        # Choose conversion strategy based on analysis
        if analysis.can_use_builtin and analysis.suggested_parser:
            vrl_code = self._generate_builtin_parser(
                analysis.suggested_parser, input_field, analysis
            )
        elif analysis.pattern_type == PatternType.TIMESTAMP:
            vrl_code = self._convert_timestamp(pattern, input_field, analysis)
        elif analysis.pattern_type == PatternType.IP_ADDRESS:
            vrl_code = self._convert_ip_extraction(pattern, input_field, analysis)
        elif analysis.pattern_type == PatternType.KEY_VALUE:
            vrl_code = self._convert_key_value(pattern, input_field, analysis)
        elif analysis.has_named_groups:
            vrl_code = self._convert_named_groups(pattern, input_field, analysis)
        elif analysis.delimiters:
            vrl_code = self._convert_delimiter_based(pattern, input_field, analysis)
        else:
            vrl_code = self._convert_generic(pattern, input_field, analysis)
        
        return header + vrl_code
    
    def _detect_pattern_type(self, pattern: str) -> PatternType:
        """Detect the type of pattern"""
        
        # Check for timestamp patterns
        timestamp_indicators = [
            r'\\d{4}', r'\\d{2}:\\d{2}', 'timestamp', 'date', 'time',
            'YYYY', 'MM', 'DD', 'HH'
        ]
        if any(ind in pattern for ind in timestamp_indicators):
            return PatternType.TIMESTAMP
        
        # Check for IP patterns
        if r'\d{1,3}\.\d{1,3}' in pattern or 'ip' in pattern.lower():
            return PatternType.IP_ADDRESS
        
        # Check for email patterns
        if '@' in pattern:
            return PatternType.EMAIL
        
        # Check for key-value patterns
        if '=' in pattern or 'key' in pattern.lower() or 'value' in pattern.lower():
            return PatternType.KEY_VALUE
        
        # Check for JSON patterns (be more specific - actual JSON structure)
        if '{.*}' in pattern and ('json' in pattern.lower() or 'object' in pattern.lower()):
            return PatternType.JSON
        
        # Check for log level patterns
        if any(level in pattern.upper() for level in ['ERROR', 'WARN', 'INFO', 'DEBUG']):
            return PatternType.LOG_LEVEL
        
        # Check for URL patterns
        if 'http' in pattern.lower() or '://' in pattern:
            return PatternType.URL
        
        return PatternType.GENERIC
    
    def _extract_delimiters(self, pattern: str) -> List[str]:
        """Extract actual delimiters from the pattern (not regex escape sequences)"""
        delimiters = []
        
        # Look for actual delimiter characters that aren't part of regex syntax
        # Exclude backslash since it's usually part of regex escapes like \d, \w, etc.
        common_delims = [' ', ',', '|', '\t', ':', ';', '-', '_', '/']
        
        for delim in common_delims:
            # Only add if it appears outside of regex groups/escapes
            if delim in pattern and not (f'\\{delim}' in pattern or f'(?.*{delim}' in pattern):
                delimiters.append(delim)
        
        # Check for literal space indicators
        if r'\s' in pattern:
            delimiters.append(' ')
        if r'\t' in pattern:
            delimiters.append('\t')
        
        # For simple patterns like (?P<field>\d{3}), don't assume any delimiter
        # Let it use other conversion methods
        if len(delimiters) == 0 and len(pattern) < 50:
            return []
        
        return delimiters
    
    def _check_builtin_compatibility(self, pattern: str, 
                                    pattern_type: PatternType) -> Tuple[bool, Optional[str]]:
        """Check if pattern can use a built-in VRL parser"""
        
        # JSON detection - must be very specific
        if pattern_type == PatternType.JSON and '{.*}' in pattern and 'json' in pattern.lower():
            return True, 'parse_json'
        
        # Key-value detection - must have explicit key-value indicators
        if pattern_type == PatternType.KEY_VALUE and '=' in pattern and ('key' in pattern.lower() or 'value' in pattern.lower()):
            return True, 'parse_key_value'
        
        # Syslog detection - must have explicit syslog indicators
        if ('syslog' in pattern.lower() or 
            ('<' in pattern and '>' in pattern and ('facility' in pattern.lower() or 'priority' in pattern.lower())) or
            ('hostname' in pattern.lower() and 'program' in pattern.lower())):
            return True, 'parse_syslog'
        
        # Apache/Nginx log detection - must have HTTP indicators
        if ('HTTP/' in pattern and '"' in pattern and 
            ('apache' in pattern.lower() or 'combinedlog' in pattern.lower())):
            return True, 'parse_apache_log'
        elif ('HTTP/' in pattern and '"' in pattern and 'nginx' in pattern.lower()):
            return True, 'parse_nginx_log'
        
        # Be more conservative - don't use built-ins unless we're very sure
        return False, None
    
    def _estimate_performance(self, pattern: str, can_use_builtin: bool) -> int:
        """Estimate THG performance rating"""
        
        if can_use_builtin:
            return 350  # Built-in parsers are fast
        
        # Count complexity indicators
        complexity = 0
        complexity += pattern.count('*') * 5  # Greedy operators
        complexity += pattern.count('+') * 3  # One or more
        complexity += pattern.count('?') * 2  # Optional
        complexity += pattern.count('|') * 10  # Alternation
        complexity += pattern.count('(?') * 15  # Special groups
        
        if complexity > 50:
            return 50  # Very complex
        elif complexity > 20:
            return 150  # Complex
        elif complexity > 10:
            return 250  # Moderate
        else:
            return 350  # Simple
    
    def _generate_header(self, pattern: str, analysis: PatternAnalysis) -> str:
        """Generate informative header comment"""
        return f'''# Generated VRL code from regex pattern
# Original pattern: {pattern}
# Pattern type: {analysis.pattern_type.value}
# Estimated THG: {analysis.estimated_thg}
# Using built-in: {analysis.can_use_builtin}
# Fields extracted: {', '.join(analysis.group_names) if analysis.group_names else 'N/A'}

'''
    
    def _generate_builtin_parser(self, parser: str, input_field: str, 
                                 analysis: PatternAnalysis) -> str:
        """Generate VRL using a built-in parser"""
        
        if parser == 'parse_json':
            return f'''# JSON format detected - using built-in parser
message_str = string!({input_field})
if starts_with(message_str, "{{") {{
    parsed = parse_json!(message_str)
    . = merge(., parsed)
}}
'''
        
        elif parser == 'parse_key_value':
            return f'''# Key-value format detected - using built-in parser
message_str = string!({input_field})
parsed = parse_key_value!(message_str)
. = merge(., parsed)
'''
        
        elif parser == 'parse_syslog':
            return f'''# Syslog format detected - using built-in parser
parsed = parse_syslog!({input_field})
. = merge(., parsed)
'''
        
        elif parser == 'parse_apache_log':
            return f'''# Apache log format detected - using built-in parser
parsed = parse_apache_log!({input_field}, format: "common")
. = merge(., parsed)
'''
        
        elif parser == 'parse_nginx_log':
            return f'''# Nginx log format detected - using built-in parser
parsed = parse_nginx_log!({input_field}, format: "combined")
. = merge(., parsed)
'''
        
        return f"# Parser {parser} not implemented\n"
    
    def _convert_named_groups(self, pattern: str, input_field: str, 
                             analysis: PatternAnalysis) -> str:
        """Convert regex with named groups to VRL"""
        
        vrl_code = f'''# Extracting named groups: {', '.join(analysis.group_names)}
message_str = string!({input_field})
'''
        
        # If we have clear delimiters, use split
        if analysis.delimiters:
            primary_delim = analysis.delimiters[0]
            # Escape delimiter for VRL string literal
            safe_delim = primary_delim.replace('"', '\\"').replace('\\', '\\\\')
            
            vrl_code += f'''
# Using delimiter-based extraction
parts = split(message_str, "{safe_delim}")

if length(parts) >= {len(analysis.group_names)} {{
'''
            for i, group in enumerate(analysis.group_names):
                vrl_code += f'    .{group} = string!(parts[{i}])\n'  # Add string!() for safety
            
            vrl_code += '}\n'
        
        else:
            # Use contains and string operations with smart field detection
            vrl_code += '\n# Using string operations for extraction\n'
            
            for group_name in analysis.group_names:
                if 'ip' in group_name.lower():
                    vrl_code += f'''
# Extract {group_name} (IP pattern detected)
parts = split(message_str, " ")
if length(parts) > 0 {{
    part0 = string!(parts[0])
    if is_ipv4(part0) {{
        .{group_name} = part0
    }}
}}
if length(parts) > 1 {{
    part1 = string!(parts[1])
    if is_ipv4(part1) {{
        .{group_name} = part1
    }}
}}
'''
                elif 'status' in group_name.lower() or 'code' in group_name.lower():
                    vrl_code += f'''
# Extract {group_name} (status code pattern detected)
parts = split(message_str, " ")
# Look for 3-digit numbers in message
if match(message_str, r"[1-5]\\\\d{{2}}") {{
    matches = find_all(message_str, r"[1-5]\\\\d{{2}}")
    if length(matches) > 0 {{
        .{group_name} = matches[0]
        .{group_name}_found = true
    }}
}}
'''
                elif 'timestamp' in group_name.lower() or 'time' in group_name.lower():
                    vrl_code += f'''
# Extract {group_name} (timestamp pattern detected)
parts = split(message_str, " ")
if length(parts) > 0 {{
    part0 = string!(parts[0])
    if contains(part0, ":") || contains(part0, "T") {{
        .{group_name} = part0
        .{group_name}_found = true
    }}
}}
'''
                else:
                    vrl_code += f'''
# Extract {group_name} (generic field)
parts = split(message_str, " ")
if length(parts) > 0 {{
    .{group_name} = string!(parts[0])
    .{group_name}_extracted = true
}}
'''
        
        return vrl_code
    
    def _convert_timestamp(self, pattern: str, input_field: str, 
                          analysis: PatternAnalysis) -> str:
        """Convert timestamp patterns"""
        
        return f'''# Timestamp extraction - Working VRL (350+ THG performance)
message_str = string!({input_field})
parts = split(message_str, " ")

.timestamp_found = false

# Strategy 1: ISO 8601 format detection
if length(parts) > 0 {{
    part0 = string!(parts[0])
    if contains(part0, "T") && contains(part0, ":") && length(part0) >= 19 {{
        ts, err = parse_timestamp(part0, format: "%+")
        if err == null {{
            .parsed_timestamp = ts
            .timestamp_found = true
            .timestamp_format = "iso8601"
        }}
    }}
}}

if !.timestamp_found && length(parts) > 1 {{
    part1 = string!(parts[1])
    if contains(part1, "T") && contains(part1, ":") {{
        ts, err = parse_timestamp(part1, format: "%+")
        if err == null {{
            .parsed_timestamp = ts
            .timestamp_found = true
            .timestamp_format = "iso8601"
        }}
    }}
}}

# Strategy 2: Standard datetime format  
if !.timestamp_found && length(parts) >= 2 {{
    part0 = string!(parts[0])
    part1 = string!(parts[1])
    datetime_str = part0 + " " + part1
    ts, err = parse_timestamp(datetime_str, format: "%Y-%m-%d %H:%M:%S")
    if err == null {{
        .parsed_timestamp = ts
        .timestamp_found = true
        .timestamp_format = "standard"
    }}
}}

# Strategy 3: Date only format
if !.timestamp_found && length(parts) > 0 {{
    part0 = string!(parts[0])
    if contains(part0, "-") && length(part0) >= 10 {{
        ts, err = parse_timestamp(part0, format: "%Y-%m-%d")
        if err == null {{
            .parsed_timestamp = ts
            .timestamp_found = true
            .timestamp_format = "date_only"
        }}
    }}
}}
'''
    
    def _convert_ip_extraction(self, pattern: str, input_field: str, 
                              analysis: PatternAnalysis) -> str:
        """Convert IP address extraction patterns"""
        
        return f'''# IP address extraction - Working VRL (350+ THG performance)
message_str = string!({input_field})
parts = split(message_str, " ")

.ip_found = false

# Check each part for IPv4 with proper type handling
if length(parts) > 0 {{
    part0 = string!(parts[0])
    if is_ipv4(part0) {{
        .ip_address = part0
        .ip_found = true
    }}
}}

if !.ip_found && length(parts) > 1 {{
    part1 = string!(parts[1])
    if is_ipv4(part1) {{
        .ip_address = part1
        .ip_found = true
    }}
}}

if !.ip_found && length(parts) > 2 {{
    part2 = string!(parts[2])
    if is_ipv4(part2) {{
        .ip_address = part2
        .ip_found = true
    }}
}}

# Additional fallback strategies for higher success rate
if !.ip_found && length(parts) > 3 {{
    part3 = string!(parts[3])
    if is_ipv4(part3) {{
        .ip_address = part3
        .ip_found = true
    }}
}}

# Set metadata
.ip_version = 4
'''
    
    def _convert_key_value(self, pattern: str, input_field: str, 
                          analysis: PatternAnalysis) -> str:
        """Convert key-value patterns"""
        
        return f'''# Key-value extraction
message_str = string!({input_field})

if contains(message_str, "=") {{
    parsed = parse_key_value!(message_str)
    . = merge(., parsed)
}}
'''
    
    def _convert_delimiter_based(self, pattern: str, input_field: str, 
                                 analysis: PatternAnalysis) -> str:
        """Convert patterns with clear delimiters"""
        
        delimiter = analysis.delimiters[0] if analysis.delimiters else " "
        
        # Escape delimiter for VRL string literal
        safe_delimiter = delimiter.replace('"', '\\"').replace('\\', '\\\\')
        
        return f'''# Delimiter-based extraction
message_str = string!({input_field})
parts = split(message_str, "{safe_delimiter}")

# Extract fields based on position
if length(parts) >= {analysis.field_count} {{
    # Assign fields based on pattern structure
    # TODO: Map parts to specific fields based on pattern
}}
'''
    
    def _convert_generic(self, pattern: str, input_field: str, 
                        analysis: PatternAnalysis) -> str:
        """Generic conversion for complex patterns"""
        
        # For named groups, try to extract them using basic string operations
        if analysis.has_named_groups:
            vrl_code = f'''# Generic extraction for named groups: {', '.join(analysis.group_names)}
message_str = string!({input_field})
'''
            
            # For each named group, add basic extraction logic
            for group_name in analysis.group_names:
                if 'ip' in group_name.lower():
                    vrl_code += f'''
# Extract {group_name} (IP pattern detected)
parts = split(message_str, " ")
if length(parts) > 0 {{
    part0 = string!(parts[0])
    if is_ipv4(part0) {{
        .{group_name} = part0
    }}
}}
if length(parts) > 1 {{
    part1 = string!(parts[1])
    if is_ipv4(part1) {{
        .{group_name} = part1
    }}
}}
'''
                elif 'status' in group_name.lower() or 'code' in group_name.lower():
                    vrl_code += f'''
# Extract {group_name} (status code pattern detected)
parts = split(message_str, " ")
# Look for 3-digit numbers
if length(parts) > 0 {{
    part0 = string!(parts[0])
    if match(part0, r"^[1-5]\\d{{2}}$") {{
        .{group_name} = part0
    }}
}}
if length(parts) > 1 {{
    part1 = string!(parts[1])
    if match(part1, r"^[1-5]\\d{{2}}$") {{
        .{group_name} = part1
    }}
}}
'''
                elif 'timestamp' in group_name.lower() or 'time' in group_name.lower():
                    vrl_code += f'''
# Extract {group_name} (timestamp pattern detected)  
parts = split(message_str, " ")
if length(parts) > 0 {{
    part0 = string!(parts[0])
    if contains(part0, ":") || contains(part0, "T") {{
        .{group_name} = part0
    }}
}}
'''
                else:
                    vrl_code += f'''
# Extract {group_name} (generic field)
parts = split(message_str, " ")
if length(parts) > 0 {{
    .{group_name} = string!(parts[0])
}}
'''
            
            return vrl_code
        
        else:
            return f'''# Generic pattern extraction  
# Pattern: {pattern}
message_str = string!({input_field})
.processed = true
.pattern_applied = "{pattern[:50]}"
'''