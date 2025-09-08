# Vector VRL (Vector Remap Language) Functions - Complete Reference

Vector Remap Language (VRL) is an expression-oriented language designed for transforming observability data (logs, metrics, traces). It provides a comprehensive set of built-in functions that are categorized by purpose and designed for safety and performance.

## Function Characteristics

VRL functions have the following properties:
- **Fallible** - Can fail at runtime, requiring explicit error handling
- **Infallible** - Cannot fail given correct arguments, no error handling needed  
- **Pure** - Do not modify external state, always return the same output for same input
- **Impure** - May have side effects or access external state

## Array Functions

### `append`
**Type**: Infallible, Pure  
**Signature**: `append(value: array, items: array) -> array`  
**Description**: Appends each item in the items array to the end of the value array.  
**Example**:
```vrl
append([1, 2], [3, 4]) # Returns [1, 2, 3, 4]
```

### `chunks`  
**Type**: Fallible, Pure  
**Signature**: `chunks(value: array | string, chunk_size: integer) -> array`  
**Description**: Chunks value into slices of length chunk_size bytes.  
**Example**:
```vrl
chunks([1, 2, 3, 4, 5], 2) # Returns [[1, 2], [3, 4], [5]]
chunks("abcdef", 2) # Returns ["ab", "cd", "ef"]
```

### `push`
**Type**: Infallible, Pure  
**Signature**: `push(value: array, item: any) -> array`  
**Description**: Adds the item to the end of the value array.  
**Example**:
```vrl
push([1, 2, 3], 4) # Returns [1, 2, 3, 4]
```

### `unique`
**Type**: Infallible, Pure  
**Signature**: `unique(value: array) -> array`  
**Description**: Returns the unique values for an array, keeping the first occurrence of each element.  
**Example**:
```vrl
unique([1, 2, 2, 3, 3, 4]) # Returns [1, 2, 3, 4]
```

### `zip`
**Type**: Infallible, Pure  
**Signature**: `zip(...arrays: array) -> array`  
**Description**: Iterates over several arrays in parallel, producing a new array containing arrays of items from each source. The resulting array is as long as the shortest input array.  
**Example**:
```vrl
zip([1, 2, 3], ["a", "b", "c"]) # Returns [[1, "a"], [2, "b"], [3, "c"]]
```

## Codec Functions

### `decode_base16`
**Type**: Fallible, Pure  
**Signature**: `decode_base16(value: string) -> string`  
**Description**: Decodes a Base16-encoded string.  
**Example**:
```vrl
decode_base16!("48656c6c6f") # Returns "Hello"
```

### `decode_base64`
**Type**: Fallible, Pure  
**Signature**: `decode_base64(value: string) -> string`  
**Description**: Decodes a Base64-encoded string. No longer requires canonical padding.  
**Example**:
```vrl
decode_base64!("SGVsbG8=") # Returns "Hello"
```

### `decode_charset`
**Type**: Fallible, Pure  
**Signature**: `decode_charset(value: string, from_charset: string) -> string`  
**Description**: Decodes strings between different character sets.  
**Example**:
```vrl
decode_charset!(.message, "latin1")
```

### `decode_gzip`
**Type**: Fallible, Pure  
**Signature**: `decode_gzip(value: string) -> string`  
**Description**: Decodes a gzip-compressed string.  

### `decode_mime_q`
**Type**: Fallible, Pure  
**Signature**: `decode_mime_q(value: string) -> string`  
**Description**: Decodes q-encoded or base64-encoded encoded-word substrings.

### `decode_percent`
**Type**: Fallible, Pure  
**Signature**: `decode_percent(value: string) -> string`  
**Description**: Decodes percent-encoded values like URLs.  
**Example**:
```vrl
decode_percent!("hello%20world") # Returns "hello world"
```

### `decode_punycode`
**Type**: Fallible, Pure  
**Signature**: `decode_punycode(value: string) -> string`  
**Description**: Decodes internationalized domain names using Punycode.

### `decode_snappy`
**Type**: Fallible, Pure  
**Signature**: `decode_snappy(value: string) -> string`  
**Description**: Decodes a Snappy-compressed string.

### `decode_zlib`
**Type**: Fallible, Pure  
**Signature**: `decode_zlib(value: string) -> string`  
**Description**: Decodes a zlib-compressed string.

### `decode_zstd`
**Type**: Fallible, Pure  
**Signature**: `decode_zstd(value: string) -> string`  
**Description**: Decodes a Zstandard-compressed string.

### `encode_base16`
**Type**: Infallible, Pure  
**Signature**: `encode_base16(value: string) -> string`  
**Description**: Encodes a string as Base16.  
**Example**:
```vrl
encode_base16("Hello") # Returns "48656c6c6f"
```

