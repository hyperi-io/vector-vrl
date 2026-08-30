//! Enrichment tables for the bundled VRL engine.
//!
//! The standalone `vrl` crate ships no enrichment support and Vector's own
//! `enrichment` library is not published to crates.io, so `get_enrichment_table_record`
//! and `find_enrichment_table_records` are implemented here against the same
//! surface Vector exposes.
//!
//! Security boundary: VRL source can only name a table KEY, never a path. Paths
//! are supplied by the Python caller through `register_enrichment_table`, and an
//! unknown key is a compile-time error.

use std::borrow::Cow;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, OnceLock, PoisonError, RwLock, RwLockReadGuard, RwLockWriteGuard};

use vrl::compiler::prelude::*;

use crate::json_to_vrl_value;

/// Name -> table. `Arc` per table so a compiled program holds its own table
/// alive without taking the registry lock on every event.
type TableMap = BTreeMap<String, Arc<EnrichmentTable>>;

static REGISTRY: OnceLock<Arc<RwLock<TableMap>>> = OnceLock::new();

fn registry() -> &'static Arc<RwLock<TableMap>> {
    REGISTRY.get_or_init(|| Arc::new(RwLock::new(TableMap::new())))
}

/// Read the registry, recovering from a writer panic rather than propagating it
/// into the Python caller as an unrelated panic.
fn read_tables(lock: &RwLock<TableMap>) -> RwLockReadGuard<'_, TableMap> {
    lock.read().unwrap_or_else(PoisonError::into_inner)
}

fn write_tables(lock: &RwLock<TableMap>) -> RwLockWriteGuard<'_, TableMap> {
    lock.write().unwrap_or_else(PoisonError::into_inner)
}

/// A CSV file loaded into memory at registration time.
pub(crate) struct FileTable {
    path: PathBuf,
    rows: Vec<ObjectMap>,
}

/// A MaxMind DB (GeoIP2/GeoLite2) opened at registration time.
pub(crate) struct GeoipTable {
    path: PathBuf,
    reader: maxminddb::Reader<Vec<u8>>,
}

pub(crate) enum EnrichmentTable {
    File(FileTable),
    Geoip(GeoipTable),
}

// maxminddb::Reader is not Debug, and dumping every CSV row would be useless
// noise in a VRL diagnostic.
impl std::fmt::Debug for EnrichmentTable {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "EnrichmentTable({}, {})",
            self.kind(),
            self.path().display()
        )
    }
}

impl EnrichmentTable {
    pub(crate) fn kind(&self) -> &'static str {
        match self {
            EnrichmentTable::File(_) => "file",
            EnrichmentTable::Geoip(_) => "geoip",
        }
    }

    pub(crate) fn path(&self) -> &Path {
        match self {
            EnrichmentTable::File(t) => &t.path,
            EnrichmentTable::Geoip(t) => &t.path,
        }
    }

    /// Row count for a `file` table. A `geoip` table is an on-disk trie with no
    /// meaningful row count, so it reports `None`.
    pub(crate) fn row_count(&self) -> Option<usize> {
        match self {
            EnrichmentTable::File(t) => Some(t.rows.len()),
            EnrichmentTable::Geoip(_) => None,
        }
    }

    fn find_rows(
        &self,
        conditions: &[(String, Value)],
        case_sensitive: bool,
        select: Option<&[String]>,
    ) -> Result<Vec<ObjectMap>, String> {
        match self {
            EnrichmentTable::File(t) => t.find_rows(conditions, case_sensitive, select),
            EnrichmentTable::Geoip(t) => t.find_rows(conditions, select),
        }
    }
}

/// Render a condition value or a table cell as text for comparison.
///
/// A `file` table stores every cell as a string, so numeric and boolean
/// conditions are compared in their string form rather than coerced.
fn comparable_text<'a>(field: &str, value: &'a Value) -> Result<Cow<'a, str>, String> {
    match value {
        Value::Bytes(b) => Ok(String::from_utf8_lossy(b)),
        Value::Integer(i) => Ok(Cow::Owned(i.to_string())),
        Value::Float(f) => Ok(Cow::Owned(f.to_string())),
        Value::Boolean(b) => Ok(Cow::Owned(b.to_string())),
        _ => Err(format!(
            "enrichment condition for field {field:?} must be a string, integer, float or boolean"
        )),
    }
}

