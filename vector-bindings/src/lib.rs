mod enrichment;
mod nesting;
mod secrets;

use pyo3::IntoPyObjectExt;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyDictMethods};
use serde_json::Value as JsonValue;
use std::collections::BTreeMap;
use std::num::Saturating;
use std::sync::{Mutex, PoisonError};
use std::time::{Duration, Instant};
use vrl::compiler::prelude::{Function, NotNan};
use vrl::compiler::runtime::{Runtime, Terminate};
use vrl::compiler::state::RuntimeState;
use vrl::compiler::{Program, TimeZone, compile};
use vrl::value::Value;

use crate::nesting::check_nesting_depth;
use crate::secrets::EventTarget;

/// A secret store as it crosses the Python boundary, and as one event's VRL
/// program sees it.
type SecretMap = BTreeMap<String, String>;

/// VRL execution result with error details
#[pyclass(skip_from_py_object)]
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

/// Stack for compiling, running and dropping a VRL program.
///
/// The compiler and the expression tree recurse once per level of expression
/// depth, and operator chains (`a + b + c ...`, `else if` ladders, `!!!x`) nest
/// without any bracket for `check_nesting_depth` to count. A release build needs
/// about 4 KiB per level, so the 512 KiB a macOS thread gets overflows at 100
/// chained operators and the 8 MiB of a Linux main thread at about 2000. A stack
/// overflow aborts the interpreter, so the work runs on a thread of its own.
const VRL_STACK_BYTES: usize = 256 * 1024 * 1024;

/// Run `work` on a thread with `VRL_STACK_BYTES` of stack and return its result.
///
/// Falls back to the calling thread when the thread cannot be created, which
/// is what an address-space limit (`ulimit -v`) does to a 256 MiB reservation.
/// A panic in `work` resumes on the caller, as it would have without the thread.
fn on_vrl_stack<T: Send>(work: impl FnOnce() -> T + Send) -> T {
    let slot = Mutex::new(Some(work));
    let run = || {
        let work = slot.lock().unwrap_or_else(PoisonError::into_inner).take();
        work.map(|work| work())
    };
    let result = std::thread::scope(|scope| {
        match std::thread::Builder::new()
            .name("vrl".into())
            .stack_size(VRL_STACK_BYTES)
            .spawn_scoped(scope, run)
        {
            Ok(handle) => handle
                .join()
                .unwrap_or_else(|panic| std::panic::resume_unwind(panic)),
            Err(_) => run(),
        }
    });
    result.expect("the work closure runs exactly once")
}

/// Every VRL function a program compiled by this crate can call.
///
/// VRL's standard library, plus the enrichment and event-secret functions this
/// crate adds. Which stdlib functions are in the list depends on the features
/// the crate was built with - see the `full-stdlib` feature in Cargo.toml.
fn vrl_functions() -> Vec<Box<dyn Function>> {
    let mut functions = vrl::stdlib::all();
    functions.extend(enrichment::functions());
    functions.extend(secrets::functions());
    functions
}

/// Compile VRL code into a runnable program using real Vector VRL compiler
fn compile_vrl_program(vrl_code: &str) -> Result<Program, String> {
    check_nesting_depth(vrl_code)?;

    // Enrichment table names are resolved against the registry at compile time,
    // so a program naming an unregistered table fails here, not at runtime.
    let functions = vrl_functions();

    // Compile VRL code using VRL's real compiler (v0.27+ API - simplified, no hardcoding!)
    compile(vrl_code, &functions)
        .map(|result| result.program)
        .map_err(|diagnostics| {
            // Format compilation errors
            let mut errors = Vec::new();
            for diagnostic in diagnostics {
                errors.push(diagnostic_text(&diagnostic, vrl_code));
            }
            errors.join("\n")
        })
}

/// A diagnostic's message, with the function name added to "call to undefined
/// function".
///
/// The compiler keeps that name only in the label's span, so without this a
/// caller cannot tell a typo from a function this build deliberately omits.
fn diagnostic_text(diagnostic: &vrl::diagnostic::Diagnostic, vrl_code: &str) -> String {
    let message = diagnostic.message();
    if message != "call to undefined function" {
        return message.to_string();
    }
    let name = diagnostic
        .labels()
        .iter()
        .find(|label| label.primary)
        .and_then(|label| vrl_code.get(label.span.range()));
    match name {
        Some(name) => format!("{message} `{name}`"),
        None => message.to_string(),
    }
}

