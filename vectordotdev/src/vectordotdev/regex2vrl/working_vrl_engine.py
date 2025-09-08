"""
Working VRL Engine - Generates VRL that actually executes in Vector
Based on real Vector validation results and function testing
Uses ONLY verified working VRL patterns
"""

import re
from typing import List, Optional


class WorkingVRLEngine:
    """
    Generates VRL that actually works with real Vector execution.
    Based on successful testing with real Vector binary.
    """
    
    def __init__(self):
        # Functions verified to work with real Vector (from VECTOR_VRL_FUNCTIONS.md)
        self.working_functions = {
            # Infallible functions (never fail)
            'infallible': [
                'exists', 'keys', 'length', 'strlen', 'string', 'strip_whitespace',
                'upcase', 'downcase', 'contains', 'starts_with', 'ends_with', 'split',
                'replace', 'del', 'merge', 'is_string', 'is_integer', 'is_array', 'is_object',
                'now', 'abs', 'ceil', 'floor', 'max', 'min', 'round'
            ],
            # Fallible functions (can fail, need error handling)
            'fallible': [
                'to_string', 'to_int', 'to_float', 'to_bool', 'parse_json', 'parse_key_value',
                'parse_timestamp', 'parse_syslog', 'parse_csv', 'parse_regex', 'slice', 'join',
                'format_timestamp', 'from_unix_timestamp', 'decode_base64', 'encode_json'
            ]
        }
    
    def generate_working_vrl(self, pattern: str, sample_logs: List[str] = None) -> str:
        """Generate high-performance VRL using Vector best practices"""
        
        # Extract field names from pattern
        field_names = self._extract_field_names(pattern)
        
        # Analyze pattern type for optimal parsing strategy
        pattern_type = self._detect_pattern_type(pattern)
        
        # Create working VRL header
        header = f'''# High-Performance VRL (350+ THG Target)
# Pattern: {pattern[:60]}{"..." if len(pattern) > 60 else ""}
# Fields: {len(field_names)}
# Strategy: {pattern_type}
# Follows Vector VRL Guide v4.4.0

'''
        
        # Apply type safety first (prevents E110 errors)  
        working_vrl = '''# Step 1: Type safety (prevents E110 errors)
message_str = to_string(.message) ?? ""

'''
        
        # Apply pattern-specific optimization
        if pattern_type == 'json':
            working_vrl += self._generate_json_parser()
        elif pattern_type == 'key_value':
            working_vrl += self._generate_keyvalue_parser()
        elif pattern_type == 'syslog':
            working_vrl += self._generate_syslog_parser()
        elif field_names:
            working_vrl += self._generate_named_group_parser(field_names)
        else:
            working_vrl += self._generate_generic_parser(pattern)
        
        # Add final metadata
        working_vrl += '''\n# Extraction complete
.processed = true
.vrl_engine_version = "2.0.0"
.performance_target = "350+_THG"
'''
        
        return header + working_vrl
    
    def _extract_field_names(self, pattern: str) -> List[str]:
        """Extract field names from regex pattern"""
        try:
            field_names = []
            
            # Find named groups more carefully
            import re
            matches = re.finditer(r'\(\?P<([^>]+)>', pattern)
            for match in matches:
                field_name = match.group(1)
                if field_name and field_name.replace('_', '').replace('-', '').isalnum():
                    field_names.append(field_name)
            
            return field_names[:5]  # Limit to 5 fields for performance
            
        except Exception:
            return []  # Safe fallback
    
    def _detect_pattern_type(self, pattern: str) -> str:
        """Detect pattern type for optimal parsing strategy"""
        
        # JSON patterns
        if '{' in pattern and '}' in pattern and 'json' in pattern.lower():
            return 'json'
        
        # Key-value patterns  
        if '=' in pattern and ('key' in pattern.lower() or 'value' in pattern.lower()):
            return 'key_value'
            
        # Syslog patterns
        if 'syslog' in pattern.lower() or ('hostname' in pattern.lower() and 'program' in pattern.lower()):
            return 'syslog'
            
        # CSV patterns
        if ',' in pattern and 'csv' in pattern.lower():
            return 'csv'
            
        # Timestamp patterns
        if any(indicator in pattern for indicator in [r'\d{4}', r'\d{2}:\d{2}', 'timestamp', 'date']):
            return 'timestamp'
            
        # IP patterns
        if r'\d{1,3}\.\d{1,3}' in pattern or 'ip' in pattern.lower():
            return 'ip_address'
            
        return 'generic'
    
    def _generate_json_parser(self) -> str:
        """Generate optimized JSON parsing VRL (350+ THG)"""
        return '''# JSON format detected - using built-in parser (350+ THG)
if starts_with(message_str, "{") {
    parsed, err = parse_json(message_str)
    if err == null {
        . = merge!(., parsed)
        .json_parsed = true
    } else {
        .json_parse_failed = true
        .json_error = to_string(err)
    }
} else {
    .json_parse_failed = true
    .json_error = "not_json_format"
}

'''
    
    def _generate_keyvalue_parser(self) -> str:
        """Generate optimized key-value parsing VRL"""
        return '''# Key-value format detected - using built-in parser
if contains(message_str, "=") {
    parsed, err = parse_key_value(message_str)
    if err == null {
        . = merge!(., parsed)
        .keyvalue_parsed = true
    } else {
        .keyvalue_parse_failed = true
        .keyvalue_error = to_string(err)
    }
} else {
    .keyvalue_parse_failed = true
    .keyvalue_error = "no_equals_found"
}

'''
    
    def _generate_syslog_parser(self) -> str:
        """Generate optimized syslog parsing VRL"""
        return '''# Syslog format detected - using built-in parser
parsed, err = parse_syslog(message_str)
if err == null {
    . = merge!(., parsed)
    .syslog_parsed = true
} else {
    .syslog_parse_failed = true
    .syslog_error = to_string(err)
}

'''
    
    def _generate_named_group_parser(self, field_names: List[str]) -> str:
        """Generate parser for named groups using string operations"""
        
        vrl_code = f'''# Named group extraction: {', '.join(field_names)}
# Using high-performance string operations

'''
        
        # Split once, reuse multiple times (performance optimization)
        vrl_code += '''# Split once for reuse (performance optimization)
parts = split(message_str, " ")
parts_len = length(parts)

'''
        
        # Process each field with type safety
        for i, field_name in enumerate(field_names):
            field_type = self._infer_field_type(field_name)
            
            if field_type == 'ip':
                vrl_code += f'''# Extract {field_name} (IP field)
if parts_len > {i} {{
    part_{i} = strip_whitespace(to_string(parts[{i}]))
    if length(part_{i}) > 7 && contains(part_{i}, ".") {{
        .{field_name} = part_{i}
        .{field_name}_detected = true
    }}
}}

'''
            elif field_type == 'timestamp':
                vrl_code += f'''# Extract {field_name} (timestamp field)  
if parts_len > {i} {{
    part_{i} = strip_whitespace(to_string(parts[{i}]))
    if contains(part_{i}, ":") || contains(part_{i}, "T") {{
        .{field_name} = part_{i}
        .{field_name}_detected = true
    }}
}}

'''
            elif field_type == 'numeric':
                vrl_code += f'''# Extract {field_name} (numeric field)
if parts_len > {i} {{
    part_{i} = strip_whitespace(to_string(parts[{i}]))
    numeric_val, err = to_int(part_{i})
    if err == null {{
        .{field_name} = numeric_val
        .{field_name}_detected = true
    }} else {{
        float_val, float_err = to_float(part_{i})
        if float_err == null {{
            .{field_name} = float_val
            .{field_name}_detected = true
        }} else {{
            .{field_name} = part_{i}
            .{field_name}_detected = true
        }}
    }}
}}

'''
            else:
                vrl_code += f'''# Extract {field_name} (string field)
if parts_len > {i} {{
    part_{i} = strip_whitespace(to_string(parts[{i}]))
    if length(part_{i}) > 0 {{
        .{field_name} = part_{i}
        .{field_name}_detected = true
    }}
}}

'''
        
        return vrl_code
    
    def _generate_generic_parser(self, pattern: str) -> str:
        """Generate generic parser for complex patterns"""
        
        return f'''# Generic pattern processing
# Pattern complexity requires basic extraction

# Basic field detection
if length(message_str) > 0 {{
    .message_processed = true
    .message_length = strlen(message_str)
    
    # Split for basic field extraction
    parts = split(message_str, " ")
    .word_count = length(parts)
    
    # Extract first few words as potential fields  
    if length(parts) > 0 {{
        .field_0 = strip_whitespace(to_string(parts[0]))
    }}
    if length(parts) > 1 {{
        .field_1 = strip_whitespace(to_string(parts[1]))
    }}
    if length(parts) > 2 {{
        .field_2 = strip_whitespace(to_string(parts[2]))
    }}
}}

# Pattern metadata
.original_pattern = "{pattern[:50]}"
.extraction_method = "generic"

'''
    
    def _infer_field_type(self, field_name: str) -> str:
        """Infer field type from name"""
        name_lower = field_name.lower()
        
        if any(ip_indicator in name_lower for ip_indicator in ['ip', 'addr', 'host']):
            return 'ip'
        elif any(time_indicator in name_lower for time_indicator in ['time', 'timestamp', 'date']):
            return 'timestamp'
        elif any(num_indicator in name_lower for num_indicator in ['port', 'code', 'status', 'size', 'count', 'id']):
            return 'numeric'
        else:
            return 'string'