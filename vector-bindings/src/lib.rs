// pyo3 0.22's #[pymethods]/#[pyfunction] macro expansion predates edition
// 2024's unsafe_op_in_unsafe_fn tightening and emits a redundant PyErr->PyErr
// conversion in its generated trampolines - neither lint fires on our own
// code. Tracked for removal on the pyo3 0.29+ migration (see repo CLAUDE.md
// / plan Decision Log, pyo3 0.22 vs Python 3.14 gap).
#![allow(unsafe_op_in_unsafe_fn, clippy::useless_conversion)]

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyDictMethods};
use serde_json::Value as JsonValue;
use std::collections::BTreeMap;
use std::num::Saturating;
use std::time::Instant;
use vrl::compiler::prelude::NotNan;
use vrl::compiler::runtime::{Runtime, Terminate};
use vrl::compiler::state::RuntimeState;
use vrl::compiler::{Program, TargetValue, TimeZone, compile};
use vrl::value::{Secrets, Value};

/// VRL execution result with error details
#[pyclass]
#[derive(Clone, Debug)]
struct VrlResult {
    #[pyo3(get)]
    success: bool,
    #[pyo3(get)]
    output: Option<String>,
    #[pyo3(get)]
    error: Option<String>,
    #[pyo3(get)]
    error_type: Option<String>,
}

#[pymethods]
impl VrlResult {
    fn __repr__(&self) -> String {
        format!(
            "VrlResult(success={}, output={:?}, error={:?})",
            self.success, self.output, self.error
        )
    }
}

// The VRL parser recurses per nesting level with no depth limit of its
// own; past a few hundred levels of (), {}, or [] it overflows the stack
// and segfaults the whole process (uncatchable in Rust - a Python caller
// could crash the interpreter with a single malicious VRL string). This
// cap rejects the input before it reaches the parser; ordinary VRL never
// nests anywhere near this deep.
const MAX_VRL_NESTING_DEPTH: usize = 64;

fn check_nesting_depth(vrl_code: &str) -> Result<(), String> {
    let mut depth: usize = 0;
    let mut max_depth: usize = 0;
    for c in vrl_code.chars() {
        match c {
            '(' | '{' | '[' => {
                depth += 1;
                max_depth = max_depth.max(depth);
            }
            ')' | '}' | ']' => {
                depth = depth.saturating_sub(1);
            }
            _ => {}
        }
    }
    if max_depth > MAX_VRL_NESTING_DEPTH {
        return Err(format!(
            "VRL source nests {max_depth} levels deep, exceeding the {MAX_VRL_NESTING_DEPTH}-level limit"
        ));
    }
    Ok(())
}

/// Compile VRL code into a runnable program using real Vector VRL compiler
fn compile_vrl_program(vrl_code: &str) -> Result<Program, String> {
    check_nesting_depth(vrl_code)?;

    // Get all VRL standard library functions
    let functions = vrl::stdlib::all();

    // Compile VRL code using VRL's real compiler (v0.27+ API - simplified, no hardcoding!)
    compile(vrl_code, &functions)
        .map(|result| result.program)
        .map_err(|diagnostics| {
            // Format compilation errors
            let mut errors = Vec::new();
            for diagnostic in diagnostics {
                errors.push(diagnostic.message().to_string());
            }
            errors.join("\n")
        })
}