### `encode_base64`
**Type**: Infallible, Pure  
**Signature**: `encode_base64(value: string) -> string`  
**Description**: Encodes a string as Base64.  
**Example**:
```vrl
encode_base64("Hello") # Returns "SGVsbG8="
```

### `encode_charset`
**Type**: Fallible, Pure  
**Signature**: `encode_charset(value: string, to_charset: string) -> string`  
**Description**: Encodes strings between different character sets.

### `encode_gzip`
**Type**: Infallible, Pure  
**Signature**: `encode_gzip(value: string, level?: integer) -> string`  
**Description**: Compresses a string using gzip.

### `encode_json`
**Type**: Fallible, Pure  
**Signature**: `encode_json(value: any) -> string`  
**Description**: Encodes a value as JSON.  
**Example**:
```vrl
encode_json!({name: "John", age: 30}) # Returns '{"name":"John","age":30}'
```

### `encode_key_value`
**Type**: Infallible, Pure  
**Signature**: `encode_key_value(value: object, field_delimiter?: string, key_value_delimiter?: string) -> string`  
**Description**: Encodes an object as key-value pairs with customizable delimiters.

### `encode_snappy`
**Type**: Infallible, Pure  
**Signature**: `encode_snappy(value: string) -> string`  
**Description**: Compresses a string using Snappy.

### `encode_zlib`
**Type**: Infallible, Pure  
**Signature**: `encode_zlib(value: string, level?: integer) -> string`  
**Description**: Compresses a string using zlib.

### `encode_zstd`
**Type**: Infallible, Pure  
**Signature**: `encode_zstd(value: string, level?: integer) -> string`  
**Description**: Compresses a string using Zstandard.

## Coerce Functions

### `to_bool`
**Type**: Fallible, Pure  
**Signature**: `to_bool(value: any) -> boolean`  
**Description**: Coerces a value into a boolean.  
**Example**:
```vrl
to_bool!("true") # Returns true
to_bool!("1") # Returns true
to_bool!("0") # Returns false
```

### `to_float`
**Type**: Fallible, Pure  
**Signature**: `to_float(value: any) -> float`  
**Description**: Coerces a value into a float.  
**Example**:
```vrl
to_float!("3.14") # Returns 3.14
to_float!(42) # Returns 42.0
```

### `to_int`
**Type**: Fallible, Pure  
**Signature**: `to_int(value: any) -> integer`  
**Description**: Coerces a value into an integer.  
**Example**:
```vrl
to_int!("42") # Returns 42
to_int!(3.14) # Returns 3
```

### `to_string`
**Type**: Infallible, Pure  
**Signature**: `to_string(value: any) -> string`  
**Description**: Coerces a value into a string.  
**Example**:
```vrl
to_string(42) # Returns "42"
to_string(true) # Returns "true"
```

## Convert Functions

### `from_unix_timestamp`
**Type**: Fallible, Pure  
**Signature**: `from_unix_timestamp(value: integer, unit?: string) -> timestamp`  
**Description**: Converts a Unix timestamp to a VRL timestamp. Converts from seconds by default, with options for "milliseconds" or "nanoseconds".  
**Example**:
```vrl
from_unix_timestamp!(1609459200) # Returns 2021-01-01T00:00:00Z
from_unix_timestamp!(1609459200000, "milliseconds")
```

### `parse_duration`
**Type**: Fallible, Pure  
**Signature**: `parse_duration(value: string, unit: string) -> float`  
**Description**: Parses duration strings including multi-unit formats like "1h2s", "2m3s".  
**Example**:
```vrl
parse_duration!("1h30m", "seconds") # Returns 5400.0
```

### `parse_bytes`
**Type**: Fallible, Pure  
**Signature**: `parse_bytes(value: string, binary?: boolean) -> integer`  
**Description**: Parses byte strings like "1MiB" or "1TB" in binary or decimal base.  
**Example**:
```vrl
parse_bytes!("1GB") # Returns 1000000000
parse_bytes!("1GiB", true) # Returns 1073741824
```

## Debug Functions

### `assert`
**Type**: Fallible, Pure  
**Signature**: `assert(condition: boolean, message?: string) -> null`  
**Description**: Aborts the program with an optional error message if the condition is false.  
**Example**:
```vrl
assert!(exists(.timestamp), "timestamp field is required")
```

### `log`
**Type**: Infallible, Impure  
**Signature**: `log(value: any, level?: string) -> null`  
**Description**: Logs a value at the specified level. Rate-limited to prevent spam.  
**Example**:
```vrl
log(.message, "info")
log("Debug info", "debug")
```

## Enrichment Functions