/// One event's VRL run: what the program produced, and the secrets it left.
///
/// `result` carries the mutated event on success and the runtime error
/// otherwise. `secrets` is the store as it stood when the program finished,
/// including after an abort - the VRL may have set secrets before failing.
pub(crate) struct EventOutcome {
    pub(crate) result: Result<Value, String>,
    pub(crate) secrets: SecretMap,
}

/// Compile `vrl_code` and run it over each event, all on the VRL stack.
///
/// Every event starts from a copy of `secrets`. The only error is a compile
/// failure, as the text `compile_vrl_program` produced.
fn run_events(
    vrl_code: &str,
    events: &[String],
    secrets: &SecretMap,
) -> Result<Vec<EventOutcome>, String> {
    on_vrl_stack(|| {
        let program = compile_vrl_program(vrl_code)?;
        Ok(events
            .iter()
            .map(|event| execute_vrl_on_event(&program, event, secrets.clone()))
            .collect())
    })
}

/// `run_events` for the Python entry points, with the GIL released while it
/// runs and a compile failure raised as a `ValueError`.
fn run_events_py(
    py: Python<'_>,
    vrl_code: &str,
    events: &[String],
    secrets: &SecretMap,
) -> PyResult<Vec<EventOutcome>> {
    py.detach(|| run_events(vrl_code, events, secrets))
        .map_err(compile_error)
}

fn compile_error(error: String) -> PyErr {
    PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("VRL compilation failed: {error}"))
}

/// Execute VRL program on a single event using Vector's VRL runtime
///
/// `secrets` seeds the event's secret store before the program runs; pass an
/// empty map for an event with no secrets.
fn execute_vrl_on_event(program: &Program, event_data: &str, secrets: SecretMap) -> EventOutcome {
    // A string starting with `{` that parses is the event. Anything else is
    // plain text, wrapped as `message`.
    let parsed = event_data
        .trim()
        .starts_with('{')
        .then(|| serde_json::from_str::<JsonValue>(event_data).ok())
        .flatten();
    let event_value = match parsed.map(json_to_vrl_value) {
        Some(Ok(value)) => value,
        Some(Err(out_of_range)) => {
            return EventOutcome {
                result: Err(format!("VRL error: input {out_of_range}")),
                secrets,
            };
        }
        None => Value::Object(BTreeMap::from([(
            "message".into(),
            Value::from(event_data),
        )])),
    };

    // EventTarget rather than vrl's TargetValue: its secret store is a map this
    // crate owns, so `execute_vrl_with_secrets` can enumerate what the program
    // set. vrl's own Secrets container has no way to list its keys.
    let mut target = EventTarget::new(event_value, secrets);

    // Create VRL runtime with RuntimeState for v0.27+ API
    let timezone = TimeZone::default();
    let state = RuntimeState::default();
    let mut runtime = Runtime::new(state);

    // Execute VRL program using Vector's runtime
    let result = match runtime.resolve(&mut target, program, &timezone) {
        // The VRL program's own return value is discarded here; the mutated
        // `target.value` (the event after any `.field = ...` assignments) is
        // what callers expect back.
        Ok(_) => match (&target.value, first_infinite_float(&target.value)) {
            (Value::Object(_), None) => Ok(target.value),
            (Value::Object(_), Some(path)) => Err(format!(
                "VRL error: field `{path}` is an infinite float, which has no JSON form"
            )),
            (other, _) => Err(format!(
                "VRL error: the program replaced the event with a value of type {}, and an event must be an object",
                other.kind_str()
            )),
        },
        Err(terminate) => {
            let error_msg = match terminate {
                Terminate::Abort(msg) => format!("VRL aborted: {}", msg),
                Terminate::Error(err) => format!("VRL error: {}", err),
                Terminate::Interrupted => "VRL interrupted".to_string(),
            };
            Err(error_msg)
        }
    };

    EventOutcome {
        result,
        secrets: target.secrets,
    }
}