/// Keep only the requested keys, erroring on a key the row does not carry.
fn apply_select(row: ObjectMap, select: Option<&[String]>) -> Result<ObjectMap, String> {
    let Some(select) = select else {
        return Ok(row);
    };
    let mut out = ObjectMap::new();
    for key in select {
        match row.get(key.as_str()) {
            Some(value) => {
                out.insert(key.as_str().into(), value.clone());
            }
            None => return Err(format!("field {key:?} not found in enrichment table row")),
        }
    }
    Ok(out)
}

impl FileTable {
    /// Load a CSV, taking the first record as the header row.
    ///
    /// Every cell is stored as a string; column typing is not supported.
    fn load(path: &Path, delimiter: u8) -> Result<Self, String> {
        let mut reader = csv::ReaderBuilder::new()
            .delimiter(delimiter)
            .has_headers(true)
            .from_path(path)
            .map_err(|e| format!("cannot read csv {}: {e}", path.display()))?;

        let headers: Vec<KeyString> = reader
            .headers()
            .map_err(|e| format!("cannot read csv header of {}: {e}", path.display()))?
            .iter()
            .map(KeyString::from)
            .collect();

        if headers.is_empty() {
            return Err(format!("csv {} has no header row", path.display()));
        }

        let mut rows = Vec::new();
        for (index, record) in reader.records().enumerate() {
            let record = record.map_err(|e| {
                format!("cannot read csv {} row {}: {e}", path.display(), index + 1)
            })?;
            if record.len() != headers.len() {
                return Err(format!(
                    "csv {} row {} has {} fields, expected {}",
                    path.display(),
                    index + 1,
                    record.len(),
                    headers.len()
                ));
            }
            let mut row = ObjectMap::new();
            for (header, cell) in headers.iter().zip(record.iter()) {
                row.insert(header.clone(), Value::from(cell));
            }
            rows.push(row);
        }

        Ok(FileTable {
            path: path.to_path_buf(),
            rows,
        })
    }

    /// Linear scan; every condition must match (AND), equality only.
    fn find_rows(
        &self,
        conditions: &[(String, Value)],
        case_sensitive: bool,
        select: Option<&[String]>,
    ) -> Result<Vec<ObjectMap>, String> {
        let mut wanted = Vec::with_capacity(conditions.len());
        for (field, value) in conditions {
            let text = comparable_text(field, value)?;
            let text = if case_sensitive {
                text.into_owned()
            } else {
                text.to_lowercase()
            };
            wanted.push((field.as_str(), text));
        }

        let mut out = Vec::new();
        'rows: for row in &self.rows {
            for (field, expected) in &wanted {
                let Some(cell) = row.get(*field) else {
                    return Err(format!("field {field:?} not found in enrichment table"));
                };
                let actual = comparable_text(field, cell)?;
                let matched = if case_sensitive {
                    actual.as_ref() == expected.as_str()
                } else {
                    actual.to_lowercase() == *expected
                };
                if !matched {
                    continue 'rows;
                }
            }
            out.push(apply_select(row.clone(), select)?);
        }
        Ok(out)
    }
}

impl GeoipTable {
    fn load(path: &Path) -> Result<Self, String> {
        let reader = maxminddb::Reader::open_readfile(path)
            .map_err(|e| format!("cannot open mmdb {}: {e}", path.display()))?;
        Ok(GeoipTable {
            path: path.to_path_buf(),
            reader,
        })
    }

    /// A geoip lookup takes exactly one condition, whose value is the IP address.
    fn find_rows(
        &self,
        conditions: &[(String, Value)],
        select: Option<&[String]>,
    ) -> Result<Vec<ObjectMap>, String> {
        let [(field, value)] = conditions else {
            return Err(
                "a geoip enrichment table takes exactly one condition, the IP address".to_string(),
            );
        };
        let text = comparable_text(field, value)?;
        let address: std::net::IpAddr = text
            .parse()
            .map_err(|_| format!("condition field {field:?} is not an IP address: {text}"))?;

        let lookup = self
            .reader
            .lookup(address)
            .map_err(|e| format!("mmdb lookup failed for {text}: {e}"))?;
        let record = lookup
            .decode::<serde_json::Value>()
            .map_err(|e| format!("cannot decode mmdb record for {text}: {e}"))?;

        let Some(record) = record else {
            return Ok(Vec::new());
        };
        match json_to_vrl_value(record) {
            Value::Object(row) => Ok(vec![apply_select(row, select)?]),
            _ => Err(format!("mmdb record for {text} is not an object")),
        }
    }
}