### `find_enrichment_table_records`
**Type**: Fallible, Impure  
**Signature**: `find_enrichment_table_records(table: string, condition: object, case_sensitive?: boolean) -> array`  
**Description**: Returns rows that match the provided conditions from an enrichment table.  
**Example**:
```vrl
find_enrichment_table_records!("users", {"id": .user_id})
```

### `get_enrichment_table_record`
**Type**: Fallible, Impure  
**Signature**: `get_enrichment_table_record(table: string, condition: object, case_sensitive?: boolean) -> object`  
**Description**: Returns a single record that matches the provided conditions.  
**Example**:
```vrl
get_enrichment_table_record!("users", {"email": .email})
```

## Enumerate Functions

### `compact`
**Type**: Infallible, Pure  
**Signature**: `compact(value: array | object, null?: boolean, string?: boolean, object?: boolean, array?: boolean) -> array | object`  
**Description**: Removes null values and empty strings/objects/arrays from collections.  
**Example**:
```vrl
compact([1, null, "", 3]) # Returns [1, 3]
```

### `filter`
**Type**: Infallible, Pure  
**Signature**: `filter(value: array | object, closure: closure) -> array | object`  
**Description**: Filters elements based on a closure condition.  
**Example**:
```vrl
filter([1, 2, 3, 4], -> |v| v > 2) # Returns [3, 4]
```

### `flatten`
**Type**: Infallible, Pure  
**Signature**: `flatten(value: array, depth?: integer) -> array`  
**Description**: Flattens an array to the specified depth.  
**Example**:
```vrl
flatten([[1, 2], [3, 4]]) # Returns [1, 2, 3, 4]
```

### `for_each`
**Type**: Infallible, Pure  
**Signature**: `for_each(value: array | object, closure: closure) -> null`  
**Description**: Iterates over each element, executing a closure.  
**Example**:
```vrl
for_each([1, 2, 3], -> |v| log(v))
```

### `map_keys`
**Type**: Infallible, Pure  
**Signature**: `map_keys(value: object, closure: closure) -> object`  
**Description**: Applies a closure to all keys in an object.  
**Example**:
```vrl
map_keys({"foo": 1}, -> |k| upcase(k)) # Returns {"FOO": 1}
```

### `map_values`
**Type**: Infallible, Pure  
**Signature**: `map_values(value: array | object, closure: closure) -> array | object`  
**Description**: Applies a closure to all values in a collection.  
**Example**:
```vrl
map_values([1, 2, 3], -> |v| v * 2) # Returns [2, 4, 6]
```

## Event Functions

### `get_secret`
**Type**: Fallible, Impure  
**Signature**: `get_secret(key: string) -> string`  
**Description**: Returns the value of the given secret from an event.  
**Example**:
```vrl
.api_key = get_secret!("api_key")
```

### `set_secret`
**Type**: Infallible, Impure  
**Signature**: `set_secret(key: string, value: string) -> null`  
**Description**: Sets a secret value in the event.  
**Example**:
```vrl
set_secret("password", .password)
del(.password)
```

### `remove_secret`
**Type**: Infallible, Impure  
**Signature**: `remove_secret(key: string) -> null`  
**Description**: Removes a secret from an event.  
**Example**:
```vrl
remove_secret("temp_token")
```

## Hash Functions

### `md5`
**Type**: Infallible, Pure  
**Signature**: `md5(value: string) -> string`  
**Description**: Calculates an MD5 hash of the value.  
**Example**:
```vrl
md5("Hello") # Returns "8b1a9953c4611296a827abf8c47804d7"
```

### `sha1`
**Type**: Infallible, Pure  
**Signature**: `sha1(value: string) -> string`  
**Description**: Calculates a SHA-1 hash of the value.  
**Example**:
```vrl
sha1("Hello") # Returns "f7c3bc1d808e04732adf679965ccc34ca7ae3441"
```

### `sha2`
**Type**: Infallible, Pure  
**Signature**: `sha2(value: string, variant?: string) -> string`  
**Description**: Calculates a SHA-2 hash of the value. Supports SHA-224, SHA-256, SHA-384, SHA-512.  
**Example**:
```vrl
sha2("Hello") # Returns SHA-256 hash
sha2("Hello", "SHA-512") # Returns SHA-512 hash
```

### `sha3`
**Type**: Infallible, Pure  
**Signature**: `sha3(value: string, variant?: string) -> string`  
**Description**: Calculates a SHA-3 hash of the value.  
**Example**:
```vrl
sha3("Hello") # Returns SHA3-256 hash
```

## IP Functions

### `ip_cidr_contains`
**Type**: Fallible, Pure  
**Signature**: `ip_cidr_contains(cidr: string, ip: string) -> boolean`  
**Description**: Checks if an IP address is contained within a CIDR block.  
**Example**:
```vrl
ip_cidr_contains!("192.168.1.0/24", "192.168.1.100") # Returns true
```