/// Execute VRL program on a single event using Vector's VRL runtime
fn execute_vrl_on_event(program: &Program, event_data: &str) -> Result<Value, String> {
    // Parse input as JSON or plain text
    let event_value = if event_data.trim().starts_with('{') {
        // Try JSON parsing
        match serde_json::from_str::<JsonValue>(event_data) {
            Ok(json_val) => {
                // Convert JSON to VRL Value
                json_to_vrl_value(json_val)
            }
            Err(_) => {
                // Fallback to plain text
                let mut obj = BTreeMap::new();
                obj.insert("message".into(), Value::from(event_data));
                Value::Object(obj)
            }
        }
    } else {
        // Plain text - wrap in message field
        let mut obj = BTreeMap::new();
        obj.insert("message".into(), Value::from(event_data));
        Value::Object(obj)
    };

    // Wrap in TargetValue for v0.27+ API (no hardcoded types!)
    let mut target = TargetValue {
        value: event_value,
        metadata: Value::Object(BTreeMap::new()),
        secrets: Secrets::new(),
    };

    // Create VRL runtime with RuntimeState for v0.27+ API
    let timezone = TimeZone::default();
    let state = RuntimeState::default();
    let mut runtime = Runtime::new(state);

    // Execute VRL program using Vector's runtime
    match runtime.resolve(&mut target, program, &timezone) {
        // The VRL program's own return value is discarded here; the mutated
        // `target.value` (the event after any `.field = ...` assignments) is
        // what callers expect back.
        Ok(_) => Ok(target.value),
        Err(terminate) => {
            let error_msg = match terminate {
                Terminate::Abort(msg) => format!("VRL aborted: {}", msg),
                Terminate::Error(err) => format!("VRL error: {}", err),
            };
            Err(error_msg)
        }
    }
}

/// Convert JSON value to VRL value
fn json_to_vrl_value(json: JsonValue) -> Value {
    match json {
        JsonValue::Null => Value::Null,
        JsonValue::Bool(b) => Value::Boolean(b),
        JsonValue::Number(n) => {
            if let Some(i) = n.as_i64() {
                Value::Integer(i)
            } else if let Some(f) = n.as_f64() {
                // Value::Float requires vrl's own NotNan type, not a separately
                // pinned ordered-float crate -- the two can diverge in version.
                // 0.0 is never NaN, so this fallback can never fail.
                Value::Float(
                    NotNan::new(f).unwrap_or_else(|_| NotNan::new(0.0).expect("0.0 is never NaN")),
                )
            } else {
                Value::Null
            }
        }
        JsonValue::String(s) => Value::Bytes(s.into()),
        JsonValue::Array(arr) => Value::Array(arr.into_iter().map(json_to_vrl_value).collect()),
        JsonValue::Object(obj) => {
            let mut map = BTreeMap::new();
            for (k, v) in obj {
                map.insert(k.into(), json_to_vrl_value(v));
            }
            Value::Object(map)
        }
    }
}

/// Convert VRL value to JSON value
fn vrl_value_to_json(value: Value) -> JsonValue {
    match value {
        Value::Null => JsonValue::Null,
        Value::Boolean(b) => JsonValue::Bool(b),
        Value::Integer(i) => JsonValue::Number(i.into()),
        Value::Float(f) => {
            JsonValue::Number(serde_json::Number::from_f64(f.into_inner()).unwrap_or(0.into()))
        }
        Value::Bytes(b) => JsonValue::String(String::from_utf8_lossy(&b).to_string()),
        Value::Array(arr) => JsonValue::Array(arr.into_iter().map(vrl_value_to_json).collect()),
        Value::Object(obj) => {
            let mut map = serde_json::Map::new();
            for (k, v) in obj {
                map.insert(k.to_string(), vrl_value_to_json(v));
            }
            JsonValue::Object(map)
        }
        Value::Timestamp(ts) => JsonValue::String(ts.to_string()),
        Value::Regex(r) => JsonValue::String(r.to_string()),
    }
}