// -----------------------------------------------------------------------------
// Registration API, called from the PyO3 layer.
// -----------------------------------------------------------------------------

/// Register a table under `name`, replacing any table already using that name.
///
/// `delimiter` applies to `kind == "file"` only.
pub(crate) fn register_table(
    name: &str,
    kind: &str,
    path: &Path,
    delimiter: u8,
) -> Result<(), String> {
    if name.is_empty() {
        return Err("enrichment table name must not be empty".to_string());
    }
    let table = match kind {
        "file" => EnrichmentTable::File(FileTable::load(path, delimiter)?),
        "geoip" => EnrichmentTable::Geoip(GeoipTable::load(path)?),
        other => return Err(format!("unknown enrichment table kind {other:?}")),
    };
    write_tables(registry()).insert(name.to_string(), Arc::new(table));
    Ok(())
}

pub(crate) fn clear_tables() {
    write_tables(registry()).clear();
}

/// (name, kind, path, row count) for every registered table, name-ordered.
pub(crate) fn list_tables() -> Vec<(String, &'static str, String, Option<usize>)> {
    read_tables(registry())
        .iter()
        .map(|(name, table)| {
            (
                name.clone(),
                table.kind(),
                table.path().display().to_string(),
                table.row_count(),
            )
        })
        .collect()
}

/// The two enrichment functions, ready to append to `vrl::stdlib::all()`.
pub(crate) fn functions() -> Vec<Box<dyn Function>> {
    vec![
        Box::new(GetEnrichmentTableRecord {
            registry: Arc::clone(registry()),
        }),
        Box::new(FindEnrichmentTableRecords {
            registry: Arc::clone(registry()),
        }),
    ]
}

// -----------------------------------------------------------------------------
// VRL functions
// -----------------------------------------------------------------------------

const PARAMETERS: &[Parameter] = &[
    Parameter::required(
        "table",
        kind::BYTES,
        "The registered enrichment table to search. Must be a literal - the name is resolved at compile time.",
    ),
    Parameter::required(
        "condition",
        kind::OBJECT,
        "Field/value pairs the row must match. All pairs must match, and only equality is supported.",
    ),
    Parameter::optional(
        "select",
        kind::ARRAY,
        "A subset of the table's fields to return. All fields are returned if omitted.",
    ),
    Parameter::optional(
        "case_sensitive",
        kind::BOOLEAN,
        "Whether string comparison is case sensitive. Defaults to true.",
    ),
];

/// A VRL program named a table that is not in the registry.
///
/// Carries the registered names so the diagnostic points at the typo rather
/// than just reporting a bad argument.
#[derive(Debug)]
struct UnknownTable {
    table: String,
    registered: Vec<String>,
}

impl std::fmt::Display for UnknownTable {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if self.registered.is_empty() {
            write!(
                f,
                "unknown enrichment table {:?}: no enrichment tables are registered",
                self.table
            )
        } else {
            write!(
                f,
                "unknown enrichment table {:?}; registered tables: {}",
                self.table,
                self.registered.join(", ")
            )
        }
    }
}

impl std::error::Error for UnknownTable {}

impl DiagnosticMessage for UnknownTable {
    // 111 is the code Vector's own enrichment integration uses.
    fn code(&self) -> usize {
        111
    }

    fn labels(&self) -> Vec<vrl::diagnostic::Label> {
        vec![vrl::diagnostic::Label::primary(
            self.to_string(),
            Span::default(),
        )]
    }
}

/// The arguments both enrichment functions take, resolved at compile time.
struct CompiledArgs {
    table: String,
    data: Arc<EnrichmentTable>,
    condition: BTreeMap<KeyString, expression::Expr>,
    select: Option<Box<dyn Expression>>,
    case_sensitive: bool,
}