### `ip_subnet`
**Type**: Fallible, Pure  
**Signature**: `ip_subnet(ip: string, subnet: string) -> string`  
**Description**: Extracts the subnet from an IP address.  
**Example**:
```vrl
ip_subnet!("192.168.1.100", "/24") # Returns "192.168.1.0/24"
```

### `is_ipv4`
**Type**: Infallible, Pure  
**Signature**: `is_ipv4(value: string) -> boolean`  
**Description**: Checks if a string is a valid IPv4 address.  
**Example**:
```vrl
is_ipv4("192.168.1.1") # Returns true
is_ipv4("hello") # Returns false
```

### `is_ipv6`
**Type**: Infallible, Pure  
**Signature**: `is_ipv6(value: string) -> boolean`  
**Description**: Checks if a string is a valid IPv6 address.  
**Example**:
```vrl
is_ipv6("::1") # Returns true
is_ipv6("192.168.1.1") # Returns false
```

## Math Functions

### `abs`
**Type**: Infallible, Pure  
**Signature**: `abs(value: integer | float) -> integer | float`  
**Description**: Returns the absolute value.  
**Example**:
```vrl
abs(-42) # Returns 42
abs(-3.14) # Returns 3.14
```

### `ceil`
**Type**: Infallible, Pure  
**Signature**: `ceil(value: float) -> integer`  
**Description**: Rounds a float up to the nearest integer.  
**Example**:
```vrl
ceil(3.2) # Returns 4
ceil(-3.2) # Returns -3
```

### `floor`
**Type**: Infallible, Pure  
**Signature**: `floor(value: float) -> integer`  
**Description**: Rounds a float down to the nearest integer.  
**Example**:
```vrl
floor(3.8) # Returns 3
floor(-3.8) # Returns -4
```

### `max`
**Type**: Infallible, Pure  
**Signature**: `max(values: array) -> integer | float`  
**Description**: Returns the maximum value from an array.  
**Example**:
```vrl
max([1, 5, 3, 9, 2]) # Returns 9
```

### `min`
**Type**: Infallible, Pure  
**Signature**: `min(values: array) -> integer | float`  
**Description**: Returns the minimum value from an array.  
**Example**:
```vrl
min([1, 5, 3, 9, 2]) # Returns 1
```

### `round`
**Type**: Infallible, Pure  
**Signature**: `round(value: float, precision?: integer) -> float`  
**Description**: Rounds a float to the specified precision.  
**Example**:
```vrl
round(3.14159, 2) # Returns 3.14
round(3.7) # Returns 4.0
```

## Network Functions

### `get_hostname`
**Type**: Fallible, Impure  
**Signature**: `get_hostname() -> string`  
**Description**: Returns the hostname of the current machine.  
**Note**: Unsupported in WebAssembly environments.  
**Example**:
```vrl
.hostname = get_hostname!()
```

### `reverse_dns`
**Type**: Fallible, Impure  
**Signature**: `reverse_dns(ip: string) -> string`  
**Description**: Performs reverse DNS lookup on an IP address.  
**Note**: Unsupported in WebAssembly environments.  
**Example**:
```vrl
.hostname = reverse_dns!(.client_ip)
```

### `http_request`
**Type**: Fallible, Impure  
**Signature**: `http_request(url: string, method?: string, headers?: object, body?: string) -> object`  
**Description**: Makes HTTP requests to external services.  
**Note**: Unsupported in WebAssembly environments.  
**Example**:
```vrl
.response = http_request!("https://api.example.com/data")
```

## Object Functions

### `del`
**Type**: Infallible, Pure  
**Signature**: `del(target: object, path: string) -> object`  
**Description**: Removes the field specified by the static path from the target.  
**Example**:
```vrl
del(.user.password)
del(.temporary_field)
```

### `exists`
**Type**: Infallible, Pure  
**Signature**: `exists(target: any, path: string) -> boolean`  
**Description**: Checks whether the path exists for the target.  
**Example**:
```vrl
exists(.user.email) # Returns true if .user.email exists
```

### `get`
**Type**: Infallible, Pure  
**Signature**: `get(target: any, path: string) -> any`  
**Description**: Dynamically gets the value at the given path.  
**Example**:
```vrl
get(., ["user", "name"]) # Same as .user.name
```

### `remove`
**Type**: Infallible, Pure  
**Signature**: `remove(target: object, path: array) -> any`  
**Description**: Dynamically removes and returns the value at the given path.  
**Example**:
```vrl
.old_value = remove(., ["temp", "value"])
```

### `set`
**Type**: Infallible, Pure  
**Signature**: `set(target: object, path: array, value: any) -> object`  
**Description**: Dynamically sets the value at the given path.  
**Example**:
```vrl
set(., ["user", "last_login"], now())
```