/// Convert one event's VRL outcome into the dict the Python caller gets back.
///
/// `execute_vrl` and `Vector::process_logs` both funnel through here, which is
/// what keeps the two entry points returning one shape. On success the event's
/// top-level fields are flattened into the dict; on a per-event runtime error
/// the dict carries `error` and `original` INSTEAD of the event's fields, so
/// `"error" in result` is the failure check for both.
///
/// Nested objects and arrays are stringified, matching what the Python API
/// reference documents - a caller wanting the structure back calls
/// `json.loads` on them.
fn vrl_outcome_to_py_dict(
    py: Python<'_>,
    outcome: Result<Value, String>,
    original: &str,
) -> PyResult<PyObject> {
    let result_dict = PyDict::new_bound(py);

    match outcome {
        Ok(vrl_result) => {
            if let JsonValue::Object(obj) = vrl_value_to_json(vrl_result) {
                for (key, value) in obj {
                    let py_value = match value {
                        JsonValue::String(s) => s.into_py(py),
                        JsonValue::Number(n) => {
                            if let Some(i) = n.as_i64() {
                                i.into_py(py)
                            } else if let Some(f) = n.as_f64() {
                                f.into_py(py)
                            } else {
                                py.None()
                            }
                        }
                        JsonValue::Bool(b) => b.into_py(py),
                        JsonValue::Null => py.None(),
                        JsonValue::Array(_) | JsonValue::Object(_) => value.to_string().into_py(py),
                    };
                    result_dict.set_item(key, py_value)?;
                }
            }
        }
        Err(e) => {
            result_dict.set_item("error", e)?;
            result_dict.set_item("original", original)?;
        }
    }

    Ok(result_dict.into())
}

/// In-process Vector configuration and execution
#[pyclass]
#[derive(Debug)]
struct Vector {
    // Accepted by Vector::new() but never applied to process_logs/initialize -
    // config-driven pipeline behaviour is not implemented, and the Python API
    // reference documents that rather than the dict being silently dropped.
    #[allow(dead_code)]
    config: JsonValue,
    initialized: bool,
    // Counters behind get_stats(), Saturating so telemetry pegs at u64::MAX
    // rather than panicking on overflow. Every event process_logs attempts
    // lands in exactly one of events_processed or errors.
    events_processed: Saturating<u64>,
    errors: Saturating<u64>,
    bytes_processed: Saturating<u64>,
    // Set by initialize(), so uptime_seconds is 0.0 on an uninitialized
    // pipeline rather than timed from construction.
    started_at: Option<Instant>,
}

#[pymethods]
impl Vector {
    #[new]
    fn new(config_dict: &Bound<'_, PyDict>) -> PyResult<Self> {
        // PyDict::to_string() is Python repr() (single-quoted, Python
        // literals), not JSON - only an empty dict happened to parse as
        // valid JSON (`{}`). Round-trip through Python's own `json`
        // module so nested dicts/lists/strings/numbers/bools/None are
        // all serialized correctly.
        let py = config_dict.py();
        let json_module = py.import_bound("json")?;
        let config_str: String = json_module
            .call_method1("dumps", (config_dict,))?
            .extract()?;
        let config: JsonValue = serde_json::from_str(&config_str).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid config: {}", e))
        })?;

        Ok(Vector {
            config,
            initialized: false,
            events_processed: Saturating(0),
            errors: Saturating(0),
            bytes_processed: Saturating(0),
            started_at: None,
        })
    }

    /// Initialize Vector pipeline in-process
    ///
    /// Starts the uptime clock and zeroes the counters, so `get_stats()`
    /// always describes the run since the most recent `initialize()` rather
    /// than mixing two runs' numbers together.
    fn initialize(&mut self) -> PyResult<bool> {
        self.initialized = true;
        self.events_processed = Saturating(0);
        self.errors = Saturating(0);
        self.bytes_processed = Saturating(0);
        self.started_at = Some(Instant::now());
        Ok(true)
    }

    /// Process logs in-process using real VRL runtime
    fn process_logs(&mut self, logs: Vec<String>, vrl_code: String) -> PyResult<Vec<PyObject>> {
        if !self.initialized {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Vector not initialized",
            ));
        }

        // Compile VRL program using real Vector VRL compiler
        let program = compile_vrl_program(&vrl_code).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "VRL compilation failed: {}",
                e
            ))
        })?;

        Python::with_gil(|py| {
            let mut results = Vec::with_capacity(logs.len());

            for log in logs {
                // bytes_processed is input volume read, so an event that
                // fails at runtime still counts its bytes.
                self.bytes_processed += Saturating(log.len() as u64);

                let outcome = execute_vrl_on_event(&program, &log);
                if outcome.is_ok() {
                    self.events_processed += Saturating(1);
                } else {
                    self.errors += Saturating(1);
                }

                results.push(vrl_outcome_to_py_dict(py, outcome, &log)?);
            }

            Ok(results)
        })
    }

    /// Get Vector runtime statistics
    ///
    /// Real accumulated counts, measured from the last `initialize()`. A
    /// batch whose VRL fails to COMPILE raises before any event is touched
    /// and so moves no counter - `errors` counts per-event runtime failures.
    fn get_stats(&self) -> PyResult<PyObject> {
        let uptime_seconds = self
            .started_at
            .map_or(0.0, |started| started.elapsed().as_secs_f64());

        Python::with_gil(|py| {
            let stats_dict = PyDict::new_bound(py);
            stats_dict.set_item("events_processed", self.events_processed.0)?;
            stats_dict.set_item("bytes_processed", self.bytes_processed.0)?;
            stats_dict.set_item("errors", self.errors.0)?;
            stats_dict.set_item("uptime_seconds", uptime_seconds)?;

            Ok(stats_dict.into())
        })
    }
}