/// A JSON integer above `i64::MAX`, which VRL's signed 64-bit integer cannot hold.
///
/// Rejected rather than rounded to a float, which would silently change an id
/// or a counter. An integer past `u64::MAX` reaches here already parsed as a
/// float by serde_json, so that range cannot be told apart from a float.
#[derive(Debug)]
pub(crate) struct IntegerOutOfRange {
    path: String,
    value: u64,
}

impl std::fmt::Display for IntegerOutOfRange {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "field `{}` holds {}, outside VRL's 64-bit signed integer range",
            self.path, self.value
        )
    }
}

/// `path` with `segment` in front, built only once a lookup has found something.
fn under(segment: impl std::fmt::Display, mut path: String) -> String {
    path.insert_str(0, &segment.to_string());
    path
}

/// Convert a JSON value to a VRL value.
pub(crate) fn json_to_vrl_value(json: JsonValue) -> Result<Value, IntegerOutOfRange> {
    Ok(match json {
        JsonValue::Null => Value::Null,
        JsonValue::Bool(b) => Value::Boolean(b),
        JsonValue::Number(n) => match (n.as_i64(), n.as_u64(), n.as_f64()) {
            (Some(i), _, _) => Value::Integer(i),
            (None, Some(value), _) => {
                return Err(IntegerOutOfRange {
                    path: String::new(),
                    value,
                });
            }
            // serde_json never parses NaN, so the 0.0 floor is never taken.
            (None, None, Some(f)) => Value::Float(NotNan::new(f).unwrap_or_default()),
            (None, None, None) => Value::Null,
        },
        JsonValue::String(s) => Value::Bytes(s.into()),
        JsonValue::Array(arr) => Value::Array(
            arr.into_iter()
                .enumerate()
                .map(|(index, item)| {
                    json_to_vrl_value(item).map_err(|e| IntegerOutOfRange {
                        path: under(format_args!("[{index}]"), e.path),
                        ..e
                    })
                })
                .collect::<Result<Vec<Value>, IntegerOutOfRange>>()?,
        ),
        JsonValue::Object(obj) => Value::Object(
            obj.into_iter()
                .map(|(key, item)| match json_to_vrl_value(item) {
                    Ok(value) => Ok((key.into(), value)),
                    Err(e) => Err(IntegerOutOfRange {
                        path: under(format_args!(".{key}"), e.path),
                        ..e
                    }),
                })
                .collect::<Result<BTreeMap<_, _>, IntegerOutOfRange>>()?,
        ),
    })
}