/// Resolve the table name against the registry and pull out the shared arguments.
///
/// The resolved `Arc<EnrichmentTable>` is handed to the returned expression, so
/// the runtime never takes the registry lock and a later `clear_enrichment_tables`
/// cannot pull the data out from under an already-compiled program.
fn compile_args(
    lock: &RwLock<TableMap>,
    state: &TypeState,
    arguments: &ArgumentList,
) -> Result<CompiledArgs, Box<dyn DiagnosticMessage>> {
    let tables = read_tables(lock);

    // required_literal forces `table` to be a compile-time constant, so VRL can
    // never compute a table name - let alone a path - at runtime.
    let table = arguments
        .required_literal("table", state)?
        .try_bytes_utf8_lossy()
        .expect("the table parameter is declared kind::BYTES")
        .into_owned();

    // An unregistered name fails HERE, at compile time, which is what makes
    // validate_vrl catch a typo before any event is processed.
    let Some(data) = tables.get(&table).map(Arc::clone) else {
        return Err(Box::new(UnknownTable {
            table,
            registered: tables.keys().cloned().collect(),
        }));
    };

    let condition = arguments.required_object("condition")?;
    let select = arguments.optional("select");
    let case_sensitive = arguments
        .optional_literal("case_sensitive", state)?
        .and_then(|value| value.as_boolean())
        .unwrap_or(true);

    Ok(CompiledArgs {
        table,
        data,
        condition,
        select,
        case_sensitive,
    })
}

/// Field/value pairs a row must match, resolved for one event.
type Conditions = Vec<(String, Value)>;

/// The optional subset of table fields to return.
type Select = Option<Vec<String>>;

/// Resolve the condition object and the optional `select` list for one event.
fn resolve_lookup(
    condition: &BTreeMap<KeyString, expression::Expr>,
    select: Option<&dyn Expression>,
    ctx: &mut Context,
) -> ExpressionResult<(Conditions, Select)> {
    let conditions = condition
        .iter()
        .map(|(key, expr)| Ok((key.to_string(), expr.resolve(ctx)?)))
        .collect::<ExpressionResult<Vec<_>>>()?;

    let select = match select {
        None => None,
        Some(expr) => match expr.resolve(ctx)? {
            Value::Array(items) => Some(
                items
                    .iter()
                    .map(|item| Ok(item.try_bytes_utf8_lossy()?.into_owned()))
                    .collect::<ExpressionResult<Vec<_>>>()?,
            ),
            _ => return Err("select must be an array of field names".into()),
        },
    };

    Ok((conditions, select))
}

#[derive(Debug)]
pub(crate) struct GetEnrichmentTableRecord {
    registry: Arc<RwLock<TableMap>>,
}

impl Function for GetEnrichmentTableRecord {
    fn identifier(&self) -> &'static str {
        "get_enrichment_table_record"
    }

    fn summary(&self) -> &'static str {
        "search an enrichment table for a single row"
    }

    fn usage(&self) -> &'static str {
        "Searches a registered enrichment table for the single row matching `condition`.\n\
         Errors if no row matches or if more than one row matches; use\n\
         `find_enrichment_table_records` when several rows are expected.\n\
         Tables are registered from Python with `register_enrichment_table`."
    }

    fn category(&self) -> &'static str {
        "Enrichment"
    }

    fn internal_failure_reasons(&self) -> &'static [&'static str] {
        &[
            "No row matched the condition.",
            "More than one row matched the condition.",
        ]
    }

    fn return_kind(&self) -> u16 {
        kind::OBJECT
    }

    fn parameters(&self) -> &'static [Parameter] {
        PARAMETERS
    }

    fn examples(&self) -> &'static [Example] {
        &[Example {
            title: "Exact match",
            source: r#"get_enrichment_table_record!("users", {"id": "1"})"#,
            input: None,
            result: Ok(r#"{"id": "1", "name": "Bob"}"#),
            file: file!(),
            line: line!(),
            deterministic: true,
            skip: true,
        }]
    }

    fn compile(
        &self,
        state: &TypeState,
        _ctx: &mut FunctionCompileContext,
        arguments: ArgumentList,
    ) -> Compiled {
        let args = compile_args(&self.registry, state, &arguments)?;
        Ok(GetEnrichmentTableRecordFn {
            table: args.table,
            data: args.data,
            condition: args.condition,
            select: args.select,
            case_sensitive: args.case_sensitive,
        }
        .as_expr())
    }
}

#[derive(Debug, Clone)]
struct GetEnrichmentTableRecordFn {
    table: String,
    data: Arc<EnrichmentTable>,
    condition: BTreeMap<KeyString, expression::Expr>,
    select: Option<Box<dyn Expression>>,
    case_sensitive: bool,
}