/// Execute VRL transformation in-process using real Vector VRL runtime
#[pyfunction]
fn execute_vrl(vrl_code: String, input_data: Vec<String>) -> PyResult<Vec<PyObject>> {
    // Compile VRL program using real Vector VRL compiler
    let program = compile_vrl_program(&vrl_code).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("VRL compilation failed: {}", e))
    })?;

    Python::with_gil(|py| {
        let mut results = Vec::with_capacity(input_data.len());

        for input in input_data {
            let outcome = execute_vrl_on_event(&program, &input);
            results.push(vrl_outcome_to_py_dict(py, outcome, &input)?);
        }

        Ok(results)
    })
}

/// Validate VRL syntax using real Vector VRL compiler
#[pyfunction]
fn validate_vrl(vrl_code: String) -> PyResult<VrlResult> {
    match compile_vrl_program(&vrl_code) {
        Ok(_) => Ok(VrlResult {
            success: true,
            output: Some("VRL syntax valid".to_string()),
            error: None,
            error_type: None,
        }),
        Err(e) => Ok(VrlResult {
            success: false,
            output: None,
            error: Some(e.clone()),
            error_type: Some("compilation_error".to_string()),
        }),
    }
}

/// Get THG performance metrics for VRL code using real VRL execution
#[pyfunction]
#[pyo3(signature = (vrl_code, test_data, iterations=None))]
fn get_vrl_performance(
    vrl_code: String,
    test_data: Vec<String>,
    iterations: Option<u32>,
) -> PyResult<PyObject> {
    let iter_count = iterations.unwrap_or(100);

    // test_data.len() * iter_count is fully materialised in memory before
    // execution; both are caller-controlled, so cap the total to bound
    // worst-case memory use.
    const MAX_TOTAL_EVENTS: usize = 1_000_000;
    let total_requested = test_data.len().saturating_mul(iter_count as usize);
    if total_requested > MAX_TOTAL_EVENTS {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "requested {total_requested} events (test_data.len() * iterations) exceeds the {MAX_TOTAL_EVENTS} limit"
        )));
    }

    let start_time = std::time::Instant::now();

    // Execute VRL processing with real VRL runtime
    let repeated_data: Vec<String> = test_data
        .iter()
        .cycle()
        .take(test_data.len() * iter_count as usize)
        .cloned()
        .collect();
    let _results = execute_vrl(vrl_code.clone(), repeated_data)?;
    let processing_time = start_time.elapsed();

    let total_events = test_data.len() * iter_count as usize;
    let events_per_second = if processing_time.as_secs_f64() > 0.0 {
        total_events as f64 / processing_time.as_secs_f64()
    } else {
        0.0
    };

    Python::with_gil(|py| {
        let metrics_dict = pyo3::types::PyDict::new_bound(py);
        metrics_dict.set_item("events_per_second", events_per_second)?;
        metrics_dict.set_item("processing_time_seconds", processing_time.as_secs_f64())?;
        metrics_dict.set_item("total_events", total_events)?;
        metrics_dict.set_item("thg_score", events_per_second.min(1000.0))?;

        Ok(metrics_dict.into())
    })
}

