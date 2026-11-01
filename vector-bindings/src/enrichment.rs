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
use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock, PoisonError, RwLock, RwLockReadGuard, RwLockWriteGuard};

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
    headers: Vec<KeyString>,
    rows: Vec<ObjectMap>,
    /// Indexes built for the condition fields of compiled programs, kept for
    /// the table's lifetime so a recompile reuses them.
    indexes: Mutex<HashMap<IndexKey, Arc<RowIndex>>>,
}

/// Case sensitivity and the condition fields, in the order VRL resolves them.
type IndexKey = (bool, Vec<String>);

/// Row numbers by the comparable text of the indexed fields, in field order.
pub(crate) type RowIndex = HashMap<Vec<String>, Vec<usize>>;

/// How many matching rows a lookup wants back.
#[derive(Clone, Copy)]
enum Wanted {
    /// `get_enrichment_table_record`: exactly one, so a second match is an error.
    One,
    /// `find_enrichment_table_records`: every match.
    All,
}

impl Wanted {
    /// Rows worth copying out: a second one is enough to report ambiguity.
    fn limit(self) -> usize {
        match self {
            Wanted::One => 2,
            Wanted::All => usize::MAX,
        }
    }
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

    /// The index a compiled lookup on `fields` uses, or None for a geoip table
    /// or a field the CSV has no column for.
    fn index_for(&self, case_sensitive: bool, fields: Vec<String>) -> Option<Arc<RowIndex>> {
        match self {
            EnrichmentTable::File(t) => t.index_for(case_sensitive, fields),
            EnrichmentTable::Geoip(_) => None,
        }
    }