/// Convert VRL value to JSON value
fn vrl_value_to_json(value: Value) -> JsonValue {
    match value {
        Value::Null => JsonValue::Null,
        Value::Boolean(b) => JsonValue::Bool(b),
        Value::Integer(i) => JsonValue::Number(i.into()),
        // Infinity has no JSON form. `execute_vrl_on_event` fails the event
        // before it gets here, so Null is only a floor.
        Value::Float(f) => {
            serde_json::Number::from_f64(f.into_inner()).map_or(JsonValue::Null, JsonValue::Number)
        }
        Value::Bytes(b) => JsonValue::String(String::from_utf8_lossy(&b).to_string()),
        Value::String(s) => JsonValue::String(s.to_string()),
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

/// Path of the first infinite float in `value`, or None when every float is finite.
///
/// VRL floats cannot be NaN but can be infinite (`parse_float!("1e999")`), and
/// JSON has no infinity. The path is built only once one is found, so a clean
/// event allocates nothing here.
fn first_infinite_float(value: &Value) -> Option<String> {
    match value {
        Value::Float(f) if f.is_infinite() => Some(String::new()),
        Value::Array(items) => items.iter().enumerate().find_map(|(index, item)| {
            first_infinite_float(item).map(|path| under(format_args!("[{index}]"), path))
        }),
        Value::Object(fields) => fields.iter().find_map(|(key, field)| {
            first_infinite_float(field).map(|path| under(format_args!(".{key}"), path))
        }),
        _ => None,
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
) -> PyResult<Py<PyAny>> {
    let result_dict = PyDict::new(py);

    match outcome {
        Ok(vrl_result) => {
            if let JsonValue::Object(obj) = vrl_value_to_json(vrl_result) {
                for (key, value) in obj {
                    let py_value = match value {
                        JsonValue::String(s) => s.into_py_any(py)?,
                        JsonValue::Number(n) => {
                            if let Some(i) = n.as_i64() {
                                i.into_py_any(py)?
                            } else if let Some(f) = n.as_f64() {
                                f.into_py_any(py)?
                            } else {
                                py.None()
                            }
                        }
                        JsonValue::Bool(b) => b.into_py_any(py)?,
                        JsonValue::Null => py.None(),
                        JsonValue::Array(_) | JsonValue::Object(_) => {
                            value.to_string().into_py_any(py)?
                        }
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
        let json_module = py.import("json")?;
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
    ///
    /// The pipeline is not borrowed while the VRL runs with the GIL released,
    /// so another thread may call it meanwhile. Counters are added once the
    /// batch is converted.
    fn process_logs(
        slf: &Bound<'_, Self>,
        logs: Vec<String>,
        vrl_code: String,
    ) -> PyResult<Vec<Py<PyAny>>> {
        if !slf.borrow().initialized {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Vector not initialized",
            ));
        }

        // No secrets surface on the pipeline API - process_logs seeds an
        // empty store and discards what the program left behind.
        let py = slf.py();
        let outcomes = run_events_py(py, &vrl_code, &logs, &SecretMap::new())?;

        let mut results = Vec::with_capacity(logs.len());
        let mut processed = Saturating(0);
        let mut errors = Saturating(0);
        // bytes_processed is input volume read, so an event that fails at
        // runtime still counts its bytes.
        let mut bytes = Saturating(0);
        for (log, outcome) in logs.iter().zip(outcomes) {
            bytes += Saturating(log.len() as u64);
            if outcome.result.is_ok() {
                processed += Saturating(1);
            } else {
                errors += Saturating(1);
            }
            results.push(vrl_outcome_to_py_dict(py, outcome.result, log)?);
        }

        let mut this = slf.borrow_mut();
        this.events_processed += processed;
        this.errors += errors;
        this.bytes_processed += bytes;
        Ok(results)
    }

    /// Get Vector runtime statistics
    ///
    /// Real accumulated counts, measured from the last `initialize()`. A
    /// batch whose VRL fails to COMPILE raises before any event is touched
    /// and so moves no counter - `errors` counts per-event runtime failures.
    fn get_stats(&self) -> PyResult<Py<PyAny>> {
        let uptime_seconds = self
            .started_at
            .map_or(0.0, |started| started.elapsed().as_secs_f64());

        Python::attach(|py| {
            let stats_dict = PyDict::new(py);
            stats_dict.set_item("events_processed", self.events_processed.0)?;
            stats_dict.set_item("bytes_processed", self.bytes_processed.0)?;
            stats_dict.set_item("errors", self.errors.0)?;
            stats_dict.set_item("uptime_seconds", uptime_seconds)?;

            Ok(stats_dict.into())
        })
    }
}

/// Execute VRL transformation in-process using real Vector VRL runtime
///
/// `secrets` is an optional `dict[str, str]` of event secrets, seeded into
/// EVERY input event's secret store before the program runs. VRL reads them
/// with `get_secret(key)`, which returns None for a key that is not set.
/// Omitting it starts each event with no secrets.
///
/// Returns one dict per input event, holding the event's top-level fields on
/// success, or `error` and `original` on a per-event runtime failure. Secrets
/// the program set are NOT in that dict - use `execute_vrl_with_secrets` to
/// read them back.
#[pyfunction]
#[pyo3(signature = (vrl_code, input_data, secrets=None))]
fn execute_vrl(
    py: Python<'_>,
    vrl_code: String,
    input_data: Vec<String>,
    secrets: Option<SecretMap>,
) -> PyResult<Vec<Py<PyAny>>> {
    let outcomes = run_events_py(py, &vrl_code, &input_data, &secrets.unwrap_or_default())?;
    input_data
        .iter()
        .zip(outcomes)
        .map(|(input, outcome)| vrl_outcome_to_py_dict(py, outcome.result, input))
        .collect()
}

/// Execute VRL and hand back each event's secret store alongside the event
///
/// Same execution as `execute_vrl` - the difference is only what comes back.
/// Each entry is a dict with two keys:
///
/// - `event`: exactly what `execute_vrl` returns for that input.
/// - `secrets`: a `dict[str, str]` of the event's secrets after the program
///   ran, being the `secrets` argument plus any `set_secret` calls and minus
///   any `remove_secret` calls.
///
/// Secrets are per-event: each input starts from the same `secrets` argument,
/// and one event's `set_secret` is invisible to the next.
///
/// An event whose program aborts still reports its secrets, as they stood when
/// the program failed.
#[pyfunction]
#[pyo3(signature = (vrl_code, input_data, secrets=None))]
fn execute_vrl_with_secrets(
    py: Python<'_>,
    vrl_code: String,
    input_data: Vec<String>,
    secrets: Option<SecretMap>,
) -> PyResult<Vec<Py<PyAny>>> {
    let outcomes = run_events_py(py, &vrl_code, &input_data, &secrets.unwrap_or_default())?;
    let mut results = Vec::with_capacity(input_data.len());
    for (input, outcome) in input_data.iter().zip(outcomes) {
        let entry = PyDict::new(py);
        entry.set_item("event", vrl_outcome_to_py_dict(py, outcome.result, input)?)?;
        entry.set_item("secrets", outcome.secrets)?;
        results.push(entry.into());
    }
    Ok(results)
}

/// Validate VRL syntax using real Vector VRL compiler
#[pyfunction]
fn validate_vrl(py: Python<'_>, vrl_code: String) -> PyResult<VrlResult> {
    match py.detach(|| on_vrl_stack(|| compile_vrl_program(&vrl_code).map(drop))) {
        Ok(()) => Ok(VrlResult {
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

/// Register an enrichment table under `name` for VRL to look up.
///
/// `kind` is "file" (a CSV whose first row is the header) or "geoip" (a
/// GeoIP2/GeoLite2 .mmdb). The file is read here, so a bad path or a malformed
/// CSV raises immediately rather than at VRL runtime. Registering an existing
/// name replaces that table.
///
/// Registration must happen before the VRL that uses the table is compiled -
/// an unknown table name is a compile-time error.
#[pyfunction]
#[pyo3(signature = (name, kind, path, delimiter=None))]
fn register_enrichment_table(
    py: Python<'_>,
    name: String,
    kind: String,
    path: String,
    delimiter: Option<String>,
) -> PyResult<()> {
    let delimiter = match delimiter {
        None => b',',
        Some(d) => {
            let bytes = d.as_bytes();
            match bytes {
                [single] => *single,
                _ => {
                    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                        "delimiter must be a single ASCII character, got {d:?}"
                    )));
                }
            }
        }
    };

    py.detach(|| enrichment::register_table(&name, &kind, std::path::Path::new(&path), delimiter))
        .map_err(PyErr::new::<pyo3::exceptions::PyValueError, _>)
}

/// Drop every registered enrichment table.
///
/// Programs already compiled keep the table data they captured; only later
/// compilations see the emptied registry.
#[pyfunction]
fn clear_enrichment_tables() {
    enrichment::clear_tables();
}

/// List the registered enrichment tables, name-ordered.
///
/// Each entry is a dict with `name`, `kind`, `path` and `rows` - `rows` is the
/// loaded row count for a "file" table and None for a "geoip" table.
#[pyfunction]
fn list_enrichment_tables() -> PyResult<Vec<Py<PyAny>>> {
    let tables = enrichment::list_tables();
    Python::attach(|py| {
        let mut out = Vec::with_capacity(tables.len());
        for (name, kind, path, rows) in tables {
            let entry = PyDict::new(py);
            entry.set_item("name", name)?;
            entry.set_item("kind", kind)?;
            entry.set_item("path", path)?;
            entry.set_item("rows", rows)?;
            out.push(entry.into());
        }
        Ok(out)
    })
}

/// Get THG performance metrics for VRL code using real VRL execution
#[pyfunction]
#[pyo3(signature = (vrl_code, test_data, iterations=None))]
fn get_vrl_performance(
    py: Python<'_>,
    vrl_code: String,
    test_data: Vec<String>,
    iterations: Option<u32>,
) -> PyResult<Py<PyAny>> {
    let iter_count = iterations.unwrap_or(100);

    // Both factors are caller-controlled, so cap the product to bound the run time.
    const MAX_TOTAL_EVENTS: usize = 1_000_000;
    let total_events = test_data.len().saturating_mul(iter_count as usize);
    if total_events > MAX_TOTAL_EVENTS {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "requested {total_events} events (test_data.len() * iterations) exceeds the {MAX_TOTAL_EVENTS} limit"
        )));
    }

    // Each pass over test_data is run and dropped in turn, so memory stays
    // at one event however many iterations are asked for.
    let processing_time = py
        .detach(|| {
            on_vrl_stack(|| -> Result<Duration, String> {
                let start_time = Instant::now();
                let program = compile_vrl_program(&vrl_code)?;
                for event in test_data.iter().cycle().take(total_events) {
                    drop(execute_vrl_on_event(&program, event, SecretMap::new()));
                }
                Ok(start_time.elapsed())
            })
        })
        .map_err(compile_error)?;

    let events_per_second = if processing_time.as_secs_f64() > 0.0 {
        total_events as f64 / processing_time.as_secs_f64()
    } else {
        0.0
    };

    let metrics_dict = PyDict::new(py);
    metrics_dict.set_item("events_per_second", events_per_second)?;
    metrics_dict.set_item("processing_time_seconds", processing_time.as_secs_f64())?;
    metrics_dict.set_item("total_events", total_events)?;
    metrics_dict.set_item("thg_score", events_per_second.min(1000.0))?;
    Ok(metrics_dict.into())
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
    m.add_function(wrap_pyfunction!(execute_vrl_with_secrets, m)?)?;
    m.add_function(wrap_pyfunction!(validate_vrl, m)?)?;
    m.add_function(wrap_pyfunction!(get_vrl_performance, m)?)?;

    // Enrichment table registry - VRL names a table key, never a path.
    m.add_function(wrap_pyfunction!(register_enrichment_table, m)?)?;
    m.add_function(wrap_pyfunction!(clear_enrichment_tables, m)?)?;
    m.add_function(wrap_pyfunction!(list_enrichment_tables, m)?)?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn compile_rejects_arrays_nested_behind_string_closers() {
        let deep = 1000;
        let vrl = format!(".x = {}1{}", "[\")\", ".repeat(deep), "]".repeat(deep));
        let error = compile_vrl_program(&vrl).expect_err("must be rejected before parsing");
        assert!(error.contains("nests 1000 levels"), "{error}");
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

    /// Every VRL function held back by the sandboxed default build.
    ///
    /// `get_env_var` needs enable_env_functions; the next six need
    /// enable_system_functions; the last three need enable_network_functions.
    /// All ten arrive together with the `full-stdlib` feature.
    const FEATURE_GATED_FUNCTIONS: &[&str] = &[
        "get_env_var",
        "encode_proto",
        "get_hostname",
        "get_timezone_name",
        "parse_etld",
        "parse_proto",
        "validate_json_schema",
        "dns_lookup",
        "http_request",
        "reverse_dns",
    ];

    fn function_identifiers() -> Vec<&'static str> {
        vrl_functions().iter().map(|f| f.identifier()).collect()
    }

    #[cfg(not(feature = "full-stdlib"))]
    #[test]
    fn env_system_network_functions_are_unavailable() {
        // Regression test for the vrl sandbox escape: these functions must
        // stay undefined on the default build so caller-supplied VRL cannot
        // read the host environment or make network requests.
        let identifiers = function_identifiers();
        for name in FEATURE_GATED_FUNCTIONS {
            assert!(
                !identifiers.contains(name),
                "{name} must not be compiled into the sandboxed default build"
            );
        }

        // And the compiler agrees - an undefined function is a compile error
        // whatever arguments it is given, and the error names the function.
        for (call, name) in [
            (r#".x = get_env_var!("HOME")"#, "get_env_var"),
            (r#".x = get_hostname!()"#, "get_hostname"),
            (
                r#".x = http_request!("http://169.254.169.254/")"#,
                "http_request",
            ),
            (r#".x = dns_lookup!("example.com")"#, "dns_lookup"),
            (".x = upcasee(.message)", "upcasee"),
        ] {
            let error = compile_vrl_program(call).expect_err("must fail to compile");
            assert_eq!(
                error,
                format!("call to undefined function `{name}`"),
                "for {call:?}"
            );
        }
    }

    /// The mirror image of `env_system_network_functions_are_unavailable`.
    ///
    /// A test asserting those functions are absent cannot pass on a build that
    /// deliberately includes them, so the two are mutually exclusive rather
    /// than one of them being deleted.
    #[cfg(feature = "full-stdlib")]
    #[test]
    fn env_system_network_functions_are_available() {
        let identifiers = function_identifiers();
        for name in FEATURE_GATED_FUNCTIONS {
            assert!(
                identifiers.contains(name),
                "{name} must be compiled in under the full-stdlib feature"
            );
        }
    }

    /// Three of the ten, actually run. Chosen because they need no descriptor
    /// file, no schema and no network - the other seven are proved present by
    /// their identifiers above.
    #[cfg(feature = "full-stdlib")]
    #[test]
    fn full_stdlib_functions_execute() {
        let program = compile_vrl_program(
            r#"
            .path = get_env_var!("PATH")
            .host = get_hostname!()
            .etld = parse_etld!("sub.example.com").etld
            "#,
        )
        .expect("the gated functions compile under full-stdlib");

        let outcome = execute_vrl_on_event(&program, r#"{"message":"seed"}"#, SecretMap::new());
        let json = vrl_value_to_json(outcome.result.expect("execution succeeds"));
        assert!(
            json.get("path")
                .and_then(|v| v.as_str())
                .is_some_and(|p| !p.is_empty()),
            "get_env_var returned nothing usable: {json}"
        );
        assert!(
            json.get("host")
                .and_then(|v| v.as_str())
                .is_some_and(|h| !h.is_empty()),
            "get_hostname returned nothing usable: {json}"
        );
        assert_eq!(json.get("etld").and_then(|v| v.as_str()), Some("com"));
    }

    #[test]
    fn secret_functions_are_always_available() {
        // Unlike the ten above, the event-secret functions are in every build.
        let identifiers = function_identifiers();
        for name in ["get_secret", "set_secret", "remove_secret"] {
            assert!(identifiers.contains(&name), "{name} must be compiled in");
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

        let outcome = execute_vrl_on_event(
            &program,
            r#"{"message": "{\"level\": \"info\"}"}"#,
            SecretMap::new(),
        );
        let json = vrl_value_to_json(outcome.result.expect("execution succeeds"));
        assert_eq!(json.get("level").and_then(|v| v.as_str()), Some("info"));
    }

    #[test]
    fn execute_vrl_on_event_reports_runtime_errors() {
        // parse_json! (fallible-fn-without-handling) aborts at runtime when
        // the input isn't valid JSON.
        let program = compile_vrl_program(r#".parsed = parse_json!(.message)"#).expect("compiles");
        let outcome =
            execute_vrl_on_event(&program, r#"{"message": "not json"}"#, SecretMap::new());
        assert!(outcome.result.is_err());
    }

    #[test]
    fn a_function_returning_a_guaranteed_utf8_string_reaches_the_output() {
        // sha1 returns vrl's Value::String variant, distinct from Value::Bytes.
        let program = compile_vrl_program(r#".digest = sha1("abc")"#).expect("compiles");
        let outcome = execute_vrl_on_event(&program, r#"{"message":"seed"}"#, SecretMap::new());
        let json = vrl_value_to_json(outcome.result.expect("program runs"));
        assert_eq!(json["digest"], "a9993e364706816aba3e25717850c26c9cd0d89d");
    }

    #[test]
    fn a_failed_event_still_reports_the_secrets_it_set() {
        let program = compile_vrl_program(
            r#"
            set_secret("touched", "yes")
            .parsed = parse_json!(.message)
            "#,
        )
        .expect("compiles");
        let outcome =
            execute_vrl_on_event(&program, r#"{"message": "not json"}"#, SecretMap::new());
        assert!(outcome.result.is_err(), "the program must abort");
        assert_eq!(
            outcome.secrets.get("touched").map(String::as_str),
            Some("yes")
        );
    }

    /// The stack of a thread spawned by Python's `threading` on macOS is 512 KiB
    /// and `std::thread::spawn` gives 2 MiB. Nothing the VRL runs may depend on
    /// the caller's stack, and an overflow aborts the test process.
    const CALLER_STACK: usize = 2 * 1024 * 1024;

    fn on_caller_stack<T: Send + 'static>(work: impl FnOnce() -> T + Send + 'static) -> T {
        std::thread::Builder::new()
            .stack_size(CALLER_STACK)
            .spawn(work)
            .expect("spawn test thread")
            .join()
            .expect("test thread panicked")
    }

    #[test]
    fn expressions_chained_without_brackets_run_on_a_small_caller_stack() {
        // None of these nests a bracket, so `check_nesting_depth` passes them.
        // At this depth the sum overflows a 2 MiB stack when the VRL stack is no
        // bigger. Compile time grows with the square of the depth.
        let depth = 400;
        for (name, vrl, expected) in [
            (
                "sum",
                format!(".x = {}1", "1 + ".repeat(depth)),
                json!(depth + 1),
            ),
            (
                "not",
                format!(".x = {}true", "!".repeat(depth)),
                json!(true),
            ),
            (
                "and",
                format!(".x = {}true", "true && ".repeat(depth)),
                json!(true),
            ),
            (
                "else if",
                format!(
                    "if .message == \"a\" {{ .x = 0 }}{} else {{ .x = 3 }}",
                    " else if .message == \"b\" { .x = 1 }".repeat(depth)
                ),
                json!(3),
            ),
        ] {
            let outcomes = on_caller_stack(move || {
                run_events(
                    &vrl,
                    &[r#"{"message":"seed"}"#.to_string()],
                    &SecretMap::new(),
                )
            })
            .unwrap_or_else(|e| panic!("{name}: {e}"));
            let event = vrl_value_to_json(outcomes.into_iter().next().unwrap().result.unwrap());
            assert_eq!(event["x"], expected, "{name}");
        }
    }

    #[test]
    fn a_panic_on_the_vrl_stack_reaches_the_caller() {
        assert_eq!(on_vrl_stack(|| 7), 7);
        let caught =
            std::panic::catch_unwind(|| on_vrl_stack(|| -> u8 { panic!("from the vrl stack") }));
        assert!(caught.is_err());
    }

    fn run_seed(vrl: &str, event: &str) -> Result<Value, String> {
        let program = compile_vrl_program(vrl).expect("compiles");
        execute_vrl_on_event(&program, event, SecretMap::new()).result
    }

    #[test]
    fn a_program_that_replaces_the_event_with_a_non_object_fails_the_event() {
        for (vrl, kind) in [
            (". = [1, 2]", "array"),
            (r#". = "value""#, "string"),
            (". = 3", "integer"),
        ] {
            let error = run_seed(vrl, r#"{"message":"seed"}"#)
                .expect_err("a non-object event has no dict form");
            assert!(
                error.contains(&format!("replaced the event with a value of type {kind}")),
                "for {vrl:?}: {error}"
            );
        }
        assert!(run_seed(". = {\"a\": 1}", r#"{"message":"seed"}"#).is_ok());
    }

    #[test]
    fn an_input_integer_outside_the_vrl_range_fails_the_event() {
        for (event, path) in [
            (r#"{"id": 18446744073709551615}"#, ".id"),
            (r#"{"a": [1, {"b": 9223372036854775808}]}"#, ".a[1].b"),
        ] {
            let error = run_seed(".seen = true", event).expect_err("must not round to a float");
            assert!(
                error.contains(&format!("field `{path}`")) && error.contains("outside"),
                "for {event}: {error}"
            );
        }
        for edge in [i64::MAX, i64::MIN] {
            let event = format!(r#"{{"id": {edge}}}"#);
            let json = vrl_value_to_json(run_seed(".seen = true", &event).expect("in range"));
            assert_eq!(json["id"], json!(edge), "for {edge}");
        }
    }

    #[test]
    fn an_infinite_float_fails_the_event_wherever_it_sits() {
        for (vrl, expected) in [
            (r#".top = parse_float!("1e999")"#, Err(".top")),
            (
                r#".n = {"list": [1.5, parse_float!("-1e999")]}"#,
                Err(".n.list[1]"),
            ),
            (r#".fine = 2.5"#, Ok(())),
        ] {
            let program = compile_vrl_program(vrl).expect("compiles");
            let outcome = execute_vrl_on_event(&program, r#"{"message":"seed"}"#, SecretMap::new());
            match (outcome.result, expected) {
                (Ok(_), Ok(())) => {}
                (Err(error), Err(path)) => assert!(
                    error.contains(&format!("`{path}` is an infinite float")),
                    "for {vrl:?}: {error}"
                ),
                (got, want) => panic!("for {vrl:?}: got {got:?}, wanted {want:?}"),
            }
        }
    }
}