impl FunctionExpression for GetEnrichmentTableRecordFn {
    fn resolve(&self, ctx: &mut Context) -> Resolved {
        let (conditions, select) = resolve_lookup(&self.condition, self.select.as_deref(), ctx)?;
        let mut rows = self
            .data
            .find_rows(&conditions, self.case_sensitive, select.as_deref())
            .map_err(ExpressionError::from)?;

        if rows.len() > 1 {
            return Err(format!(
                "More than one row found in enrichment table {:?}",
                self.table
            )
            .into());
        }
        match rows.pop() {
            Some(row) => Ok(Value::Object(row)),
            None => Err(format!("No rows found in enrichment table {:?}", self.table).into()),
        }
    }

    fn type_def(&self, _: &TypeState) -> TypeDef {
        TypeDef::object(Collection::any()).fallible()
    }
}

#[derive(Debug)]
pub(crate) struct FindEnrichmentTableRecords {
    registry: Arc<RwLock<TableMap>>,
}

impl Function for FindEnrichmentTableRecords {
    fn identifier(&self) -> &'static str {
        "find_enrichment_table_records"
    }

    fn summary(&self) -> &'static str {
        "search an enrichment table for all matching rows"
    }

    fn usage(&self) -> &'static str {
        "Searches a registered enrichment table for every row matching `condition`,\n\
         returning them as an array. Returns an empty array when nothing matches.\n\
         Tables are registered from Python with `register_enrichment_table`."
    }

    fn category(&self) -> &'static str {
        "Enrichment"
    }

    fn return_kind(&self) -> u16 {
        kind::ARRAY
    }

    fn parameters(&self) -> &'static [Parameter] {
        PARAMETERS
    }

    fn examples(&self) -> &'static [Example] {
        &[Example {
            title: "Exact match",
            source: r#"find_enrichment_table_records!("users", {"surname": "Smith"})"#,
            input: None,
            result: Ok(r#"[{"id": "1", "surname": "Smith"}]"#),
            file: file!(),
            line: line!(),
            deterministic: true,
            skip: true,
        }]
    }

    fn compile(
        &self,
        state: &TypeState,
        _ctx: &mut FunctionCompileContext,
        arguments: ArgumentList,
    ) -> Compiled {
        let args = compile_args(&self.registry, state, &arguments)?;
        Ok(FindEnrichmentTableRecordsFn {
            data: args.data,
            condition: args.condition,
            select: args.select,
            case_sensitive: args.case_sensitive,
        }
        .as_expr())
    }
}

#[derive(Debug, Clone)]
struct FindEnrichmentTableRecordsFn {
    data: Arc<EnrichmentTable>,
    condition: BTreeMap<KeyString, expression::Expr>,
    select: Option<Box<dyn Expression>>,
    case_sensitive: bool,
}

impl FunctionExpression for FindEnrichmentTableRecordsFn {
    fn resolve(&self, ctx: &mut Context) -> Resolved {
        let (conditions, select) = resolve_lookup(&self.condition, self.select.as_deref(), ctx)?;
        let rows = self
            .data
            .find_rows(&conditions, self.case_sensitive, select.as_deref())
            .map_err(ExpressionError::from)?;
        Ok(Value::Array(rows.into_iter().map(Value::Object).collect()))
    }

    fn type_def(&self, _: &TypeState) -> TypeDef {
        TypeDef::array(Collection::from_unknown(Kind::object(Collection::any()))).fallible()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{compile_vrl_program, execute_vrl_on_event, vrl_value_to_json};
    use std::sync::Mutex;

    /// The registry is process-global, so the enrichment tests take turns.
    static TEST_LOCK: Mutex<()> = Mutex::new(());

    fn lock() -> std::sync::MutexGuard<'static, ()> {
        let guard = TEST_LOCK.lock().unwrap_or_else(PoisonError::into_inner);
        clear_tables();
        guard
    }

    const USERS_CSV: &str = "id,name,team\n1,Bob,red\n2,Fred,blue\n3,Alice,red\n";

    /// A real CSV on disk - these tests exercise the loader, not a stub.
    struct TempCsv(PathBuf);