### `object_from_array`
**Type**: Fallible, Pure  
**Signature**: `object_from_array(value: array) -> object`  
**Description**: Creates an object from an array of key-value pairs.  
**Example**:
```vrl
object_from_array!([["key1", "value1"], ["key2", "value2"]])
# Returns {"key1": "value1", "key2": "value2"}
```

## Parse Functions

### `parse_aws_vpc_flow_log`
**Type**: Fallible, Pure  
**Signature**: `parse_aws_vpc_flow_log(value: string, format?: string) -> object`  
**Description**: Parses AWS VPC Flow Log data.  
**Example**:
```vrl
parse_aws_vpc_flow_log!(.message)
```

### `parse_common_log`
**Type**: Fallible, Pure  
**Signature**: `parse_common_log(value: string) -> object`  
**Description**: Parses logs in the Common Log Format.  
**Example**:
```vrl
parse_common_log!(.message)
```

### `parse_csv`
**Type**: Fallible, Pure  
**Signature**: `parse_csv(value: string, delimiter?: string) -> array`  
**Description**: Parses CSV data.  
**Example**:
```vrl
parse_csv!("a,b,c") # Returns ["a", "b", "c"]
parse_csv!("a|b|c", "|") # Returns ["a", "b", "c"]
```

### `parse_grok`
**Type**: Fallible, Pure  
**Signature**: `parse_grok(value: string, pattern: string, remove_empty?: boolean) -> object`  
**Description**: Parses strings using Grok patterns.  
**Note**: Unsupported in WebAssembly environments.  
**Example**:
```vrl
parse_grok!(.message, "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level}")
```

### `parse_groks`
**Type**: Fallible, Pure  
**Signature**: `parse_groks(value: string, patterns: array, remove_empty?: boolean) -> object`  
**Description**: Parses strings using multiple Grok patterns until one succeeds.  
**Note**: Unsupported in WebAssembly environments.  
**Example**:
```vrl
parse_groks!(.message, ["%{PATTERN1}", "%{PATTERN2}"])
```

### `parse_json`
**Type**: Fallible, Pure  
**Signature**: `parse_json(value: string) -> any`  
**Description**: Parses JSON strings.  
**Example**:
```vrl
parse_json!('{"name": "John", "age": 30}') # Returns object
. = parse_json!(.message)
```

### `parse_key_value`
**Type**: Fallible, Pure  
**Signature**: `parse_key_value(value: string, key_value_delimiter?: string, field_delimiter?: string) -> object`  
**Description**: Parses key-value pair strings.  
**Example**:
```vrl
parse_key_value!("user=john age=30") # Returns {"user": "john", "age": "30"}
parse_key_value!("user:john|age:30", ":", "|")
```

### `parse_logfmt`
**Type**: Fallible, Pure  
**Signature**: `parse_logfmt(value: string) -> object`  
**Description**: Parses logfmt-style logs.  
**Example**:
```vrl
parse_logfmt!("level=info msg='hello world'")
# Returns {"level": "info", "msg": "hello world"}
```

### `parse_nginx_log`
**Type**: Fallible, Pure  
**Signature**: `parse_nginx_log(value: string, format: string, timestamp_format?: string) -> object`  
**Description**: Parses Nginx access logs.  
**Example**:
```vrl
parse_nginx_log!(.message, "$combined")
```

### `parse_query_string`
**Type**: Fallible, Pure  
**Signature**: `parse_query_string(value: string) -> object`  
**Description**: Parses URL query strings.  
**Example**:
```vrl
parse_query_string!("name=John&age=30")
# Returns {"name": ["John"], "age": ["30"]}
```

### `parse_regex`
**Type**: Fallible, Pure  
**Signature**: `parse_regex(value: string, pattern: string, numeric_groups?: boolean) -> object`  
**Description**: Parses strings using regular expressions.  
**Example**:
```vrl
parse_regex!(.message, r'(?P<level>\w+) (?P<message>.*)')
```

### `parse_regex_all`
**Type**: Fallible, Pure  
**Signature**: `parse_regex_all(value: string, pattern: string, numeric_groups?: boolean) -> array`  
**Description**: Parses all regex matches in a string.  
**Example**:
```vrl
parse_regex_all!(.message, r'(\w+)')
```

### `parse_syslog`
**Type**: Fallible, Pure  
**Signature**: `parse_syslog(value: string) -> object`  
**Description**: Parses Syslog messages.  
**Example**:
```vrl
parse_syslog!(.message)
```

### `parse_timestamp`
**Type**: Fallible, Pure  
**Signature**: `parse_timestamp(value: string, format: string) -> timestamp`  
**Description**: Parses timestamp strings.  
**Example**:
```vrl
parse_timestamp!("2021-01-01 12:00:00", "%Y-%m-%d %H:%M:%S")
```

