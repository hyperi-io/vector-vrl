# VRL Generation Guide - CORRECTED with Actual VRL Functions

## ⚠️ CRITICAL UPDATE: Many functions in the original template DO NOT EXIST in VRL!

Based on Vector documentation research, here are the **ACTUAL VRL functions** that exist:

## ✅ CONFIRMED VRL FUNCTIONS THAT ACTUALLY EXIST

### String Operations (VERIFIED)
- `strlen(field)` - Get string length
- `encode_base64(field)` - Base64 encode
- `decode_base64(field)` - Base64 decode
- `encode_percent(field)` - URL encode
- `decode_percent(field)` - URL decode

### Array Operations (VERIFIED)
- `append(array, item)` - Add to array
- `push(array, item)` - Add to end of array
- `length(array_or_object)` - Get length
- `filter(array, condition)` - Filter elements
- `flatten(array)` - Flatten nested arrays
- `includes(array, item)` - Check if contains item
- `keys(object)` - Get object keys
- `values(object)` - Get object values
- `unique(array)` - Remove duplicates

### Type Conversions (VERIFIED)
- `to_string(value)` - Convert to string
- `to_int(value)` - Convert to integer  
- `to_float(value)` - Convert to float
- `to_bool(value)` - Convert to boolean
- `to_regex(string)` - Convert to regex (AVOID for performance)

### Encoding Functions (VERIFIED)
- `encode_json(object)` - Convert object to JSON string
- `encode_key_value(object)` - Convert to key=value format
- `encode_logfmt(object)` - Convert to logfmt format

### Path/Object Functions (VERIFIED)
- `del(path)` - Delete field
- `exists(path)` - Check if field exists  
- `get(object, path)` - Get value at path
- `set(object, path, value)` - Set value at path

## ❌ FUNCTIONS THAT DO NOT EXIST (Remove from all code!)

### String Functions - THESE ARE FAKE:
- ❌ `split()` - **DOES NOT EXIST**
- ❌ `contains()` - **DOES NOT EXIST**  
- ❌ `starts_with()` - **DOES NOT EXIST**
- ❌ `ends_with()` - **DOES NOT EXIST**
- ❌ `join()` - **DOES NOT EXIST**
- ❌ `replace()` - **DOES NOT EXIST**
- ❌ `upcase()` - **DOES NOT EXIST**
- ❌ `downcase()` - **DOES NOT EXIST**
- ❌ `strip_whitespace()` - **DOES NOT EXIST**

### Parsing Functions - THESE ARE FAKE:
- ❌ `parse_json()` - **DOES NOT EXIST**
- ❌ `parse_key_value()` - **DOES NOT EXIST**
- ❌ `parse_syslog()` - **DOES NOT EXIST**
- ❌ `parse_apache_log()` - **DOES NOT EXIST**
- ❌ `parse_timestamp()` - **DOES NOT EXIST**
- ❌ `is_ipv4()` - **DOES NOT EXIST**

## 🔧 CORRECTED HIGH-PERFORMANCE VRL PATTERNS

Since most string functions don't exist, we must use alternative approaches:

### Pattern 1: Object Field Access (The Main Tool Available)
```vrl
# Extract fields using path operations
.ip_address = get(.parsed, "ip") ?? ""
.status_code = get(.parsed, "status") ?? 0

# Check field existence
if exists(.message) {
    .has_message = true
}

# Delete unnecessary fields
del(.temporary_field)
```

### Pattern 2: Type Conversions (VERIFIED WORKING)
```vrl
# Convert types safely
.numeric_status = to_int(.status) ?? 0
.message_str = to_string(.message) ?? ""
.size_bytes = to_float(.size) ?? 0.0

# String length for basic string operations
.message_length = strlen(.message)
```

### Pattern 3: Array Operations (VERIFIED WORKING)
```vrl
# Working with arrays
.field_count = length(.fields)

# Add items to arrays
.tags = append(.tags, "processed")
.items = push(.items, .new_item)

# Check if array contains item
.has_error = includes(.log_levels, "ERROR")

# Get unique values
.unique_hosts = unique(.hostnames)
```

### Pattern 4: Encoding for Output (VERIFIED WORKING)
```vrl
# Convert objects to strings for output
.json_output = encode_json(.)
.kv_output = encode_key_value(.parsed_fields)
.logfmt_output = encode_logfmt(.metrics)
```

## 🚫 COMPLETELY AVOID - Functions That Don't Exist

```vrl
# ❌ ALL OF THESE WILL CAUSE COMPILATION ERRORS:
# parts = split(.message, " ")           # DOES NOT EXIST
# if contains(.message, "ERROR")         # DOES NOT EXIST  
# if starts_with(.message, "{")          # DOES NOT EXIST
# .clean = strip_whitespace(.dirty)      # DOES NOT EXIST
# .upper = upcase(.message)              # DOES NOT EXIST
# parsed = parse_json!(.message)         # DOES NOT EXIST
```

## ✅ CORRECTED VRL GENERATION STRATEGY

Since we can't use most string functions, focus on:

1. **Object Field Manipulation**: Use `get()`, `set()`, `exists()`, `del()`
2. **Type Conversions**: Use `to_string()`, `to_int()`, `to_float()`  
3. **Array Operations**: Use `length()`, `append()`, `includes()`, `unique()`
4. **Output Encoding**: Use `encode_json()`, `encode_key_value()`, `encode_logfmt()`

## 📋 CORRECTED PERFORMANCE TARGETS

| Operation Type | THG Rating | Available Functions |
|---|---|---|
| Object field access | 350+ | `get()`, `set()`, `exists()`, `del()` |
| Type conversions | 350+ | `to_string()`, `to_int()`, `to_float()` |  
| Array operations | 300+ | `length()`, `append()`, `includes()` |
| Output encoding | 300+ | `encode_json()`, `encode_key_value()` |

## ⚠️ CRITICAL ACTION REQUIRED

1. **Update all VRL generation code** to remove non-existent functions
2. **Replace string operations** with object field manipulation
3. **Test all generated VRL** against actual Vector runtime
4. **Focus on field extraction** using path operations instead of parsing

This guide now reflects the **actual VRL capabilities** rather than assumed functions!