    fn find_rows(
        &self,
        index: Option<&RowIndex>,
        conditions: &[(String, Value)],
        case_sensitive: bool,
        select: Option<&[String]>,
        wanted: Wanted,
    ) -> Result<Vec<ObjectMap>, String> {
        match self {
            EnrichmentTable::File(t) => {
                t.find_rows(index, conditions, case_sensitive, select, wanted)
            }
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
        Value::String(s) => Ok(Cow::Borrowed(&**s)),
        Value::Integer(i) => Ok(Cow::Owned(i.to_string())),
        Value::Float(f) => Ok(Cow::Owned(f.to_string())),
        Value::Boolean(b) => Ok(Cow::Owned(b.to_string())),
        _ => Err(format!(
            "enrichment condition for field {field:?} must be a string, integer, float or boolean"
        )),
    }
}

/// `text` as an index key compares it: lowercased when the lookup ignores case.
fn comparable_key(text: Cow<'_, str>, case_sensitive: bool) -> String {
    if case_sensitive {
        text.into_owned()
    } else {
        text.to_lowercase()
    }
}

/// Copy out only the requested keys, erroring on a key the row does not carry.
fn apply_select(row: &ObjectMap, select: Option<&[String]>) -> Result<ObjectMap, String> {
    let Some(select) = select else {
        return Ok(row.clone());
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
            headers,
            rows,
            indexes: Mutex::new(HashMap::new()),
        })
    }

    /// The index on `fields`, built on first use and cached.
    ///
    /// None when a field is not a column, which the lookup reports at run time
    /// as Vector does. A poisoned cache builds the index uncached rather than
    /// trusting a map a panicking writer left.
    fn index_for(&self, case_sensitive: bool, fields: Vec<String>) -> Option<Arc<RowIndex>> {
        if !fields
            .iter()
            .all(|field| self.headers.iter().any(|header| header.as_str() == field))
        {
            return None;
        }
        let key: IndexKey = (case_sensitive, fields);
        if let Ok(cache) = self.indexes.lock()
            && let Some(index) = cache.get(&key)
        {
            return Some(Arc::clone(index));
        }

        let mut index = RowIndex::new();
        for (number, row) in self.rows.iter().enumerate() {
            let values: Option<Vec<String>> = key
                .1
                .iter()
                .map(|field| {
                    let cell = row.get(field.as_str())?;
                    let text = comparable_text(field, cell).ok()?;
                    Some(comparable_key(text, case_sensitive))
                })
                .collect();
            if let Some(values) = values {
                index.entry(values).or_default().push(number);
            }
        }
        let index = Arc::new(index);
        if let Ok(mut cache) = self.indexes.lock() {
            cache.insert(key, Arc::clone(&index));
        }
        Some(index)
    }

    /// Every row whose condition fields all equal the condition values.
    ///
    /// `index` is the one `index_for` built for these condition fields, and
    /// None only when a field has no column.
    fn find_rows(
        &self,
        index: Option<&RowIndex>,
        conditions: &[(String, Value)],
        case_sensitive: bool,
        select: Option<&[String]>,
        wanted: Wanted,
    ) -> Result<Vec<ObjectMap>, String> {
        let Some(index) = index else {
            return match conditions
                .iter()
                .find(|(field, _)| !self.headers.iter().any(|h| h.as_str() == field))
            {
                Some((field, _)) if !self.rows.is_empty() => {
                    Err(format!("field {field:?} not found in enrichment table"))
                }
                _ => Ok(Vec::new()),
            };
        };

        let key = conditions
            .iter()
            .map(|(field, value)| {
                Ok(comparable_key(
                    comparable_text(field, value)?,
                    case_sensitive,
                ))
            })
            .collect::<Result<Vec<String>, String>>()?;
        index
            .get(&key)
            .map_or(&[][..], Vec::as_slice)
            .iter()
            .take(wanted.limit())
            .filter_map(|&number| self.rows.get(number))
            .map(|row| apply_select(row, select))
            .collect()
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
        let record =
            json_to_vrl_value(record).map_err(|e| format!("mmdb record for {text}: {e}"))?;
        match record {
            Value::Object(row) => Ok(vec![apply_select(&row, select)?]),
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
    index: Option<Arc<RowIndex>>,
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

    let fields: Vec<String> = condition
        .keys()
        .map(|key| key.as_str().to_owned())
        .collect();
    let index = data.index_for(case_sensitive, fields);

    Ok(CompiledArgs {
        table,
        data,
        index,
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
            index: args.index,
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
    index: Option<Arc<RowIndex>>,
    condition: BTreeMap<KeyString, expression::Expr>,
    select: Option<Box<dyn Expression>>,
    case_sensitive: bool,
}

impl FunctionExpression for GetEnrichmentTableRecordFn {
    fn resolve(&self, ctx: &mut Context) -> Resolved {
        let (conditions, select) = resolve_lookup(&self.condition, self.select.as_deref(), ctx)?;
        let mut rows = self
            .data
            .find_rows(
                self.index.as_deref(),
                &conditions,
                self.case_sensitive,
                select.as_deref(),
                Wanted::One,
            )
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
            index: args.index,
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
    index: Option<Arc<RowIndex>>,
    condition: BTreeMap<KeyString, expression::Expr>,
    select: Option<Box<dyn Expression>>,
    case_sensitive: bool,
}

impl FunctionExpression for FindEnrichmentTableRecordsFn {
    fn resolve(&self, ctx: &mut Context) -> Resolved {
        let (conditions, select) = resolve_lookup(&self.condition, self.select.as_deref(), ctx)?;
        let rows = self
            .data
            .find_rows(
                self.index.as_deref(),
                &conditions,
                self.case_sensitive,
                select.as_deref(),
                Wanted::All,
            )
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
        execute_vrl_on_event(&program, r#"{"message":"seed"}"#, BTreeMap::new())
            .result
            .map(vrl_value_to_json)
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
    fn a_condition_from_a_string_returning_function_matches_a_cell() {
        // md5 returns vrl's Value::String variant, distinct from Value::Bytes.
        let _guard = lock();
        let csv = TempCsv::new(
            "string-cond",
            "id,key\n1,9dd4e461268c8034f5c8564e155c67a6\n",
        );
        register_table("hashes", "file", csv.path(), b',').expect("csv loads");
        let row = run(r#". = get_enrichment_table_record!("hashes", {"key": md5("x")})"#)
            .expect("lookup runs");
        assert_eq!(row["id"], "1");
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
    fn indexed_lookups_match_every_condition_and_shape() {
        let _guard = lock();
        let _csv = register_users("indexed");
        for (vrl, want) in [
            (
                r#". = {"r": find_enrichment_table_records!("users", {"team": "red", "name": "Alice"})}"#,
                Ok(serde_json::json!({"r": [{"id": "3", "name": "Alice", "team": "red"}]})),
            ),
            (
                r#". = {"r": find_enrichment_table_records!("users", {"team": "RED"}, select: ["id"], case_sensitive: false)}"#,
                Ok(serde_json::json!({"r": [{"id": "1"}, {"id": "3"}]})),
            ),
            (
                r#". = get_enrichment_table_record!("users", {"id": 2}, select: ["name"])"#,
                Ok(serde_json::json!({"name": "Fred"})),
            ),
            (
                r#". = get_enrichment_table_record!("users", {"team": "red", "id": "9"})"#,
                Err("No rows found"),
            ),
        ] {
            match (run(vrl), want) {
                (Ok(got), Ok(want)) => assert_eq!(got, want, "for {vrl}"),
                (Err(got), Err(want)) => assert!(got.contains(want), "for {vrl}: {got}"),
                (got, want) => panic!("for {vrl}: got {got:?}, wanted {want:?}"),
            }
        }
    }

    #[test]
    fn programs_on_the_same_condition_fields_share_one_index() {
        let _guard = lock();
        let _csv = register_users("shared-index");
        for vrl in [
            r#". = get_enrichment_table_record!("users", {"id": "1"})"#,
            r#". = {"r": find_enrichment_table_records!("users", {"id": "2"})}"#,
            r#". = get_enrichment_table_record!("users", {"id": "1"}, case_sensitive: false)"#,
        ] {
            compile_vrl_program(vrl).expect("compiles");
        }
        let tables = read_tables(registry());
        let Some(EnrichmentTable::File(table)) = tables.get("users").map(Arc::as_ref) else {
            panic!("users is a file table");
        };
        let cached = table.indexes.lock().expect("cache lock").len();
        assert_eq!(cached, 2, "one index per (case, fields), got {cached}");
    }

    #[test]
    fn an_unknown_condition_field_on_an_empty_table_finds_nothing() {
        let _guard = lock();
        let csv = TempCsv::new("empty", "id,name\n");
        register_table("empty", "file", csv.path(), b',').expect("csv loads");
        let out = run(r#". = {"r": find_enrichment_table_records!("empty", {"nosuch": "1"})}"#)
            .expect("an empty table has no row to report a missing column on");
        assert_eq!(out, serde_json::json!({"r": []}));
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
    /// checkout at the repo root (`<repo>/vector/`, a sibling of this crate).
    /// That checkout is gitignored and `build/build --clean` removes it, so
    /// the test reports and returns rather than failing when it is gone. The
    /// path is anchored on `CARGO_MANIFEST_DIR`, not on where the repo is
    /// cloned.
    #[test]
    fn geoip_lookup_returns_a_record() {
        let _guard = lock();
        let mmdb = Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../vector/tests/data/GeoLite2-ASN-Test.mmdb"
        ));
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