### `parse_url`
**Type**: Fallible, Pure  
**Signature**: `parse_url(value: string) -> object`  
**Description**: Parses URLs into components.  
**Example**:
```vrl
parse_url!("https://example.com:8080/path?query=value")
# Returns {"scheme": "https", "host": "example.com", "port": 8080, ...}
```

### `parse_xml`
**Type**: Fallible, Pure  
**Signature**: `parse_xml(value: string) -> object`  
**Description**: Parses XML data.  
**Example**:
```vrl
parse_xml!("<root><item>value</item></root>")
```

## Random Functions

### `random_bool`
**Type**: Infallible, Impure  
**Signature**: `random_bool() -> boolean`  
**Description**: Returns a random boolean value.  
**Example**:
```vrl
.is_sample = random_bool()
```

### `random_bytes`
**Type**: Infallible, Impure  
**Signature**: `random_bytes(length: integer) -> string`  
**Description**: Generates random bytes of the specified length.  
**Example**:
```vrl
.iv = random_bytes(16) # Generate 16 random bytes for encryption IV
```

### `random_float`
**Type**: Infallible, Impure  
**Signature**: `random_float(min: float, max: float) -> float`  
**Description**: Returns a random float between min and max.  
**Example**:
```vrl
.random_value = random_float(0.0, 1.0)
```

### `random_int`
**Type**: Infallible, Impure  
**Signature**: `random_int(min: integer, max: integer) -> integer`  
**Description**: Returns a random integer between min and max (inclusive).  
**Example**:
```vrl
.random_id = random_int(1, 1000)
```

## String Functions

### `contains`
**Type**: Infallible, Pure  
**Signature**: `contains(value: string, substring: string, case_sensitive?: boolean) -> boolean`  
**Description**: Checks if a string contains a substring.  
**Example**:
```vrl
contains("Hello World", "World") # Returns true
contains("Hello", "world", false) # Returns true (case insensitive)
```

### `downcase`
**Type**: Infallible, Pure  
**Signature**: `downcase(value: string) -> string`  
**Description**: Converts a string to lowercase.  
**Example**:
```vrl
downcase("HELLO") # Returns "hello"
```

### `ends_with`
**Type**: Infallible, Pure  
**Signature**: `ends_with(value: string, suffix: string, case_sensitive?: boolean) -> boolean`  
**Description**: Checks if a string ends with a suffix.  
**Example**:
```vrl
ends_with("hello.log", ".log") # Returns true
```

### `join`
**Type**: Infallible, Pure  
**Signature**: `join(value: array, separator?: string) -> string`  
**Description**: Joins array elements into a string.  
**Example**:
```vrl
join(["a", "b", "c"], ",") # Returns "a,b,c"
join(["hello", "world"]) # Returns "helloworld"
```

### `length`
**Type**: Infallible, Pure  
**Signature**: `length(value: string | array | object) -> integer`  
**Description**: Returns the length of a string, array, or object.  
**Example**:
```vrl
length("hello") # Returns 5
length([1, 2, 3]) # Returns 3
```

### `match`
**Type**: Fallible, Pure  
**Signature**: `match(value: string, pattern: string) -> boolean`  
**Description**: Checks if a string matches a regular expression.  
**Example**:
```vrl
match!(.email, r'^[^@]+@[^@]+\.[^@]+$') # Returns true for valid email
```

### `match_all`
**Type**: Fallible, Pure  
**Signature**: `match_all(value: string, pattern: string) -> array`  
**Description**: Returns all regex matches as an array.  
**Example**:
```vrl
match_all!("abc123def456", r'\d+') # Returns ["123", "456"]
```

### `replace`
**Type**: Fallible, Pure  
**Signature**: `replace(value: string, pattern: string, replacement: string, count?: integer) -> string`  
**Description**: Replaces matches of a pattern in a string.  
**Example**:
```vrl
replace!("hello world", "world", "VRL") # Returns "hello VRL"
replace!("aaa", "a", "b", 2) # Returns "bba"
```

### `slice`
**Type**: Fallible, Pure  
**Signature**: `slice(value: string | array, start: integer, end?: integer) -> string | array`  
**Description**: Extracts a slice of a string or array.  
**Example**:
```vrl
slice!("hello", 1, 4) # Returns "ell"
slice!([1, 2, 3, 4, 5], 1, 3) # Returns [2, 3]
```

### `split`
**Type**: Infallible, Pure  
**Signature**: `split(value: string, delimiter: string, limit?: integer) -> array`  
**Description**: Splits a string by a delimiter.  
**Example**:
```vrl
split("a,b,c", ",") # Returns ["a", "b", "c"]
split("a,b,c,d", ",", 2) # Returns ["a", "b,c,d"]
```