/// Vector data processing bindings for Python with real VRL execution
#[pymodule]
fn vector_bindings(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;

    // Add manually-written Vector class for in-process execution
    m.add_class::<Vector>()?;
    m.add_class::<VrlResult>()?;

    // Add VRL functions with real Vector VRL runtime
    m.add_function(wrap_pyfunction!(execute_vrl, m)?)?;
    m.add_function(wrap_pyfunction!(validate_vrl, m)?)?;
    m.add_function(wrap_pyfunction!(get_vrl_performance, m)?)?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nesting_depth_within_limit_is_accepted() {
        let vrl = format!("{}{}{}", "(".repeat(64), "true", ")".repeat(64));
        assert!(check_nesting_depth(&vrl).is_ok());
    }

    #[test]
    fn nesting_depth_over_limit_is_rejected() {
        let vrl = format!("{}{}{}", "(".repeat(65), "true", ")".repeat(65));
        assert!(check_nesting_depth(&vrl).is_err());
    }

    #[test]
    fn compile_rejects_deeply_nested_vrl_before_parsing() {
        // Regression test: this exact shape used to segfault the process
        // (unbounded parser recursion) instead of returning an error.
        let vrl = format!(".x = {}{}{}", "(".repeat(1000), "true", ")".repeat(1000));
        let result = compile_vrl_program(&vrl);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("nests"));
    }

    #[test]
    fn compile_accepts_ordinary_vrl() {
        let program = compile_vrl_program(r#".upper = upcase!(to_string!(.message))"#);
        assert!(program.is_ok());
    }

    #[test]
    fn compile_rejects_invalid_vrl_syntax() {
        let result = compile_vrl_program("this is not valid VRL {{{");
        assert!(result.is_err());
    }

    #[test]
    fn env_system_network_functions_are_unavailable() {
        // Regression test for the vrl sandbox escape: these functions must
        // stay undefined so caller-supplied VRL cannot read the host
        // environment or make network requests.
        for call in [
            r#".x = get_env_var!("HOME")"#,
            r#".x = get_hostname!()"#,
            r#".x = http_request!("http://169.254.169.254/")"#,
            r#".x = dns_lookup!("example.com")"#,
        ] {
            let result = compile_vrl_program(call);
            assert!(result.is_err(), "expected {call:?} to fail to compile");
        }
    }

    #[test]
    fn execute_vrl_on_event_runs_parse_json_and_mutates_event() {
        let program = compile_vrl_program(
            r#"
            parsed, err = parse_json(.message)
            if err == null {
                .level = parsed.level
            }
            "#,
        )
        .expect("valid VRL compiles");

        let output = execute_vrl_on_event(&program, r#"{"message": "{\"level\": \"info\"}"}"#)
            .expect("execution succeeds");
        let json = vrl_value_to_json(output);
        assert_eq!(json.get("level").and_then(|v| v.as_str()), Some("info"));
    }

    #[test]
    fn execute_vrl_on_event_reports_runtime_errors() {
        // parse_json! (fallible-fn-without-handling) aborts at runtime when
        // the input isn't valid JSON.
        let program = compile_vrl_program(r#".parsed = parse_json!(.message)"#).expect("compiles");
        let result = execute_vrl_on_event(&program, r#"{"message": "not json"}"#);
        assert!(result.is_err());
    }
}