    impl TempCsv {
        fn new(tag: &str, contents: &str) -> Self {
            let path = std::env::temp_dir().join(format!(
                "vector-bindings-enrichment-{}-{tag}.csv",
                std::process::id()
            ));
            std::fs::write(&path, contents).expect("temp csv is writable");
            TempCsv(path)
        }

        fn path(&self) -> &Path {
            &self.0
        }
    }

    impl Drop for TempCsv {
        fn drop(&mut self) {
            let _ = std::fs::remove_file(&self.0);
        }
    }

    fn register_users(tag: &str) -> TempCsv {
        let csv = TempCsv::new(tag, USERS_CSV);
        register_table("users", "file", csv.path(), b',').expect("csv loads");
        csv
    }

    fn run(vrl: &str) -> Result<serde_json::Value, String> {
        let program = compile_vrl_program(vrl)?;
        execute_vrl_on_event(&program, r#"{"message":"seed"}"#).map(vrl_value_to_json)
    }

    #[test]
    fn compile_accepts_a_registered_enrichment_table() {
        let _guard = lock();
        let _csv = register_users("compile-ok");
        assert!(
            compile_vrl_program(r#". = get_enrichment_table_record!("users", {"id":"1"})"#).is_ok()
        );
        assert!(
            compile_vrl_program(
                r#". = {"r": find_enrichment_table_records!("users", {"team":"red"})}"#
            )
            .is_ok()
        );
    }

    #[test]
    fn compile_rejects_an_unknown_enrichment_table() {
        let _guard = lock();
        let _csv = register_users("compile-unknown");
        let err = compile_vrl_program(r#". = get_enrichment_table_record!("nope", {"id":"1"})"#)
            .expect_err("an unregistered table must not compile");
        assert!(
            err.contains(r#"unknown enrichment table "nope""#),
            "unexpected diagnostic: {err}"
        );
        assert!(
            err.contains("users"),
            "diagnostic should list what IS registered: {err}"
        );
    }

    #[test]
    fn compile_rejects_every_table_when_none_are_registered() {
        let _guard = lock();
        let err = compile_vrl_program(r#". = get_enrichment_table_record!("users", {"id":"1"})"#)
            .expect_err("nothing is registered");
        assert!(
            err.contains("no enrichment tables are registered"),
            "unexpected diagnostic: {err}"
        );
        assert!(
            compile_vrl_program(
                r#". = {"r": find_enrichment_table_records!("users", {"id":"1"})}"#
            )
            .is_err()
        );
    }

    #[test]
    fn compile_rejects_a_non_literal_table_name() {
        // The table argument must be a compile-time literal, so VRL can never
        // compute the name (or a path) at runtime.
        let _guard = lock();
        let _csv = register_users("compile-dynamic");
        let err = compile_vrl_program(
            r#"t = .message
               . = get_enrichment_table_record!(t, {"id":"1"})"#,
        )
        .expect_err("a computed table name must not compile");
        assert!(!err.is_empty());
    }

    #[test]
    fn get_returns_the_matching_row() {
        let _guard = lock();
        let _csv = register_users("get-hit");
        let out =
            run(r#". = get_enrichment_table_record!("users", {"id":"2"})"#).expect("lookup runs");
        assert_eq!(out.get("name").and_then(|v| v.as_str()), Some("Fred"));
        assert_eq!(out.get("team").and_then(|v| v.as_str()), Some("blue"));
    }

    #[test]
    fn get_errors_when_no_row_matches() {
        let _guard = lock();
        let _csv = register_users("get-miss");
        let err = run(r#". = get_enrichment_table_record!("users", {"id":"99"})"#)
            .expect_err("a miss must abort");
        assert!(err.contains("No rows found"), "unexpected error: {err}");
    }

    #[test]
    fn get_errors_when_several_rows_match() {
        let _guard = lock();
        let _csv = register_users("get-many");
        let err = run(r#". = get_enrichment_table_record!("users", {"team":"red"})"#)
            .expect_err("an ambiguous match must abort");
        assert!(
            err.contains("More than one row found"),
            "unexpected error: {err}"
        );
    }

    #[test]
    fn find_returns_every_matching_row() {
        let _guard = lock();
        let _csv = register_users("find-many");
        let out = run(r#". = {"rows": find_enrichment_table_records!("users", {"team":"red"})}"#)
            .expect("lookup runs");
        let rows = out.get("rows").and_then(|v| v.as_array()).expect("array");
        assert_eq!(rows.len(), 2);
        let names: Vec<&str> = rows
            .iter()
            .filter_map(|r| r.get("name").and_then(|v| v.as_str()))
            .collect();
        assert_eq!(names, vec!["Bob", "Alice"]);
    }

    #[test]
    fn find_returns_an_empty_array_when_nothing_matches() {
        let _guard = lock();
        let _csv = register_users("find-none");
        let out = run(r#". = {"rows": find_enrichment_table_records!("users", {"team":"green"})}"#)
            .expect("lookup runs");
        assert_eq!(
            out.get("rows").and_then(|v| v.as_array()).map(Vec::len),
            Some(0)
        );
    }

    #[test]
    fn case_sensitivity_is_honoured() {
        let _guard = lock();
        let _csv = register_users("case");
        assert!(run(r#". = get_enrichment_table_record!("users", {"name":"bob"})"#).is_err());
        let out = run(
            r#". = get_enrichment_table_record!("users", {"name":"bob"}, case_sensitive: false)"#,
        )
        .expect("case-insensitive lookup runs");
        assert_eq!(out.get("id").and_then(|v| v.as_str()), Some("1"));
    }

    #[test]
    fn select_limits_the_returned_fields() {
        let _guard = lock();
        let _csv = register_users("select");
        let out = run(r#". = get_enrichment_table_record!("users", {"id":"2"}, select: ["name"])"#)
            .expect("lookup runs");
        assert_eq!(out.get("name").and_then(|v| v.as_str()), Some("Fred"));
        assert!(out.get("team").is_none());
    }

    #[test]
    fn an_unknown_condition_field_errors_at_runtime() {
        let _guard = lock();
        let _csv = register_users("bad-field");
        let err = run(r#". = get_enrichment_table_record!("users", {"nosuch":"1"})"#)
            .expect_err("an unknown column must abort");
        assert!(err.contains("not found"), "unexpected error: {err}");
    }

    #[test]
    fn a_ragged_csv_is_rejected_at_registration() {
        let _guard = lock();
        let csv = TempCsv::new("ragged", "id,name\n1,Bob,extra\n");
        let err = register_table("ragged", "file", csv.path(), b',')
            .expect_err("a ragged csv must not load");
        assert!(!err.is_empty());
    }

    #[test]
    fn an_unknown_table_kind_is_rejected() {
        let _guard = lock();
        let csv = TempCsv::new("kind", USERS_CSV);
        let err = register_table("k", "sqlite", csv.path(), b',').expect_err("bad kind");
        assert!(err.contains("unknown enrichment table kind"), "{err}");
    }

    #[test]
    fn list_reports_what_is_registered() {
        let _guard = lock();
        let _csv = register_users("list");
        let listed = list_tables();
        assert_eq!(listed.len(), 1);
        assert_eq!(listed[0].0, "users");
        assert_eq!(listed[0].1, "file");
        assert_eq!(listed[0].3, Some(3));
        clear_tables();
        assert!(list_tables().is_empty());
    }

    #[test]
    fn a_missing_mmdb_is_rejected_at_registration() {
        let _guard = lock();
        let missing = std::env::temp_dir().join("vector-bindings-no-such-db.mmdb");
        let err = register_table("geo", "geoip", &missing, b',').expect_err("missing mmdb");
        assert!(err.contains("cannot open mmdb"), "{err}");
    }

    /// Real GeoLite2 lookup, using the test database in the upstream `vector`
    /// checkout. That checkout is gitignored and `build/build --clean` removes
    /// it, so the test reports and returns rather than failing when it is gone.
    #[test]
    fn geoip_lookup_returns_a_record() {
        let _guard = lock();
        let mmdb = Path::new("/projects/vectordotdev/vector/tests/data/GeoLite2-ASN-Test.mmdb");
        if !mmdb.exists() {
            eprintln!("skipping: {} is absent", mmdb.display());
            return;
        }
        register_table("asn", "geoip", mmdb, b',').expect("mmdb opens");
        let out = run(r#". = get_enrichment_table_record!("asn", {"ip":"1.128.0.0"})"#)
            .expect("geoip lookup runs");
        assert!(
            out.as_object().is_some_and(|o| !o.is_empty()),
            "expected a non-empty record, got {out}"
        );
    }
}