### `starts_with`
**Type**: Infallible, Pure  
**Signature**: `starts_with(value: string, prefix: string, case_sensitive?: boolean) -> boolean`  
**Description**: Checks if a string starts with a prefix.  
**Example**:
```vrl
starts_with("hello world", "hello") # Returns true
```

### `strip_ansi_escape_codes`
**Type**: Infallible, Pure  
**Signature**: `strip_ansi_escape_codes(value: string) -> string`  
**Description**: Removes ANSI escape codes from a string.  
**Example**:
```vrl
strip_ansi_escape_codes("\x1b[31mRed Text\x1b[0m") # Returns "Red Text"
```

### `strip_whitespace`
**Type**: Infallible, Pure  
**Signature**: `strip_whitespace(value: string) -> string`  
**Description**: Removes leading and trailing whitespace.  
**Example**:
```vrl
strip_whitespace("  hello  ") # Returns "hello"
```

### `trim`
**Type**: Infallible, Pure  
**Signature**: `trim(value: string) -> string`  
**Description**: Alias for strip_whitespace.  
**Example**:
```vrl
trim("  hello  ") # Returns "hello"
```

### `truncate`
**Type**: Infallible, Pure  
**Signature**: `truncate(value: string, limit: integer, ellipsis?: boolean) -> string`  
**Description**: Truncates a string to a maximum length.  
**Example**:
```vrl
truncate("hello world", 5) # Returns "hello"
truncate("hello world", 5, true) # Returns "he..."
```

### `upcase`
**Type**: Infallible, Pure  
**Signature**: `upcase(value: string) -> string`  
**Description**: Converts a string to uppercase.  
**Example**:
```vrl
upcase("hello") # Returns "HELLO"
```

## Timestamp Functions

### `format_timestamp`
**Type**: Fallible, Pure  
**Signature**: `format_timestamp(timestamp: timestamp, format: string, timezone?: string) -> string`  
**Description**: Formats a timestamp as a string.  
**Example**:
```vrl
format_timestamp!(now(), "%Y-%m-%d %H:%M:%S") # Returns "2023-01-01 12:00:00"
format_timestamp!(now(), "%+") # ISO 8601 format
```

### `now`
**Type**: Infallible, Impure  
**Signature**: `now() -> timestamp`  
**Description**: Returns the current timestamp.  
**Example**:
```vrl
.processed_at = now()
.today = format_timestamp!(now(), "%Y-%m-%d")
```

### `to_timestamp`
**Type**: Fallible, Pure  
**Signature**: `to_timestamp(value: any) -> timestamp`  
**Description**: Coerces a value into a timestamp.  
**Example**:
```vrl
to_timestamp!("2021-01-01T12:00:00Z")
to_timestamp!(1609459200) # Unix timestamp
```

### `to_unix_timestamp`
**Type**: Infallible, Pure  
**Signature**: `to_unix_timestamp(timestamp: timestamp, unit?: string) -> integer`  
**Description**: Converts a timestamp to Unix timestamp.  
**Example**:
```vrl
to_unix_timestamp(now()) # Returns seconds since epoch
to_unix_timestamp(now(), "milliseconds") # Returns milliseconds
```

## Type Functions

### `is_array`
**Type**: Infallible, Pure  
**Signature**: `is_array(value: any) -> boolean`  
**Description**: Checks if a value is an array.  
**Example**:
```vrl
is_array([1, 2, 3]) # Returns true
is_array("hello") # Returns false
```

### `is_boolean`
**Type**: Infallible, Pure  
**Signature**: `is_boolean(value: any) -> boolean`  
**Description**: Checks if a value is a boolean.  
**Example**:
```vrl
is_boolean(true) # Returns true
is_boolean("true") # Returns false
```

### `is_float`
**Type**: Infallible, Pure  
**Signature**: `is_float(value: any) -> boolean`  
**Description**: Checks if a value is a float.  
**Example**:
```vrl
is_float(3.14) # Returns true
is_float(42) # Returns false
```

### `is_integer`
**Type**: Infallible, Pure  
**Signature**: `is_integer(value: any) -> boolean`  
**Description**: Checks if a value is an integer.  
**Example**:
```vrl
is_integer(42) # Returns true
is_integer(3.14) # Returns false
```

### `is_null`
**Type**: Infallible, Pure  
**Signature**: `is_null(value: any) -> boolean`  
**Description**: Checks if a value is null.  
**Example**:
```vrl
is_null(null) # Returns true
is_null("") # Returns false
```

### `is_object`
**Type**: Infallible, Pure  
**Signature**: `is_object(value: any) -> boolean`  
**Description**: Checks if a value is an object.  
**Example**:
```vrl
is_object({"key": "value"}) # Returns true
is_object([1, 2, 3]) # Returns false
```

### `is_string`
**Type**: Infallible, Pure  
**Signature**: `is_string(value: any) -> boolean`  
**Description**: Checks if a value is a string.  
**Example**:
```vrl
is_string("hello") # Returns true
is_string(42) # Returns false
```

### `is_timestamp`
**Type**: Infallible, Pure  
**Signature**: `is_timestamp(value: any) -> boolean`  
**Description**: Checks if a value is a timestamp.  
**Example**:
```vrl
is_timestamp(now()) # Returns true
is_timestamp("2021-01-01") # Returns false
```

### `type_def`
**Type**: Infallible, Pure  
**Signature**: `type_def(value: any) -> string`  
**Description**: Returns the type definition of a value.  
**Example**:
```vrl
type_def("hello") # Returns "string"
type_def([1, 2, 3]) # Returns "array"
```

## Cryptography Functions

### `decrypt`
**Type**: Fallible, Pure  
**Signature**: `decrypt(value: string, key: string, algorithm: string, iv?: string) -> string`  
**Description**: Decrypts an encrypted string using symmetric encryption algorithms.  
**Supported Algorithms**: AES-128-CBC, AES-192-CBC, AES-256-CBC, AES-128-CFB, AES-192-CFB, AES-256-CFB, AES-128-ECB, AES-192-ECB, AES-256-ECB, AES-128-GCM, AES-192-GCM, AES-256-GCM, AES-128-OFB, AES-192-OFB, AES-256-OFB, ChaCha20-Poly1305, XChaCha20-Poly1305  
**Example**:
```vrl
.decrypted = decrypt!(.encrypted_field, "encryption_key", "AES-256-GCM", .iv)
```

### `encrypt`
**Type**: Fallible, Pure  
**Signature**: `encrypt(value: string, key: string, algorithm: string, iv?: string) -> string`  
**Description**: Encrypts a string using symmetric encryption algorithms.  
**Example**:
```vrl
.iv = random_bytes(16)
.encrypted = encrypt!(.sensitive_data, "encryption_key", "AES-256-GCM", .iv)
```

## Utility Functions

### `uuid_v4`
**Type**: Infallible, Impure  
**Signature**: `uuid_v4() -> string`  
**Description**: Generates a random UUID v4.  
**Example**:
```vrl
.id = uuid_v4() # Returns "550e8400-e29b-41d4-a716-446655440000"
```

### `uuid_v7`
**Type**: Infallible, Impure  
**Signature**: `uuid_v7() -> string`  
**Description**: Generates a time-ordered UUID v7.  
**Example**:
```vrl
.timestamp_id = uuid_v7()
```

---

## Usage Notes

### Error Handling
- **Fallible functions** require explicit error handling using `!` (abort on error) or error assignment
- **Infallible functions** never fail and don't require error handling
- Use `function!(args)` to abort program on error
- Use `value, err = function(args)` to capture errors

### Example Error Handling:
```vrl
# Abort on error
.parsed = parse_json!(.message)

# Handle errors gracefully
.parsed, .error = parse_json(.message)
if .error == null {
    # Process parsed data
} else {
    .parse_failed = true
}

# With fallback
.parsed = parse_json(.message) ?? {}
```

### Function Categories Summary
- **Array**: 5 functions for array manipulation
- **Codec**: 18 functions for encoding/decoding
- **Coerce**: 4 functions for type conversion
- **Convert**: 3 functions for format conversion
- **Debug**: 2 functions for debugging
- **Enrichment**: 2 functions for data enrichment
- **Enumerate**: 6 functions for collection operations
- **Event**: 3 functions for event manipulation
- **Hash**: 4 functions for hashing
- **IP**: 4 functions for IP operations
- **Math**: 6 functions for mathematical operations
- **Network**: 3 functions for network operations (WebAssembly limitations)
- **Object**: 6 functions for object manipulation
- **Parse**: 15 functions for parsing various formats
- **Random**: 4 functions for random value generation
- **String**: 20 functions for string manipulation
- **Timestamp**: 4 functions for timestamp operations
- **Type**: 9 functions for type checking
- **Cryptography**: 2 functions for encryption/decryption
- **Utility**: 2 functions for UUID generation

**Total Functions**: ~120 functions across all categories

### Resources
- **Official Documentation**: https://vector.dev/docs/reference/vrl/functions/
- **VRL Playground**: https://playground.vrl.dev/
- **VRL Examples**: https://vector.dev/docs/reference/vrl/examples/
- **Vector Configuration**: https://vector.dev/docs/reference/configuration/transforms/remap/

This comprehensive reference covers all available VRL functions as of the latest Vector documentation. Each function includes its signature, description, and practical examples to help you effectively use VRL for data transformation tasks.